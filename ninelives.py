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
    import log
    log.reset()
    log.log("desktop: importing webview/api")
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

    # WebView2 creates its user-data folder in the process working directory by
    # default. On a double-click that cwd is System32, and when installed the
    # exe dir is C:\Program Files\NineLives — both read-only — so WebView2 can't
    # create the folder and webview.start() hangs. Pin it to our writable
    # per-user data dir. (Reproduced: launching from a read-only cwd hangs
    # exactly at webview.start until this is set.)
    wv2 = os.path.join(hc.DATA_DIR, "webview2")
    os.makedirs(wv2, exist_ok=True)
    os.environ["WEBVIEW2_USER_DATA_FOLDER"] = wv2
    # WebView2 writes into the process working directory, which is read-only on
    # a double-click (System32) or installed launch (Program Files) — that hangs
    # webview.start(). Move cwd to our writable data dir. (All app paths are
    # absolute, so this is safe.)
    try:
        os.chdir(hc.DATA_DIR)
    except OSError:
        pass
    log.log(f"desktop: cwd={os.getcwd()}; WEBVIEW2_USER_DATA_FOLDER={wv2}")

    log.log("desktop: constructing Api()")
    bridge = api.Api()
    index = os.path.join(hc.APP_DIR, "webui", "index.html")
    log.log(f"desktop: Api() ready; index exists={os.path.isfile(index)} ({index})")
    # No background_color — some WebView2 runtimes lack the controller interface
    # it probes (E_NOINTERFACE); the page's own CSS paints the bg.
    window = webview.create_window(
        "NineLives", url=index,
        js_api=bridge, width=1120, height=860, min_size=(900, 640))
    log.log("desktop: window created; binding")
    bridge.bind(window)
    log.log("desktop: calling webview.start()")
    webview.start(storage_path=wv2, private_mode=False,
                  debug=bool(os.environ.get("NINELIVES_DEBUG")))
    log.log("desktop: webview.start() returned (window closed)")


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
