#!/usr/bin/env python3
"""Load a deterministic, full-size PostgreSQL fixture for the project brief."""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
import time
from calendar import monthrange
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from decimal import Decimal
from itertools import islice
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from dotenv import load_dotenv
from faker import Faker
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
LISBON = ZoneInfo("Europe/Lisbon")
SEED = 20261111
COUNTRIES = ("PT", "ES", "GB", "US", "BR", "FR", "DE", "JP", "CA", "IT")
DEVICES = ("mobile", "desktop", "web", "speaker", "car")
GENRES = ("Pop", "Rock", "Hip Hop", "Jazz", "Classical", "Electronic", "R&B")

COUNTS = {
    "labels": 300,
    "artists": 20_000,
    "albums": 60_000,
    "tracks": 300_000,
    "listeners": 100_000,
    "subscriptions": 35_000,
    "plays": 2_100_000,
    "playlists": 100_000,
    "likes": 500_000,
    "follows": 500_000,
}
HOT_TRACK_COUNT = 200
HOT_PLAY_COUNT = 300_000
FULL_PLAYLIST_COUNT = 1_000
COLLABORATIVE_PLAYLIST_COUNT = 20_000
BATCH_SIZE = 50_000


def postgres_dsn() -> str:
    raw_url = os.environ.get("MIGRATION_DATABASE_URL")
    if not raw_url:
        raise RuntimeError("Missing MIGRATION_DATABASE_URL in the environment or .env")
    url = make_url(raw_url)
    if url.drivername.startswith("postgresql+"):
        url = url.set(drivername="postgresql")
    elif url.drivername == "postgres":
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


def month_start(month: date, offset: int) -> date:
    index = month.year * 12 + month.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


def local_export_start(now: datetime) -> datetime:
    return datetime.combine(month_start(now.date().replace(day=1), -11), datetime_time.min, LISBON)


def copy_rows(cursor, table: str, columns: tuple[str, ...], rows, expected: int) -> None:
    column_sql = ", ".join(columns)
    started = time.monotonic()
    print(f"  {table}: loading {expected:,} rows", flush=True)
    with cursor.copy(f"COPY {table} ({column_sql}) FROM STDIN") as copy:
        for row_number, row in enumerate(rows, start=1):
            copy.write_row(row)
            if row_number % BATCH_SIZE == 0:
                print(f"    {row_number:,}/{expected:,}", flush=True)
    if row_number != expected:
        raise RuntimeError(f"{table}: wrote {row_number:,}; expected {expected:,}")
    print(f"    complete in {time.monotonic() - started:.1f}s", flush=True)


def insert_rows(cursor, statement: str, rows, expected: int, label: str) -> None:
    started = time.monotonic()
    print(f"  {label}: inserting {expected:,} rows with constraints and triggers enabled", flush=True)
    iterator = iter(rows)
    inserted = 0
    while batch := list(islice(iterator, BATCH_SIZE)):
        cursor.executemany(statement, batch)
        inserted += len(batch)
        print(f"    {inserted:,}/{expected:,}", flush=True)
    if inserted != expected:
        raise RuntimeError(f"{label}: inserted {inserted:,}; expected {expected:,}")
    print(f"    complete in {time.monotonic() - started:.1f}s", flush=True)


def labels_rows():
    fake = Faker()
    fake.seed_instance(SEED)
    for label_id in range(1, COUNTS["labels"] + 1):
        yield (
            f"{fake.company()} Records {label_id:03d}",
            COUNTRIES[(label_id - 1) % len(COUNTRIES)],
        )


def artist_rows():
    rng = random.Random(SEED + 1)
    fake = Faker()
    fake.seed_instance(SEED + 1)
    for artist_id in range(1, COUNTS["artists"] + 1):
        yield (
            fake.name(),
            COUNTRIES[rng.randrange(len(COUNTRIES))],
            rng.randrange(1, COUNTS["labels"] + 1),
            artist_id % 3 != 0,
        )


def album_rows(today: date):
    rng = random.Random(SEED + 2)
    fake = Faker()
    fake.seed_instance(SEED + 2)
    for album_id in range(1, COUNTS["albums"] + 1):
        release_offset = rng.randrange(365 * 10 + 1)
        album_type = ("album", "single", "ep")[(album_id - 1) % 3]
        yield (
            f"{fake.catch_phrase()} ({album_id:06d})",
            album_type,
            today - timedelta(days=release_offset),
            rng.randrange(1, COUNTS["labels"] + 1),
        )


def album_artist_rows():
    for album_id in range(1, COUNTS["albums"] + 1):
        first_artist = ((album_id - 1) * 7) % COUNTS["artists"] + 1
        yield (album_id, first_artist, 1)
        if album_id % 3 == 0:
            second_artist = first_artist % COUNTS["artists"] + 1
            yield (album_id, second_artist, 2)


def track_rows(rng: random.Random):
    fake = Faker()
    fake.seed_instance(SEED + 4)
    tracks_per_album = COUNTS["tracks"] // COUNTS["albums"]
    for track_id in range(1, COUNTS["tracks"] + 1):
        album_id = (track_id - 1) // tracks_per_album + 1
        position = (track_id - 1) % tracks_per_album + 1
        yield (
            album_id,
            fake.sentence(nb_words=4).rstrip("."),
            position,
            rng.randrange(120, 601),
            track_id % 7 == 0,
            f"US{track_id // 100_000:03d}{track_id:07d}",
        )


def track_artist_rows():
    for track_id in range(1, COUNTS["tracks"] + 1):
        main_artist = (track_id - 1) % COUNTS["artists"] + 1
        yield (track_id, main_artist, "main", 1)
        if track_id % 4 == 0:
            yield (track_id, main_artist % COUNTS["artists"] + 1, "main", 2)
        if track_id % 5 == 0:
            yield (track_id, main_artist % COUNTS["artists"] + 1, "featured", 1)


def track_genre_rows():
    for track_id in range(1, COUNTS["tracks"] + 1):
        yield (track_id, (track_id - 1) % len(GENRES) + 1)


def listener_rows(today: date):
    rng = random.Random(SEED + 3)
    fake = Faker()
    fake.seed_instance(SEED + 3)
    for listener_id in range(1, COUNTS["listeners"] + 1):
        age_days = rng.randrange(13 * 365, 66 * 365)
        yield (
            fake.name(),
            f"{fake.user_name()}-{listener_id:06d}@example.test",
            "seeded-password-hash-not-for-authentication",
            today - timedelta(days=age_days),
            COUNTRIES[rng.randrange(len(COUNTRIES))],
        )


def subscription_start_date(subscription_id: int, today: date) -> date:
    start_month = month_start(today.replace(day=1), -(subscription_id % 12))
    latest_day = monthrange(start_month.year, start_month.month)[1]
    if start_month.year == today.year and start_month.month == today.month:
        latest_day = min(latest_day, today.day)
    return start_month.replace(day=min(1 + subscription_id % 27, latest_day))


def subscription_rows(today: date, plan_ids: dict[str, int]):
    for subscription_id in range(1, COUNTS["subscriptions"] + 1):
        if subscription_id <= 1_000:
            plan = "premium_family"
        elif subscription_id <= 5_000:
            plan = "premium_duo"
        else:
            plan = "premium_individual"
        yield (
            subscription_id,
            plan_ids[plan],
            "active",
            subscription_start_date(subscription_id, today),
        )


def subscription_member_rows(today: date):
    for subscription_id in range(1, COUNTS["subscriptions"] + 1):
        start_date = subscription_start_date(subscription_id, today)
        joined_at = datetime.combine(start_date, datetime_time.min, timezone.utc)
        owner_id = subscription_id
        yield (subscription_id, owner_id, joined_at, None)

        if subscription_id <= 1_000:
            extra_members = 5
        else:
            extra_members = 1 if subscription_id <= 5_000 else 0
        for offset in range(extra_members):
            if subscription_id <= 1_000:
                listener_id = 35_000 + (subscription_id - 1) * 5 + offset + 1
            else:
                listener_id = 40_000 + subscription_id - 1_000
            yield (subscription_id, listener_id, joined_at, None)


def payment_rows(today: date, prices: dict[str, Decimal]):
    for subscription_id in range(1, COUNTS["subscriptions"] + 1):
        if subscription_id <= 1_000:
            plan = "premium_family"
        elif subscription_id <= 5_000:
            plan = "premium_duo"
        else:
            plan = "premium_individual"
        start_date = subscription_start_date(subscription_id, today)
        start_month = start_date.replace(day=1)
        for month_index in range(
            start_month.year * 12 + start_month.month - 1,
            today.year * 12 + today.month,
        ):
            month = date(month_index // 12, month_index % 12 + 1, 1)
            paid_day = min(15, monthrange(month.year, month.month)[1])
            if month.year == today.year and month.month == today.month:
                paid_day = min(paid_day, today.day)
            if month == start_month:
                paid_day = max(paid_day, start_date.day)
            paid_at = datetime.combine(month.replace(day=paid_day), datetime_time(12), timezone.utc)
            yield (
                subscription_id,
                month,
                prices[plan],
                paid_at,
                "approved",
                f"seed-{subscription_id:05d}-{month:%Y%m}",
            )


def play_rows(now: datetime):
    rng = random.Random(SEED + 4)
    start_utc = local_export_start(now).astimezone(timezone.utc)
    span_seconds = int((now.astimezone(timezone.utc) - start_utc).total_seconds())
    for play_number in range(COUNTS["plays"]):
        track_id = (
            play_number % HOT_TRACK_COUNT + 1
            if play_number < HOT_PLAY_COUNT
            else rng.randrange(1, COUNTS["tracks"] + 1)
        )
        if play_number < HOT_PLAY_COUNT:
            short_play = (play_number // HOT_TRACK_COUNT) % 4 == 0
        else:
            short_play = play_number % 4 == 0
        seconds_played = rng.randrange(30) if short_play else rng.randrange(30, 301)
        started_at = start_utc + timedelta(seconds=rng.randrange(span_seconds + 1))
        yield (
            rng.randrange(1, COUNTS["listeners"] + 1),
            track_id,
            started_at,
            seconds_played,
            DEVICES[rng.randrange(len(DEVICES))],
            COUNTRIES[rng.randrange(len(COUNTRIES))],
        )


def playlist_rows():
    fake = Faker()
    fake.seed_instance(SEED + 6)
    for playlist_id in range(1, COUNTS["playlists"] + 1):
        owner_id = (playlist_id - 1) % COUNTS["listeners"] + 1
        yield (
            owner_id,
            f"{fake.word().title()} Mix {playlist_id:06d}",
            fake.sentence(nb_words=8),
            "public" if playlist_id % 2 else "private",
            playlist_id <= COLLABORATIVE_PLAYLIST_COUNT,
        )


def collaborator_rows():
    for playlist_id in range(1, COLLABORATIVE_PLAYLIST_COUNT + 1):
        owner_id = (playlist_id - 1) % COUNTS["listeners"] + 1
        collaborator_id = owner_id % COUNTS["listeners"] + 1
        yield (playlist_id, collaborator_id)


def playlist_track_rows():
    for playlist_id in range(1, COUNTS["playlists"] + 1):
        track_count = 500 if playlist_id <= FULL_PLAYLIST_COUNT else 6
        owner_id = (playlist_id - 1) % COUNTS["listeners"] + 1
        for position in range(1, track_count + 1):
            track_id = ((playlist_id * 37 + position - 1) % COUNTS["tracks"]) + 1
            yield (playlist_id, position, track_id, owner_id)


def pair_rows(left_count: int, right_count: int, pair_count: int, step: int):
    total_pairs = left_count * right_count
    if math.gcd(step, total_pairs) != 1:
        raise ValueError("pair sequence step must be coprime to the pair space")
    for index in range(pair_count):
        pair = (index * step + SEED) % total_pairs
        yield (pair % left_count + 1, pair // left_count + 1)


def verify_seed(cursor, now: datetime) -> None:
    expected = {
        "label": COUNTS["labels"],
        "artist": COUNTS["artists"],
        "album": COUNTS["albums"],
        "track": COUNTS["tracks"],
        "listener": COUNTS["listeners"],
        "subscription": COUNTS["subscriptions"],
        "play": COUNTS["plays"],
        "playlist": COUNTS["playlists"],
        "track_like": COUNTS["likes"],
        "artist_follow": COUNTS["follows"],
    }
    for table, count in expected.items():
        actual = cursor.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        if actual != count:
            raise RuntimeError(f"{table}: expected {count:,} rows, found {actual:,}")

    short_plays, full_playlists, popular_tracks = cursor.execute(
        """
        SELECT
            count(*) FILTER (WHERE seconds_played < 30),
            (SELECT count(*) FROM playlist WHERE track_count = 500),
            (
                SELECT count(*) FROM (
                    SELECT track_id
                    FROM play
                    WHERE seconds_played >= 30
                    GROUP BY track_id
                    HAVING count(*) >= 1000
                ) AS popular
            )
        FROM play
        """
    ).fetchone()
    if short_plays * 4 < COUNTS["plays"]:
        raise RuntimeError("at least 25% of plays must be shorter than 30 seconds")
    if full_playlists < FULL_PLAYLIST_COUNT:
        raise RuntimeError("the fixture must include playlists with exactly 500 tracks")
    if popular_tracks < HOT_TRACK_COUNT:
        raise RuntimeError("at least 200 tracks must have 1,000 or more streams")
    cutoff = local_export_start(now).astimezone(timezone.utc)
    latest = cursor.execute("SELECT max(started_at) FROM play").fetchone()[0]
    earliest = cursor.execute("SELECT min(started_at) FROM play").fetchone()[0]
    if earliest < cutoff or latest > now.astimezone(timezone.utc):
        raise RuntimeError("play timestamps must fall inside the last 12 Lisbon calendar months")


def seed() -> None:
    load_dotenv(ROOT / ".env")
    dsn = postgres_dsn()
    started = time.monotonic()
    now = datetime.now(LISBON)
    today = now.date()
    rng = random.Random(SEED)

    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            print("Clearing fixture tables (the four migration-defined plans are preserved).", flush=True)
            cursor.execute(
                """
                TRUNCATE TABLE
                    label, artist, album, track, listener, subscription, play,
                    playlist, genre, payment, payout
                RESTART IDENTITY CASCADE
                """
            )
            plan_rows = cursor.execute(
                "SELECT id, name, monthly_price FROM plan ORDER BY id"
            ).fetchall()
            plan_ids = {name: plan_id for plan_id, name, _ in plan_rows}
            prices = {name: price for _, name, price in plan_rows}
            required_plans = {"free", "premium_individual", "premium_duo", "premium_family"}
            if set(plan_ids) != required_plans:
                raise RuntimeError(
                    f"Expected the four migration-defined plans, found {sorted(plan_ids)}"
                )

            print("Seeding relational catalogue and listeners.", flush=True)
            copy_rows(cursor, "label", ("name", "country"), labels_rows(), COUNTS["labels"])
            copy_rows(
                cursor,
                "genre",
                ("name",),
                ((genre,) for genre in GENRES),
                len(GENRES),
            )
            copy_rows(cursor, "artist", ("name", "country", "label_id", "verified"), artist_rows(), COUNTS["artists"])
            copy_rows(cursor, "album", ("title", "type", "release_date", "label_id"), album_rows(today), COUNTS["albums"])
            copy_rows(
                cursor,
                "album_artist",
                ("album_id", "artist_id", "position"),
                album_artist_rows(),
                COUNTS["albums"] + COUNTS["albums"] // 3,
            )
            copy_rows(
                cursor,
                "track",
                ("album_id", "title", "position", "duration_seconds", "explicit", "isrc"),
                track_rows(rng),
                COUNTS["tracks"],
            )
            track_artist_count = COUNTS["tracks"] + COUNTS["tracks"] // 4 + COUNTS["tracks"] // 5
            copy_rows(
                cursor,
                "track_artist",
                ("track_id", "artist_id", "role", "position"),
                track_artist_rows(),
                track_artist_count,
            )
            copy_rows(
                cursor,
                "track_genre",
                ("track_id", "genre_id"),
                track_genre_rows(),
                COUNTS["tracks"],
            )
            copy_rows(
                cursor,
                "listener",
                ("display_name", "email", "password_hash", "birth_date", "country"),
                listener_rows(today),
                COUNTS["listeners"],
            )

            print("Seeding subscriptions, memberships and monthly payments.", flush=True)
            copy_rows(
                cursor,
                "subscription",
                ("owner_id", "plan_id", "status", "started_at"),
                subscription_rows(today, plan_ids),
                COUNTS["subscriptions"],
            )
            member_count = COUNTS["subscriptions"] + 1_000 * 5 + 4_000
            insert_rows(
                cursor,
                """
                INSERT INTO subscription_member
                    (subscription_id, listener_id, joined_at, left_at)
                VALUES (%s, %s, %s, %s)
                """,
                subscription_member_rows(today),
                member_count,
                "subscription_member",
            )
            invite_count = 5_000
            invite_now = now.astimezone(timezone.utc)
            copy_rows(
                cursor,
                "invite_code",
                ("code", "subscription_id", "created_at", "expires_at"),
                (
                    (
                        f"seed-invite-{subscription_id:05d}",
                        subscription_id,
                        invite_now,
                        invite_now + timedelta(days=7),
                    )
                    for subscription_id in range(1, invite_count + 1)
                ),
                invite_count,
            )
            payment_count = sum(
                1 + (subscription_id % 12)
                for subscription_id in range(1, COUNTS["subscriptions"] + 1)
            )
            copy_rows(
                cursor,
                "payment",
                ("subscription_id", "month", "amount", "paid_at", "status", "provider_ref"),
                payment_rows(today, prices),
                payment_count,
            )

            print("Seeding 2.1 million plays across the last 12 Lisbon calendar months.", flush=True)
            copy_rows(
                cursor,
                "play",
                ("listener_id", "track_id", "started_at", "seconds_played", "device_type", "country"),
                play_rows(now),
                COUNTS["plays"],
            )

            print("Seeding playlists, collaborators, likes and follows.", flush=True)
            copy_rows(
                cursor,
                "playlist",
                ("owner_id", "name", "description", "visibility", "is_collaborative"),
                playlist_rows(),
                COUNTS["playlists"],
            )
            copy_rows(
                cursor,
                "playlist_collaborator",
                ("playlist_id", "listener_id"),
                collaborator_rows(),
                COLLABORATIVE_PLAYLIST_COUNT,
            )
            playlist_entry_count = (
                FULL_PLAYLIST_COUNT * 500
                + (COUNTS["playlists"] - FULL_PLAYLIST_COUNT) * 6
            )
            copy_rows(
                cursor,
                "playlist_track",
                ("playlist_id", "position", "track_id", "added_by"),
                playlist_track_rows(),
                playlist_entry_count,
            )
            copy_rows(
                cursor,
                "track_like",
                ("listener_id", "track_id"),
                pair_rows(COUNTS["listeners"], COUNTS["tracks"], COUNTS["likes"], 7),
                COUNTS["likes"],
            )
            copy_rows(
                cursor,
                "artist_follow",
                ("listener_id", "artist_id"),
                pair_rows(COUNTS["listeners"], COUNTS["artists"], COUNTS["follows"], 7),
                COUNTS["follows"],
            )

            print("Checking fixture counts and required distributions.", flush=True)
            verify_seed(cursor, now)
        connection.commit()

    print(f"PostgreSQL fixture loaded successfully in {time.monotonic() - started:.1f}s.", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-reset",
        action="store_true",
        help="allow truncating existing fixture tables before loading the dataset",
    )
    args = parser.parse_args()
    if not args.confirm_reset:
        parser.error(
            "this seed truncates project data; rerun with --confirm-reset after backing up anything important"
        )
    try:
        seed()
    except Exception as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
