#!/usr/bin/env python3
"""Compare Redis derived charts and histories with their PostgreSQL source."""
from __future__ import annotations

import os
import sys
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from redis import Redis
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rebuild import (
    LISBON,
    SQL_DAILY_STREAMS,
    SQL_LAST_PLAYS,
    STREAM_SECONDS,
    chart_rows,
    day_bounds,
    load_environment,
    postgres_url,
    redis_chart_key,
    redis_last_plays_key,
    redis_stream_key,
    stream_rows,
)


def expected_values(connection, today):
    charts: dict[str, object] = {}
    for day in (today - timedelta(days=1), today):
        global_rows, country_rows = chart_rows(connection, day)
        if global_rows:
            charts[redis_chart_key(day)] = {
                str(track_id): streams for track_id, streams in global_rows
            }
        for country, rows in country_rows.items():
            if rows:
                charts[redis_chart_key(day, country)] = {
                    str(track_id): streams for track_id, streams in rows
                }

    start, end = day_bounds(today)
    params = {"start": start, "end": end, "stream_seconds": STREAM_SECONDS}
    streams = {
        redis_stream_key(today, int(row.track_id)): str(int(row.streams))
        for row in stream_rows(connection, SQL_DAILY_STREAMS, params)
    }

    last_plays: dict[int, list[str]] = {}
    for row in stream_rows(connection, SQL_LAST_PLAYS, {}):
        last_plays.setdefault(int(row.listener_id), []).append(str(row.track_id))
    histories = {
        redis_last_plays_key(listener_id): tracks
        for listener_id, tracks in last_plays.items()
    }
    return charts, streams, histories


def compare_keyspace(
    client: Redis,
    name: str,
    pattern: str,
    expected: dict[str, object],
    redis_type: str,
    read_value: Callable[[Redis, str], object],
    differences: list[str],
) -> None:
    expected_keys = set(expected)
    actual_keys = set(client.scan_iter(match=pattern, count=1000))

    for key in sorted(expected_keys - actual_keys):
        differences.append(f"{name}: missing key {key}")
    for key in sorted(actual_keys - expected_keys):
        differences.append(f"{name}: unexpected key {key}")

    for key in sorted(expected_keys & actual_keys):
        actual_type = client.type(key)
        if actual_type != redis_type:
            differences.append(
                f"{name}: {key} has type {actual_type!r}; expected {redis_type!r}"
            )
            continue

        actual = read_value(client, key)
        if actual != expected[key]:
            differences.append(
                f"{name}: {key} differs; expected {expected[key]!r}, "
                f"found {actual!r}"
            )


def main() -> int:
    load_environment()
    today = datetime.now(LISBON).date()
    engine = create_engine(postgres_url())
    client = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    try:
        client.ping()
        with engine.connect().execution_options(
            isolation_level="REPEATABLE READ"
        ) as connection:
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                charts, streams, histories = expected_values(connection, today)

        differences: list[str] = []
        compare_keyspace(
            client,
            "Charts",
            "charts:*",
            charts,
            "zset",
            lambda redis_client, key: dict(
                redis_client.zrange(key, 0, -1, withscores=True)
            ),
            differences,
        )
        compare_keyspace(
            client,
            "Daily stream counters",
            "streams:*",
            streams,
            "string",
            lambda redis_client, key: redis_client.get(key),
            differences,
        )
        compare_keyspace(
            client,
            "Last-play histories",
            "last50:*",
            histories,
            "list",
            lambda redis_client, key: redis_client.lrange(key, 0, -1),
            differences,
        )
    finally:
        engine.dispose()
        client.close()

    if differences:
        print("Redis verification failed:")
        for difference in differences:
            print(f"- {difference}")
        print(f"Found {len(differences)} difference(s).")
        return 1

    print(
        "Redis verification passed: "
        f"{len(streams)} daily stream counters, "
        f"{len(charts)} charts, and {len(histories)} last-play histories "
        f"match PostgreSQL for {today} (Europe/Lisbon)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
