#!/usr/bin/env python3
"""Report export: PostgreSQL (read-only role) -> derived MongoDB collections.

Reads the plays of the last 12 calendar months (Lisbon time) and rebuilds
three derived collections, one per report pipeline:

  listener_month_stats   one document per listener and month   (pipeline 1)
  artist_country_month   one document per artist, country, month (pipeline 2)
  genre_country_month    one document per genre, country, month  (pipeline 3)

A stream is a play with at least 30 seconds played. Months and days use the
Europe/Lisbon time zone. Safe to run again at any time: each run empties the
three collections (keeping their validators and indexes) and writes them again.

Run from the repo root:
    uv run --project app python mongodb/export.py

Needs READONLY_DATABASE_URL (read-only role) and MONGO_URL (app user, readWrite)
in the environment or in .env.

Columns assumed in PostgreSQL (change the SQL below if yours differ):
    play(listener_id, track_id, started_at, seconds_played, country, device_type)
    track(id, title)   artist(id, name)   genre(id, name)
    track_artist(track_id, artist_id, role)   track_genre(track_id, genre_id)
"""
from __future__ import annotations

import os
import sys
from itertools import groupby
from operator import itemgetter
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

BATCH = 5000
STREAM_SECONDS = 30

# Local (Lisbon) timestamp of a play, used for every month and day bucket.
LOCAL = "(p.started_at AT TIME ZONE 'Europe/Lisbon')"

# First day of the oldest month we export: current month plus the 11 before it.
SQL_CUTOFF = (
    "SELECT date_trunc('month', now() AT TIME ZONE 'Europe/Lisbon') - interval '11 months'"
)

SQL_STREAMS_TOTAL = (
    "SELECT count(*) FROM play p "
    f"WHERE {LOCAL} >= :cutoff AND p.seconds_played >= {STREAM_SECONDS}"
)

# Tracks listened to, per listener and month (rows ordered by listener, month).
SQL_TRACKS = f"""
SELECT p.listener_id,
       to_char(date_trunc('month', {LOCAL}), 'YYYY-MM') AS month,
       p.track_id,
       t.title,
       count(*) FILTER (WHERE p.seconds_played >= {STREAM_SECONDS}) AS streams,
       sum(p.seconds_played) AS seconds
FROM play p
JOIN track t ON t.id = p.track_id
WHERE {LOCAL} >= :cutoff
GROUP BY 1, 2, 3, 4
ORDER BY 1, 2, 3
"""

# Listening per day, country and device, per listener and month.
SQL_DAYS = f"""
SELECT p.listener_id,
       to_char(date_trunc('month', {LOCAL}), 'YYYY-MM') AS month,
       to_char(date_trunc('day', {LOCAL}), 'YYYY-MM-DD') AS day,
       p.country,
       p.device_type,
       count(*) AS plays,
       count(*) FILTER (WHERE p.seconds_played >= {STREAM_SECONDS}) AS streams,
       sum(p.seconds_played) AS seconds
FROM play p
WHERE {LOCAL} >= :cutoff
GROUP BY 1, 2, 3, 4, 5
ORDER BY 1, 2, 3, 4, 5
"""

# Streams per main artist, country and month. A track with several main artists
# counts as one stream for each of them (the payout split is a different thing).
SQL_ARTIST_COUNTRY = f"""
SELECT ta.artist_id,
       a.name AS artist_name,
       p.country,
       to_char(date_trunc('month', {LOCAL}), 'YYYY-MM') AS month,
       count(*) AS streams
FROM play p
JOIN track_artist ta ON ta.track_id = p.track_id AND ta.role = 'main'
JOIN artist a ON a.id = ta.artist_id
WHERE {LOCAL} >= :cutoff AND p.seconds_played >= {STREAM_SECONDS}
GROUP BY 1, 2, 3, 4
"""

# Streams per genre, country and month.
SQL_GENRE_COUNTRY = f"""
SELECT g.name AS genre,
       p.country,
       to_char(date_trunc('month', {LOCAL}), 'YYYY-MM') AS month,
       count(*) AS streams
FROM play p
JOIN track_genre tg ON tg.track_id = p.track_id
JOIN genre g ON g.id = tg.genre_id
WHERE {LOCAL} >= :cutoff AND p.seconds_played >= {STREAM_SECONDS}
GROUP BY 1, 2, 3
"""

SQL_MAIN_ARTISTS = (
    "SELECT track_id, artist_id FROM track_artist WHERE role = 'main' ORDER BY track_id, artist_id"
)
SQL_ARTIST_NAMES = "SELECT id, name FROM artist"
SQL_TRACK_GENRES = (
    "SELECT tg.track_id, g.name FROM track_genre tg JOIN genre g ON g.id = tg.genre_id "
    "ORDER BY tg.track_id, g.name"
)


def load_env() -> None:
    """Fill os.environ from the repo's .env when the variables are not set."""
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def listener_month_docs(track_rows, day_rows, artists_of, genres_of, artist_name):
    """Merge the two ordered row streams into one document per listener and month."""
    tracks_by_key = groupby(track_rows, key=itemgetter(0, 1))
    days_by_key = groupby(day_rows, key=itemgetter(0, 1))
    for (t_key, t_group), (d_key, d_group) in zip(tracks_by_key, days_by_key):
        if t_key != d_key:
            raise RuntimeError(f"track rows and day rows out of step: {t_key} vs {d_key}")
        listener_id, month = t_key

        tracks = []
        for _, _, track_id, title, streams, seconds in t_group:
            artist_ids = artists_of.get(track_id, [])
            tracks.append(
                {
                    "track_id": track_id,
                    "title": title,
                    "artist_ids": artist_ids,
                    "artists": [artist_name[a] for a in artist_ids if a in artist_name],
                    "genres": genres_of.get(track_id, []),
                    "streams": int(streams),
                    "seconds": int(seconds),
                }
            )

        days = []
        plays = streams_total = seconds_total = 0
        for _, _, day, country, device_type, d_plays, d_streams, d_seconds in d_group:
            days.append(
                {
                    "day": day,
                    "country": country,
                    "device_type": device_type,
                    "plays": int(d_plays),
                    "streams": int(d_streams),
                    "seconds": int(d_seconds),
                }
            )
            plays += int(d_plays)
            streams_total += int(d_streams)
            seconds_total += int(d_seconds)

        yield {
            "_id": f"{listener_id}:{month}",
            "listener_id": listener_id,
            "month": month,
            "plays": plays,
            "streams": streams_total,
            "seconds": seconds_total,
            "tracks": tracks,
            "days": days,
        }


def stream_rows(conn, sql, params=None):
    """Yield rows using a server-side cursor, so large results do not fill memory."""
    result = conn.execution_options(yield_per=10000).execute(text(sql), params or {})
    try:
        yield from result
    finally:
        result.close()


def write_collection(collection, docs) -> int:
    """Empty the collection (keeps validator and indexes) and insert in batches."""
    collection.delete_many({})
    batch, total = [], 0
    for doc in docs:
        batch.append(doc)
        if len(batch) >= BATCH:
            collection.insert_many(batch, ordered=False)
            total += len(batch)
            batch = []
    if batch:
        collection.insert_many(batch, ordered=False)
        total += len(batch)
    return total


def main() -> int:
    load_env()
    for var in ("READONLY_DATABASE_URL", "MONGO_URL"):
        if not os.environ.get(var):
            print(f"Missing {var} (set it in .env)", file=sys.stderr)
            return 1

    from pymongo import MongoClient
    pg_url = make_url(os.environ["READONLY_DATABASE_URL"])
    if pg_url.drivername in ("postgres", "postgresql"):
        pg_url = pg_url.set(drivername="postgresql+psycopg")
    engine = create_engine(pg_url)
    client = MongoClient(os.environ["MONGO_URL"])
    db = client.get_default_database(default="music")

    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        with conn.begin():
            conn.execute(text("SET TRANSACTION READ ONLY"))

            cutoff = conn.execute(text(SQL_CUTOFF)).scalar_one()
            params = {"cutoff": cutoff}
            print(f"Exporting plays since {cutoff:%Y-%m-%d} (Lisbon time)")

            artists_of: dict[int, list[int]] = {}
            for track_id, artist_id in conn.execute(text(SQL_MAIN_ARTISTS)):
                artists_of.setdefault(track_id, []).append(artist_id)
            genres_of: dict[int, list[str]] = {}
            for track_id, genre in conn.execute(text(SQL_TRACK_GENRES)):
                genres_of.setdefault(track_id, []).append(genre)
            artist_name = dict(conn.execute(text(SQL_ARTIST_NAMES)).all())

            n_listener = write_collection(
                db["listener_month_stats"],
                listener_month_docs(
                    stream_rows(conn, SQL_TRACKS, params),
                    stream_rows(conn, SQL_DAYS, params),
                    artists_of, genres_of, artist_name,
                ),
            )
            print(f"listener_month_stats: {n_listener} documents")

            n_artist = write_collection(
                db["artist_country_month"],
                (
                    {"artist_id": a, "artist_name": n, "country": c, "month": m, "streams": int(s)}
                    for a, n, c, m, s in stream_rows(conn, SQL_ARTIST_COUNTRY, params)
                ),
            )
            print(f"artist_country_month: {n_artist} documents")

            n_genre = write_collection(
                db["genre_country_month"],
                (
                    {"genre": g, "country": c, "month": m, "streams": int(s)}
                    for g, c, m, s in stream_rows(conn, SQL_GENRE_COUNTRY, params)
                ),
            )
            print(f"genre_country_month: {n_genre} documents")

            # check: streams in PostgreSQL must equal streams in the listener collection
            expected = conn.execute(
                text(SQL_STREAMS_TOTAL), params
            ).scalar_one()
    engine.dispose()

    agg = list(db["listener_month_stats"].aggregate([{"$group": {"_id": None, "s": {"$sum": "$streams"}}}]))
    client.close()
    got = agg[0]["s"] if agg else 0
    if got != expected:
        print(f"MISMATCH: PostgreSQL has {expected} streams, MongoDB has {got}", file=sys.stderr)
        return 1
    print(f"Check ok: {expected} streams in PostgreSQL and in MongoDB")
    return 0


if __name__ == "__main__":
    sys.exit(main())