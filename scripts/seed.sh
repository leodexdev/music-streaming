#!/usr/bin/env bash
# Replaces PostgreSQL fixture data, seeds MongoDB events, exports reports and rebuilds Redis.
#
# Usage:
#   ./scripts/seed.sh                 (runs the full pipeline; asks before truncating PostgreSQL)
#   ./scripts/seed.sh --yes           (same, without the confirmation prompt)
#   ./scripts/seed.sh postgres        (only seed PostgreSQL; asks before truncating)
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

CONFIRM_RESET=0
TARGETS=()
for arg in "$@"; do
  case "$arg" in
    -y|--yes) CONFIRM_RESET=1 ;;
    *) TARGETS+=("$arg") ;;
  esac
done
if [ "${#TARGETS[@]}" -eq 0 ]; then
  TARGETS=(postgres mongo export redis)
fi

for target in "${TARGETS[@]}"; do
  case "$target" in
    postgres) needs_postgres_reset=1 ;;
    mongo|export|redis) ;;
    *) echo "Unknown target: $target (use postgres, mongo, export or redis)" >&2; exit 1 ;;
  esac
done
if [ "${needs_postgres_reset:-0}" -eq 1 ] && [ "$CONFIRM_RESET" -ne 1 ]; then
  echo "WARNING: PostgreSQL seed truncates project data and replaces it with a large fixture." >&2
  if [ ! -t 0 ]; then
    echo "Run interactively or pass --yes only if you intend to replace the data." >&2
    exit 1
  fi
  read -r -p "Continue and replace PostgreSQL fixture data? [y/N] " answer
  [ "$answer" = "y" ] || { echo "Cancelled."; exit 1; }
fi

# ---------------------------------------------------------------- PostgreSQL
seed_postgres() {
  echo "==> PostgreSQL"
  if [ ! -f "postgres/seed.py" ]; then
    skip "postgres/seed.py not found"
    return
  fi

  if uv run --project app python postgres/seed.py --confirm-reset; then
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
for t in "${TARGETS[@]}"; do
  case "$t" in
    postgres) seed_postgres ;;
    mongo)    seed_mongo ;;
    export)   export_reports ;;
    redis)    seed_redis ;;
  esac
  if [ "${#FAILED[@]}" -gt 0 ]; then
    echo "Stopping pipeline after a failed step." >&2
    break
  fi
done

echo
echo "==================== Summary ===================="
for m in ${DONE[@]+"${DONE[@]}"};       do echo "  done:    $m"; done
for m in ${SKIPPED[@]+"${SKIPPED[@]}"}; do echo "  skipped: $m"; done
for m in ${FAILED[@]+"${FAILED[@]}"};   do echo "  FAILED:  $m"; done
echo "================================================="

[ "${#FAILED[@]}" -eq 0 ]