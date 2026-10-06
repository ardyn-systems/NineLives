#!/usr/bin/env python3
"""
Register bundled .ttf fonts (vendor/fonts) with the OS so Tkinter can use them
by family name, giving the exact NetSeer faces (Orbitron / Exo 2) rather than
fallbacks.

Windows: AddFontResourceEx as a private, process-scoped font (no admin, no
install). Linux: drop into ~/.local/share/fonts and refresh the cache (picked up
on next launch if the running process has already enumerated fonts).

Best-effort: every step is guarded so a missing font never breaks startup.
"""

import os
import sys
import glob
import shutil
import subprocess

import settings

FONT_DIR = os.path.join(settings.APP_DIR, "vendor", "fonts")


def _register_windows(path):
    import ctypes
    FR_PRIVATE = 0x10
    try:
        return ctypes.windll.gdi32.AddFontResourceExW(path, FR_PRIVATE, 0) > 0
    except Exception:  # noqa: BLE001
        return False


def _register_linux(path):
    dest_dir = os.path.expanduser("~/.local/share/fonts")
    try:
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, os.path.basename(path))
        if not os.path.exists(dest):
            shutil.copy2(path, dest)
            subprocess.run(["fc-cache", "-f", dest_dir],
                           check=False, capture_output=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def register():
    """Register every .ttf/.otf in vendor/fonts. Returns how many loaded."""
    if not os.path.isdir(FONT_DIR):
        return 0
    n = 0
    for path in glob.glob(os.path.join(FONT_DIR, "*.ttf")) + \
            glob.glob(os.path.join(FONT_DIR, "*.otf")):
        ok = _register_windows(path) if sys.platform.startswith("win") \
            else _register_linux(path)
        n += 1 if ok else 0
    return n


if __name__ == "__main__":
    print(f"registered {register()} font(s) from {FONT_DIR}")
