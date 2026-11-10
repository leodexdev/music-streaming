# Group Project C (Music Streaming) - Task Plan (2 Members)

Members: **Leandro** (repo owner, infrastructure, reports) and **Tiago** (relational core, concurrency, API).
Budget: ~22.5 h per person (~18 h hands-on + 4.5 h testing, debugging, documentation).

## Mandatory Git rule

Each member must have **non-trivial, non-merge commits in all four areas**: `postgres/`, `mongodb/`, `redis/`, `app/`. A missing area costs 2 points. Merge with "Create a merge commit" or "Rebase and merge" (never squash). The author email must match the README authors table.

---

## Current status

| Item | Owner | Status |
|---|---|---|
| `compose.yml`, `.env.example`, Dockerfile, `/health` | Leandro | Done |
| Migration `0001` primary schema (15 tables, triggers) | Tiago | Done, pending trigger tests and PR |
| Migration `0002` secondary tables | Leandro | Done (Tiago to review) |
| `env.py` reads `MIGRATION_DATABASE_URL` | Tiago | Done, pending PR |
| `scripts/setup.sh` (roles, extensions, migrations, Mongo) | Leandro | **To confirm**: it must create roles, extensions, run migrations and set up Mongo (the compose launcher is `run.sh`) |
| `config.py`, `database.py` | Tiago | In progress |
| `docs/postgres.md` (primary part) | Tiago | Written, to commit |

## Repository structure

```
music-streaming/
├── .devcontainer/                       devcontainer.json, devcontainer-lock.json
├── compose.yml                          [L]
├── .env, .env.example, .gitignore       [L] (.env is never committed)
├── README.md                            [L, T fills their parts]
├── app/
│   ├── Dockerfile, pyproject.toml, uv.lock, README.md, .python-version
│   └── src/app/
│       ├── main.py                      /health, include_router            [T edits]
│       ├── config.py                    Settings from .env                  [T]
│       ├── database.py                  engine, mongo_db, redis_client      [T]
│       ├── deps.py                      reads X-User-Id header              [T]
│       ├── routers/
│       │   ├── subscriptions.py         F2, F3                              [T]
│       │   ├── playlists.py             F5                                  [T]
│       │   ├── playback.py              F4                                  [T]
│       │   ├── catalogue.py             F1                                  [L]
│       │   ├── charts.py                F6 (reads only Redis)               [L]
│       │   ├── payouts.py               F7                                  [L]
│       │   └── reports.py               F8                                  [L]
│       └── services/                    one service per router, SQL parameterised
├── database/                           
├── postgres/
│   ├── alembic.ini
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/
│   │       ├── 0001_primary_schema.py       [T]
│   │       ├── 0002_secondary_tables.py     [L] (+ grants for app and read-only roles)
│   │       └── 0003_indexes.py              [T] (after seed, for EXPLAIN)
│   └── seed.py                          deterministic, COPY / batch         [L]
├── mongodb/
│   ├── setup_collections.py             validators + indexes, idempotent    [T]
│   ├── export.py                        PostgreSQL (read-only) -> Mongo     [L]
│   └── pipelines/                       pipeline_1..3.json (+ sample output) [L]
├── redis/
│   ├── keys.py                          key builders (one naming convention) [T]
│   ├── skips.py                         skip counter                        [T]
│   ├── active_device.py                 single active device                [T]
│   ├── rebuild.py                       recreate derived keys after FLUSHALL [L]
│   └── verify.py                        compare Redis vs source, exit 0/1   [L]
├── scripts/
│   ├── run.sh                           docker compose 
│   ├── setup.sh                         [L]
│   ├── seed.sh                          [L]
│   └── concurrency_test.py              [T]
└── docs/
    ├── postgres.md [T primary, L secondary]   mongodb.md [T events, L reports]
    ├── redis.md [T + L]   concurrency.md [T]   architecture.md [both]
    ├── runbook.md [L]   ai-usage.md [both, one entry per use]
    └── project/ (brief, README of the course, tasks.md)
```

---

## 1. Leandro (Infrastructure, Reports and Export)

### Root and infrastructure

**Task 1.1: `compose.yml`** (done). Services: postgres, mongo, redis (with `requirepass`), app, dbgate. Ports on `127.0.0.1`. PostgreSQL with `log_statement=all`. All passwords from `.env`. The app service must receive `DATABASE_URL`, `MONGO_URL`, `REDIS_URL` with **service hostnames** (`postgres`, `mongo`, `redis`), not `127.0.0.1`.

**Task 1.2: `.env.example`** (done). Placeholders for `DATABASE_URL` (app role), `MIGRATION_DATABASE_URL` (owner), `READONLY_DATABASE_URL`, `MONGO_URL`, `MONGO_ROOT_URL`, `REDIS_URL`, plus the role passwords. Use `postgresql+psycopg://` or let `env.py` convert the prefix. Keep LF endings.

**Task 1.3: `scripts/setup.sh`** (2 h, **to do**). Idempotent, runs from the repo root (`cd "$(dirname "$0")/.."`), loads `.env`, in this order:
1. As PostgreSQL superuser: create roles `music_owner`, `music_app`, `music_readonly` (only if missing), database `music`, extensions `pg_trgm` and `btree_gist`.
2. As owner: `alembic upgrade head` (grants live in a migration, with `ALTER DEFAULT PRIVILEGES`).
3. As MongoDB root: create the app user (`readWrite` on the project DB only), then run `mongodb/setup_collections.py`.
The compose launcher lives in `scripts/run.sh`, so `setup.sh` must not be a launcher. Test: run it twice in a row without errors, then log in as `music_app`.

### `postgres/`

**Task 1.4: `0002_secondary_tables.py`** (2.5 h, done, to verify). Expected content: `genre`, `track_genre`, `track_like`, `artist_follow`, `payment` (unique `provider_ref`, unique subscription + month), `payout` (unique artist + month, rate per stream column, status), and the rule "a payout cannot change after `paid`" (trigger or documented as app-enforced). Also `playlist_change` if agreed. Must contain:
- `CHECK` for amounts, rates and prices >= 0, and for statuses.
- Grants: `music_app` gets SELECT/INSERT/UPDATE/DELETE on tables, **only SELECT/INSERT on `play`** (`REVOKE UPDATE, DELETE`); `music_readonly` gets SELECT. `ALTER DEFAULT PRIVILEGES` for later tables.
- `down_revision = "0001"` and a working `downgrade()`.

**Task 1.9a: `postgres/seed.py`** (see seed below).

### `mongodb/`

**Task 1.5: `export.py`** (3 h). Connects to PostgreSQL with `READONLY_DATABASE_URL`, reads plays of the last 12 months with listener, track, artists, genres, country, device. Writes **derived** collections (for example `listener_month_stats`, `track_day_stats`, `artist_country_month`). Idempotent: drop and recreate (or upsert) each run. Uses `executemany` or batches, not one query per row. Lisbon time for month and day buckets. Document each collection (what, why Mongo, derived, example) in `docs/mongodb.md`. Agree document shapes with Tiago so validators match.

**Task 1.6: pipelines** (3 h). At least 3 of the brief's reports (suggested: 1 yearly summary per listener, 2 streams per artist per country per month, 3 top genres per country per month). Each file has the question, the pipeline and a sample output in `docs/mongodb.md`.

### `redis/`

**Task 1.7: `rebuild.py`** (1.5 h). After `FLUSHALL`, recreate every **derived** key from PostgreSQL: today's top 50 charts (global and per country, sorted sets), daily stream counters per track, each listener's last 50 plays. TTLs set in the same command (`ZADD` + `EXPIRE` in one `MULTI/EXEC`). Charts: current day (Lisbon) and previous day with 7-day TTL. Uses Tiago's `redis/keys.py`.

**Task 1.8: `verify.py`** (1.5 h). Compares Redis with PostgreSQL (stream counters per track for today must equal streams in `play`; charts; last-50). Prints differences, exit 1 on mismatch, 0 otherwise. Acceptance test: `FLUSHALL`, `rebuild.py`, `verify.py` exits 0.

### `app/` and seed

**Task 1.9: `scripts/seed.sh` and `postgres/seed.py`** (2.5 h). Fixed random seed, dates relative to today, `COPY`/batch inserts, **no constraints or triggers disabled**, under 5 minutes. Volumes from the brief: 300 labels, 20k artists, 60k albums, 300k tracks, 100k listeners, ~35k subscriptions (some with the max members), monthly payments, >= 2M plays over 12 months (25% under 30 s, skewed: at least 200 tracks with >= 1,000 plays), 100k playlists, ~1M playlist entries (some collaborative, some with exactly 500), ~500k likes and follows, >= 50k playback events in Mongo within 30 days. Do not re-insert the 4 plans (`0001` does it). `seed.sh` runs: PostgreSQL seed, Mongo seed, `export.py`, `rebuild.py`.

**Task 1.10: flows F1, F6, F7, F8** (4 h). 
- F1: title search (`ILIKE`/trigram), album with tracks, artist with albums.
- F6: charts and last-50 **read only from Redis** (prove with `MONITOR` and PostgreSQL log, in `docs/redis.md`).
- F7: close a month: per main artist, `rate * streams`, split equally among main artists, round half up to the cent, one payout per artist per month (closing twice fails).
- F8: report endpoints reading the Mongo derived collections.
Streams = plays with `seconds_played >= 30`, month by Lisbon time.

### Documentation (Leandro)
`docs/runbook.md` (backup and restore commands per engine, RTO and RPO), `docs/redis.md` (rebuild and verify, persistence settings), `docs/mongodb.md` (reports), secondary tables in `docs/postgres.md`, README (run steps, ER diagram, endpoints, authors table).

---

## 2. Tiago (Relational Core, Concurrency and API)

### `postgres/`

**Task 2.1: `0001_primary_schema.py`** (4 h, done). 15 tables: `label`, `artist`, `album`, `album_artist`, `track`, `track_artist`, `listener`, `plan` (4 plans inserted), `subscription`, `subscription_member`, `invite_code`, `play`, `playlist`, `playlist_collaborator`, `playlist_track`. Key mechanisms:
- Partial unique indexes: one current subscription per owner, one current membership per listener.
- Trigger `enforce_max_members`: locks the subscription row (`FOR UPDATE`), counts current members, raises `23514` when full.
- `playlist_track UNIQUE (playlist_id, position) DEFERRABLE INITIALLY DEFERRED`.
- `playlist.track_count` with `CHECK (0..500)`, maintained by statement-level triggers (deliberate denormalisation).

Remaining:
- [ ] Test: 3rd member in a duo is refused; 501st playlist track is refused.
- [ ] `alembic downgrade base` then `upgrade head`.
- [ ] Push and PR.
- [ ] Decide where "a track has at least one `main` artist" and "free plan has no subscription" are enforced (trigger or app) and document.

**Task 2.2: `0003_indexes.py` and EXPLAIN evidence** (2 h, after seed). Indexes, each with a stated reason:
- `play (listener_id, started_at DESC)`: listener history, newest first (query 2).
- `play (track_id, started_at)`: streams of a track per month and artist's last 30 days (queries 1 and 6).
- `track USING gin (title gin_trgm_ops)`: title search (query 4).
- FKs: say which are indexed and which are not, and why.
For at least 3 queries show `EXPLAIN (ANALYZE, BUFFERS)` without (`BEGIN; DROP INDEX ...; EXPLAIN ...; ROLLBACK;`) and with the index, on seeded data, with one sentence comparing them. Indexes created by PK or UNIQUE do not count.

### `mongodb/`

**Task 2.3: `setup_collections.py`** (2.5 h). Idempotent (create if missing, otherwise `collMod`), connects with `MONGO_ROOT_URL`.
- Collection `playback_events`, `validationLevel: "strict"`, `validationAction: "error"`. Required: `listener_id` (int), `device_id` (string), `device_type` (enum mobile/desktop/web/speaker/car), `track_id` (int), `event_type` (enum start/heartbeat/pause/seek/skip/end), `position_seconds` (int >= 0), `ts` (date).
- Indexes: TTL on `ts` with `expireAfterSeconds: 2592000` (30 days); `{listener_id: 1, ts: -1}`.
- Validators and indexes for Leandro's report collections (agree shapes first).
- Decide and document where variable track details live (suggestion: collection `track_details`: lyrics, language, BPM, key, credits, blocked countries).
- Show `explain("executionStats")` for one query without and with its index in `docs/mongodb.md`.

### `redis/` (pure Python, `redis-py`)

**Task 2.4** (2.5 h).
- `keys.py`: key builders, e.g. `skips:{listener_id}:{YYYYMMDDHH}`, `active_device:{listener_id}`. One convention for the whole team.
- `skips.py`: `try_skip(r, listener_id)`; `pipeline(transaction=True)` with `SET key 0 EX 3600 NX` then `INCR key`; allowed if result <= 6; the 7th returns refusal (app answers 409 and the track keeps playing). Free listeners only.
- `active_device.py`: `start_on_device` (`SET ... EX 60`, replaces the previous device); `heartbeat` with `WATCH`/`MULTI` so compare-and-renew is atomic; a device that is not active gets refused (409).
- `docs/redis.md`: per key pattern the structure, example value, TTL and reason, commands, class (ephemeral).

### `app/`

**Task 2.5: base** (2.5 h).
- `config.py`: pydantic `Settings` (`database_url`, `mongo_url`, `redis_url`), `extra="ignore"`.
- `database.py`: SQLAlchemy engine with role `music_app` and `pool_size=20` (50 simultaneous requests), Mongo client (`readWrite` user), Redis client with password. Never `postgres` or `root`.
- `deps.py`: actor id from header `X-User-Id` (no authentication).
- `main.py`: routers plus `/health` (SELECT 1, Mongo ping, Redis PING).

**Task 2.6: F2, F3, F4, F5 and the concurrency test** (6 h in total, includes F2 and F4).

*F3, join a plan* (`POST /subscriptions/join`, body `{"invite_code": ...}`):
- Real mode, one transaction: read the code and check `expires_at`; `SELECT ... FROM subscription WHERE id = :s FOR UPDATE`; refuse if the listener is already a current member; insert the member. Trigger error `23514` becomes **409**. Any other expected refusal is 4xx, never 5xx.
- Naive mode: `count(*)`, `if count < max`, `INSERT`, no lock.

*F5, edit a playlist* (`POST /playlists/{id}/tracks`, `DELETE /playlists/{id}/tracks/{position}`, `PATCH /playlists/{id}/tracks/{position}`):
- Real mode, one transaction: `SELECT ... FROM playlist WHERE id = :p FOR UPDATE`; actor must be owner or collaborator (else 403); position outside 1..n+1 gives **422**; playlist with 500 tracks gives **409**; shift with `UPDATE ... SET position = position + 1 WHERE position >= :pos`, then insert (remove does the reverse shift; move does both); write a `playlist_change` row with actor and time.
- Naive mode: read count, shift and insert without `FOR UPDATE`.

*F2, subscriptions*: subscribe with a simulated first charge, cancel (subscription `cancelled`, every membership ends that date), monthly charge run (`simulate`: `approved`, `declined`, or a list to decline; declined gives `past_due`, approved gives `active`; at most one charge per subscription per month).

*F4, play*: start a track on a device (Redis active device, plus a `start` event in Mongo and a `play` row), heartbeat every 30 s, report seconds played, skip (free listeners 6 per hour, 409 on the 7th). A heartbeat or report from a non-active device is 409.

*Naive mode needs the guards off.* Because the trigger and the `CHECK` already protect the data, the test fixture (running as owner) must disable them for naive runs and restore them in teardown: `ALTER TABLE subscription_member DISABLE TRIGGER subscription_member_limit`; for the playlist, disable the count trigger and drop and re-create the position unique constraint and the 500 `CHECK`. Document this in `docs/concurrency.md`.

*`scripts/concurrency_test.py`*:
- Fixtures write directly to the DB and reset before every run, so it can run many times in a row.
- Family: `premium_family` subscription with owner plus 1 member, valid invite code, 50 free listeners; 50 simultaneous requests (`asyncio.gather` + `httpx`). Expect **4 accepted, 46 refused (409), 6 members**.
- Playlist: 490 tracks, 5 collaborators, 50 simultaneous adds at random positions 1..491. Expect **10 accepted, 40 refused (409)**, positions exactly 1..500, no gaps or duplicates. (Positions are always valid because the playlist only grows from 490, so no 422 is expected.)
- Per scenario prints: mode, accepted, refused, 5xx, whether the rule holds in the data. Exit 1 if the rule is broken or, in real mode, any 5xx.
- Extension (optional): rule 3, one device at a time.

*`docs/concurrency.md`*: isolation level (READ COMMITTED + `FOR UPDATE`) and why, locks used, what the naive version shows, and **3 runs per scenario in each mode (12 outputs)**.

### Documentation (Tiago)
`docs/postgres.md` (primary tables, constraints, where each rule is enforced, denormalisation, EXPLAIN, roles), `docs/concurrency.md`, `docs/redis.md` (skip and device keys), `docs/mongodb.md` (playback events, track details), `docs/ai-usage.md` entry for every AI use, including mistakes caught.

### Buffer (4.5 h)
Trigger tests, downgrade/upgrade test, running the concurrency test 3 times per scenario and mode and saving the outputs, learning Leandro's parts for session 19.

---

## Working order

| Step | Who | What |
|---|---|---|
| 1 | Tiago | Test `0001`, push, PR; Leandro reviews |
| 2 | Leandro | `setup.sh` with roles, grants, Mongo (unblocks testing as `music_app`) |
| 3 | Tiago | Task 2.5, then F3 + concurrency test, then F5 |
| 3 | Leandro | Seed, export, rebuild, verify |
| 4 | Tiago | Redis (2.4), F4, F2, Mongo (2.3) |
| 4 | Leandro | Pipelines, F1, F6, F7, F8 |
| 5 | Tiago | EXPLAIN (2.2) after the seed |
| 6 | Both | Docs, `ai-usage.md`, explain your parts to each other (session 18), tag `v1.0.0` before session 19 |

## Git verification script

Run before tagging. Use the **exact emails** from the README authors table.

```bash
#!/bin/bash
AUTHORS=("leandro@example.com" "tiago@example.com")   # replace with the real emails
AREAS=("postgres/" "mongodb/" "redis/" "app/")

for author in "${AUTHORS[@]}"; do
  echo "== $author =="
  for area in "${AREAS[@]}"; do
    count=$(git log v1.0.0 --no-merges --author="$author" --oneline -- "$area" | wc -l)
    printf "%-12s %d commits\n" "$area" "$count"
  done
done
```

A commit that only changes whitespace, formatting, comments or generated files does not count.