#!/usr/bin/env bash
# Sets up PostgreSQL, MongoDB and Redis.
# Each part runs only if its requirements exist. Otherwise it is skipped and the
# summary at the end says what is missing. Safe to run more than once.
#
#   ./scripts/setup.sh                 all three
#   ./scripts/setup.sh postgres        only PostgreSQL (also: mongo, redis)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Missing .env. Run: cp .env.example .env" >&2
  exit 1
fi
set -a; source .env; set +a

DONE=(); SKIPPED=(); FAILED=()
ok()   { DONE+=("$1");    echo "    ok: $1"; }
skip() { SKIPPED+=("$1"); echo "    SKIPPED: $1"; }
fail() { FAILED+=("$1");  echo "    FAILED: $1" >&2; }

# prints the names of the variables that are empty or unset
missing_vars() {
  local v out=()
  for v in "$@"; do [ -n "${!v:-}" ] || out+=("$v"); done
  echo "${out[*]:-}"
}

# ---------------------------------------------------------------- PostgreSQL
psql_su() {
  docker compose exec -T -e PGPASSWORD="$POSTGRES_SUPERUSER_PASSWORD" postgres \
    psql -v ON_ERROR_STOP=1 -U "$POSTGRES_SUPERUSER" "$@"
}

setup_postgres() {
  echo "==> PostgreSQL"
  local miss
  miss=$(missing_vars POSTGRES_SUPERUSER POSTGRES_SUPERUSER_PASSWORD \
                      OWNER_PASSWORD APP_PASSWORD READONLY_PASSWORD)
  if [ -n "$miss" ]; then
    skip "PostgreSQL: add these variables to .env: $miss"
    return
  fi
  if ! psql_su -d postgres -c 'SELECT 1' >/dev/null 2>&1; then
    skip "PostgreSQL: cannot connect. Is the postgres container running (docker compose up -d postgres)?"
    return
  fi

  if psql_su -d postgres \
      -v owner_pw="$OWNER_PASSWORD" -v app_pw="$APP_PASSWORD" -v ro_pw="$READONLY_PASSWORD" <<'SQL'
-- owner: runs the migrations and owns the schema
SELECT format('CREATE ROLE music_owner LOGIN PASSWORD %L', :'owner_pw')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'music_owner') \gexec
-- app: used by the API (privileges are granted in a migration)
SELECT format('CREATE ROLE music_app LOGIN PASSWORD %L', :'app_pw')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'music_app') \gexec
-- read-only: reports and the MongoDB export
SELECT format('CREATE ROLE music_ro LOGIN PASSWORD %L', :'ro_pw')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'music_ro') \gexec
-- keep the passwords in sync with .env on every run
SELECT format('ALTER ROLE music_owner PASSWORD %L', :'owner_pw') \gexec
SELECT format('ALTER ROLE music_app PASSWORD %L', :'app_pw') \gexec
SELECT format('ALTER ROLE music_ro PASSWORD %L', :'ro_pw') \gexec

SELECT 'CREATE DATABASE music OWNER music_owner'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'music') \gexec
SQL
  then ok "roles (music_owner, music_app, music_ro) and database music"
  else fail "PostgreSQL roles and database"; return
  fi

  if psql_su -d music <<'SQL'
-- pg_trgm: index for "title contains text" (query 4 of the brief)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
ALTER DATABASE music SET timezone TO 'Europe/Lisbon';
REVOKE CONNECT ON DATABASE music FROM PUBLIC;
GRANT CONNECT ON DATABASE music TO music_owner, music_app, music_ro;
SQL
  then ok "extension pg_trgm, time zone Europe/Lisbon, connect rights"
  else fail "PostgreSQL extensions and connect rights"; return
  fi

  # migrations, run as the owner role
  if ! command -v uv >/dev/null 2>&1; then
    skip "PostgreSQL migrations: uv is not installed"
  elif [ ! -f postgres/alembic.ini ]; then
    skip "PostgreSQL migrations: postgres/alembic.ini not found (set up Alembic in postgres/)"
  elif ! compgen -G "postgres/migrations/versions/*.py" >/dev/null; then
    skip "PostgreSQL migrations: no files in postgres/migrations/versions/ yet"
  elif MIGRATION_DATABASE_URL="postgresql+psycopg://music_owner:${OWNER_PASSWORD}@127.0.0.1:5432/music" \
         uv run --project app alembic -c postgres/alembic.ini upgrade head; then
    ok "migrations applied (alembic upgrade head)"
  else
    fail "PostgreSQL migrations (see the error above)"
  fi
}

# ------------------------------------------------------------------- MongoDB
mongo_root() {
  docker compose exec -T -e APP_PW="$MONGO_APP_PASSWORD" mongo mongosh --quiet \
    -u "$MONGO_ROOT_USER" -p "$MONGO_ROOT_PASSWORD" --authenticationDatabase admin "$@"
}

setup_mongo() {
  echo "==> MongoDB"
  local miss
  miss=$(missing_vars MONGO_ROOT_USER MONGO_ROOT_PASSWORD MONGO_APP_PASSWORD MONGO_ROOT_URL)
  if [ -n "$miss" ]; then
    skip "MongoDB: add these variables to .env: $miss"
    return
  fi
  if ! mongo_root --eval 'db.adminCommand("ping")' >/dev/null 2>&1; then
    skip "MongoDB: cannot connect. Is the mongo container running (docker compose up -d mongo)?"
    return
  fi

  if mongo_root music --eval '
      const pw = process.env.APP_PW;
      if (db.getUser("music_app")) db.updateUser("music_app", { pwd: pw });
      else db.createUser({ user: "music_app", pwd: pw, roles: [{ role: "readWrite", db: "music" }] });
    ' >/dev/null
  then ok "user music_app with readWrite on music"
  else fail "MongoDB app user"; return
  fi

  if [ ! -f mongodb/setup_collections.py ]; then
    skip "MongoDB collections, validators and indexes: mongodb/setup_collections.py not found"
  elif ! command -v uv >/dev/null 2>&1; then
    skip "MongoDB collections, validators and indexes: uv is not installed"
  elif uv run --project app python mongodb/setup_collections.py; then
    ok "collections, validators and indexes (mongodb/setup_collections.py)"
  else
    fail "mongodb/setup_collections.py (run it by hand to see the error)"
  fi
}

# --------------------------------------------------------------------- Redis
setup_redis() {
  echo "==> Redis"
  local miss
  miss=$(missing_vars REDIS_PASSWORD)
  if [ -n "$miss" ]; then
    skip "Redis: add these variables to .env: $miss"
    return
  fi
  if docker compose exec -T -e REDISCLI_AUTH="$REDIS_PASSWORD" redis redis-cli ping 2>/dev/null | grep -q PONG; then
    ok "Redis is reachable and the password works"
  else
    skip "Redis: cannot connect. Is the redis container running and REDIS_PASSWORD the same as in compose?"
    return
  fi

  # nothing to create in Redis: the keys are built by the rebuild script (seed.sh)
  local f
  for f in redis/rebuild.py redis/verify.py; do
    [ -f "$f" ] || skip "Redis: $f not found yet (seed.sh needs it)"
  done
}

# ---------------------------------------------------------------------- main
TARGETS=("$@")
[ "${#TARGETS[@]}" -gt 0 ] || TARGETS=(postgres mongo redis)

for t in "${TARGETS[@]}"; do
  case "$t" in
    postgres) setup_postgres ;;
    mongo)    setup_mongo ;;
    redis)    setup_redis ;;
    *) echo "Unknown target: $t (use postgres, mongo or redis)" >&2; exit 1 ;;
  esac
done

echo
echo "==================== Summary ===================="
for m in ${DONE[@]+"${DONE[@]}"};       do echo "  done:    $m"; done
for m in ${SKIPPED[@]+"${SKIPPED[@]}"}; do echo "  skipped: $m"; done
for m in ${FAILED[@]+"${FAILED[@]}"};   do echo "  FAILED:  $m"; done
echo "================================================="

[ "${#FAILED[@]}" -eq 0 ]