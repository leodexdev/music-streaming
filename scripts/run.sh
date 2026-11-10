#!/usr/bin/env bash
# One entry point for the whole project.
#
#   ./scripts/run.sh            start all services, then run setup.sh
#   ./scripts/run.sh reset      wipe ALL data (volumes) and start again from zero
#   ./scripts/run.sh reset -y   same, without asking
#   ./scripts/run.sh logs       follow the logs (optionally: logs app)
#   ./scripts/run.sh seed       run seed.sh
#   ./scripts/run.sh ps         show the services
#   ./scripts/run.sh down       stop the services (keeps the data)
set -euo pipefail
cd "$(dirname "$0")/.."

usage() {
  sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
}

ensure_env() {
  if [ ! -f .env ]; then
    # tr -d '\r' removes Windows line endings while copying
    tr -d '\r' < .env.example > .env
    echo "Created .env from .env.example (edit the passwords if needed)"
  elif grep -q $'\r' .env; then
    # an existing .env that already has CRLF gets cleaned in place
    tr -d '\r' < .env > .env.tmp && mv .env.tmp .env
    echo "Removed Windows line endings (CRLF) from .env"
  fi
}

up() {
  ensure_env
  # The databases go first, so the roles and users exist before the app starts.
  echo "==> Starting PostgreSQL, MongoDB and Redis"
  docker compose up -d --wait postgres mongo redis

  echo "==> Running setup (database, roles, migrations, MongoDB user)"
  ./scripts/setup.sh

  echo "==> Starting the app and the other services"
  docker compose up -d --build
  docker compose ps
}

reset() {
  if [ "${1:-}" != "-y" ]; then
    read -r -p "This deletes ALL data in PostgreSQL, MongoDB, Redis and DbGate. Continue? [y/N] " answer
    [ "$answer" = "y" ] || { echo "Cancelled."; exit 1; }
  fi
  docker compose down -v --remove-orphans
  up
}

cmd="${1:-up}"
[ $# -gt 0 ] && shift

case "$cmd" in
  up)          up ;;
  reset)       reset "$@" ;;
  logs)        docker compose logs -f --tail=100 "$@" ;;
  seed)        ./scripts/seed.sh ;;
  ps|status)   docker compose ps ;;
  down)        docker compose down ;;
  -h|--help|help) usage ;;
  *)           usage; exit 1 ;;
esac