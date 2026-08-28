"""Model Dashboard (port 8189).

Paste a Civitai / Hugging Face / direct link, pick a folder, hit download.
Also: one-click Krea 2 presets, file browser, API-key storage, service control.
"""
from __future__ import annotations

import contextlib
import os
import pathlib
import shutil
import subprocess
import time

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

import core
import resolvers
from downloader import manager

@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    _bootstrap()
    yield


app = FastAPI(title="ComfyUI Model Dashboard", docs_url=None, redoc_url=None,
              lifespan=lifespan)
STARTED = time.time()
COOKIE = "modelhub_token"
PUBLIC_PATHS = {"/healthz", "/login", "/api/login", "/favicon.ico"}


# --------------------------------------------------------------------- auth
def _token_ok(request: Request) -> bool:
    if not core.DASHBOARD_TOKEN:
        return True
    supplied = (
        request.query_params.get("token")
        or request.headers.get("x-token")
        or request.cookies.get(COOKIE)
        or ""
    )
    auth = request.headers.get("authorization", "")
    if not supplied and auth.lower().startswith("bearer "):
        supplied = auth[7:]
    return supplied == core.DASHBOARD_TOKEN


@app.middleware("http")
async def auth_gate(request: Request, call_next):
    path = request.url.path
    if path in PUBLIC_PATHS or path.startswith("/static/"):
        return await call_next(request)
    if _token_ok(request):
        response = await call_next(request)
        if request.query_params.get("token") and core.DASHBOARD_TOKEN:
            response.set_cookie(COOKIE, core.DASHBOARD_TOKEN, httponly=True,
                                samesite="lax", max_age=60 * 60 * 24 * 30)
        return response
    if path.startswith("/api/"):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return FileResponse(core.APP_DIR / "static" / "login.html", status_code=401)


# --------------------------------------------------------------------- pages
@app.get("/healthz")
def healthz():
    return {"ok": True, "uptime": round(time.time() - STARTED, 1)}


@app.get("/")
def index():
    return FileResponse(core.APP_DIR / "static" / "index.html")


@app.get("/login")
def login_page():
    return FileResponse(core.APP_DIR / "static" / "login.html")


@app.post("/api/login")
def api_login(payload: dict = Body(...)):
    token = (payload.get("token") or "").strip()
    if core.DASHBOARD_TOKEN and token != core.DASHBOARD_TOKEN:
        raise HTTPException(401, "โทเคนไม่ถูกต้อง / invalid token")
    resp = JSONResponse({"ok": True})
    resp.set_cookie(COOKIE, core.DASHBOARD_TOKEN, httponly=True,
                    samesite="lax", max_age=60 * 60 * 24 * 30)
    return resp


# --------------------------------------------------------------------- state
@app.get("/api/state")
def api_state():
    keys = core.load_keys()
    return {
        "folders": [{"id": f, "label": lbl} for f, lbl in core.MODEL_FOLDERS],
        "keys": {k: core.mask(v) for k, v in keys.items()},
        "has_keys": {k: bool(v) for k, v in keys.items()},
        "disk": core.disk_usage(),
        "gpus": core.gpu_info(),
        "urls": core.public_urls(),
        "models_dir": str(core.MODELS_DIR),
        "active_downloads": manager.active_count(),
        "aria2": bool(shutil.which("aria2c")),
        "uptime": round(time.time() - STARTED, 1),
    }


@app.post("/api/keys")
def api_keys(payload: dict = Body(...)):
    core.save_keys({
        "civitai": payload.get("civitai"),
        "huggingface": payload.get("huggingface"),
    })
    keys = core.load_keys()
    return {"ok": True, "keys": {k: core.mask(v) for k, v in keys.items()}}


@app.post("/api/keys/test")
def api_keys_test(payload: dict = Body(...)):
    """Verify a stored key against the provider's API."""
    import httpx

    provider = payload.get("provider")
    keys = core.load_keys()
    token = keys.get(provider)
    if not token:
        return {"ok": False, "message": "ยังไม่ได้บันทึกคีย์"}
    try:
        if provider == "civitai":
            r = httpx.get("https://civitai.com/api/v1/models", timeout=20,
                          params={"limit": 1},
                          headers={"Authorization": "Bearer " + token})
            ok = r.status_code < 400
            return {"ok": ok, "message": "ใช้งานได้" if ok else "HTTP %d" % r.status_code}
        r = httpx.get("https://huggingface.co/api/whoami-v2", timeout=20,
                      headers={"Authorization": "Bearer " + token})
        if r.status_code < 400:
            return {"ok": True, "message": "ใช้งานได้ (%s)" % r.json().get("name", "")}
        return {"ok": False, "message": "HTTP %d" % r.status_code}
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "message": str(exc)[:200]}


# --------------------------------------------------------------------- downloads
@app.post("/api/resolve")
def api_resolve(payload: dict = Body(...)):
    try:
        return resolvers.resolve(payload.get("url", ""), core.load_keys())
    except resolvers.ResolveError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:                                   # noqa: BLE001
        raise HTTPException(500, "resolve ล้มเหลว: %s" % str(exc)[:300])


@app.post("/api/download")
def api_download(payload: dict = Body(...)):
    url = (payload.get("url") or "").strip()
    folder = (payload.get("folder") or "").strip()
    filename = (payload.get("filename") or "").strip()
    if not url or not folder or not filename:
        raise HTTPException(400, "ต้องมี url, folder และ filename")
    if folder not in core.VALID_FOLDERS:
        raise HTTPException(400, "โฟลเดอร์ไม่ถูกต้อง: %s" % folder)

    keys = core.load_keys()
    if payload.get("overwrite") is not True:
        target = core.resolve_target(folder, filename)
        if target.exists() and target.stat().st_size > 0:
            raise HTTPException(409, "มีไฟล์ %s อยู่แล้ว (ติ๊ก overwrite ถ้าจะโหลดทับ)" % target.name)

    job = manager.submit(
        url=url,
        folder=folder,
        filename=filename,
        headers=resolvers.auth_headers(url, keys),
        total=int(payload.get("size") or 0),
        source=payload.get("source", ""),
        title=payload.get("title", "") or filename,
    )
    return {"ok": True, "job": job.as_dict()}


@app.get("/api/jobs")
def api_jobs():
    return {"jobs": manager.list(), "active": manager.active_count()}


@app.post("/api/jobs/{job_id}/cancel")
def api_cancel(job_id: str):
    return {"ok": manager.cancel(job_id)}


@app.post("/api/jobs/clear")
def api_clear():
    return {"ok": True, "removed": manager.clear_finished()}


# --------------------------------------------------------------------- catalog
@app.get("/api/catalog")
def api_catalog():
    catalog = core.load_catalog()
    for group in catalog.get("groups", []):
        for item in group.get("items", []):
            try:
                target = core.resolve_target(item["dest"], item["filename"])
                item["installed"] = target.exists() and target.stat().st_size > 0
            except Exception:                                  # noqa: BLE001
                item["installed"] = False
    return catalog


@app.post("/api/catalog/install")
def api_catalog_install(payload: dict = Body(...)):
    ids = payload.get("ids") or ([payload["id"]] if payload.get("id") else [])
    if not ids:
        raise HTTPException(400, "ต้องระบุ id")
    return {"ok": True, "jobs": _install_catalog_ids(ids)}


def _install_catalog_ids(ids) -> list:
    catalog = core.load_catalog()
    by_id = {}
    for group in catalog.get("groups", []):
        for item in group.get("items", []):
            by_id[item["id"]] = item
    bundles = catalog.get("bundles", {})

    wanted = []
    for i in ids:
        wanted.extend(bundles.get(i, [i]))

    keys = core.load_keys()
    started = []
    for item_id in dict.fromkeys(wanted):
        item = by_id.get(item_id)
        if not item:
            continue
        try:
            target = core.resolve_target(item["dest"], item["filename"])
            if target.exists() and target.stat().st_size > 0:
                continue
            job = manager.submit(
                url=item["url"], folder=item["dest"], filename=item["filename"],
                headers=resolvers.auth_headers(item["url"], keys),
                total=int(item.get("bytes") or 0),
                source=item.get("source", "huggingface"), title=item["name"],
            )
            started.append(job.as_dict())
        except Exception as exc:                               # noqa: BLE001
            print("[catalog] %s failed: %s" % (item_id, exc), flush=True)
    return started


# --------------------------------------------------------------------- files
@app.get("/api/files")
def api_files(folder: str = ""):
    out = []
    folders = [folder] if folder and folder in core.VALID_FOLDERS else \
        [f for f, _ in core.MODEL_FOLDERS]
    for name in folders:
        d = core.MODELS_DIR / name
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if not p.is_file() or p.name.startswith("."):
                continue
            if p.suffix in (".part", ".aria2", ".md", ".txt", ".json"):
                continue
            st = p.stat()
            out.append({
                "folder": name,
                "name": p.name,
                "rel": str(p.relative_to(d)).replace("\\", "/"),
                "size": st.st_size,
                "size_h": core.human(st.st_size),
                "mtime": st.st_mtime,
            })
    out.sort(key=lambda x: -x["mtime"])
    return {"files": out, "count": len(out),
            "total_h": core.human(sum(f["size"] for f in out))}


@app.post("/api/files/delete")
def api_files_delete(payload: dict = Body(...)):
    folder = payload.get("folder", "")
    rel = payload.get("rel") or payload.get("name") or ""
    if folder not in core.VALID_FOLDERS or not rel:
        raise HTTPException(400, "พารามิเตอร์ไม่ถูกต้อง")
    root = (core.MODELS_DIR / folder).resolve()
    target = (root / rel).resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(400, "ไฟล์ไม่ถูกต้อง")
    size = target.stat().st_size
    target.unlink()
    return {"ok": True, "freed": size, "freed_h": core.human(size)}


# --------------------------------------------------------------------- services
@app.get("/api/logs/{service}")
def api_logs(service: str, lines: int = 200):
    allowed = {"comfyui", "dashboard", "jupyter", "provisioning", "supervisord"}
    if service not in allowed:
        raise HTTPException(400, "unknown service")
    path = core.LOG_DIR / ("%s.log" % service)
    if not path.exists():
        return PlainTextResponse("(ยังไม่มี log)")
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - 256_000))
            data = fh.read().decode("utf-8", "replace")
        return PlainTextResponse("\n".join(data.splitlines()[-max(10, min(lines, 2000)):]))
    except Exception as exc:                                   # noqa: BLE001
        return PlainTextResponse("อ่าน log ไม่ได้: %s" % exc)


@app.post("/api/service/{service}/restart")
def api_restart(service: str):
    if service not in {"comfyui", "jupyter"}:
        raise HTTPException(400, "restart ได้เฉพาะ comfyui / jupyter")
    try:
        r = subprocess.run(["supervisorctl", "-c", "/etc/supervisor/supervisord.conf",
                            "restart", service],
                           capture_output=True, text=True, timeout=60)
        return {"ok": r.returncode == 0, "output": (r.stdout + r.stderr).strip()}
    except Exception as exc:                                   # noqa: BLE001
        raise HTTPException(500, str(exc))


@app.get("/api/comfy/status")
def api_comfy_status():
    import httpx

    port = os.environ.get("COMFYUI_PORT", "8188")
    try:
        r = httpx.get("http://127.0.0.1:%s/system_stats" % port, timeout=4)
        return {"up": r.status_code < 400, "stats": r.json() if r.status_code < 400 else None}
    except Exception:
        return {"up": False, "stats": None}


# --------------------------------------------------------------------- startup
def _bootstrap() -> None:
    core.ensure_dirs()
    auto = os.environ.get("AUTO_INSTALL", "krea2-turbo").strip()
    state = core.load_state()
    if auto and auto.lower() not in ("none", "off", "0", "false") \
            and not state.get("auto_install_done"):
        ids = [x.strip() for x in auto.split(",") if x.strip()]
        print("[dashboard] auto-install: %s" % ids, flush=True)
        try:
            _install_catalog_ids(ids)
            state["auto_install_done"] = True
            state["auto_install_ids"] = ids
            core.save_state(state)
        except Exception as exc:                               # noqa: BLE001
            print("[dashboard] auto-install failed: %s" % exc, flush=True)

    pathlib.Path(core.LOG_DIR).mkdir(parents=True, exist_ok=True)
    print("[dashboard] ready on :%s" % os.environ.get("DASHBOARD_PORT", "8189"),
          flush=True)
