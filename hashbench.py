#!/usr/bin/env python3
"""
HashBench launcher — a pywebview desktop window hosting the NetSeer-styled web
UI (webui/) backed by the Python API (api.py).

Modules:
  webui/            HTML/CSS/JS front-end (NetSeer look, four themes)
  api.py            JS <-> Python bridge
  hashcat_iface.py  locate/run hashcat, parse --help into a live hash catalog
  compat.py         attack-mode <-> stackable-option matrix (+ explanations)
  wordlists.py      SecLists catalog + hash-aware suggestions
  updater.py        check/install hashcat releases into vendor/
  themes.py         NetSeer theme tokens (easter-egg themes excluded)
  settings.py       shared JSON settings

Run:  python hashbench.py
"""

import os
import sys

import webview

import api
import hashcat_iface as hc


def _index_path():
    return os.path.join(hc.APP_DIR, "webui", "index.html")


def main():
    bridge = api.Api()
    window = webview.create_window(
        "HashBench",
        url=_index_path(),
        js_api=bridge,
        width=1120,
        height=860,
        min_size=(900, 640),
        background_color="#15140f",
    )
    bridge.bind(window)
    # gui=None lets pywebview pick the platform backend (EdgeChromium on Windows,
    # GTK/WebKit on Linux). debug mode is on when HASHBENCH_DEBUG is set.
    webview.start(debug=bool(os.environ.get("HASHBENCH_DEBUG")))


if __name__ == "__main__":
    sys.exit(main() or 0)
