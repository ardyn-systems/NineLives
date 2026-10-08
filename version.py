"""Single source of truth for the NineLives version.

Reads the version from electron/package.json — the Electron app's version, which
the release tags track — so the hosted Python server (and anything else on the
Python side) reports the same version as the shipping app."""

import json
import os


def _read_version():
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(here, "electron", "package.json"), encoding="utf-8") as f:
            v = json.load(f).get("version")
            if v:
                return str(v)
    except Exception:
        pass
    return "0.0.0"


__version__ = _read_version()
