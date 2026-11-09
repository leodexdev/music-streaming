#!/usr/bin/env bash
# Starts everything defined in your Docker Compose file.
# Usage: ./run.sh [up|down|restart|logs|status]   (default: up)
set -euo pipefail

cd "$(dirname "$0")"

# Use "docker compose" (v2) if available, else fall back to "docker-compose" (v1)
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  echo "Docker Compose not found. Install Docker first." >&2
  exit 1
fi

# Optional: pass a specific file with COMPOSE_FILE=compose.yml ./setup.sh
cmd="${1:-up}"

case "$cmd" in
  up)
    $DC pull --ignore-pull-failures || true
    $DC up -d --build --remove-orphans
    $DC ps
    ;;
  down)
    $DC down
    ;;
  restart)
    $DC down
    $DC up -d --build --remove-orphans
    $DC ps
    ;;
  logs)
    $DC logs -f --tail=100
    ;;
  status)
    $DC ps
    ;;
  *)
    echo "Usage: $0 [up|down|restart|logs|status]" >&2
    exit 1
    ;;
esac