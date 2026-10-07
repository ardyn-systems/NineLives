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


def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = base_dir()
VENDOR_DIR = os.path.join(APP_DIR, "vendor", "hashcat")
CATALOG_CACHE = os.path.join(APP_DIR, "hash_modes.cache.json")


def find_hashcat():
    """Prefer the bundled vendor copy, then PATH, then common install dirs."""
    names = ("hashcat.exe", "hashcat.bin", "hashcat")
    for n in names:
        p = os.path.join(VENDOR_DIR, n)
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


def _run_text(path, args, timeout=60):
    try:
        return subprocess.run([path] + args, capture_output=True, text=True,
                              timeout=timeout, cwd=os.path.dirname(path) or None)
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
def load_hash_modes(refresh=False):
    """Live parse (and cache) if hashcat is present; else cached; else static."""
    path = find_hashcat()
    if path and (refresh or not os.path.isfile(CATALOG_CACHE)):
        modes = parse_hash_modes(path)
        if modes:
            try:
                with open(CATALOG_CACHE, "w", encoding="utf-8") as fh:
                    json.dump(modes, fh)
            except OSError:
                pass
            return modes
    if os.path.isfile(CATALOG_CACHE):
        try:
            with open(CATALOG_CACHE, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            pass
    return list(STATIC_HASH_MODES)


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
