#!/usr/bin/env bash
set -Eeuo pipefail
source /opt/scripts/env.sh

ARGS=(
  --listen 0.0.0.0
  --port "${COMFYUI_PORT:-8188}"
  --disable-auto-launch
  --preview-method auto
)

# Blackwell (sm_120) likes fp16 accumulation; harmless elsewhere. COMFY_FAST=0 disables.
if [[ "${COMFY_FAST:-1}" == "1" ]]; then
  ARGS+=(--fast)
fi

# Extra flags from the Vast template, e.g. "--lowvram --reserve-vram 1.5"
if [[ -n "${COMFY_ARGS:-}" ]]; then
  # shellcheck disable=SC2206
  ARGS+=(${COMFY_ARGS})
fi

echo "[comfyui] python main.py ${ARGS[*]}"
exec python main.py "${ARGS[@]}"
