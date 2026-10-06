#!/usr/bin/env python3
"""
Populate vendor/wordlists/ with wordlists to bundle into the app.

By default it fetches a CURATED set (rockyou + top WPA/common-credential lists)
so the installer stays a reasonable size (~150 MB). Pass --full to clone the
entire SecLists collection instead (multi-GB installer).

    python fetch_wordlists.py            # curated (recommended default)
    python fetch_wordlists.py --full     # entire SecLists (large!)

hashcat itself ships rules, not wordlists - those come bundled via
fetch_hashcat.py. This script covers the wordlists.
"""

import os
import sys
import io
import tarfile
import shutil
import subprocess
import urllib.request

import hashcat_iface as hc

DEST = os.path.join(hc.APP_DIR, "vendor", "wordlists")
RAW = "https://raw.githubusercontent.com/danielmiessler/SecLists/master/"
UA = {"User-Agent": "HashBench-fetch"}

# (relative-url, local-subpath). rockyou is handled specially (tar.gz).
CURATED = [
    ("Passwords/WiFi-WPA/probable-v2-wpa-top4800.txt",
     "WiFi-WPA/probable-v2-wpa-top4800.txt"),
    ("Passwords/WiFi-WPA/probable-v2-wpa-top62.txt",
     "WiFi-WPA/probable-v2-wpa-top62.txt"),
    ("Passwords/Common-Credentials/10k-most-common.txt",
     "Common-Credentials/10k-most-common.txt"),
    ("Passwords/Common-Credentials/best1050.txt",
     "Common-Credentials/best1050.txt"),
    ("Passwords/Common-Credentials/"
     "10-million-password-list-top-1000000.txt",
     "Common-Credentials/10-million-password-list-top-1000000.txt"),
    ("Usernames/top-usernames-shortlist.txt",
     "Usernames/top-usernames-shortlist.txt"),
]
ROCKYOU_TGZ = RAW + "Passwords/Leaked-Databases/rockyou.txt.tar.gz"


def _get(url, timeout=120):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _save(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print(f"  {url.split('/')[-1]}")
    with open(dest, "wb") as fh:
        fh.write(_get(url))


def fetch_curated():
    os.makedirs(DEST, exist_ok=True)
    print(f"Fetching curated wordlists into {DEST}")
    for rel, sub in CURATED:
        try:
            _save(RAW + rel, os.path.join(DEST, sub))
        except Exception as e:  # noqa: BLE001
            print(f"  skip {rel}: {e}")
    # rockyou ships as a tar.gz in SecLists; extract the .txt
    try:
        print("  rockyou.txt (from tar.gz)...")
        data = _get(ROCKYOU_TGZ)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            for m in tf.getmembers():
                if m.name.endswith("rockyou.txt"):
                    out = os.path.join(DEST, "Leaked-Databases", "rockyou.txt")
                    os.makedirs(os.path.dirname(out), exist_ok=True)
                    with tf.extractfile(m) as src, open(out, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    break
    except Exception as e:  # noqa: BLE001
        print(f"  skip rockyou: {e}")
    print("done.")


def fetch_full():
    """Clone the entire SecLists repo (large)."""
    target = os.path.join(DEST, "SecLists")
    if os.path.isdir(os.path.join(target, ".git")):
        print("Updating existing SecLists clone...")
        subprocess.run(["git", "-C", target, "pull", "--ff-only"], check=False)
        return
    os.makedirs(DEST, exist_ok=True)
    print("Cloning full SecLists (this is large)...")
    subprocess.run(["git", "clone", "--depth", "1",
                    "https://github.com/danielmiessler/SecLists.git", target],
                   check=True)


def main(argv):
    if "--full" in argv:
        fetch_full()
    else:
        fetch_curated()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
