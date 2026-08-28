# Sourced by every service launcher. Supervisor does not inherit the shell
# environment we built in entrypoint.sh, so re-read the persisted values.
export VIRTUAL_ENV="${VIRTUAL_ENV:-/opt/venv}"
export PATH="${VIRTUAL_ENV}/bin:${PATH}"
export DATA_DIR="${DATA_DIR:-/workspace}"
export COMFY_HOME="${COMFY_HOME:-/opt/ComfyUI}"
export HF_HOME="${HF_HOME:-${DATA_DIR}/.cache/huggingface}"
export HF_HUB_ENABLE_HF_TRANSFER="${HF_HUB_ENABLE_HF_TRANSFER:-1}"
export PYTHONUNBUFFERED=1
export TOKENIZERS_PARALLELISM=false

if [[ -f "${DATA_DIR}/.credentials" ]]; then
  # shellcheck disable=SC1091
  source "${DATA_DIR}/.credentials"
  export DASHBOARD_TOKEN="${DASHBOARD_TOKEN:-${SAVED_DASHBOARD_TOKEN:-}}"
  export JUPYTER_TOKEN="${JUPYTER_TOKEN:-${SAVED_JUPYTER_TOKEN:-}}"
fi
