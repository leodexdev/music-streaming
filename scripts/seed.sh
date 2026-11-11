#!/usr/bin/env bash
# Wipes old data and seeds PostgreSQL, MongoDB, and Redis with fresh dummy data.
# Each part runs only if its seed script exists.
#
# Usage:
#   ./scripts/seed.sh                 (runs all three if available)
#   ./scripts/seed.sh postgres        (only seed PostgreSQL)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Missing .env. Run: cp .env.example .env" >&2
  exit 1
fi
set -a; source .env; set +a

if ! command -v uv >/dev/null 2>&1; then
  echo "Error: 'uv' is not installed. Cannot run Python scripts." >&2
  exit 1
fi

DONE=(); SKIPPED=(); FAILED=()
ok()   { DONE+=("$1");    echo "    ok: $1"; }
skip() { SKIPPED+=("$1"); echo "    SKIPPED: $1"; }
fail() { FAILED+=("$1");  echo "    FAILED: $1" >&2; }

# ---------------------------------------------------------------- PostgreSQL
seed_postgres() {
  echo "==> PostgreSQL"
  if [ ! -f "postgres/seed.py" ]; then
    skip "postgres/seed.py not found"
    return
  fi

  if uv run --project app python postgres/seed.py; then
    ok "PostgreSQL seeded successfully"
  else
    fail "PostgreSQL seeding (see error above)"
  fi
}

# ------------------------------------------------------------------- MongoDB
seed_mongo() {
  echo "==> MongoDB"
  if [ -f "mongodb/seed.py" ]; then
    if uv run --project app python mongodb/seed.py; then
      ok "MongoDB seeded successfully (Python)"
    else
      fail "MongoDB seeding (Python)"
    fi
  elif [ -f "mongodb/seed.js" ]; then
    if docker compose exec -T -e APP_PW="$MONGO_APP_PASSWORD" mongo mongosh --quiet \
      -u "music_app" -p "$MONGO_APP_PASSWORD" music < mongodb/seed.js >/dev/null; then
      ok "MongoDB seeded successfully (JS)"
    else
      fail "MongoDB seeding (JS)"
    fi
  else
    skip "neither mongodb/seed.py nor mongodb/seed.js found"
  fi
}

export_reports() {
  echo "==> MongoDB report export"
  if [ ! -f mongodb/export.py ]; then
    skip "mongodb/export.py not found"
    return
  fi
  if uv run --project app python mongodb/export.py; then
    ok "report collections exported"
  else
    fail "mongodb/export.py (see error above)"
  fi
}

# --------------------------------------------------------------------- Redis
seed_redis() {
  echo "==> Redis"
  if [ ! -f "redis/rebuild.py" ]; then
    skip "redis/rebuild.py not found"
    return
  fi

  if uv run --project app python redis/rebuild.py; then
    ok "Redis rebuilt successfully"
  else
    fail "Redis rebuild (see error above)"
  fi
}

# ---------------------------------------------------------------------- main
TARGETS=("$@")
[ "${#TARGETS[@]}" -gt 0 ] || TARGETS=(postgres mongo export redis)

for t in "${TARGETS[@]}"; do
  case "$t" in
    postgres) seed_postgres ;;
    mongo)    seed_mongo ;;
    export)   export_reports ;;
    redis)    seed_redis ;;
    *) echo "Unknown target: $t (use postgres, mongo, export or redis)" >&2; exit 1 ;;
  esac
done

echo
echo "==================== Summary ===================="
for m in ${DONE[@]+"${DONE[@]}"};       do echo "  done:    $m"; done
for m in ${SKIPPED[@]+"${SKIPPED[@]}"}; do echo "  skipped: $m"; done
for m in ${FAILED[@]+"${FAILED[@]}"};   do echo "  FAILED:  $m"; done
echo "================================================="

[ "${#FAILED[@]}" -eq 0 ]