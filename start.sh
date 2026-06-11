#!/usr/bin/env sh
# Railway start script. Kept as a committed file (not an inline railway.toml
# startCommand) so we never hit shell-quoting ambiguity in the V2 runtime.
set -e

echo "=== BUILD_COMMIT=${BUILD_COMMIT:-unknown} GIT_SHA=${RAILWAY_GIT_COMMIT_SHA:-unknown} ==="
echo "=== migrations ==="
alembic upgrade head
echo "=== starting bot ==="
exec python -u -m bot.main
