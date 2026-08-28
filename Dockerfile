# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Vast.ai template : ComfyUI (8188) + Model Dashboard (8189) + JupyterLab (8888)
# Tuned for Krea 2 / Krea 2 Turbo on Blackwell (RTX 5090) and Ada GPUs.
# ---------------------------------------------------------------------------
ARG CUDA_IMAGE=nvidia/cuda:12.9.1-cudnn-runtime-ubuntu24.04
FROM ${CUDA_IMAGE}

# cu129 works on any host driver reporting CUDA >= 12.9 (incl. CUDA 13 hosts).
# Build with --build-arg TORCH_CHANNEL=cu128 for wider host coverage,
# or cu130 if you only rent CUDA 13 machines.
ARG TORCH_CHANNEL=cu129
ARG TORCH_VERSION=2.13.0
ARG COMFYUI_REF=master

LABEL org.opencontainers.image.title="comfyui-krea2-vast" \
      org.opencontainers.image.description="ComfyUI + model download dashboard + JupyterLab for Vast.ai" \
      org.opencontainers.image.source="https://github.com/comfyanonymous/ComfyUI"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LANG=C.UTF-8 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin \
    COMFY_HOME=/opt/ComfyUI \
    DASHBOARD_HOME=/opt/dashboard \
    DATA_DIR=/workspace \
    COMFYUI_PORT=8188 \
    DASHBOARD_PORT=8189 \
    JUPYTER_PORT=8888

# --- system packages ------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python3-dev \
        build-essential pkg-config \
        git git-lfs curl wget aria2 ca-certificates gnupg \
        ffmpeg libgl1 libglib2.0-0 libsm6 libxext6 \
        supervisor tini openssh-server rsync unzip zip nano vim tmux htop jq \
    && rm -rf /var/lib/apt/lists/* \
    && git lfs install --system --skip-repo

# --- python venv + pytorch ------------------------------------------------
RUN python3 -m venv ${VIRTUAL_ENV} \
    && pip install --upgrade pip wheel setuptools

RUN pip install \
        --index-url https://download.pytorch.org/whl/${TORCH_CHANNEL} \
        --extra-index-url https://pypi.org/simple \
        "torch==${TORCH_VERSION}" torchvision torchaudio \
    && python -c "import torch; print('torch', torch.__version__, 'cuda', torch.version.cuda)"

# --- ComfyUI --------------------------------------------------------------
RUN git clone --depth 1 --branch ${COMFYUI_REF} https://github.com/comfyanonymous/ComfyUI.git ${COMFY_HOME} \
    && pip install -r ${COMFY_HOME}/requirements.txt

# --- ComfyUI-Manager (required) -------------------------------------------
RUN git clone --depth 1 https://github.com/Comfy-Org/ComfyUI-Manager.git ${COMFY_HOME}/custom_nodes/comfyui-manager \
    && pip install -r ${COMFY_HOME}/custom_nodes/comfyui-manager/requirements.txt

# --- Crystools resource monitor (nice to have, never fails the build) ------
RUN git clone --depth 1 https://github.com/crystian/ComfyUI-Crystools.git \
        ${COMFY_HOME}/custom_nodes/comfyui-crystools \
    && pip install -r ${COMFY_HOME}/custom_nodes/comfyui-crystools/requirements.txt \
    || { echo "crystools unavailable - skipping"; rm -rf ${COMFY_HOME}/custom_nodes/comfyui-crystools; }

# --- JupyterLab + dashboard runtime --------------------------------------
RUN pip install \
        jupyterlab notebook ipywidgets jupyterlab-lsp jupyter-server-terminals \
        fastapi "uvicorn[standard]" httpx python-multipart jinja2 \
        "huggingface_hub[hf_transfer,cli]" psutil \
        opencv-python-headless pillow-avif-plugin \
        sentencepiece protobuf accelerate safetensors einops

# --- our code -------------------------------------------------------------
COPY dashboard/ ${DASHBOARD_HOME}/
COPY supervisor/supervisord.conf /etc/supervisor/supervisord.conf
COPY scripts/ /opt/scripts/
RUN chmod +x /opt/scripts/*.sh \
    && mkdir -p /var/log/services /run/sshd \
    && ln -sf /opt/scripts/modelctl.py /usr/local/bin/modelctl \
    && chmod +x /opt/scripts/modelctl.py

WORKDIR ${DATA_DIR}
EXPOSE 8188 8189 8888 22

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=5 \
    CMD curl -fsS "http://127.0.0.1:${DASHBOARD_PORT}/healthz" || exit 1

ENTRYPOINT ["/usr/bin/tini", "-g", "--"]
CMD ["/opt/scripts/entrypoint.sh"]
