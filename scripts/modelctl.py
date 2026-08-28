#!/opt/venv/bin/python
"""modelctl - command line front-end for the Model Dashboard.

Everything goes through the dashboard API on localhost, so downloads started
here show up in the web UI queue (and vice versa).

  modelctl tokens
  modelctl get "https://civitai.com/models/1234?modelVersionId=5678"
  modelctl get Comfy-Org/Krea-2:loras/krea2_neondrip.safetensors
  modelctl get <url> --folder loras --name my_lora.safetensors --all
  modelctl install krea2-turbo krea2-styles
  modelctl catalog
  modelctl jobs [--watch]
  modelctl list [loras]
  modelctl key civitai <API_KEY>
  modelctl key huggingface hf_xxx
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

PORT = os.environ.get("DASHBOARD_PORT", "8189")
BASE = "http://127.0.0.1:%s" % PORT


def _token() -> str:
    tok = os.environ.get("DASHBOARD_TOKEN", "")
    if tok:
        return tok
    path = os.path.join(os.environ.get("DATA_DIR", "/workspace"), ".credentials")
    try:
        for line in open(path):
            if line.startswith("SAVED_DASHBOARD_TOKEN="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def call(path: str, payload=None, raw=False):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json", "X-Token": _token()},
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            msg = json.loads(body).get("detail", body)
        except Exception:
            msg = body
        sys.exit("error %d: %s" % (e.code, msg))
    except urllib.error.URLError as e:
        sys.exit("ติดต่อ dashboard ที่ %s ไม่ได้ (%s)" % (BASE, e))
    return body if raw else json.loads(body or "{}")


# ------------------------------------------------------------------ commands
def cmd_tokens(_):
    path = os.path.join(os.environ.get("DATA_DIR", "/workspace"), ".credentials")
    print(open(path).read() if os.path.exists(path) else "(no credentials file)")


def cmd_get(a):
    info = call("/api/resolve", {"url": a.url})
    print("%s  [%s]" % (info["title"], info["source"]))
    print("  %s" % info["subtitle"])
    choices = info["choices"] if a.all else info["choices"][:1]
    if a.pick is not None:
        choices = [info["choices"][a.pick]]
    for c in choices:
        folder = a.folder or c.get("folder") or info["folder"]
        name = a.name or c["filename"]
        job = call("/api/download", {
            "url": c["url"], "folder": folder, "filename": name,
            "size": c["size"], "source": info["source"], "title": info["title"],
            "overwrite": a.overwrite,
        })
        print("  -> queued %s (%s) into %s" % (name, c["size_h"], folder))
    if a.watch:
        cmd_jobs(argparse.Namespace(watch=True))


def cmd_install(a):
    res = call("/api/catalog/install", {"ids": a.ids})
    if not res["jobs"]:
        print("ไฟล์ทั้งหมดมีอยู่แล้ว")
    for j in res["jobs"]:
        print("queued %s (%s)" % (j["filename"], j["total_h"]))
    if a.watch:
        cmd_jobs(argparse.Namespace(watch=True))


def cmd_catalog(_):
    cat = call("/api/catalog")
    print("=== bundles (ใช้กับ modelctl install) ===")
    for q in cat["quick"]:
        print("  %-22s %-10s %s" % (q["id"], q["size_h"], q["name"]))
    for g in cat["groups"]:
        print("\n=== %s ===" % g["name"])
        for it in g["items"]:
            mark = "*" if it.get("installed") else " "
            print(" %s %-26s %-10s -> %s" % (mark, it["id"], it["size_h"], it["dest"]))


def cmd_jobs(a):
    while True:
        data = call("/api/jobs")
        lines = []
        for j in data["jobs"][:20]:
            lines.append("%-10s %5.1f%%  %10s/%-10s %10s  %s" % (
                j["status"], j["percent"], j["downloaded_h"], j["total_h"],
                j["speed_h"], j["filename"]))
        out = "\n".join(lines) or "(ไม่มีงาน)"
        if not getattr(a, "watch", False):
            print(out)
            return
        sys.stdout.write("\033[2J\033[H" + out + "\n")
        sys.stdout.flush()
        if data["active"] == 0:
            return
        time.sleep(2)


def cmd_list(a):
    data = call("/api/files" + ("?folder=" + a.folder if a.folder else ""))
    for f in data["files"]:
        print("%-18s %10s  %s" % (f["folder"], f["size_h"], f["rel"]))
    print("--- %d ไฟล์ รวม %s" % (data["count"], data["total_h"]))


def cmd_key(a):
    provider = {"hf": "huggingface", "civit": "civitai"}.get(a.provider, a.provider)
    call("/api/keys", {provider: a.value})
    res = call("/api/keys/test", {"provider": provider})
    print("%s: %s" % (provider, res["message"]))


def main() -> None:
    p = argparse.ArgumentParser(prog="modelctl", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("tokens").set_defaults(fn=cmd_tokens)

    g = sub.add_parser("get", help="ดาวน์โหลดจากลิงก์")
    g.add_argument("url")
    g.add_argument("--folder")
    g.add_argument("--name")
    g.add_argument("--pick", type=int, help="เลือกไฟล์ลำดับที่ (0-based)")
    g.add_argument("--all", action="store_true", help="โหลดทุกไฟล์ที่เจอ")
    g.add_argument("--overwrite", action="store_true")
    g.add_argument("--watch", action="store_true")
    g.set_defaults(fn=cmd_get)

    i = sub.add_parser("install", help="ติดตั้งจาก catalog")
    i.add_argument("ids", nargs="+")
    i.add_argument("--watch", action="store_true")
    i.set_defaults(fn=cmd_install)

    sub.add_parser("catalog").set_defaults(fn=cmd_catalog)

    j = sub.add_parser("jobs")
    j.add_argument("--watch", action="store_true")
    j.set_defaults(fn=cmd_jobs)

    l = sub.add_parser("list")
    l.add_argument("folder", nargs="?", default="")
    l.set_defaults(fn=cmd_list)

    k = sub.add_parser("key")
    k.add_argument("provider", choices=["civitai", "huggingface", "civit", "hf"])
    k.add_argument("value")
    k.set_defaults(fn=cmd_key)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
