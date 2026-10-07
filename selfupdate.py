#!/usr/bin/env python3
"""
NineLives in-app self-updater.

Checks the project's GitHub releases, compares to the running version, and (on
request, desktop only) downloads the right asset for this OS and launches it:

  * Windows -> NineLives-Setup-<ver>.exe  (run the installer, then quit so it
    can replace files)
  * Linux   -> NineLives-<ver>-x86_64.AppImage  (download + mark executable;
    the user swaps it in)

Read-only checks hit the GitHub API; downloads are always an explicit user
action from the desktop app. Mirrors the hashcat updater's shape (updater.py).
"""

import os
import re
import sys
import json
import stat
import tempfile
import urllib.request

import version

REPO = "ardyn-systems/NineLives"
GH_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
UA = {"User-Agent": "NineLives-selfupdate"}


def current_version():
    return version.__version__


def _norm(v):
    return re.sub(r"[^0-9.]", "", v or "")


def _vtuple(v):
    return tuple(int(x) for x in _norm(v).split(".") if x != "")


def latest_release(timeout=20):
    """Latest published release: {version, tag, notes, url, assets[]} or None."""
    try:
        req = urllib.request.Request(GH_LATEST, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
    except Exception:  # noqa: BLE001
        return None
    return {
        "tag": d.get("tag_name", ""),
        "version": _norm(d.get("tag_name", "")),
        "notes": d.get("body", "") or "",
        "url": d.get("html_url", ""),
        "assets": [{"name": a["name"], "url": a["browser_download_url"],
                    "size": a.get("size", 0)} for a in d.get("assets", [])],
    }


def _platform_asset(assets):
    """Pick the installer/AppImage asset for the current OS."""
    names = {a["name"]: a for a in assets}
    if sys.platform.startswith("win"):
        for n, a in names.items():
            if n.lower().startswith("ninelives-setup") and n.lower().endswith(".exe"):
                return a
    elif sys.platform.startswith("linux"):
        for n, a in names.items():
            if n.lower().endswith(".appimage"):
                return a
    return None


def check():
    """Return {current, latest, available, notes, url, asset}."""
    cur = current_version()
    rel = latest_release()
    if not rel or not rel["version"]:
        return {"current": cur, "latest": "", "available": False,
                "error": "Could not reach GitHub releases."}
    available = _vtuple(rel["version"]) > _vtuple(cur)
    return {
        "current": cur, "latest": rel["version"], "available": available,
        "notes": rel["notes"], "url": rel["url"],
        "asset": _platform_asset(rel["assets"]) if available else None,
    }


def download_and_launch(asset_url, name, progress=None):
    """Download the asset; on Windows launch the installer. Returns a dict with
    the saved path and whether the app should quit for the installer."""
    import subprocess
    dest = os.path.join(tempfile.gettempdir(), name)
    req = urllib.request.Request(asset_url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        total = int(r.headers.get("Content-Length", 0))
        got = 0
        with open(dest, "wb") as fh:
            while True:
                chunk = r.read(262144)
                if not chunk:
                    break
                fh.write(chunk)
                got += len(chunk)
                if progress and total:
                    progress(f"downloading... {got * 100 // total}%")

    if sys.platform.startswith("win") and name.lower().endswith(".exe"):
        subprocess.Popen([dest], close_fds=True)   # run the installer
        return {"path": dest, "quit": True}
    # AppImage / other: mark executable and leave it for the user to swap in.
    try:
        os.chmod(dest, os.stat(dest).st_mode | stat.S_IEXEC | stat.S_IXGRP)
    except OSError:
        pass
    return {"path": dest, "quit": False}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
