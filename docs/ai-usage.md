## Entry 1: repository structure

**Who:** Leo.
**Tool:** Claude (Sonnet 5.5), claude.ai.
**For what:** deciding the folder structure of the repository from the course README and the Project C brief: root files, `app/`, `postgres/`, `mongodb/`, `redis/`, `scripts/`, `docs/`.
**Outcome:** The first proposal was a deep tree with many sub-folders and extra files. I rejected it as too much for a 5-day project and asked for only what the README requires. I kept the second version: the six required folders, the four root files, `scripts/setup.sh`, `scripts/seed.sh` and the seven documents in `docs/`. I changed the AI usage notes into a folder `docs/ai-usage/` with one file per member, and put the course README and brief in `project/`.
**Verification:** compared the final tree against the "Repository structure" and "Documentation" sections of the course README. TODO: run the trainer's `git log` commands once we have commits.
**Mistakes caught:** the AI's first tree was over-engineered and went beyond the README. It also reminded me that the README requires a file named `docs/ai-usage.md` with the signed declaration, so the folder alone does not match the required name. We will add that file.

## Entry 2: Docker Compose and Dockerfile

**Who:** Leo.
**Tool:** Claude (Sonnet 5.5), claude.ai.
**For what:** first draft of `compose.yml` (PostgreSQL, MongoDB, Redis, the FastAPI app, DbGate) and `app/Dockerfile`, plus the variables in `.env.example`.
**Outcome:** TODO: write what we kept as it came, what we changed and what we rejected. For example: we chose DbGate as one admin tool for the three databases instead of separate pgAdmin and mongo-express services; passwords are read from `.env`; ports are published on `127.0.0.1`; PostgreSQL runs with `log_statement=all` for the cache evidence.
**Verification:** TODO: `docker compose up -d`, `docker compose build app`, `curl http://127.0.0.1:8000/health`, and a connection to each engine from DbGate.
**Mistakes caught:** TODO: add any error found when running it, or write "none found".

## Entry 3: Task distribution and time budget

**Who:** Tiago.
**Tool:** Gemini (2.5 Flash), gemini.google.com.
**For what:** creating the team task distribution and time budget document (`docs/task-distribution.md`), defining core responsibilities, estimated durations, priorities, and directory mapping for all 3 group members (Tiago, Leandro, and Paulo).
**Outcome:** The initial AI proposal allocated equal technical weights across engines without considering member expertise or Git verification risks. I requested a refined 15-hour budget per member (~12 hours coding, 3 hours buffer/research) where Leandro acts as repo owner (Docker/infrastructure), I handle core database architecture and Python concurrency control, and Paulo handles auxiliary features. I also rejected Lua script proposals, enforcing pure Python, SQL, and FastAPI libraries (`redis-py`, SQLAlchemy transaction locks). I kept the final markdown table structure and the automated bash verification script.
**Verification:** cross-referenced task paths against the four mandatory Git areas (`postgres/`, `mongodb/`, `redis/`, `app/`) to ensure no member receives a 0-commit penalty.
**Mistakes caught:** the AI's early versions assigned Lua scripts (contrary to our stack decisions) and initially forgot to distribute tasks across all 4 mandatory engine directories for every member. I corrected it to guarantee cross-directory compliance for everyone.

## Entry 4: `scripts/setup.sh`

**Who:** Leo.
**Tool:** Claude (Sonnet 5.5), claude.ai.
**For what:** the order of the steps in `scripts/setup.sh`: PostgreSQL database, roles and extensions as the superuser, then migrations as the owner, then the MongoDB app user, collections, validators and indexes as root.
**Outcome:** TODO: write what we kept from that order and what we wrote or changed ourselves (role names, variables from `.env`, making the script safe to run twice).
**Verification:** TODO: write what was run, for example `./scripts/setup.sh` twice in a row without errors, and a login to PostgreSQL as `music_app` and to MongoDB as the app user.
**Mistakes caught:** TODO: write any error found, or "none found".

## Entry 5: FastAPI app and Dockerfile

**Who:** Leo.
**Tool:** Claude (Sonnet 5.5), claude.ai.
**For what:** first draft of `app/src/app/main.py` (a `/health` route) and `app/Dockerfile`, and help finding why the `app` container kept restarting.
**Outcome:** kept the structure of both files. The `app/` folder had been created wrongly, so we deleted it and recreated it with `uv init`, then added FastAPI and uvicorn.
**Verification:** TODO: write the commands run, for example `docker compose up -d --build app` and `curl http://localhost:8000/health`.
**Mistakes caught:** the app folder was created wrongly by me and had to be recreated. TODO: add any error found in the Claude output, or write "none found".

## Entry 6: ER diagram of the PostgreSQL schema

**Who:** Leo.
**Tool:** Claude (Sonnet 5.5), claude.ai.
**For what:** first draft of the Mermaid ER diagram for the README and `docs/postgres.md`, based on `c-music-streaming.md`. Claude proposed 24 tables; we simplified it to 19, and then split it into primary and secondary tables for the migrations.
**Outcome:** kept the 19 tables, the keys and the relationships. Rermoved `album_artist`, `invite_code`, `playlist_change` and `stream_rate`: invite codes move to Redis with a TTL, and the rate per stream is now a column in `payout`. TODO: write any other change we made to the columns.
**Verification:** checked every rule of "Where the rules are enforced" against the tables, and compared the final table list with the primary and secondary split. TODO: add that the diagram renders in Mermaid, and a review by another member.
**Mistakes caught:** none found so far. TODO: add any error found when writing the migrations (for example a missing foreign key or a wrong key type).

## Entry 7: Alembic migrations setup

**Who:** Leo.
**Tool:** Claude (Sonnet 5.5), claude.ai.
**For what:** explaining how to set up Alembic in `postgres/` (config, `env.py` reading `MIGRATION_DATABASE_URL`), how migration files are named and chained with `revision` and `down_revision`, and how to split the schema into `001_primary_tables.py` and `002_secondary_tables.py` with fixed ids so two people can work in parallel.
**Outcome:** kept the structure: config in `postgres/`, migrations written by hand as SQL inside `op.execute`, no SQLAlchemy models, and the fixed ids `001` and `002`. TODO: write what we wrote ourselves (the SQL, constraints and the table order) and what we changed from the explanation.
**Verification:** TODO: write what was run, for example `alembic upgrade head`, `downgrade -1` and `upgrade head` again, and `alembic current` showing `002 (head)`. Also add a check of the Alembic documentation if one was done.
**Mistakes caught:** none found so far. TODO: add any error found when running the migrations, for example a wrong `down_revision` or a wrong table order.

## Entry 8: primary schema migration (`0001`)

**Who:** Tiago.
**Tool:** Claude (Sonnet 5.5), claude.ai.
**For what:** first draft of the Alembic migration for the primary tables (`postgres/migrations/versions/`), based on `c-music-streaming.md` and the ER diagram: catalogue, listeners, plans, subscriptions, members, invite codes, plays, playlists. It also drafted the member-limit trigger and the playlist track-count triggers.
**Outcome:** kept the table structure, the partial unique indexes ("one current subscription per owner", "one current membership per listener"), the `UNIQUE (playlist_id, position) DEFERRABLE INITIALLY DEFERRED`, and the trigger that locks the subscription row with `FOR UPDATE` before counting members. Kept `playlist.track_count` with `CHECK (track_count BETWEEN 0 AND 500)` as a deliberate denormalisation, maintained by statement-level triggers so a `COPY` seed stays fast. TODO: write what we change to match the team convention (ids `001`/`002`, raw SQL in `op.execute`) and the tables removed in the ER diagram.
**Verification:** `alembic upgrade head` ran without errors on an empty database. TODO: run `downgrade base` then `upgrade head`; insert a 3rd member in a duo subscription and a 501st playlist track and confirm both are refused; run the 50-request concurrency test.
**Mistakes caught:** the draft included `album_artist` and `invite_code`, which the team had already removed from the ER diagram, and used `0001` and `op.create_table` instead of the team convention. It also assumed IDs and table names before checking the existing schema work. TODO: confirm the member-limit trigger holds under 50 simultaneous requests.

## Entry 9: Alembic `env.py` and database connection

**Who:** Tiago.
**Tool:** Claude (Sonnet 5.5), claude.ai.
**For what:** diagnosing why `alembic upgrade head` failed with `Can't load plugin: sqlalchemy.dialects:driver` and later with `password authentication failed`, and changing `postgres/migrations/env.py` to read `MIGRATION_DATABASE_URL`.
**Outcome:** the cause was the placeholder `sqlalchemy.url = driver://...` in `alembic.ini`. We kept the AI's fix (set `sqlalchemy.url` from the environment in `env.py`) and left credentials out of the `.ini`. TODO: write whether `env.py` also converts `postgresql://` to `postgresql+psycopg://` or whether `.env.example` is changed instead.
**Verification:** the migration ran after the fix. We read the traceback to confirm the driver in use was `psycopg`.
**Mistakes caught:** the AI first suggested running `alembic init` and creating `postgres/alembic/`, but the Alembic setup already existed in `postgres/migrations/`; we found this in the traceback. It also suggested a `pgtest` container that does not exist in our compose setup, and it said the `postgresql://` prefix would pick the wrong driver without checking it against our dependencies.

## Entry 10: local environment troubleshooting

**Who:** Tiago.
**Tool:** Claude (Sonnet 5.5), claude.ai.
**For what:** getting the local stack to run: the `app` container restarting in a loop, the `.env` with Windows line endings, the missing `music_owner` role and `music` database, and a review of `scripts/setup.sh`.
**Outcome:** kept the findings: `main.py` must be at `app/src/app/main.py` because of `PYTHONPATH=/app/src` and `app.main:app`; `sed -i 's/\r$//'` fixed the CRLF in `.env`; the owner role and database were created by hand locally, since the current `scripts/setup.sh` only wraps `docker compose up/down`. Rejected rewriting `setup.sh` ourselves, because it is Leo's task. TODO: add a `.gitattributes` with `eol=lf` if the team agrees.
**Verification:** `curl localhost:8000/health` returned `ok`; `\dt` as `music_owner` and `alembic upgrade head` worked after creating the role. TODO: rerun everything from a clean clone once `setup.sh` is done.
**Mistakes caught:** the AI used `<superuser>` as a placeholder in a command, which bash read as a redirection. It also assumed a role and database existed before checking with `\du`.

## Entry 11: where the primary-schema rules live

**Who:** Tiago.
**Tool:** Claude (Sonnet 5.5), claude.ai.
**For what:** advice on keeping `album_artist`, `invite_code` and `playlist_change` in PostgreSQL after Leo's ER diagram removed them, and on where two rules are enforced: "a track has at least one `main` artist" and "the free plan has no subscription".
**Outcome:** the AI recommended keeping `album_artist` (the brief requires the main artists of an album in order) and `invite_code` in PostgreSQL (same transaction and `FOR UPDATE` as the join; in Redis a `FLUSHALL` would lose a source of truth). It also said `playlist_change` is needed because the brief asks who changed a playlist and when. This conflicts with Entry 6, where Leo moved invite codes to Redis. TODO: write the final decision we agreed with Leo and what we changed in the ER diagram. TODO: write where the two rules above are enforced (trigger or app).
**Verification:** compared the proposal with the "Catalogue" and "Playlists" sections of the brief. TODO: review by Leo.
**Mistakes caught:** TODO: add any error found. (The AI explained that a `CHECK` cannot count rows in another table, which is why "at least one main artist" needs a trigger or the app; check it against the PostgreSQL documentation.)

## Entry 12: task plan for two members

**Who:** Tiago.
**Tool:** Claude (Sonnet 5.5), claude.ai.
**For what:** adapting `docs/project/tasks.md` after Paulo left the group: detailed tasks per file for both members, the target folder structure, who owns each flow (F1 to F8), and the order of work.
**Outcome:** kept the split: Tiago owns F2, F3, F4, F5, the primary schema, the playback-events validator, the skip and active-device keys, and the concurrency test; Leo owns infrastructure, seed, export, pipelines, rebuild/verify, F1, F6, F7, F8. We replaced the template paths and names (`booking_service`, `app/services/cache_service.py`, `EXCLUDE`) with project ones and removed the "open decisions" section. TODO: write what Leo changed after reviewing it.
**Verification:** compared the plan with the brief and with the four mandatory Git areas. TODO: confirm the content of Leo's migration `0002`; the AI wrote what it should contain without seeing it.
**Mistakes caught:**
- The AI first said that positions above n+1 would give 422 in the playlist scenario. That is wrong for the test: the playlist starts with 490 tracks and only grows, so positions 1 to 491 are always valid and the 40 refused requests are all 409.
- The AI did not notice that the naive mode would never show a race, because the member-limit trigger and the playlist `CHECK` already protect the data. The test fixture (as owner) must disable those guards in naive mode and restore them afterwards.
- The AI first proposed a Lua script for the skip counter, against our decision to use pure Python (Entry 3); it was corrected to `pipeline(transaction=True)` and `WATCH` with `redis-py`.
- The AI first put Redis code under `app/services/`, where it would not count as a commit in `redis/`; it was moved to `redis/`.

## Entry 13: application core (`config.py`, `database.py`, `main.py`)

**Who:** Tiago.
**Tool:** Claude (Sonnet 5.5), claude.ai.
**For what:** first draft of the connection layer in `app/src/app/`:
- `config.py`: a pydantic `Settings` class that reads `DATABASE_URL`, `MONGO_URL` and `REDIS_URL` from `.env`, with `extra="ignore"` because `.env` holds many variables the app does not use, and a property that turns `postgresql://` into `postgresql+psycopg://`.
- `database.py`: the SQLAlchemy engine and session factory (`pool_size=20`, `max_overflow=20`, `pool_pre_ping`), the pymongo client and database, and the Redis client with the password in the URL.
- `main.py`: `/health` now runs `SELECT 1`, a MongoDB ping and a Redis `PING`.
- `pyproject.toml` and `uv.lock`: dependencies added with `uv add` (`pydantic-settings`, `pymongo`, `redis`).
**Outcome:** kept the structure of the three files. We chose a bigger connection pool than the default because the concurrency test sends 50 simultaneous requests and an exhausted pool would show up as 5xx errors. TODO: write what we changed (variable names from Leo's `.env.example`, anything we rejected).
**Verification:** TODO: `docker compose up -d --build app`, `curl localhost:8000/health` returning ok with the three checks, and a connection as `music_app` once `setup.sh` creates the app role. TODO: confirm that no engine is reached as `postgres` or `root`.
**Mistakes caught:** the AI wrote the files with assumed variable names before reading `.env.example`. It also warned that the app container can restart in a loop if the compose file does not pass the variables or uses `127.0.0.1` instead of the service names (`postgres`, `mongo`, `redis`). TODO: add any error found when running it.

## Entry 14: `docs/postgres.md`

**Who:** Tiago.
**Tool:** Claude (Sonnet 5.5), claude.ai.
**For what:** structure and first draft of `docs/postgres.md` for the primary tables: what each table is for, each constraint, index and trigger with the rule it serves, both "where the rules are enforced" lists, the `track_count` denormalisation, and TODO sections for EXPLAIN and roles.
**Outcome:** kept the structure and the tables from migration `0001`. Rules that depend on Leo's migration (`payment`, `payout`, likes, follows, grants on `play`) were left as TODO instead of being described as done. TODO: update the table list after the final decision in Entry 11.
**Verification:** TODO: run the trigger tests (3rd member in a duo, 501st playlist track) and `downgrade base` then `upgrade head` before writing "verified"; add the EXPLAIN evidence after the seed.
**Mistakes caught:** the AI listed some foreign keys (`subscription.plan_id`, `play.listener_id`, `play.track_id`) as not indexed. That is a gap in migration `0001` to decide on, not a finished design. TODO: add anything else found.

## Entry 15: Git workflow, commits and push

**Who:** Tiago.
**Tool:** Claude (Sonnet 5.5), claude.ai.
**For what:** checking that our commits are attributed through the author email, splitting the work into small commits, deciding what stays out of them, and the pull request rules (no squash merge).
**Outcome:** separate commits per concern, with the area in the scope: `feat(postgres)` for the migration and `fix(postgres)` for `env.py`, then `feat(app)` for the settings and database connections, `feat(app)` for F3, `chore(app)` for the `httpx` dependency, `test` for the concurrency script, and `docs` commits for `tasks.md` and `ai-usage`. `.env`, `.env.example` and files that were not ours were left out of every commit. We pushed the app work straight to `main` instead of opening a pull request.
**Verification:** `git log --author="$(git config user.email)" --oneline -- postgres/` listed both postgres commits, and `git status` never showed `.env`. TODO: run the same command for `app/`, `mongodb/` and `redis/` for both members, and the trainer's per-area loop, before tagging. TODO: turn off squash merging in the repository settings.
**Mistakes caught:**
- The AI kept telling me to add `postgres/drafts/subscription.sql` to the commit, which confused me because I had deleted that file on purpose; the deletion only needed to be staged.
- The AI suggested testing the app on the `tiago` branch before opening a pull request, but I had already pushed to `main`. It then had to warn that the container could restart in a loop for Leo. TODO: write the result of that test.
- The AI told me to copy a script it had created, without saying that I had to create the file in my own `scripts/` folder first. The path it gave did not exist in my repository.

## Entry 16: F3 join a subscription and the family-plan concurrency test

**Who:** Tiago.
**Tool:** Claude (Sonnet 5.5), claude.ai.
**For what:** first draft of flow F3 and of the test for the first concurrent scenario:
- `app/src/app/deps.py`: the acting listener from the `X-User-Id` header (no authentication, as the rules say).
- `app/src/app/services/subscription_service.py`: `POST /subscriptions/join` with two modes. Real mode runs in one transaction: read the invite code and its expiry, lock the subscription row with `SELECT ... FOR UPDATE OF s`, refuse a listener who is already a current member, count the members and insert. The member-limit trigger is the last guarantee, and its error code `23514` becomes a 409. Naive mode does the same without the lock and waits 50 ms between the check and the insert so the race shows up.
- `app/src/app/routers/subscriptions.py`: the endpoint, with `mode=real|naive`.
- `scripts/concurrency_test.py`: creates and resets its own fixture as the owner role (a `premium_family` subscription with the owner and 1 member, a valid invite code, 50 free listeners), sends the 50 requests at the same moment with `asyncio` and `httpx`, and prints the mode, accepted, refused, 5xx and whether the rule holds. It exits with 1 if the rule is broken or, in real mode, if the result is not the expected one.
**Outcome:** kept the structure of the service, router and script. The test only deletes rows it created (listeners with the prefix `ct-family-`), so it is safe to run after the seed. In naive mode the script disables the member-limit trigger for the run and enables it again in a `finally` block, because otherwise the trigger would protect the data and hide the race. TODO: write anything we change when we reuse this for the playlist scenario.
**Verification:** real mode gave 4 accepted, 46 refused, 0 errors and 6 members in PostgreSQL, with exit code 0. Naive mode gave 40 accepted, 10 refused and 42 members in a plan with a limit of 6, with exit code 1, so the race breaks the rule as expected. The naive numbers come from uvicorn running at most 40 requests at the same time: those 40 all counted 2 members, and the other 10 started later and were refused. TODO: run each mode two more times and save the 3 outputs per mode in `docs/concurrency.md`. TODO: check that the trigger is enabled again after the naive run (`tgenabled` in `pg_trigger`). TODO: test the invite code errors (404 for an unknown code, 410 for an expired one) and a listener who is already a member.
**Mistakes caught:**
- The first version of the service locked the row with `FOR UPDATE` on a query that joins `subscription` and `plan`. That tries to lock both tables, and the app role only has `SELECT` on `plan`. The endpoint returned a 500, and `FOR UPDATE OF s` (lock only the subscription row, the same as the trigger does) fixed it.
- The AI assumed the app role already had the grants the endpoint needs (`SELECT, UPDATE` on `subscription`, `SELECT, INSERT, UPDATE` on `subscription_member`, `SELECT` on `invite_code` and `plan`). They do not exist in `scripts/setup.sh` yet, so we created them by hand locally. TODO: Leo adds them to the grants.
- The AI first assumed that the naive mode would show the race by itself. It would not, because the trigger already enforces the limit, so the test has to disable it.

## Entry 17: PostgreSQL EXPLAIN validation, query optimizer analysis, and MongoDB schema verification

**Who:** Tiago.
**Tool:** Gemini (2.5 Flash), gemini.google.com.
**For what:** 
- Diagnosing and executing the `EXPLAIN (ANALYZE, BUFFERS)` benchmark query on the `play` table following data seeding to verify index configuration (`play_listener_started_desc_idx`).
- Analyzing PostgreSQL cost-based optimizer mechanics regarding small vs. large datasets.
- Reviewing completed MongoDB tasks (Task 2.3: JSON schema validation with `$jsonSchema`, type constraints, enums, and TTL indexing for playback events).
**Outcome:** Kept the pure Python and SQLAlchemy execution approach via terminal one-liners (`uv run python -c`) without creating unnecessary script files. Explained why PostgreSQL selects a `Seq Scan` over an `Index Scan` when table row counts are low, and confirmed the MongoDB schema and TTL index setup ready for application integration.
**Verification:** Ran the EXPLAIN execution plan in the terminal, confirmed `rows=4` and `Rows Removed by Filter: 296` after running `postgres/seed.py`.
**Mistakes caught:** The initial query execution returned `rows=0` due to an empty table; identified that `postgres/seed.py` needed to be executed first, populated the data, and re-ran the benchmark to get true execution metrics.

## Entry 18: Redis key naming and Mongo collection setup

**Who:** Tiago.
**Tool:** GitHub Copilot.
**For what:** correcting the task 2.4 Redis implementation and aligning the task 2.3 Mongo collection setup with the project brief, including key naming, `SET ... NX` + `INCR` skip logic, active-device heartbeat logic, TTL index setup, and strict validation for `playback_events`.
**Outcome:** Kept the project-local structure: `redis/keys.py`, `redis/skips.py`, `redis/active_device.py`, `redis/cache_service.py`, and the updated `mongodb/setup_collections.py`. The Redis key convention now follows `skips:{listener_id}:{YYYYMMDDHH}` and `active_device:{listener_id}`; the skip counter is limited to 6 per hour and the 7th request returns a refusal; the active-device lock is renewed atomically with `WATCH`/`MULTI` and rejected for non-active devices. The Mongo collection includes strict schema validation, TTL on `ts`, and the compound index `{listener_id: 1, ts: -1}` with a `track_details` collection suggestion for variable metadata.
**Verification:** ran `cd /workspaces/music-streaming && python -m compileall redis mongodb` and then a `uv run python` validation script that checked the Redis behavior. The verified output was:
- `PING: True`
- `skip1: True` to `skip6: True`
- `skip7: False`
- `device: True`
- `same heartbeat: True`
- `other heartbeat: False`
- `key sample: skips:777:2026111116`
**Mistakes caught:** the main issue was the directory name collision between the project folder `redis/` and the installed `redis` Python package; imports like `from redis.keys import ...` failed because Python resolved the package name instead of the project-local module. We fixed this by importing project-local files by path in the test runner and by changing the module imports to `from keys import ...`, `from skips import ...`, and `from active_device import ...` inside the Redis task files. We also had to separate the “usage of AI” notes from the actual implementation: the AI suggestions were used for the structure and logic, but the final code and verification were checked in the project environment before being accepted.