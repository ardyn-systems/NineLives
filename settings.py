#!/usr/bin/env python3
"""Tiny JSON-backed settings shared across HashBench modules."""

import os
import sys
import json


def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = base_dir()
_PATH = os.path.join(APP_DIR, "settings.json")
_cache = None


def _load():
    global _cache
    if _cache is None:
        try:
            with open(_PATH, encoding="utf-8") as fh:
                _cache = json.load(fh)
        except (OSError, ValueError):
            _cache = {}
    return _cache


def get(key, default=None):
    return _load().get(key, default)


def set(key, value):  # noqa: A001 - mirrors dict.set vibe intentionally
    data = _load()
    data[key] = value
    try:
        with open(_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except OSError:
        pass
