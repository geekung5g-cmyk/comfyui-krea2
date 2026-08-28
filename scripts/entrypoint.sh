#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Container entrypoint: prepare persistent dirs, tokens, then hand over to
# supervisord which runs ComfyUI (8188), Dashboard (8189), JupyterLab (8888).
# ---------------------------------------------------------------------------
set -Eeuo pipefail

COMFY_HOME="${COMFY_HOME:-/opt/ComfyUI}"
DATA_DIR="${DATA_DIR:-/workspace}"
COMFY_DATA="${DATA_DIR}/ComfyUI"
CRED_FILE="${DATA_DIR}/.credentials"
LOG_DIR=/var/log/services

log()  { printf '\033[36m[init]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[init]\033[0m %s\n' "$*" >&2; }

mkdir -p "${DATA_DIR}" "${LOG_DIR}" "${DATA_DIR}/.cache" "${DATA_DIR}/notebooks"

# ---------------------------------------------------------------------------
# 1. Persist ComfyUI state on the instance disk (/workspace) via symlinks so
#    models survive restarts and are reachable from JupyterLab.
# ---------------------------------------------------------------------------
log "preparing persistent storage under ${COMFY_DATA}"
for d in models output input user custom_nodes; do
    src="${COMFY_HOME}/${d}"
    dst="${COMFY_DATA}/${d}"
    if [[ ! -d "${dst}" ]]; then
        mkdir -p "${dst}"
        if [[ -d "${src}" && ! -L "${src}" ]]; then
            cp -a "${src}/." "${dst}/" 2>/dev/null || true
        fi
    fi
    rm -rf "${src}"
    ln -sfn "${dst}" "${src}"
done

# Model sub-folders ComfyUI + the dashboard expect to exist.
for d in checkpoints diffusion_models text_encoders clip clip_vision vae loras \
         controlnet upscale_models embeddings style_models ipadapter unet \
         model_patches audio_encoders hypernetworks gligen photomaker vae_approx \
         diffusers configs; do
    mkdir -p "${COMFY_DATA}/models/${d}"
done

# ---------------------------------------------------------------------------
# 2. Tokens - reused across reboots so bookmarked URLs keep working.
# ---------------------------------------------------------------------------
gen_token() { head -c 18 /dev/urandom | od -An -tx1 | tr -d ' \n'; }

if [[ -f "${CRED_FILE}" ]]; then
    # shellcheck disable=SC1090
    source "${CRED_FILE}"
fi

DASHBOARD_TOKEN="${DASHBOARD_TOKEN:-${SAVED_DASHBOARD_TOKEN:-${OPEN_BUTTON_TOKEN:-}}}"
JUPYTER_TOKEN="${JUPYTER_TOKEN:-${SAVED_JUPYTER_TOKEN:-${OPEN_BUTTON_TOKEN:-}}}"
if [[ -z "${DASHBOARD_TOKEN}" ]]; then DASHBOARD_TOKEN="$(gen_token)"; fi
if [[ -z "${JUPYTER_TOKEN}"  ]]; then JUPYTER_TOKEN="$(gen_token)"; fi

cat > "${CRED_FILE}" <<EOF
SAVED_DASHBOARD_TOKEN=${DASHBOARD_TOKEN}
SAVED_JUPYTER_TOKEN=${JUPYTER_TOKEN}
EOF
chmod 600 "${CRED_FILE}"
export DASHBOARD_TOKEN JUPYTER_TOKEN

# Seed API keys from template env vars (optional convenience).
if [[ -n "${CIVITAI_TOKEN:-}${HF_TOKEN:-}" ]]; then
    python3 - <<'PYEOF' || warn "could not seed API keys"
import json, os, pathlib
p = pathlib.Path(os.environ.get("DATA_DIR", "/workspace")) / ".config" / "modelhub"
p.mkdir(parents=True, exist_ok=True)
f = p / "keys.json"
keys = json.loads(f.read_text()) if f.exists() else {}
if os.environ.get("CIVITAI_TOKEN"):
    keys.setdefault("civitai", os.environ["CIVITAI_TOKEN"])
if os.environ.get("HF_TOKEN"):
    keys.setdefault("huggingface", os.environ["HF_TOKEN"])
f.write_text(json.dumps(keys, indent=2))
f.chmod(0o600)
PYEOF
fi

# ---------------------------------------------------------------------------
# 3. Optional SSH (only when the template supplies a public key)
# ---------------------------------------------------------------------------
PUBKEY="${PUBLIC_KEY:-${SSH_PUBLIC_KEY:-}}"
if [[ -n "${PUBKEY}" ]]; then
    mkdir -p /root/.ssh && chmod 700 /root/.ssh
    grep -qxF "${PUBKEY}" /root/.ssh/authorized_keys 2>/dev/null \
        || echo "${PUBKEY}" >> /root/.ssh/authorized_keys
    chmod 600 /root/.ssh/authorized_keys
    ssh-keygen -A >/dev/null 2>&1 || true
    export ENABLE_SSHD=1
    log "SSH public key installed"
fi

# ---------------------------------------------------------------------------
# 4. Optional user provisioning script (Vast convention)
# ---------------------------------------------------------------------------
if [[ -n "${PROVISIONING_SCRIPT:-}" ]]; then
    log "fetching PROVISIONING_SCRIPT -> ${PROVISIONING_SCRIPT}"
    if curl -fsSL "${PROVISIONING_SCRIPT}" -o /tmp/provisioning.sh; then
        chmod +x /tmp/provisioning.sh
        ( bash /tmp/provisioning.sh 2>&1 | tee -a "${LOG_DIR}/provisioning.log" ) &
    else
        warn "failed to download provisioning script"
    fi
fi

# ---------------------------------------------------------------------------
# 5. Banner
# ---------------------------------------------------------------------------
PUB_IP="${PUBLIC_IPADDR:-<instance-ip>}"
p_comfy="${VAST_TCP_PORT_8188:-8188}"
p_dash="${VAST_TCP_PORT_8189:-8189}"
p_jup="${VAST_TCP_PORT_8888:-8888}"

cat <<EOF

================================================================================
  ComfyUI + Model Dashboard + JupyterLab
--------------------------------------------------------------------------------
  ComfyUI     http://${PUB_IP}:${p_comfy}
  Dashboard   http://${PUB_IP}:${p_dash}/?token=${DASHBOARD_TOKEN}
  JupyterLab  http://${PUB_IP}:${p_jup}/lab?token=${JUPYTER_TOKEN}

  DASHBOARD_TOKEN = ${DASHBOARD_TOKEN}
  JUPYTER_TOKEN   = ${JUPYTER_TOKEN}
  Data dir        = ${COMFY_DATA}
  Auto-install    = ${AUTO_INSTALL:-krea2-turbo}
================================================================================

EOF

nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv 2>/dev/null \
    || warn "nvidia-smi unavailable - is the instance GPU-enabled?"

log "starting supervisord"
exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf
