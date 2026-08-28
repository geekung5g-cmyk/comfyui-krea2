"""Background download queue.

Uses aria2c (16 parallel connections, resumable) when available and falls back
to a plain streaming HTTP download. Progress is measured by stat()-ing the file
on disk, which works identically for both backends.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import threading
import time
import uuid
from collections import OrderedDict

from core import MAX_PARALLEL, human, resolve_target

ARIA2 = shutil.which("aria2c")


class Job:
    __slots__ = ("id", "url", "folder", "filename", "total", "downloaded", "status",
                 "error", "speed", "eta", "created", "started", "finished",
                 "source", "title", "_proc", "_cancel", "path")

    def __init__(self, url, folder, filename, total=0, source="", title=""):
        self.id = uuid.uuid4().hex[:12]
        self.url = url
        self.folder = folder
        self.filename = filename
        self.total = int(total or 0)
        self.downloaded = 0
        self.status = "queued"          # queued|downloading|done|error|canceled
        self.error = ""
        self.speed = 0.0
        self.eta = 0
        self.created = time.time()
        self.started = 0.0
        self.finished = 0.0
        self.source = source
        self.title = title or filename
        self.path = ""
        self._proc = None
        self._cancel = False

    def as_dict(self) -> dict:
        pct = (self.downloaded / self.total * 100) if self.total else 0.0
        return {
            "id": self.id,
            "url": self.url,
            "folder": self.folder,
            "filename": self.filename,
            "title": self.title,
            "source": self.source,
            "status": self.status,
            "error": self.error,
            "total": self.total,
            "total_h": human(self.total) if self.total else "?",
            "downloaded": self.downloaded,
            "downloaded_h": human(self.downloaded),
            "percent": round(min(pct, 100.0), 1),
            "speed_h": human(self.speed) + "/s" if self.speed else "-",
            "eta": self.eta,
            "eta_h": _fmt_eta(self.eta) if self.eta else "-",
            "created": self.created,
            "elapsed": round((self.finished or time.time()) - self.started, 1)
                       if self.started else 0,
        }


def _fmt_eta(seconds: int) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm %02ds" % (seconds // 60, seconds % 60)
    return "%dh %02dm" % (seconds // 3600, (seconds % 3600) // 60)


class DownloadManager:
    def __init__(self, concurrency: int = MAX_PARALLEL):
        self.jobs: OrderedDict[str, Job] = OrderedDict()
        self.lock = threading.Lock()
        self.sem = threading.BoundedSemaphore(max(1, concurrency))

    # ---------------------------------------------------------------- public
    def submit(self, url, folder, filename, headers=None, total=0,
               source="", title="") -> Job:
        target = resolve_target(folder, filename)
        job = Job(url, folder, target.name, total, source, title)
        job.path = str(target)
        with self.lock:
            self.jobs[job.id] = job
            while len(self.jobs) > 200:
                self.jobs.popitem(last=False)
        threading.Thread(target=self._run, args=(job, headers or {}),
                         daemon=True, name="dl-" + job.id).start()
        return job

    def list(self) -> list:
        with self.lock:
            return [j.as_dict() for j in reversed(self.jobs.values())]

    def get(self, job_id: str):
        with self.lock:
            return self.jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if not job or job.status in ("done", "error", "canceled"):
            return False
        job._cancel = True
        proc = job._proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        job.status = "canceled"
        job.finished = time.time()
        return True

    def clear_finished(self) -> int:
        with self.lock:
            gone = [k for k, j in self.jobs.items()
                    if j.status in ("done", "error", "canceled")]
            for k in gone:
                del self.jobs[k]
        return len(gone)

    def active_count(self) -> int:
        with self.lock:
            return sum(1 for j in self.jobs.values()
                       if j.status in ("queued", "downloading"))

    # ---------------------------------------------------------------- worker
    def _run(self, job: Job, headers: dict) -> None:
        with self.sem:
            if job._cancel:
                return
            job.status = "downloading"
            job.started = time.time()
            target = pathlib.Path(job.path)
            target.parent.mkdir(parents=True, exist_ok=True)
            monitor = threading.Thread(target=self._monitor, args=(job, target),
                                       daemon=True)
            monitor.start()
            try:
                if ARIA2:
                    self._aria2(job, target, headers)
                else:
                    self._httpx(job, target, headers)

                if job._cancel:
                    job.status = "canceled"
                elif target.exists() and target.stat().st_size > 0:
                    job.downloaded = target.stat().st_size
                    if job.total and job.downloaded < job.total * 0.98:
                        job.status = "error"
                        job.error = "ไฟล์ไม่ครบ (%s / %s) - ลองกดโหลดซ้ำเพื่อ resume" % (
                            human(job.downloaded), human(job.total))
                    else:
                        job.total = job.total or job.downloaded
                        job.status = "done"
                else:
                    job.status = "error"
                    job.error = job.error or "ไม่ได้ไฟล์ปลายทาง"
            except Exception as exc:                       # noqa: BLE001
                job.status = "canceled" if job._cancel else "error"
                job.error = str(exc)[:500]
            finally:
                job.finished = time.time()
                job.speed = 0.0
                job.eta = 0

    def _monitor(self, job: Job, target: pathlib.Path) -> None:
        last_size, last_t = 0, time.time()
        while job.status == "downloading":
            time.sleep(1.0)
            try:
                size = target.stat().st_size
            except OSError:
                part = target.with_suffix(target.suffix + ".part")
                try:
                    size = part.stat().st_size
                except OSError:
                    size = 0
            now = time.time()
            dt = now - last_t
            if dt > 0:
                inst = (size - last_size) / dt
                job.speed = inst if job.speed == 0 else job.speed * 0.6 + inst * 0.4
            job.downloaded = size
            if job.total and job.speed > 0:
                job.eta = int(max(job.total - size, 0) / job.speed)
            last_size, last_t = size, now

    # ---------------------------------------------------------------- backends
    def _aria2(self, job: Job, target: pathlib.Path, headers: dict) -> None:
        cmd = [
            ARIA2, job.url,
            "--dir", str(target.parent),
            "--out", target.name,
            "--continue=true",
            "--max-connection-per-server=16",
            "--split=16",
            "--min-split-size=8M",
            "--max-tries=5",
            "--retry-wait=5",
            "--timeout=60",
            "--connect-timeout=30",
            "--auto-file-renaming=false",
            "--allow-overwrite=true",
            "--check-certificate=true",
            "--console-log-level=warn",
            "--summary-interval=0",
            "--file-allocation=none",
        ]
        for k, v in headers.items():
            cmd += ["--header", "%s: %s" % (k, v)]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                errors="replace")
        job._proc = proc
        tail = []
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                tail.append(line)
                del tail[:-15]
        rc = proc.wait()
        job._proc = None
        if rc != 0 and not job._cancel:
            raise RuntimeError("aria2c exit %d\n%s" % (rc, "\n".join(tail[-6:])))

    def _httpx(self, job: Job, target: pathlib.Path, headers: dict) -> None:
        import httpx

        part = target.with_suffix(target.suffix + ".part")
        pos = part.stat().st_size if part.exists() else 0
        hdrs = dict(headers)
        if pos:
            hdrs["Range"] = "bytes=%d-" % pos

        with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(None, connect=30)) as c:
            with c.stream("GET", job.url, headers=hdrs) as r:
                if r.status_code == 416:
                    pos = 0
                    part.unlink(missing_ok=True)
                    raise RuntimeError("ช่วงไฟล์ไม่ถูกต้อง ลองใหม่อีกครั้ง")
                if r.status_code >= 400:
                    raise RuntimeError("HTTP %d จากเซิร์ฟเวอร์ต้นทาง" % r.status_code)
                if r.status_code == 200:
                    pos = 0
                if not job.total:
                    cl = r.headers.get("content-length")
                    if cl:
                        job.total = int(cl) + pos
                mode = "ab" if pos else "wb"
                with open(part, mode) as fh:
                    for chunk in r.iter_bytes(chunk_size=1024 * 1024):
                        if job._cancel:
                            raise RuntimeError("canceled")
                        fh.write(chunk)
        os.replace(part, target)


manager = DownloadManager()
