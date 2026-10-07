#!/usr/bin/env python3
"""
NineLives launcher.

Two modes from one entry point:
  * Desktop (default): a pywebview window hosting the web UI (webui/) with the
    Python API (api.py) behind it — the full console, cracking included.
  * Server (--host/--port): serves the same UI over HTTP for a hosted,
    explore + extract deployment (e.g. Render). Cracking is disabled server-side.

Modules:
  webui/            HTML/CSS/JS front-end (NetSeer look, six themes)
  api.py            JS <-> Python bridge (and HTTP API in server mode)
  server.py         stdlib HTTP server for hosted mode
  hashcat_iface.py  locate/run hashcat, parse --help into a live hash catalog
  compat.py         attack-mode <-> stackable-option matrix (+ explanations)
  wordlists.py      SecLists catalog + hash-aware suggestions
  updater.py        check/install hashcat releases into vendor/
  captures.py       pcap/pcapng -> WPA 22000 extractor
  themes.py         theme tokens (synthwave default + cyberpunk + NetSeer four)
  settings.py       shared JSON settings

Run:  python ninelives.py                       # desktop
      python ninelives.py --host 0.0.0.0 --port 8000   # server
"""

import os
import sys
import argparse


def _run_desktop():
    import logging
    import webview
    import api
    import hashcat_iface as hc

    class _DropNativeIntrospection(logging.Filter):
        """Drop pywebview's benign 'window.native…' COM introspection errors on
        Windows (it fails to walk the WinForms accessibility object). Real
        errors still pass through."""

        def filter(self, record):
            return "window.native" not in record.getMessage()

    logging.getLogger("pywebview").addFilter(_DropNativeIntrospection())

    bridge = api.Api()
    # No background_color — some WebView2 runtimes lack the controller interface
    # it probes (E_NOINTERFACE); the page's own CSS paints the bg.
    window = webview.create_window(
        "NineLives",
        url=os.path.join(hc.APP_DIR, "webui", "index.html"),
        js_api=bridge, width=1120, height=860, min_size=(900, 640))
    bridge.bind(window)
    webview.start(debug=bool(os.environ.get("NINELIVES_DEBUG")))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ninelives", description="NineLives")
    ap.add_argument("--host", help="serve over HTTP on this address (hosted mode)")
    ap.add_argument("--port", type=int, help="serve over HTTP on this port")
    ap.add_argument("--server", action="store_true", help="force server mode")
    args = ap.parse_args(argv)

    if args.server or args.host or args.port:
        import server
        server.serve(host=args.host or "0.0.0.0", port=args.port or 8000)
    else:
        _run_desktop()


if __name__ == "__main__":
    sys.exit(main() or 0)
