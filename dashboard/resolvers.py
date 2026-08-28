"""Turn a pasted link into a concrete download job.

Supported inputs
----------------
Civitai   https://civitai.com/models/1234                    (latest version)
          https://civitai.com/models/1234?modelVersionId=567
          https://civitai.com/api/download/models/567
          urn:air:sdxl:lora:civitai:1234@567
HF        https://huggingface.co/Comfy-Org/Krea-2
          https://huggingface.co/Comfy-Org/Krea-2/blob/main/loras/krea2_neondrip.safetensors
          https://huggingface.co/Comfy-Org/Krea-2/resolve/main/vae/qwen_image_vae.safetensors
          Comfy-Org/Krea-2                 (repo shorthand -> file picker)
          Comfy-Org/Krea-2:vae/qwen_image_vae.safetensors
Direct    any other http(s) URL
"""
from __future__ import annotations

import posixpath
import re
import urllib.parse

import httpx

from core import CIVITAI_TYPE_MAP, HF_PREFIX_MAP, human, safe_name

CIVITAI_API = "https://civitai.com/api/v1"
HF_API = "https://huggingface.co/api"
TIMEOUT = httpx.Timeout(30.0, connect=15.0)

WEIGHT_EXT = (".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf",
              ".sft", ".onnx", ".pkl")

AIR_RE = re.compile(r"^urn:air:[^:]*:([^:]*):civitai:(\d+)(?:@(\d+))?", re.I)
REPO_RE = re.compile(r"^[A-Za-z0-9][\w.\-]*/[\w.\-]+$")


class ResolveError(Exception):
    pass


# --------------------------------------------------------------- helpers
def _guess_folder_from_name(name: str) -> str:
    low = name.lower()
    for needle, folder in (
        ("vae", "vae"), ("lora", "loras"), ("lycoris", "loras"), ("locon", "loras"),
        ("controlnet", "controlnet"), ("control_", "controlnet"),
        ("upscal", "upscale_models"), ("esrgan", "upscale_models"),
        ("ultrasharp", "upscale_models"), ("nmkd", "upscale_models"),
        ("swinir", "upscale_models"), ("4x", "upscale_models"), ("2x", "upscale_models"),
        ("clip_vision", "clip_vision"), ("clipvision", "clip_vision"),
        ("text_encoder", "text_encoders"), ("t5", "text_encoders"),
        ("qwen3vl", "text_encoders"), ("umt5", "text_encoders"), ("clip", "text_encoders"),
        ("embedding", "embeddings"), ("ipadapter", "ipadapter"),
    ):
        if needle in low:
            return folder
    # .pth without other hints is almost always an ESRGAN-family upscaler
    if low.endswith(".pth"):
        return "upscale_models"
    return "checkpoints"


def _folder_from_hf_path(path: str, filename: str) -> str:
    parts = [p for p in path.split("/") if p]
    for part in parts[:-1]:
        mapped = HF_PREFIX_MAP.get(part.lower())
        if mapped:
            return mapped
    return _guess_folder_from_name(filename)


def _client(headers: dict | None = None) -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, follow_redirects=True,
                        headers=headers or {})


def _head_size(url: str, headers: dict) -> int:
    """Best-effort content length; 0 when the server will not say."""
    try:
        with _client(headers) as c:
            r = c.head(url)
            if r.status_code >= 400:
                r = c.get(url, headers={**headers, "Range": "bytes=0-0"})
            if "x-linked-size" in r.headers:
                return int(r.headers["x-linked-size"])
            if "content-range" in r.headers:
                return int(r.headers["content-range"].split("/")[-1])
            if "content-length" in r.headers:
                return int(r.headers["content-length"])
    except Exception:
        pass
    return 0


# --------------------------------------------------------------- civitai
def _civitai_ids(url: str):
    """Return (model_id, version_id); either may be None."""
    air = AIR_RE.match(url.strip())
    if air:
        return int(air.group(2)), (int(air.group(3)) if air.group(3) else None)

    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    version_id = int(qs["modelVersionId"][0]) if "modelVersionId" in qs else None

    m = re.search(r"/api/download/models/(\d+)", parsed.path)
    if m:
        return None, int(m.group(1))
    m = re.search(r"/model-versions/(\d+)", parsed.path)
    if m:
        return None, int(m.group(1))
    m = re.search(r"/models/(\d+)", parsed.path)
    if m:
        return int(m.group(1)), version_id
    if version_id:
        return None, version_id
    raise ResolveError("อ่านหมายเลขโมเดลจากลิงก์ Civitai ไม่ได้ / cannot read Civitai model id")


def resolve_civitai(url: str, token) -> dict:
    model_id, version_id = _civitai_ids(url)
    headers = {"User-Agent": "comfyui-modelhub/1.0"}
    if token:
        headers["Authorization"] = "Bearer " + token

    with _client(headers) as c:
        if version_id is None:
            r = c.get(CIVITAI_API + "/models/" + str(model_id))
            if r.status_code == 401:
                raise ResolveError("Civitai ต้องใช้ API key (ใส่ในแท็บ API Keys)")
            if r.status_code >= 400:
                raise ResolveError("Civitai API %s: %s" % (r.status_code, r.text[:200]))
            versions = r.json().get("modelVersions") or []
            if not versions:
                raise ResolveError("โมเดลนี้ไม่มีเวอร์ชันให้โหลด")
            version_id = versions[0]["id"]

        r = c.get(CIVITAI_API + "/model-versions/" + str(version_id))
        if r.status_code == 401:
            raise ResolveError("Civitai ต้องใช้ API key (ใส่ในแท็บ API Keys)")
        if r.status_code == 404:
            raise ResolveError("ไม่พบ model version %s บน Civitai" % version_id)
        if r.status_code >= 400:
            raise ResolveError("Civitai API %s: %s" % (r.status_code, r.text[:200]))
        ver = r.json()

    files = ver.get("files") or []
    if not files:
        raise ResolveError("เวอร์ชันนี้ไม่มีไฟล์ให้ดาวน์โหลด")

    def rank(f):
        return (
            0 if f.get("primary") else 1,
            0 if f.get("type") in ("Model", "Pruned Model") else 1,
            0 if str(f.get("name", "")).endswith(".safetensors") else 1,
        )

    files = sorted(files, key=rank)
    model = ver.get("model") or {}
    folder = CIVITAI_TYPE_MAP.get(model.get("type", ""), "loras")

    preview = ""
    for img in (ver.get("images") or []):
        if img.get("type", "image") == "image" and img.get("url"):
            preview = img["url"]
            break

    choices = []
    for f in files:
        size = int((f.get("sizeKB") or 0) * 1024)
        meta = f.get("metadata") or {}
        note = " ".join(str(x) for x in (f.get("type"), meta.get("fp"), meta.get("size")) if x)
        choices.append({
            "filename": safe_name(f.get("name") or "model.safetensors"),
            "url": f.get("downloadUrl"),
            "size": size,
            "size_h": human(size),
            "note": note,
            "folder": folder,
        })

    return {
        "source": "civitai",
        "title": ("%s - %s" % (model.get("name", "Civitai model"), ver.get("name", ""))).strip(" -"),
        "subtitle": "%s | base: %s | version #%s" % (
            model.get("type", "?"), ver.get("baseModel", "?"), version_id),
        "folder": folder,
        "preview": preview,
        "page": "https://civitai.com/models/%s?modelVersionId=%s" % (
            ver.get("modelId", model_id or ""), version_id),
        "needs_key": True,
        "trigger_words": ver.get("trainedWords") or [],
        "choices": choices,
    }


# --------------------------------------------------------------- hugging face
def _parse_hf(url: str):
    """Return (repo, revision, path). Empty path means 'whole repo'."""
    raw = url.strip()

    if REPO_RE.match(raw):
        return raw, "main", ""
    if ":" in raw and not raw.lower().startswith("http"):
        head, _, tail = raw.partition(":")
        if REPO_RE.match(head):
            return head, "main", tail.strip("/")

    parsed = urllib.parse.urlparse(raw)
    parts = [p for p in parsed.path.split("/") if p]
    if parts and parts[0] == "datasets":
        raise ResolveError("รองรับเฉพาะ model repo ยังไม่รองรับ datasets")
    if len(parts) < 2:
        raise ResolveError("ลิงก์ Hugging Face ไม่ถูกต้อง")

    repo = parts[0] + "/" + parts[1]
    if len(parts) >= 4 and parts[2] in ("blob", "resolve", "tree"):
        return repo, parts[3], "/".join(parts[4:])
    return repo, "main", ""


def resolve_hf(url: str, token) -> dict:
    repo, revision, path = _parse_hf(url)
    headers = {"User-Agent": "comfyui-modelhub/1.0"}
    if token:
        headers["Authorization"] = "Bearer " + token

    with _client(headers) as c:
        info = c.get(HF_API + "/models/" + repo, params={"revision": revision})
        if info.status_code in (401, 403):
            raise ResolveError(
                "เข้าถึง '%s' ไม่ได้ - อาจพิมพ์ชื่อ repo ผิด หรือเป็น gated/private "
                "ถ้า gated ให้ใส่ Hugging Face token ในแท็บ API Keys "
                "และกด Accept license บนหน้าเว็บก่อน" % repo)
        if info.status_code == 404:
            raise ResolveError("ไม่พบ repo '%s' บน Hugging Face" % repo)
        if info.status_code >= 400:
            raise ResolveError("HF API %s: %s" % (info.status_code, info.text[:200]))
        meta = info.json()

        sizes = {}
        try:
            tree = c.get(HF_API + "/models/%s/tree/%s" % (repo, revision),
                         params={"recursive": "true"})
            if tree.status_code < 400:
                for node in tree.json():
                    if node.get("type") == "file":
                        lfs = node.get("lfs") or {}
                        sizes[node["path"]] = int(lfs.get("size") or node.get("size") or 0)
        except Exception:
            pass

    siblings = [s["rfilename"] for s in (meta.get("siblings") or [])]
    if path:
        if siblings and path not in siblings and path not in sizes:
            raise ResolveError("ไม่พบไฟล์ '%s' ใน %s" % (path, repo))
        candidates = [path]
    else:
        candidates = [f for f in siblings if f.lower().endswith(WEIGHT_EXT)]
        if not candidates:
            raise ResolveError("%s ไม่มีไฟล์น้ำหนักโมเดล (.safetensors/.gguf/...)" % repo)
        candidates.sort(key=lambda f: (-sizes.get(f, 0), f))

    choices = []
    for p in candidates[:300]:
        size = sizes.get(p, 0)
        choices.append({
            "filename": safe_name(posixpath.basename(p)),
            "url": "https://huggingface.co/%s/resolve/%s/%s?download=true" % (
                repo, revision, urllib.parse.quote(p)),
            "size": size,
            "size_h": human(size) if size else "?",
            "note": p,
            "folder": _folder_from_hf_path(p, posixpath.basename(p)),
        })

    subtitle = "revision %s | %d ไฟล์ที่โหลดได้" % (revision, len(choices))
    if meta.get("pipeline_tag"):
        subtitle += " | " + str(meta["pipeline_tag"])

    return {
        "source": "huggingface",
        "title": repo,
        "subtitle": subtitle,
        "folder": choices[0].get("folder", "checkpoints"),
        "preview": "",
        "page": "https://huggingface.co/" + repo,
        "needs_key": bool(meta.get("gated")),
        "trigger_words": [],
        "choices": choices,
    }


# --------------------------------------------------------------- direct
def resolve_direct(url: str) -> dict:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ResolveError("รองรับเฉพาะลิงก์ http/https")
    base = urllib.parse.unquote(posixpath.basename(parsed.path))
    name = safe_name(base or "model.safetensors")
    size = _head_size(url, {"User-Agent": "comfyui-modelhub/1.0"})
    folder = _guess_folder_from_name(name)
    return {
        "source": "direct",
        "title": name,
        "subtitle": parsed.netloc,
        "folder": folder,
        "preview": "",
        "page": url,
        "needs_key": False,
        "trigger_words": [],
        "choices": [{
            "filename": name,
            "url": url,
            "size": size,
            "size_h": human(size) if size else "?",
            "note": "direct link",
            "folder": folder,
        }],
    }


def resolve(url: str, keys: dict) -> dict:
    url = (url or "").strip()
    if not url:
        raise ResolveError("กรุณาวางลิงก์")

    low = url.lower()
    if low.startswith("urn:air:") or "civitai.com" in low:
        return resolve_civitai(url, keys.get("civitai"))

    looks_like_repo = bool(REPO_RE.match(url))
    if not looks_like_repo and ":" in url and not low.startswith("http"):
        looks_like_repo = bool(REPO_RE.match(url.split(":", 1)[0]))

    if "huggingface.co" in low or "hf.co/" in low or looks_like_repo:
        return resolve_hf(url, keys.get("huggingface"))
    return resolve_direct(url)


def auth_headers(url: str, keys: dict) -> dict:
    """Headers the downloader must send for this URL."""
    low = url.lower()
    headers = {"User-Agent": "comfyui-modelhub/1.0"}
    if "civitai.com" in low and keys.get("civitai"):
        headers["Authorization"] = "Bearer " + keys["civitai"]
    elif ("huggingface.co" in low or "hf.co/" in low) and keys.get("huggingface"):
        headers["Authorization"] = "Bearer " + keys["huggingface"]
    return headers
