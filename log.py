"""Startup/diagnostic log written to a per-user file, flushed every line.

A hang leaves no traceback, so this records each startup step; the last line in
%LOCALAPPDATA%\\NineLives\\startup.log is where it got stuck. Open/append/close
per call so nothing is lost if the process freezes or is killed.
"""

import os
import time

import paths

PATH = os.path.join(paths.DATA_DIR, "startup.log")


def reset():
    try:
        with open(PATH, "w", encoding="utf-8") as fh:
            fh.write(f"=== NineLives startup {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    except Exception:  # noqa: BLE001
        pass


def log(msg):
    try:
        with open(PATH, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:  # noqa: BLE001
        pass
