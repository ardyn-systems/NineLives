#!/usr/bin/env python3
"""
NineLives hashcat auto-updater.

Checks the latest hashcat release, compares it to the bundled copy, and (on
request) downloads and installs it into vendor/hashcat/. This is how the app
"updates when hashcat updates": the wrapper stays put, the engine refreshes.

Version discovery uses GitHub's API; the binary itself comes from the official
hashcat.net release archive (a .7z). Extraction uses py7zr if available, else a
system 7z/7za binary.

Nothing here runs automatically - the GUI calls check()/install() when the user
clicks. Downloads are always an explicit user action.
"""

import os
import re
import json
import shutil
import tempfile
import subprocess
import urllib.request

import hashcat_iface as hc

VENDOR_DIR = hc.VENDOR_DIR
VERSION_FILE = os.path.join(VENDOR_DIR, "VERSION")
GITHUB_LATEST = "https://api.github.com/repos/hashcat/hashcat/releases/latest"
DL_TEMPLATE = "https://hashcat.net/files/hashcat-{ver}.7z"
UA = {"User-Agent": "NineLives-updater"}


def _norm(ver):
    return re.sub(r"[^0-9.]", "", ver or "")


def latest_version(timeout=20):
    """Latest hashcat version string (e.g. '6.2.6'), or '' on failure."""
    try:
        req = urllib.request.Request(GITHUB_LATEST, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        return _norm(data.get("tag_name", ""))
    except Exception:  # noqa: BLE001
        return ""


def current_version():
    """Version of the bundled hashcat, from our VERSION stamp or hashcat itself."""
    if os.path.isfile(VERSION_FILE):
        try:
            with open(VERSION_FILE, encoding="utf-8") as fh:
                v = _norm(fh.read())
                if v:
                    return v
        except OSError:
            pass
    path = hc.find_hashcat()
    if path:
        m = re.search(r"\d+\.\d+(?:\.\d+)?", hc.version(path))
        if m:
            return m.group(0)
    return ""


def _vtuple(v):
    return tuple(int(x) for x in _norm(v).split(".") if x != "")


def check():
    """Return dict: {current, latest, update_available, have_hashcat}."""
    cur, lat = current_version(), latest_version()
    avail = bool(lat) and (not cur or _vtuple(lat) > _vtuple(cur))
    return {"current": cur, "latest": lat, "update_available": avail,
            "have_hashcat": bool(hc.find_hashcat())}


# --------------------------------------------------------------------------- #
# Download + extract
# --------------------------------------------------------------------------- #
def _download(url, dest, progress=None, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        total = int(r.headers.get("Content-Length", 0))
        got = 0
        with open(dest, "wb") as fh:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                fh.write(chunk)
                got += len(chunk)
                if progress and total:
                    progress(f"downloading... {got * 100 // total}%")
    return dest


def _extract_7z(archive, into):
    """Extract a .7z, preferring py7zr, falling back to a 7z/7za CLI."""
    try:
        import py7zr  # noqa: PLC0415
        with py7zr.SevenZipFile(archive, "r") as z:
            z.extractall(path=into)
        return True
    except ImportError:
        pass
    for exe in ("7z", "7za", "7zr"):
        if shutil.which(exe):
            subprocess.run([exe, "x", "-y", f"-o{into}", archive], check=True)
            return True
    raise RuntimeError(
        "Need py7zr (pip install py7zr) or a 7-Zip CLI (7z/7za) on PATH "
        "to extract the hashcat archive.")


def install(version=None, progress=None, archive_path=None):
    """
    Download (unless archive_path is given) and install hashcat into vendor/.

    progress(msg) is called with human-readable status lines.
    Returns the installed version string.
    """
    version = _norm(version) or latest_version()
    if not version and not archive_path:
        raise RuntimeError("Could not determine a hashcat version to install.")

    os.makedirs(VENDOR_DIR, exist_ok=True)
    tmpdir = tempfile.mkdtemp(prefix="ninelives_")
    try:
        if archive_path:
            archive = archive_path
        else:
            if progress:
                progress(f"fetching hashcat {version}...")
            archive = _download(DL_TEMPLATE.format(ver=version),
                                os.path.join(tmpdir, f"hashcat-{version}.7z"),
                                progress=progress)
        if progress:
            progress("extracting...")
        staging = os.path.join(tmpdir, "x")
        os.makedirs(staging, exist_ok=True)
        _extract_7z(archive, staging)

        # hashcat archives extract to a hashcat-<ver>/ folder; flatten it.
        entries = [os.path.join(staging, e) for e in os.listdir(staging)]
        src = entries[0] if len(entries) == 1 and os.path.isdir(entries[0]) \
            else staging

        if progress:
            progress("installing into vendor/...")
        # Clear the old vendor copy, then move the new tree in.
        if os.path.isdir(VENDOR_DIR):
            for e in os.listdir(VENDOR_DIR):
                p = os.path.join(VENDOR_DIR, e)
                shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) \
                    else os.remove(p)
        for e in os.listdir(src):
            shutil.move(os.path.join(src, e), os.path.join(VENDOR_DIR, e))

        with open(VERSION_FILE, "w", encoding="utf-8") as fh:
            fh.write(version or "")
        # Make the Linux binary executable.
        for n in ("hashcat.bin", "hashcat"):
            p = os.path.join(VENDOR_DIR, n)
            if os.path.isfile(p):
                os.chmod(p, 0o755)
        if progress:
            progress(f"installed hashcat {version}.")
        return version
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    print("Checking hashcat releases...")
    info = check()
    print(json.dumps(info, indent=2))
    if info["update_available"]:
        print(f"\nAn update is available: {info['current'] or 'none'} "
              f"-> {info['latest']}")
        print("Run install() from the app (or this module) to fetch it.")
