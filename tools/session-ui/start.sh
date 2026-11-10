#!/usr/bin/env bash
# Start the session UI for the cwd (or $1), unless it is already running.
# Usage: start.sh [root] [session]
root="${1:-$PWD}"
session="${2:-}"
port="${SESSION_UI_PORT:-8765}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if curl -s -o /dev/null "localhost:$port/api/config"; then
  echo "already running: http://localhost:$port"
  exit 0
fi

args=(--root "$root" --port "$port")
[ -n "$session" ] && args+=(--session "$session")
echo "http://localhost:$port"
exec python3 "$here/session_ui.py" "${args[@]}"
