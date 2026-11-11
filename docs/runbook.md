# Backup and recovery runbook

This runbook covers the local Compose deployment. The repository does not
schedule backups or copy them off-host; an operator must run the commands,
protect the resulting files, and verify that the backup destination is
separate from the Compose volumes. The RTO/RPO values below are planning
targets, not measured service guarantees.

## Before backup or restore

Run commands from the repository root. Ensure `.env` contains real credentials
and that the services are running:

```bash
set -a
source .env
set +a
mkdir -p backups
docker compose ps
```

Keep backups encrypted and outside this repository. Do not commit the
`backups/` directory. Before a restore, stop the app to prevent writes and
confirm the target database/collections may be replaced.

## PostgreSQL

**What:** the complete `music` database, including schema, migrations, and
business data. **Cadence:** at least daily and before a migration or large
seed. Copy the dump off the machine after creation.

### Backup

```bash
set -a
source .env
set +a
mkdir -p backups
docker compose exec -T \
  -e PGPASSWORD="$POSTGRES_SUPERUSER_PASSWORD" postgres \
  pg_dump -U "$POSTGRES_SUPERUSER" -Fc -d music \
  > "backups/postgres-$(date -u +%Y%m%dT%H%M%SZ).dump"
```

### Restore

This replaces database objects in `music`. Ensure the dump is the desired
recovery point first.

```bash
set -a
source .env
set +a
docker compose stop app
./scripts/setup.sh postgres
docker compose exec -T \
  -e PGPASSWORD="$OWNER_PASSWORD" postgres \
  pg_restore -U music_owner --clean --if-exists --no-owner \
  -d music < backups/postgres-YYYYMMDDTHHMMSSZ.dump
./scripts/setup.sh postgres
docker compose up -d app
```

`setup.sh postgres` ensures the roles, database settings, extension, and
migrations are present. `pg_restore --clean` replaces the schema/data from the
dump; restoring is destructive to the current contents of `music`.

### Verify

```bash
docker compose exec -T postgres \
  psql -U music_owner -d music -c \
  "SELECT version_num FROM alembic_version; SELECT count(*) FROM track;"
curl -fsS http://127.0.0.1:8000/health
```

**Targets:** RTO 1 hour; RPO 24 hours with a daily dump. A daily dump can lose
up to a day's subscription/payment/play changes. These targets are only
acceptable for the coursework demo; a production billing system needs
continuous/WAL-based recovery and tested point-in-time restore.

## MongoDB

**What:** `playback_events`, `track_details`, and the three report collections.
**Cadence:** daily, and after substantial data changes. Raw playback events
expire after 30 days; report collections can be regenerated from PostgreSQL,
but raw events and manually authored track details cannot.

### Backup

```bash
set -a
source .env
set +a
mkdir -p backups
docker compose exec -T \
  -e MONGO_ROOT_URL="$MONGO_ROOT_URL" mongo \
  sh -c 'mongodump --uri "$MONGO_ROOT_URL" --db music --archive' \
  > "backups/mongo-$(date -u +%Y%m%dT%H%M%SZ).archive"
```

### Restore

`--drop` replaces matching collections. Stop the app first and verify the
archive name before running this command.

```bash
set -a
source .env
set +a
docker compose stop app
docker compose exec -T \
  -e MONGO_ROOT_URL="$MONGO_ROOT_URL" mongo \
  sh -c 'mongorestore --uri "$MONGO_ROOT_URL" --nsInclude="music.*" --drop --archive' \
  < backups/mongo-YYYYMMDDTHHMMSSZ.archive
uv run --project app python mongodb/setup_collections.py
uv run --project app python mongodb/export.py
docker compose up -d app
```

The export step recreates report data from PostgreSQL; it does not recreate
expired or missing raw playback events or `track_details`.

### Verify

```bash
docker compose exec -T mongo sh -c \
  'mongosh "$MONGO_ROOT_URL" --quiet --eval \
  "const d=db.getSiblingDB(\"music\"); printjson({events:d.playback_events.countDocuments(), listeners:d.listener_month_stats.countDocuments()})"'
```

**Targets:** RTO 30 minutes; RPO 24 hours for raw events with daily backups.
Report collections have an effective RPO of the PostgreSQL source because
they can be re-exported. Losing unbacked `track_details` loses those optional
metadata permanently.

## Redis

Redis persistence (AOF) and a named volume are enabled in Compose, but the
project treats Redis as rebuildable rather than as the only copy of business
data. The charts, per-track daily counters, and last-50 lists are derived from
PostgreSQL. Active-device and skip keys are short-lived state and cannot be
recovered from PostgreSQL.

### Recovery

After Redis is lost or flushed, rebuild only the derived key families:

```bash
uv run --project app python redis/rebuild.py
uv run --project app python redis/verify.py
```

The rebuild does not restore active devices or skip counters. Users resume
playback, and those keys expire naturally. It does not use `FLUSHALL`.

### Verify

`redis/verify.py` is read-only. It compares current/previous charts, today's
stream counters, and all last-50 histories with PostgreSQL and exits nonzero
on a mismatch.

**Targets:** RTO 15 minutes; RPO is zero for rebuildable derived data after a
successful rebuild. Temporary active-device and skip state may be lost; the
business accepts that temporary state loss for this project.

## Recovery drill status

The backup/restore commands are documented but a full disaster-recovery drill
has not been run. Test restores against disposable Compose volumes before
relying on these targets.