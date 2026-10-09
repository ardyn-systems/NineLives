#!/usr/bin/env python3
"""
NineLives <-> hashcat interface.

Locates the bundled (or system) hashcat, reports its version, runs it with
streaming output, and parses `hashcat --help` to build a live hash-mode
catalog. When hashcat isn't present yet, a cached catalog (or a built-in
static fallback) keeps the UI populated.
"""

import os
import re
import sys
import json
import shutil
import subprocess

import paths


def base_dir():
    return paths.APP_DIR


APP_DIR = paths.APP_DIR            # install dir (read-only when installed)
DATA_DIR = paths.DATA_DIR          # per-user writable dir
VENDOR_DIR = os.path.join(APP_DIR, "vendor", "hashcat")    # bundled (read-only)
UPDATE_DIR = os.path.join(DATA_DIR, "vendor", "hashcat")   # self-update target
CATALOG_CACHE = os.path.join(DATA_DIR, "hash_modes.cache.json")
# Full hash-mode catalog shipped in the repo, used when there's no live hashcat
# and no user cache (e.g. the hosted web demo, which has no hashcat binary).
BUNDLED_CATALOG = os.path.join(APP_DIR, "data", "hash_modes.json")


def find_hashcat():
    """An updated copy (DATA_DIR) wins over the bundled one (APP_DIR), then PATH."""
    names = ("hashcat.exe", "hashcat.bin", "hashcat")
    for d in (UPDATE_DIR, VENDOR_DIR):
        for n in names:
            p = os.path.join(d, n)
            if os.path.isfile(p):
                return p
    for n in ("hashcat", "hashcat.exe"):
        p = shutil.which(n)
        if p:
            return p
    for c in (r"C:\hashcat\hashcat.exe", r"C:\Program Files\hashcat\hashcat.exe",
              "/usr/bin/hashcat", "/usr/local/bin/hashcat"):
        if os.path.isfile(c):
            return c
    return ""


# --------------------------------------------------------------------------- #
# Run directory
# --------------------------------------------------------------------------- #
# hashcat resolves its shared folders (OpenCL kernels, modules, charsets, rules,
# tunings, hashcat.hcstat2, ...) relative to the CURRENT WORKING DIRECTORY, and
# also writes its own runtime files there (hashcat.pid, the compiled-kernel
# cache, restore/induct files). The bundled hashcat lives in a read-only install
# dir, so running from it fails to write ("Permission denied"); running from the
# data dir fails to read ("./OpenCL/: No such file or directory"). So we run from
# a writable per-user work dir with the read-only shared folders linked in
# (Windows directory junctions / POSIX symlinks — neither needs admin) and the
# small data files copied. Without this, every crack exits instantly doing
# nothing.
WORKDIR = os.path.join(DATA_DIR, "hcwork")
# Written by hashcat into cwd at runtime, or the binaries we call by full path —
# never linked/copied from the install dir.
_WORK_SKIP = {"hashcat.exe", "hashcat.bin", "kernels", "hashcat.pid",
              "hashcat.induct", "hashcat.log", "hashcat.restore",
              "hashcat.dictstat2", "hashcat.potfile"}


def _rm_link(dst):
    """Remove a previously linked entry without touching its target. A Windows
    junction is removed with rmdir (removes the link, keeps the target)."""
    if not os.path.lexists(dst):
        return
    try:
        if os.path.islink(dst):
            os.unlink(dst)
        elif os.path.isdir(dst):
            os.rmdir(dst)          # junction or empty dir
        else:
            os.remove(dst)
    except OSError:
        pass


def _link_dir(src, dst):
    _rm_link(dst)
    try:
        if sys.platform.startswith("win"):
            subprocess.run(["cmd", "/c", "mklink", "/J", dst, src],
                           capture_output=True, check=False)
        else:
            os.symlink(src, dst)
    except Exception:  # noqa: BLE001
        pass


def hashcat_workdir():
    """A writable directory to run hashcat from, with its read-only shared
    folders linked in. Rebuilt only when the hashcat location changes (first run
    or after an update), tracked by a marker file; otherwise returned as-is."""
    try:
        os.makedirs(WORKDIR, exist_ok=True)
    except OSError:
        return DATA_DIR
    path = find_hashcat()
    hc_dir = os.path.dirname(path) if path else ""
    if not hc_dir or not os.path.isdir(hc_dir):
        return WORKDIR
    marker = os.path.join(WORKDIR, ".hcsrc")
    prev = ""
    try:
        with open(marker, encoding="utf-8") as fh:
            prev = fh.read().strip()
    except OSError:
        pass
    if prev == hc_dir:
        return WORKDIR              # already prepared for this hashcat
    for name in os.listdir(hc_dir):
        if name in _WORK_SKIP:
            continue
        src = os.path.join(hc_dir, name)
        dst = os.path.join(WORKDIR, name)
        try:
            if os.path.isdir(src):
                _link_dir(src, dst)           # junction / symlink (instant)
            elif os.path.isfile(src):
                shutil.copyfile(src, dst)      # small data files (e.g. .hcstat2)
        except Exception:  # noqa: BLE001
            pass
    try:
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write(hc_dir)
    except OSError:
        pass
    return WORKDIR


def _run_text(path, args, timeout=60):
    try:
        return subprocess.run([path] + args, capture_output=True, text=True,
                              timeout=timeout, cwd=hashcat_workdir())
    except Exception:  # noqa: BLE001
        return None


def version(path=None):
    path = path or find_hashcat()
    if not path:
        return ""
    out = _run_text(path, ["--version"], timeout=20)
    return (out.stdout.strip() if out and out.stdout else "")


# --------------------------------------------------------------------------- #
# Parsing `hashcat --help`
# --------------------------------------------------------------------------- #
# Hash-mode rows look like:   "    22000 | WPA-PBKDF2-PMKID+EAPOL | Network Protocol"
_MODE_ROW = re.compile(r"^\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*$")


def parse_hash_modes(path=None):
    """Return [{id,name,category}, ...] parsed from `hashcat --help`."""
    path = path or find_hashcat()
    if not path:
        return []
    out = _run_text(path, ["--help"], timeout=40)
    if not out or not out.stdout:
        return []
    modes, in_section = [], False
    for line in out.stdout.splitlines():
        if "[ Hash modes ]" in line:
            in_section = True
            continue
        if in_section:
            if line.strip().startswith("- [") and "Hash modes" not in line:
                break  # next section
            m = _MODE_ROW.match(line)
            if m and m.group(2).lower() != "name":
                modes.append({"id": int(m.group(1)),
                              "name": m.group(2).strip(),
                              "category": m.group(3).strip()})
    return modes


def example_hash(mode_id, path=None):
    """Fetch hashcat's own example hash for a mode (for a 'what should this
    look like?' hint in the UI)."""
    path = path or find_hashcat()
    if not path:
        return ""
    out = _run_text(path, ["-m", str(mode_id), "--example-hashes"], timeout=30)
    if not out or not out.stdout:
        return ""
    for line in out.stdout.splitlines():
        s = line.strip()
        if s.lower().startswith("example.hash"):
            return s.split(":", 1)[-1].strip()
    return ""


# --------------------------------------------------------------------------- #
# Catalog: live -> cache -> static fallback
# --------------------------------------------------------------------------- #
def load_hash_modes():
    """Instant: user cache -> bundled full catalog -> curated static fallback. NO
    subprocess (so startup never blocks on hashcat)."""
    for src in (CATALOG_CACHE, BUNDLED_CATALOG):
        if os.path.isfile(src):
            try:
                with open(src, encoding="utf-8") as fh:
                    modes = json.load(fh)
                if modes:
                    return modes
            except (OSError, ValueError):
                pass
    return list(STATIC_HASH_MODES)


def refresh_hash_modes():
    """Run `hashcat --help` (subprocess), cache and return the full mode list.
    Slow on first run (AV/device scan) — call from a BACKGROUND thread only."""
    path = find_hashcat()
    if not path:
        return []
    modes = parse_hash_modes(path)
    if modes:
        try:
            with open(CATALOG_CACHE, "w", encoding="utf-8") as fh:
                json.dump(modes, fh)
        except OSError:
            pass
    return modes


# A curated fallback so dropdowns work before hashcat is installed. Refreshed
# automatically into the cache the first time real hashcat is found.
STATIC_HASH_MODES = [
    {"id": 22000, "name": "WPA-PBKDF2-PMKID+EAPOL", "category": "Network Protocol"},
    {"id": 16800, "name": "WPA-PMKID-PBKDF2", "category": "Network Protocol"},
    {"id": 0, "name": "MD5", "category": "Raw Hash"},
    {"id": 100, "name": "SHA1", "category": "Raw Hash"},
    {"id": 1400, "name": "SHA2-256", "category": "Raw Hash"},
    {"id": 1700, "name": "SHA2-512", "category": "Raw Hash"},
    {"id": 1000, "name": "NTLM", "category": "Operating System"},
    {"id": 1800, "name": "sha512crypt $6$ (Unix)", "category": "Operating System"},
    {"id": 500, "name": "md5crypt $1$ (Unix)", "category": "Operating System"},
    {"id": 3200, "name": "bcrypt $2*$ (Blowfish)", "category": "Operating System"},
    {"id": 1500, "name": "descrypt (DES Unix)", "category": "Operating System"},
    {"id": 5600, "name": "NetNTLMv2", "category": "Network Protocol"},
    {"id": 13100, "name": "Kerberos 5 TGS-REP (etype 23)", "category": "Network Protocol"},
    {"id": 18200, "name": "Kerberos 5 AS-REP (etype 23)", "category": "Network Protocol"},
    {"id": 2500, "name": "WPA-EAPOL-PBKDF2 (legacy hccapx)", "category": "Network Protocol"},
    {"id": 900, "name": "MD4", "category": "Raw Hash"},
    {"id": 1100, "name": "Domain Cached Credentials (DCC)", "category": "Operating System"},
    {"id": 2100, "name": "Domain Cached Credentials 2 (DCC2)", "category": "Operating System"},
    {"id": 7500, "name": "Kerberos 5 AS-REQ Pre-Auth (etype 23)", "category": "Network Protocol"},
    {"id": 22921, "name": "RSA/DSA/EC/OpenSSH Private Keys", "category": "Private Key"},
]


if __name__ == "__main__":
    hc = find_hashcat()
    print("hashcat:", hc or "(not found - using static catalog)")
    if hc:
        print("version:", version(hc))
    modes = load_hash_modes()
    print(f"\n{len(modes)} hash modes available. First 12:")
    for m in modes[:12]:
        print(f"  {m['id']:>6}  {m['name']:<40} {m['category']}")
