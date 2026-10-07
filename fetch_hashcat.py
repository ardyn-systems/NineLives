#!/usr/bin/env python3
"""
One-shot: download the latest official hashcat into vendor/hashcat/ so it can be
bundled into the build. Run before building, or any time to refresh.

    python fetch_hashcat.py            # latest
    python fetch_hashcat.py 6.2.6      # a specific version
    python fetch_hashcat.py ./hashcat-6.2.6.7z   # install from a local archive

Needs py7zr (pip install py7zr) or a 7z/7za CLI on PATH to unpack the archive.
"""

import os
import sys
import updater
import hashcat_iface as hc


def main(argv):
    arg = argv[1] if len(argv) > 1 else None
    try:
        # Build-time: bundle into the install vendor dir (not the runtime
        # self-update dir), so PyInstaller packages it.
        dest = hc.VENDOR_DIR
        if arg and os.path.isfile(arg):
            ver = updater.install(archive_path=arg, progress=print, dest=dest)
        else:
            ver = updater.install(version=arg, progress=print, dest=dest)
        print(f"\nOK: hashcat {ver} installed to {dest}")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"\nfailed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
