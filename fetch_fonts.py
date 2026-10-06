#!/usr/bin/env python3
"""
Download the NetSeer display fonts (Orbitron + Exo 2) into vendor/fonts/ so they
can be bundled and registered at runtime for an exact visual match.

Both are licensed under the SIL Open Font License (redistributable); the license
is fetched alongside them.

    python fetch_fonts.py
"""

import os
import urllib.request

import settings

DEST = os.path.join(settings.APP_DIR, "vendor", "fonts")
UA = {"User-Agent": "HashBench-fetch"}
BASE = "https://github.com/google/fonts/raw/main/ofl/"

FILES = {
    "Orbitron[wght].ttf": BASE + "orbitron/Orbitron%5Bwght%5D.ttf",
    "Exo2[wght].ttf": BASE + "exo2/Exo2%5Bwght%5D.ttf",
    "Orbitron-OFL.txt": BASE + "orbitron/OFL.txt",
    "Exo2-OFL.txt": BASE + "exo2/OFL.txt",
}


def main():
    os.makedirs(DEST, exist_ok=True)
    print(f"Fetching fonts into {DEST}")
    for name, url in FILES.items():
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            with open(os.path.join(DEST, name), "wb") as fh:
                fh.write(data)
            print(f"  {name}  ({len(data):,} bytes)")
        except Exception as e:  # noqa: BLE001
            print(f"  skip {name}: {e}")
    print("done.")


if __name__ == "__main__":
    main()
