#!/usr/bin/env python3
"""
NineLives launcher — a pywebview desktop window hosting the NetSeer-styled web
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

Run:  python ninelives.py
"""

import os
import sys
import logging

import webview

import api
import hashcat_iface as hc


class _DropNativeIntrospection(logging.Filter):
    """Drop pywebview's benign 'window.native…' COM introspection errors on
    Windows (it fails to walk the WinForms accessibility object and logs a
    recursion error). Real errors still pass through."""

    def filter(self, record):
        return "window.native" not in record.getMessage()


logging.getLogger("pywebview").addFilter(_DropNativeIntrospection())


def _index_path():
    return os.path.join(hc.APP_DIR, "webui", "index.html")


def main():
    bridge = api.Api()
    # Note: no background_color — some WebView2 runtimes lack the controller
    # interface it probes (E_NOINTERFACE); the page's own CSS paints the bg.
    window = webview.create_window(
        "NineLives",
        url=_index_path(),
        js_api=bridge,
        width=1120,
        height=860,
        min_size=(900, 640),
    )
    bridge.bind(window)
    # gui=None lets pywebview pick the platform backend (EdgeChromium on Windows,
    # GTK/WebKit on Linux). debug mode is on when NINELIVES_DEBUG is set.
    webview.start(debug=bool(os.environ.get("NINELIVES_DEBUG")))


if __name__ == "__main__":
    sys.exit(main() or 0)
