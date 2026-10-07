"""Filesystem locations for NineLives.

APP_DIR is where the app lives (the install folder when frozen) — read-only on a
normal install (e.g. C:\\Program Files\\NineLives). Bundled assets (vendor/) are
read from here.

DATA_DIR is a per-user, WRITABLE location (e.g. %LOCALAPPDATA%\\NineLives) for all
runtime files: settings, potfile, caches, extracted captures, and any
hashcat update. Never write into APP_DIR.
"""

import os
import sys


def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = _app_dir()


def _data_dir():
    if sys.platform.startswith("win"):
        root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        root = os.path.expanduser("~/Library/Application Support")
    else:
        root = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    d = os.path.join(root, "NineLives")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        d = APP_DIR  # last-resort fallback (e.g. portable with a writable dir)
    return d


DATA_DIR = _data_dir()
