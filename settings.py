#!/usr/bin/env python3
"""Tiny JSON-backed settings shared across NineLives modules."""

import os
import json

import paths

APP_DIR = paths.APP_DIR          # install dir (for locating bundled assets)
_PATH = os.path.join(paths.DATA_DIR, "settings.json")   # writable
_cache = None


def base_dir():
    return paths.APP_DIR


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
