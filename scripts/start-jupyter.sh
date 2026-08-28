#!/usr/bin/env bash
set -Eeuo pipefail
source /opt/scripts/env.sh
cd "${DATA_DIR:-/workspace}"
echo "[jupyter] lab on :${JUPYTER_PORT:-8888}"
exec jupyter lab \
  --ip=0.0.0.0 \
  --port="${JUPYTER_PORT:-8888}" \
  --no-browser \
  --allow-root \
  --ServerApp.token="${JUPYTER_TOKEN}" \
  --ServerApp.password='' \
  --ServerApp.root_dir="${DATA_DIR:-/workspace}" \
  --ServerApp.allow_origin='*' \
  --ServerApp.allow_remote_access=True \
  --ServerApp.trust_xheaders=True \
  --ServerApp.terminado_settings="{'shell_command': ['/bin/bash']}"
