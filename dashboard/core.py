"""Shared configuration, credential store and small helpers for the dashboard."""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import threading

DATA_DIR = pathlib.Path(os.environ.get("DATA_DIR", "/workspace"))
COMFY_HOME = pathlib.Path(os.environ.get("COMFY_HOME", "/opt/ComfyUI"))
MODELS_DIR = COMFY_HOME / "models"
CONFIG_DIR = DATA_DIR / ".config" / "modelhub"
KEYS_FILE = CONFIG_DIR / "keys.json"
STATE_FILE = CONFIG_DIR / "state.json"
LOG_DIR = pathlib.Path("/var/log/services")
APP_DIR = pathlib.Path(__file__).resolve().parent

DASHBOARD_TOKEN = os.environ.get("DASHBOARD_TOKEN", "")
JUPYTER_TOKEN = os.environ.get("JUPYTER_TOKEN", "")
MAX_PARALLEL = int(os.environ.get("DOWNLOAD_CONCURRENCY", "2"))

# Folders a model can be dropped into, in the order they appear in the UI.
MODEL_FOLDERS: list[tuple[str, str]] = [
    ("loras", "LoRA / LyCORIS"),
    ("checkpoints", "Checkpoint (all-in-one)"),
    ("diffusion_models", "Diffusion model / UNet (Krea 2, Flux, Qwen)"),
    ("text_encoders", "Text encoder (Qwen3-VL, T5, CLIP-L)"),
    ("vae", "VAE"),
    ("controlnet", "ControlNet"),
    ("upscale_models", "Upscaler (ESRGAN ...)"),
    ("embeddings", "Textual inversion / embedding"),
    ("clip_vision", "CLIP Vision"),
    ("style_models", "Style model / Redux"),
    ("ipadapter", "IP-Adapter"),
    ("unet", "UNet (legacy path)"),
    ("model_patches", "Model patch"),
    ("audio_encoders", "Audio encoder"),
    ("hypernetworks", "Hypernetwork"),
    ("photomaker", "PhotoMaker"),
]
VALID_FOLDERS = {name for name, _ in MODEL_FOLDERS}

# Civitai model.type -> ComfyUI folder
CIVITAI_TYPE_MAP = {
    "Checkpoint": "checkpoints",
    "LORA": "loras",
    "LoCon": "loras",
    "DoRA": "loras",
    "TextualInversion": "embeddings",
    "VAE": "vae",
    "Controlnet": "controlnet",
    "ControlNet": "controlnet",
    "Upscaler": "upscale_models",
    "Hypernetwork": "hypernetworks",
    "MotionModule": "diffusion_models",
    "AestheticGradient": "embeddings",
    "Workflows": "loras",
    "Other": "loras",
}

# Hugging Face path prefix -> ComfyUI folder (matches Comfy-Org repo layout)
HF_PREFIX_MAP = {
    "diffusion_models": "diffusion_models",
    "unet": "diffusion_models",
    "transformer": "diffusion_models",
    "text_encoders": "text_encoders",
    "text_encoder": "text_encoders",
    "clip": "text_encoders",
    "vae": "vae",
    "loras": "loras",
    "lora": "loras",
    "controlnet": "controlnet",
    "controlnets": "controlnet",
    "clip_vision": "clip_vision",
    "style_models": "style_models",
    "upscale_models": "upscale_models",
    "embeddings": "embeddings",
    "checkpoints": "checkpoints",
    "split_files": "",  # handled by the next path segment
}

_lock = threading.Lock()


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    for folder, _ in MODEL_FOLDERS:
        (MODELS_DIR / folder).mkdir(parents=True, exist_ok=True)


def load_keys() -> dict:
    try:
        return json.loads(KEYS_FILE.read_text())
    except Exception:
        return {}


def save_keys(keys: dict) -> None:
    """Store keys. None = leave alone, "" = delete, anything that merely echoes
    back the masked form we handed out = leave alone (never overwrite a real key
    with its own asterisks)."""
    with _lock:
        ensure_dirs()
        current = load_keys()
        for k, v in keys.items():
            if v is None:
                continue
            v = v.strip()
            if v == "":
                current.pop(k, None)
            elif v == mask(current.get(k)) or set(v) <= set("*"):
                continue
            else:
                current[k] = v
        KEYS_FILE.write_text(json.dumps(current, indent=2))
        try:
            KEYS_FILE.chmod(0o600)
        except OSError:
            pass


def mask(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * 8}{value[-4:]}"


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_state(state: dict) -> None:
    with _lock:
        ensure_dirs()
        STATE_FILE.write_text(json.dumps(state, indent=2))


def human(n: float | int | None) -> str:
    if not n:
        return "0 B"
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < step:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= step
    return f"{n:.2f} PB"


def safe_name(name: str) -> str:
    """Strip any directory component - downloads must stay inside the target dir."""
    name = os.path.basename(name.strip().replace("\\", "/"))
    return "".join(c for c in name if c not in '<>:"|?*') or "model.safetensors"


def resolve_target(folder: str, filename: str) -> pathlib.Path:
    if folder not in VALID_FOLDERS:
        raise ValueError(f"unknown folder: {folder}")
    target = (MODELS_DIR / folder / safe_name(filename)).resolve()
    root = (MODELS_DIR / folder).resolve()
    if root not in target.parents:
        raise ValueError("path escapes the models directory")
    return target


def disk_usage() -> dict:
    usage = shutil.disk_usage(DATA_DIR)
    return {
        "total": usage.total,
        "used": usage.used,
        "free": usage.free,
        "percent": round(usage.used / usage.total * 100, 1) if usage.total else 0,
        "total_h": human(usage.total),
        "used_h": human(usage.used),
        "free_h": human(usage.free),
    }


def gpu_info() -> list[dict]:
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=8,
        )
        gpus = []
        for line in out.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                gpus.append({
                    "name": parts[0],
                    "vram_total": f"{int(float(parts[1])) / 1024:.1f} GB",
                    "vram_used": f"{int(float(parts[2])) / 1024:.1f} GB",
                    "util": f"{parts[3]}%",
                    "temp": f"{parts[4]}C",
                })
        return gpus
    except Exception:
        return []


def public_urls() -> dict:
    """Build externally reachable URLs from the env vars Vast.ai injects."""
    ip = os.environ.get("PUBLIC_IPADDR") or os.environ.get("VAST_IP_ADDR") or ""

    def port_for(internal: str, default: str) -> str:
        return os.environ.get(f"VAST_TCP_PORT_{internal}", default)

    if not ip:
        return {"comfyui": "", "jupyter": "", "host": ""}
    return {
        "host": ip,
        "comfyui": f"http://{ip}:{port_for('8188', '8188')}",
        "jupyter": f"http://{ip}:{port_for('8888', '8888')}/lab?token={JUPYTER_TOKEN}",
    }


def load_catalog() -> dict:
    return json.loads((APP_DIR / "catalog.json").read_text(encoding="utf-8"))
