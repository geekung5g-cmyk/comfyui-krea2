#!/usr/bin/env bash
set -Eeuo pipefail
source /opt/scripts/env.sh
cd /opt/dashboard
echo "[dashboard] uvicorn on :${DASHBOARD_PORT:-8189}"
exec uvicorn app:app \
  --host 0.0.0.0 \
  --port "${DASHBOARD_PORT:-8189}" \
  --no-access-log \
  --timeout-keep-alive 75
