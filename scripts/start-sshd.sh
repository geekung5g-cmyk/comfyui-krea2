#!/usr/bin/env bash
set -Eeuo pipefail
source /opt/scripts/env.sh
if [[ "${ENABLE_SSHD:-0}" != "1" ]]; then
  echo "[sshd] no PUBLIC_KEY provided - sshd disabled"
  exit 0
fi
mkdir -p /run/sshd
echo "[sshd] listening on :22"
exec /usr/sbin/sshd -D -e
