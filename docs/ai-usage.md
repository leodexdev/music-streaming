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
