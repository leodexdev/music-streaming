# Concurrency Notes and Validation

This document records the concurrency rules implemented by Tiago for the relational API and the validation approach used in the project.

## 1. Concurrency model

The API uses PostgreSQL as the source of truth and relies on `READ COMMITTED` semantics plus row locks for the contested operations.

- `subscription_member` checks are protected by the database trigger `subscription_member_limit` and by the application-level `SELECT ... FOR UPDATE` on the owning subscription row.
- `playlist` edits are serialized with `SELECT ... FOR UPDATE` on the specific playlist row before the position updates.
- The playlist position constraint is kept `DEFERRABLE INITIALLY DEFERRED`, which is crucial when the system shifts multiple rows inside one transaction.

## 2. Real vs naive mode

The project distinguishes between the real implementation and the intentionally naive mode used to demonstrate race conditions.

### Real mode

- Uses a lock on the contested row before editing.
- Validates state in the same transaction.
- Returns 4xx for business-logic refusals and 5xx only for unexpected server failures.

### Naive mode

- Removes the lock and widens the check-then-write gap with a short `pg_sleep()` delay.
- This reproduces the race condition and demonstrates why the atomic guard is required.
- The concurrency fixtures explicitly disable the guards before the run and restore them afterward.

## 3. Playlist concurrency (F5)

The most important validation in the current implementation is the collaborative playlist scenario.

The fixture in `scripts/concurrency_playlist_test.py` creates a playlist with 490 tracks and 5 collaborators, then sends 50 concurrent inserts at random positions.

### Verified real-mode result

Command run:

```bash
cd /workspaces/music-streaming/app && \
MIGRATION_DATABASE_URL='postgresql://music_owner:change-me-owner@127.0.0.1:5432/music' \
uv run python ../scripts/concurrency_playlist_test.py --mode real --base-url http://localhost:8001
```

Observed output:

```text
Scenario: collaborative playlist (F5) | mode: real
Requests: 50 | accepted: 10 | refused: 40 | 5xx/errors: 0
Tracks in PostgreSQL: 500 (limit 500) | distinct positions: 500 | min: 1 | max: 500 | track_count: 500
Positions are exactly 1..500 with no duplicates: True -> rule HOLDS
Expected: accepted 10, refused 40, positions 1..500 -> OK
```

This demonstrates that the real implementation preserves the invariant:
- no duplicate positions
- no gaps
- playlist never exceeds 500 tracks
- no 5xx errors under the concurrent workload

## 4. Why this is the correct pattern

The project deliberately separates the SQL guarantees from the application logic:

- PostgreSQL enforces the integrity rules that must never be broken.
- The FastAPI layer translates them into the expected 4xx responses for the client.
- `FOR UPDATE` orders the competing transactions when the same row is being mutated.

This is the same pattern used for the subscription join rule and the playlist edit rule in the Tiago side of the project.
