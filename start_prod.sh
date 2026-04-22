#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

if [[ ! -d ".venv" ]]; then
  echo "No existe .venv. Crea el entorno primero con python3.11 -m venv .venv"
  exit 1
fi

if [[ ! -f ".env" ]]; then
  echo "No existe .env. Copia .env.example y completa las variables."
  exit 1
fi

source .venv/bin/activate

export PORT="${PORT:-5000}"
export GUNICORN_WORKERS="${GUNICORN_WORKERS:-4}"
export GUNICORN_THREADS="${GUNICORN_THREADS:-32}"
export GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"
export GUNICORN_KEEPALIVE="${GUNICORN_KEEPALIVE:-5}"

ulimit -n "${ULIMIT_NOFILE:-65535}" || true

exec gunicorn -c gunicorn.conf.py run:app
