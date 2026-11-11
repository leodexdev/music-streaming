#!/usr/bin/env python3
"""Concurrency test, scenario 2: collaborative playlist (F5).

Fixture: a collaborative playlist with 490 tracks and 5 collaborators. The collaborators
send 50 requests at the same moment, each adding one track at a random position between
1 and 491. Expected in real mode: exactly 10 are added and 40 are refused (409), and the
positions in PostgreSQL are exactly 1 to 500 (no duplicates, no gaps, 500 tracks).

The fixture writes straight to the database as the owner role (MIGRATION_DATABASE_URL).
Only the contested requests go through the API. It only touches rows it created
(listeners with the email prefix below, their playlist, one album and one track).

Naive mode: the database constraints would hide the race (and turn it into errors), so the
script drops the three guards for the run: the 500-track CHECK on playlist, the position
CHECK and the UNIQUE (playlist_id, position). After measuring, it deletes the fixture
playlist and puts the guards back (also at the start of the next run, if this one crashed).

Exit code: 1 if the rule is broken or, in real mode, if the result is not the expected
one or any request returned 5xx. 0 otherwise. In naive mode exit 1 is expected,
because the race breaks the rule.
"""
import argparse
import asyncio
import os
import random
import sys

import httpx
import psycopg

EMAIL_PREFIX = "ct-playlist-"
ALBUM_TITLE = "ct-playlist-album"
TRACK_ISRC = "CTPLAYLIST01"
N_COLLABORATORS = 5
START_TRACKS = 490
MAX_TRACKS = 500
N_REQUESTS = 50
EXPECTED_ACCEPTED = MAX_TRACKS - START_TRACKS

# (table, constraint name, definition): the guards that protect the playlist rules
GUARDS = [
    ("playlist", "playlist_max_tracks_ck", "CHECK (track_count BETWEEN 0 AND 500)"),
    ("playlist_track", "playlist_track_pos_ck", "CHECK (position BETWEEN 1 AND 500)"),
    ("playlist_track", "playlist_track_pos_uq",
     "UNIQUE (playlist_id, position) DEFERRABLE INITIALLY DEFERRED"),
]


def reset_data(conn) -> None:
    """Delete everything a previous run created (playlist first: its tracks reference the track)."""
    like = EMAIL_PREFIX + "%"
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM playlist WHERE owner_id IN (SELECT id FROM listener WHERE email LIKE %s)",
        (like,))
    cur.execute("DELETE FROM listener WHERE email LIKE %s", (like,))
    cur.execute("DELETE FROM album WHERE title = %s", (ALBUM_TITLE,))  # its track cascades


def guard_exists(conn, table: str, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM pg_constraint WHERE conname = %s AND conrelid = %s::regclass",
        (name, table)).fetchone()
    return row is not None


def ensure_guards(conn) -> None:
    for table, name, definition in GUARDS:
        if not guard_exists(conn, table, name):
            conn.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} {definition}")


def drop_guards(conn) -> None:
    for table, name, _ in GUARDS:
        conn.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")


def create_fixture(conn) -> dict:
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO listener (display_name, email, password_hash, birth_date, country)
           SELECT 'ctp' || g, %s::text || g || '@test.local', 'h', DATE '2000-01-01', 'PT'
           FROM generate_series(1, %s::int) g
           RETURNING id""",
        (EMAIL_PREFIX, N_COLLABORATORS + 1))
    ids = sorted(row[0] for row in cur.fetchall())
    owner, collaborators = ids[0], ids[1:]

    cur.execute(
        "INSERT INTO album (title, type, release_date) VALUES (%s, 'album', current_date) RETURNING id",
        (ALBUM_TITLE,))
    album_id = cur.fetchone()[0]
    cur.execute(
        """INSERT INTO track (album_id, title, position, duration_seconds, isrc)
           VALUES (%s, 'ct track', 1, 200, %s) RETURNING id""", (album_id, TRACK_ISRC))
    track_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO playlist (owner_id, name, is_collaborative) VALUES (%s, 'ct-playlist', true) RETURNING id",
        (owner,))
    playlist_id = cur.fetchone()[0]
    for listener_id in collaborators:
        cur.execute(
            "INSERT INTO playlist_collaborator (playlist_id, listener_id) VALUES (%s, %s)",
            (playlist_id, listener_id))

    # the statement-level trigger sets playlist.track_count to 490
    cur.execute(
        """INSERT INTO playlist_track (playlist_id, position, track_id, added_by)
           SELECT %s::bigint, g, %s::bigint, %s::bigint FROM generate_series(1, %s::int) g""",
        (playlist_id, track_id, owner, START_TRACKS))
    return {"playlist_id": playlist_id, "track_id": track_id, "collaborators": collaborators}


async def fire(base_url: str, mode: str, fixture: dict, rng: random.Random) -> list[int]:
    """Send all requests at the same moment (a gate releases them together)."""
    gate = asyncio.Event()
    limits = httpx.Limits(max_connections=N_REQUESTS, max_keepalive_connections=N_REQUESTS)
    collaborators = fixture["collaborators"]
    plan = [(collaborators[i % len(collaborators)], rng.randint(1, START_TRACKS + 1))
            for i in range(N_REQUESTS)]

    async with httpx.AsyncClient(base_url=base_url, timeout=120, limits=limits) as client:

        async def one(actor_id: int, position: int) -> int:
            await gate.wait()
            try:
                response = await client.post(
                    f"/playlists/{fixture['playlist_id']}/tracks?mode={mode}",
                    json={"track_id": fixture["track_id"], "position": position},
                    headers={"X-User-Id": str(actor_id)})
                return response.status_code
            except httpx.HTTPError:
                return 0  # connection error or timeout: counts as a failure

        tasks = [asyncio.create_task(one(actor, position)) for actor, position in plan]
        await asyncio.sleep(0.5)  # let every task reach the gate
        gate.set()
        return await asyncio.gather(*tasks)


def measure(conn, playlist_id: int) -> dict:
    count, distinct, lo, hi = conn.execute(
        "SELECT count(*), count(DISTINCT position), min(position), max(position) "
        "FROM playlist_track WHERE playlist_id = %s", (playlist_id,)).fetchone()
    track_count = conn.execute(
        "SELECT track_count FROM playlist WHERE id = %s", (playlist_id,)).fetchone()[0]
    return {"count": count, "distinct": distinct, "min": lo, "max": hi, "track_count": track_count}


def main() -> int:
    parser = argparse.ArgumentParser(description="Collaborative playlist concurrency test (F5)")
    parser.add_argument("--mode", choices=["real", "naive"], default="real")
    parser.add_argument("--base-url", default="http://localhost:8001")
    parser.add_argument("--seed", type=int, default=None, help="seed for the random positions")
    args = parser.parse_args()

    url = os.environ.get("MIGRATION_DATABASE_URL")
    if not url:
        print("MIGRATION_DATABASE_URL is not set (owner role).", file=sys.stderr)
        return 2
    url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    rng = random.Random(args.seed)

    with psycopg.connect(url, autocommit=True) as conn:
        # a previous crashed naive run may have left duplicates and missing guards
        reset_data(conn)
        ensure_guards(conn)
        fixture = create_fixture(conn)

        if args.mode == "naive":
            drop_guards(conn)
        try:
            statuses = asyncio.run(fire(args.base_url, args.mode, fixture, rng))
            result = measure(conn, fixture["playlist_id"])
        finally:
            reset_data(conn)       # remove the (possibly corrupted) fixture before the guards return
            ensure_guards(conn)

    accepted = sum(1 for s in statuses if 200 <= s < 300)
    refused = sum(1 for s in statuses if 400 <= s < 500)
    failed = len(statuses) - accepted - refused  # 5xx and connection errors

    positions_ok = (result["distinct"] == result["count"]
                    and result["min"] == 1 and result["max"] == result["count"])
    rule_holds = result["count"] <= MAX_TRACKS and positions_ok

    print(f"Scenario: collaborative playlist (F5) | mode: {args.mode}")
    print(f"Requests: {len(statuses)} | accepted: {accepted} | refused: {refused} | 5xx/errors: {failed}")
    print(f"Tracks in PostgreSQL: {result['count']} (limit {MAX_TRACKS}) | "
          f"distinct positions: {result['distinct']} | min: {result['min']} | max: {result['max']} | "
          f"track_count: {result['track_count']}")
    print(f"Positions are exactly 1..{result['count']} with no duplicates: {positions_ok} -> "
          f"rule {'HOLDS' if rule_holds else 'BROKEN'}")

    ok = rule_holds
    if args.mode == "real":
        ok = (ok and failed == 0 and accepted == EXPECTED_ACCEPTED
              and result["count"] == MAX_TRACKS and result["track_count"] == MAX_TRACKS)
        print(f"Expected: accepted {EXPECTED_ACCEPTED}, refused {N_REQUESTS - EXPECTED_ACCEPTED}, "
              f"positions 1..{MAX_TRACKS} -> {'OK' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())