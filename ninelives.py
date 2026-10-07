#!/usr/bin/env python3
"""
NineLives launcher.

Desktop (default): starts a local HTTP server (server.py) on 127.0.0.1 and shows
it in a window — pywebview's WebView2 (Windows) / WebKitGTK (Linux), falling back
to the default browser if neither is available. The page talks to the backend
over HTTP (fetch), the same way the hosted build does; there is no JS<->Python
bridge, so a slow WebView2 start can't strand the UI on "Starting…". Cracking is
enabled because the server is local (loopback only).

Server (--host/--port): the public explore + extract deployment (e.g. Render) —
import a capture, download the .hc22000; cracking is disabled.

Modules:
  webui/            HTML/CSS/JS front-end (NetSeer look, six themes)
  server.py         HTTP server + /api/* dispatch and the event stream
  api.py            the backend the server calls (crack, extract, catalog, …)
  hashcat_iface.py  locate/run hashcat, parse --help into a live hash catalog
  compat.py         attack-mode <-> stackable-option matrix (+ explanations)
  wordlists.py      SecLists catalog + hash-aware suggestions
  wordlist_dl.py    on-demand wordlist downloads
  updater.py        check/install hashcat releases into vendor/
  captures.py       pcap/pcapng -> WPA 22000 extractor
  themes.py         theme tokens (synthwave default + cyberpunk + NetSeer four)
  settings.py       shared JSON settings

Run:  python ninelives.py                                  # desktop
      python ninelives.py --host 0.0.0.0 --port 8000       # public server
      python ninelives.py --browser                        # desktop, in a browser
"""

import os
import sys
import time
import socket
import argparse
import threading
import urllib.request

DEFAULT_PORT = 8731
FALLBACK_PORTS = range(8732, 8741)


def _port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) != 0


def _choose_port():
    for p in (DEFAULT_PORT, *FALLBACK_PORTS):
        if _port_free(p):
            return p
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(port, timeout=30.0):
    """Poll /api/health until the local server answers."""
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/api/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as r:
                if r.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.1)
    return False


def _open_window(url, log):
    """Show the UI in a pywebview window. Raises if pywebview/WebView2 is
    unavailable so the caller can fall back to a browser."""
    import logging
    import webview
    import hashcat_iface as hc

    class _DropNativeIntrospection(logging.Filter):
        def filter(self, record):
            return "window.native" not in record.getMessage()

    pwlog = logging.getLogger("pywebview")
    pwlog.addFilter(_DropNativeIntrospection())
    # A windowed frozen app has no console; route pywebview's own DEBUG log to a
    # file so a stalled start still leaves a trail.
    try:
        _pw = logging.FileHandler(
            os.path.join(hc.DATA_DIR, "pywebview.log"), mode="w", encoding="utf-8")
        _pw.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        pwlog.addHandler(_pw)
        pwlog.setLevel(logging.DEBUG)
        pwlog.propagate = False
    except Exception:  # noqa: BLE001
        pass

    wv2 = os.path.join(hc.DATA_DIR, "webview2")
    os.makedirs(wv2, exist_ok=True)
    os.environ["WEBVIEW2_USER_DATA_FOLDER"] = wv2

    window = webview.create_window(
        "NineLives", url=url, width=1120, height=860, min_size=(900, 640))
    try:
        window.events.shown += lambda: log("desktop: window shown (WebView2 ready)")
        window.events.loaded += lambda: log("desktop: page loaded")
        window.events.closing += lambda: log("desktop: window closing")
    except Exception:  # noqa: BLE001
        pass

    shown = threading.Event()
    try:
        window.events.shown += shown.set
    except Exception:  # noqa: BLE001
        pass

    def _watchdog():
        if not shown.wait(25):
            log("desktop: WARN window not shown after 25s — WebView2 init stalled "
                "(see pywebview.log for the last step)")
    threading.Thread(target=_watchdog, daemon=True).start()

    log("desktop: calling webview.start()")
    webview.start(storage_path=wv2, private_mode=False,
                  debug=bool(os.environ.get("NINELIVES_DEBUG")))
    log("desktop: webview.start() returned (window closed)")


def _open_browser(url, httpd, api, log):
    """Fallback: open the default browser and keep the server alive until the
    page stops checking in (its event long-poll doubles as a heartbeat)."""
    import webbrowser
    log(f"desktop: opening browser at {url}")
    try:
        webbrowser.open(url)
    except Exception as e:  # noqa: BLE001
        log(f"desktop: webbrowser.open failed ({e})")
    # Quit a little after the page stops polling (tab closed). The page polls
    # /api/events continuously, so api._last_poll tracks liveness.
    first_grace, idle = 300.0, 150.0
    start = time.monotonic()
    while True:
        time.sleep(3)
        last = getattr(api, "_last_poll", 0.0)
        now = time.monotonic()
        if last == 0.0:
            if now - start > first_grace:
                log("desktop: no page opened; quitting")
                break
        elif now - last > idle:
            log("desktop: page gone; quitting")
            break
    try:
        httpd.shutdown()
    except Exception:  # noqa: BLE001
        pass


def _run_desktop(browser_only=False):
    import log
    log.reset()
    log.log("desktop: starting")
    import server as server_mod
    import hashcat_iface as hc
    import version as appver

    # WebView2 writes into the process working directory; a double-click / Program
    # Files cwd is read-only, so move to the writable data dir.
    try:
        os.chdir(hc.DATA_DIR)
    except OSError:
        pass

    port = _choose_port()
    log.log(f"desktop: starting local server on 127.0.0.1:{port} (local=full)")
    httpd = server_mod.make_server("127.0.0.1", port, local=True)
    threading.Thread(target=httpd.serve_forever, name="nl-server", daemon=True).start()

    if not _wait_ready(port):
        log.log("desktop: WARN server did not answer /api/health in time")
    url = f"http://127.0.0.1:{port}/?v={appver.__version__}"
    log.log(f"desktop: serving {url}")

    api = server_mod.Handler.api
    if not browser_only:
        try:
            _open_window(url, log.log)
            try:
                httpd.shutdown()
            except Exception:  # noqa: BLE001
                pass
            return
        except Exception as exc:  # ImportError / missing WebView2 / no display
            log.log(f"desktop: window unavailable ({exc}); falling back to browser")
    _open_browser(url, httpd, api, log.log)


def smoke_test():
    """Start the local server on a spare port and exercise the bundle: health,
    the web UI files, and get_init (themes, attack modes, hash catalog). Exits 0
    when everything the UI needs to boot is present. Run in CI on the frozen
    build to catch packaging breakage before a user does."""
    import json
    import server as server_mod
    import hashcat_iface as hc

    # A windowed frozen exe has no console (sys.stdout is None), so collect
    # results and write them to a file; also echo to stdout when there is one.
    results_path = os.path.join(hc.DATA_DIR, "smoke-test.log")
    lines = []

    def emit(s):
        lines.append(s)
        try:
            if sys.stdout is not None:
                print(s)
        except Exception:  # noqa: BLE001
            pass

    port = _choose_port()
    httpd = server_mod.make_server("127.0.0.1", port, local=True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    checks = []

    def get(path):
        with urllib.request.urlopen(base + path, timeout=30) as r:
            return r.read()

    def post(path, body):
        req = urllib.request.Request(
            base + path, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())

    try:
        if not _wait_ready(port):
            raise RuntimeError("server did not answer /api/health")
        checks.append(("index.html", b"NineLives" in get("/"), ""))
        checks.append(("app.js", len(get("/app.js")) > 1000, ""))
        checks.append(("styles.css", len(get("/styles.css")) > 1000, ""))
        init = post("/api/get_init", [])
        checks.append(("themes", len(init.get("themes", [])) >= 4, ""))
        checks.append(("attack modes", len(init.get("attack_modes", [])) >= 1, ""))
        checks.append(("hash catalog", len(init.get("hash_modes", [])) >= 1,
                       f"{len(init.get('hash_modes', []))} modes"))
        checks.append(("not hosted (local=full)", init.get("hosted") is False, ""))
        drained = json.loads(get("/api/events?since=0").decode())
        checks.append(("event stream", "cursor" in drained, ""))
    except Exception as exc:  # noqa: BLE001
        checks.append(("exception", False, repr(exc)))
    finally:
        httpd.shutdown()

    for name, ok, note in checks:
        emit(f"{'PASS' if ok else 'FAIL'} {name} {note}".rstrip())
    ok_all = all(ok for _, ok, _ in checks)
    emit(f"smoke test {'passed' if ok_all else 'FAILED'}")
    try:
        with open(results_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        pass
    return 0 if ok_all else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ninelives", description="NineLives")
    ap.add_argument("--host", help="serve over HTTP on this address (public server)")
    ap.add_argument("--port", type=int, help="serve over HTTP on this port")
    ap.add_argument("--server", action="store_true", help="force public server mode")
    ap.add_argument("--browser", action="store_true",
                    help="desktop mode, but open in the default browser")
    ap.add_argument("--smoke-test", action="store_true",
                    help="check the installation and exit (0 = OK)")
    args = ap.parse_args(argv)

    if args.smoke_test:
        return smoke_test()
    if args.server or args.host or args.port:
        import server
        server.serve(host=args.host or "0.0.0.0", port=args.port or 8000, local=False)
    else:
        _run_desktop(browser_only=args.browser)


if __name__ == "__main__":
    sys.exit(main() or 0)
