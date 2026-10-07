#!/usr/bin/env python3
"""
NineLives web-server mode — serves the same webui/ over HTTP with the Python
API behind it, so the app can run hosted (e.g. on Render) as an EXPLORE +
EXTRACT console: browse the UI, import a capture to pull its WPA hashes, and
download the resulting .hc22000.

Cracking is intentionally NOT available here (no server-side hashcat, no GPU,
and a public crack endpoint would be an abuse risk) — that lives in the desktop
app. The shared api.py reports hosted=True whenever there's no desktop window,
and disables run/install accordingly.

Pure standard library; launched via `python ninelives.py --host 0.0.0.0 --port N`.
"""

import os
import json
import mimetypes
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import api as api_mod
import settings
import hashcat_iface as hc

VERSION = "0.1.0"
WEBUI = os.path.join(hc.APP_DIR, "webui")
CAPT_DIR = api_mod.CAPT_DIR
# Cap uploads on small hosted instances (free Render = 512 MB RAM).
MAX_UPLOAD = int(os.environ.get("NINELIVES_MAX_UPLOAD_MB", "50")) * 1024 * 1024

# Methods reachable over HTTP. Excludes FS-path methods (pick_file, set_seclists,
# import_capture) that would let a hosted visitor touch the server filesystem;
# run/install_update stay listed but self-disable without a desktop window.
HTTP_ALLOWED = {
    "get_init", "acknowledge", "get_options", "suggest_wordlists", "set_theme",
    "build_command", "run", "stop", "show_recovered", "check_update",
    "install_update", "import_capture_bytes", "get_captures", "use_capture",
    "remove_capture",
}


class Handler(BaseHTTPRequestHandler):
    api = None
    server_version = "NineLives/" + VERSION

    def log_message(self, fmt, *args):   # keep logs quiet/one-line
        pass

    # --- helpers ---------------------------------------------------------
    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _safe_webui(self, path):
        rel = path.lstrip("/") or "index.html"
        full = os.path.normpath(os.path.join(WEBUI, rel))
        if not full.startswith(os.path.normpath(WEBUI)):
            return None
        return full if os.path.isfile(full) else None

    # --- GET -------------------------------------------------------------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            return self._json({"status": "ok", "name": "NineLives",
                               "version": VERSION, "hosted": True})
        if path == "/api/download":
            return self._download(urllib.parse.parse_qs(parsed.query))
        full = self._safe_webui(path)
        if not full:
            return self._json({"error": "not found"}, 404)
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as fh:
            data = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _download(self, qs):
        entry_id = (qs.get("id") or [""])[0]
        for e in settings.get("captures_index", []):
            if e["id"] == entry_id:
                p = e["path"]
                if os.path.normpath(p).startswith(os.path.normpath(CAPT_DIR)) \
                        and os.path.isfile(p):
                    with open(p, "rb") as fh:
                        data = fh.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.send_header("Content-Disposition",
                                     f'attachment; filename="{entry_id}"')
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
        self._json({"error": "capture not found"}, 404)

    # --- POST /api/<method> ---------------------------------------------
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        method = parsed.path[len("/api/"):]
        if method not in HTTP_ALLOWED:
            return self._json({"error": f"method not allowed: {method}"}, 403)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > MAX_UPLOAD:
                return self._json({"error": f"upload too large (max "
                                   f"{MAX_UPLOAD // (1024 * 1024)} MB)"}, 413)
            raw = self.rfile.read(length) if length else b"[]"
            args = json.loads(raw.decode("utf-8") or "[]")
            if not isinstance(args, list):
                args = [args]
        except Exception as e:  # noqa: BLE001
            return self._json({"error": f"bad request: {e}"}, 400)
        try:
            result = getattr(self.api, method)(*args)
        except Exception as e:  # noqa: BLE001
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)
        self._json(result)


def serve(host="0.0.0.0", port=8000):
    Handler.api = api_mod.Api()          # no window bound -> hosted mode
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"NineLives server (explore + extract) on http://{host}:{port}",
          flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()
