#!/usr/bin/env python3
"""Rebuild derived Redis charts, stream counters, and listener histories."""
from __future__ import annotations

import math
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parent))
from keys import build_key

ROOT = Path(__file__).resolve().parent.parent
LISBON = ZoneInfo("Europe/Lisbon")
STREAM_SECONDS = 30
CHART_SIZE = 50
PIPELINE_BATCH_SIZE = 500
PREVIOUS_CHART_TTL = 7 * 24 * 60 * 60

SQL_GLOBAL_CHART = text("""
    SELECT p.track_id, count(*) AS streams
    FROM play AS p
    WHERE p.started_at >= :start
      AND p.started_at < :end
      AND p.seconds_played >= :stream_seconds
    GROUP BY p.track_id
    ORDER BY streams DESC, p.track_id
    LIMIT :chart_size
""")

SQL_COUNTRY_CHARTS = text("""
    WITH track_counts AS (
        SELECT p.country, p.track_id, count(*) AS streams
        FROM play AS p
        WHERE p.started_at >= :start
          AND p.started_at < :end
          AND p.seconds_played >= :stream_seconds
        GROUP BY p.country, p.track_id
    ),
    ranked AS (
        SELECT country, track_id, streams,
               row_number() OVER (
                   PARTITION BY country
                   ORDER BY streams DESC, track_id
               ) AS position
        FROM track_counts
    )
    SELECT country, track_id, streams
    FROM ranked
    WHERE position <= :chart_size
    ORDER BY country, position
""")

SQL_DAILY_STREAMS = text("""
    SELECT p.track_id, count(*) AS streams
    FROM play AS p
    WHERE p.started_at >= :start
      AND p.started_at < :end
      AND p.seconds_played >= :stream_seconds
    GROUP BY p.track_id
    ORDER BY p.track_id
""")

SQL_LAST_PLAYS = text("""
    SELECT listener_id, track_id
    FROM (
        SELECT p.listener_id,
               p.track_id,
               row_number() OVER (
                   PARTITION BY p.listener_id
                   ORDER BY p.started_at DESC, p.id DESC
               ) AS position
        FROM play AS p
    ) AS ranked
    WHERE position <= 50
    ORDER BY listener_id, position
""")


def load_environment() -> None:
    load_dotenv(ROOT / ".env")
    missing = [
        name
        for name in ("READONLY_DATABASE_URL", "REDIS_URL")
        if not os.environ.get(name)
    ]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")


def postgres_url():
    url = make_url(os.environ["READONLY_DATABASE_URL"])
    if url.drivername in ("postgres", "postgresql"):
        url = url.set(drivername="postgresql+psycopg")
    return url


def redis_chart_key(day: date, country: str | None = None) -> str:
    date_part = day.strftime("%Y%m%d")
    if country is None:
        return build_key("charts", date_part, "global")
    return build_key("charts", date_part, "country", country)


def redis_stream_key(day: date, track_id: int) -> str:
    return build_key("streams", day.strftime("%Y%m%d"), "track", track_id)


def redis_last_plays_key(listener_id: int) -> str:
    return build_key("last50", listener_id)


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=LISBON)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=LISBON)
    return start, end


def seconds_until(end: datetime, now: datetime) -> int:
    elapsed = end.astimezone(timezone.utc) - now.astimezone(timezone.utc)
    return max(1, math.ceil(elapsed.total_seconds()))


def stream_rows(connection, statement, params):
    result = connection.execution_options(yield_per=10_000).execute(statement, params)
    try:
        yield from result
    finally:
        result.close()


def delete_derived_keys(client: Redis) -> int:
    deleted = 0
    patterns = ("charts:*", "streams:*", "last50:*")
    for pattern in patterns:
        while True:
            batch: list[str] = []
            found_keys = False
            for key in client.scan_iter(match=pattern, count=1000):
                found_keys = True
                batch.append(key)
                if len(batch) == PIPELINE_BATCH_SIZE:
                    deleted += client.unlink(*batch)
                    batch.clear()
            if batch:
                deleted += client.unlink(*batch)
            if not found_keys:
                break
    return deleted


def chart_rows(connection, day: date):
    start, end = day_bounds(day)
    params = {
        "start": start,
        "end": end,
        "stream_seconds": STREAM_SECONDS,
        "chart_size": CHART_SIZE,
    }

    global_rows = [
        (int(row.track_id), int(row.streams))
        for row in connection.execute(SQL_GLOBAL_CHART, params)
    ]
    country_rows: dict[str, list[tuple[int, int]]] = {}
    for row in connection.execute(SQL_COUNTRY_CHARTS, params):
        country_rows.setdefault(row.country, []).append(
            (int(row.track_id), int(row.streams))
        )
    return global_rows, country_rows


def write_chart(
    client: Redis,
    key: str,
    rows: list[tuple[int, int]],
    ttl: int,
) -> None:
    if not rows:
        return
    values = {str(track_id): streams for track_id, streams in rows}
    with client.pipeline(transaction=True) as pipeline:
        pipeline.zadd(key, values)
        pipeline.expire(key, ttl)
        pipeline.execute()


def rebuild_charts(client: Redis, chart_data, today: date, today_ttl: int) -> int:
    written = 0
    for day, ttl in (
        (today - timedelta(days=1), PREVIOUS_CHART_TTL),
        (today, today_ttl),
    ):
        global_rows, country_rows = chart_data[day]
        write_chart(client, redis_chart_key(day), global_rows, ttl)
        written += bool(global_rows)
        for country, rows in country_rows.items():
            write_chart(client, redis_chart_key(day, country), rows, ttl)
            written += 1
    return written


def rebuild_daily_streams(
    client: Redis,
    connection,
    today: date,
    today_ttl: int,
) -> int:
    start, end = day_bounds(today)
    params = {"start": start, "end": end, "stream_seconds": STREAM_SECONDS}
    count = 0
    with client.pipeline(transaction=True) as pipeline:
        for row in stream_rows(connection, SQL_DAILY_STREAMS, params):
            pipeline.set(
                redis_stream_key(today, int(row.track_id)),
                int(row.streams),
                ex=today_ttl,
            )
            count += 1
            if count % PIPELINE_BATCH_SIZE == 0:
                pipeline.execute()
        if count % PIPELINE_BATCH_SIZE:
            pipeline.execute()
    return count


def rebuild_last_plays(client: Redis, connection) -> int:
    listener_id = None
    track_ids: list[str] = []
    listeners_written = 0
    pending_listeners = 0
    pipeline = client.pipeline(transaction=True)

    def queue_listener(listener: int, tracks: list[str]) -> None:
        key = redis_last_plays_key(listener)
        pipeline.delete(key)
        if tracks:
            pipeline.rpush(key, *tracks)

    for row in stream_rows(connection, SQL_LAST_PLAYS, {}):
        current_listener = int(row.listener_id)
        if listener_id is not None and current_listener != listener_id:
            queue_listener(listener_id, track_ids)
            listeners_written += 1
            pending_listeners += 1
            track_ids = []
            if pending_listeners == 250:
                pipeline.execute()
                pending_listeners = 0
        listener_id = current_listener
        track_ids.append(str(row.track_id))

    if listener_id is not None:
        queue_listener(listener_id, track_ids)
        listeners_written += 1
        pending_listeners += 1
    if pending_listeners:
        pipeline.execute()
    return listeners_written


def main() -> int:
    load_environment()
    now = datetime.now(LISBON)
    today = now.date()
    _, tomorrow_start = day_bounds(today)
    today_ttl = seconds_until(tomorrow_start, now)

    engine = create_engine(postgres_url())
    client = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    try:
        client.ping()
        with engine.connect().execution_options(
            isolation_level="REPEATABLE READ"
        ) as connection:
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                chart_data = {
                    day: chart_rows(connection, day)
                    for day in (today - timedelta(days=1), today)
                }
                deleted = delete_derived_keys(client)
                charts = rebuild_charts(client, chart_data, today, today_ttl)
                counters = rebuild_daily_streams(
                    client, connection, today, today_ttl
                )
                listeners = rebuild_last_plays(client, connection)
    finally:
        engine.dispose()
        client.close()

    print(f"Removed {deleted} old derived keys")
    print(f"Rebuilt {charts} non-empty chart keys")
    print(f"Rebuilt {counters} daily track stream counters")
    print(f"Rebuilt last-play lists for {listeners} listeners")
    return 0


if __name__ == "__main__":
    sys.exit(main())
