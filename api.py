#!/usr/bin/env python3
"""
JS API exposed to the NineLives web UI (webui/) via pywebview.

Every method returns JSON-serializable data to the page. Long-running output
(hashcat, updates) is pushed to the page by calling JS functions
(window.hbOutput / window.hbDone) through the bound window's evaluate_js.

All the actual work lives in the existing backend modules; this is just the
bridge, so the web UI and the logic stay cleanly separated.
"""

import os
import re
import json
import time
import base64
import tempfile
import threading
import subprocess

import log
import settings
import compat
import wordlists
import wordlist_dl
import updater
import selfupdate
import version as appver
import themes
import captures
import hashcat_iface as hc

POTFILE = os.path.join(hc.DATA_DIR, "ninelives.potfile")
CAPT_DIR = os.path.join(hc.DATA_DIR, "captures")


class Api:
    def __init__(self):
        self.window = None
        log.log("Api.__init__: catalog scan")
        self.catalog = wordlists.Catalog()
        self.catalog.scan()
        log.log(f"Api.__init__: load_hash_modes (indexed {len(self.catalog.all_entries())} wordlists)")
        self.modes = hc.load_hash_modes()
        self._mode_by_id = {m["id"]: m for m in self.modes}
        self._opt_by_key = {(o.long or o.flag): o for o in compat.OPTIONS}
        self.proc = None
        self._refreshed = False
        os.makedirs(CAPT_DIR, exist_ok=True)
        log.log(f"Api.__init__: done ({len(self.modes)} modes)")

    def bind(self, window):
        self.window = window

    def log(self, msg):
        """Called from the page so the browser side's steps land in the log too."""
        log.log("js: " + str(msg))
        return {"ok": True}

    def _refresh_catalog(self):
        """Background: run the slow hashcat probes (--help, --version) and push
        the full hash-mode list + version to the UI. Never blocks startup."""
        try:
            log.log("refresh: hashcat --help")
            modes = hc.refresh_hash_modes()
            log.log(f"refresh: got {len(modes)} modes")
            if modes:
                self.modes = modes
                self._mode_by_id = {m["id"]: m for m in self.modes}
            path = hc.find_hashcat()
            ver = ""
            if path:
                import re
                log.log("refresh: hashcat --version")
                m = re.search(r"\d+\.\d+(?:\.\d+)?", hc.version(path) or "")
                ver = m.group(0) if m else ""
            log.log(f"refresh: emit hbCatalog (ver={ver})")
            self._emit("hbCatalog", self.modes, ver)
            log.log("refresh: done")
        except Exception as e:  # noqa: BLE001
            log.log(f"refresh: error {e!r}")

    def _emit(self, fn, *args):
        if not self.window:
            return
        try:
            payload = ",".join(json.dumps(a) for a in args)
            self.window.evaluate_js(f"window.{fn}({payload})")
        except Exception:  # noqa: BLE001
            pass

    # ---- initial state -----------------------------------------------------
    def get_init(self):
        log.log("get_init: begin")
        path = hc.find_hashcat()
        log.log(f"get_init: hashcat_present={bool(path)}")
        # Kick off the slow hashcat probing in the background (desktop only);
        # the UI starts instantly with cached/static modes and upgrades later.
        if path and self.window is not None and not self._refreshed:
            self._refreshed = True
            log.log("get_init: starting background refresh")
            threading.Thread(target=self._refresh_catalog, daemon=True).start()
        log.log("get_init: returning")
        return {
            "themes": [{"id": t, "name": themes.THEMES[t]["name"],
                        "note": themes.THEMES[t]["note"],
                        "swatch": themes.THEMES[t]["swatch"]} for t in themes.ORDER],
            "current_theme": settings.get("ui_theme", themes.DEFAULT),
            "acknowledged": bool(settings.get("acknowledged")),
            "attack_modes": [{"id": m["id"], "name": m["name"], "desc": m["desc"],
                              "inputs": m["inputs"]} for m in compat.ATTACK_MODES],
            "hash_modes": self.modes,
            "hashcat": {"present": bool(path),
                        "version": updater.current_version() if path else ""},
            "seclists_root": self.catalog.root,
            "wordlists_count": len(self.catalog.all_entries()),
            # hosted = running as a web server (no desktop window): explore +
            # extract only, cracking happens in the desktop app. NINELIVES_DOCS
            # forces the full desktop UI for screenshot generation.
            "hosted": self.window is None and not os.environ.get("NINELIVES_DOCS"),
            "app_version": appver.__version__,
        }

    def acknowledge(self):
        settings.set("acknowledged", True)
        return {"ok": True}

    def get_options(self, attack_id):
        groups = compat.grouped_options_for(int(attack_id))
        out = []
        for grp, opts in groups.items():
            out.append({"group": grp, "options": [
                {"key": o.long or o.flag, "flag": o.flag, "long": o.long,
                 "takes_value": o.takes_value, "desc": o.desc, "example": o.example}
                for o in opts]})
        return {"groups": out}

    def suggest_wordlists(self, mode_id):
        m = self._mode_by_id.get(int(mode_id)) if mode_id is not None else None
        suggested, fam = ([], "")
        if m:
            suggested, fam = self.catalog.suggest(m)

        def entry(e):
            return {"label": f"{e['name']}  [{e['category']}]", "path": e["path"]}

        return {"family": fam,
                "suggested": [entry(e) for e in suggested],
                "all": [entry(e) for e in self.catalog.all_entries()]}

    def set_theme(self, theme_id):
        settings.set("ui_theme", theme_id)
        return {"ok": True}

    def set_seclists(self, path):
        self.catalog.set_root(path or "")
        return {"count": len(self.catalog.all_entries())}

    # ---- downloadable wordlists -------------------------------------------
    def list_wordlist_downloads(self):
        return {"items": wordlist_dl.catalog()}

    def install_wordlist(self, item_id):
        """Download a wordlist in the background, streaming progress to the
        console and refreshing the catalog + dropdowns when it lands."""
        if self.window is None:
            return {"error": "Wordlist downloads run in the desktop app only."}

        def worker():
            try:
                self._emit("hbWordlistStatus", item_id, "starting…")
                wordlist_dl.install(
                    item_id,
                    progress=lambda m: (
                        self._emit("hbOutput", f"[wordlist] {m}\n"),
                        self._emit("hbWordlistStatus", item_id, m)))
                self.catalog.scan()
                self._emit("hbOutput",
                           f"[wordlist] done ({len(self.catalog.all_entries())} "
                           "wordlists indexed)\n")
                self._emit("hbWordlists", len(self.catalog.all_entries()))
                self._emit("hbWordlistStatus", item_id, "installed")
            except Exception as e:  # noqa: BLE001
                self._emit("hbOutput", f"[wordlist] failed: {e}\n")
                self._emit("hbWordlistStatus", item_id, f"failed: {e}")

        threading.Thread(target=worker, daemon=True).start()
        return {"started": True}

    def pick_file(self, kind):
        if not self.window:
            return None
        import webview
        if kind == "folder":
            r = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        elif kind == "capture":
            r = self.window.create_file_dialog(
                webview.OPEN_DIALOG, allow_multiple=False,
                file_types=("Captures (*.pcap;*.pcapng;*.cap)", "All files (*.*)"))
        else:
            r = self.window.create_file_dialog(webview.OPEN_DIALOG,
                                               allow_multiple=False)
        if not r:
            return None
        return r[0] if isinstance(r, (list, tuple)) else r

    # ---- captures ----------------------------------------------------------
    def _ingest(self, path, source):
        try:
            res = captures.extract(path)
        except Exception as e:  # noqa: BLE001
            return {"error": f"Could not parse capture: {e}"}
        index = settings.get("captures_index", [])
        by_id = {e["id"]: e for e in index}
        added = []
        for net in res["networks"]:
            lines = net.get("lines") or []
            if not lines:
                continue
            safe = re.sub(r"[^A-Za-z0-9_.-]", "_", net["essid"] or net["bssid"])
            bss = net["bssid"].replace(":", "")
            fname = f"{safe}_{bss}.hc22000"
            fpath = os.path.join(CAPT_DIR, fname)
            with open(fpath, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            entry = {"id": fname, "source": source, "essid": net["essid"],
                     "bssid": net["bssid"], "pmkid": net["pmkid"],
                     "handshake": net["handshake"], "path": fpath,
                     "imported": time.strftime("%Y-%m-%d %H:%M")}
            by_id[entry["id"]] = entry
            added.append(entry)
        settings.set("captures_index", list(by_id.values()))
        msg = (f"Imported {len(added)} network(s) from {source}." if added
               else f"No WPA hashes found in {source} "
                    "(metadata-only formats carry no crackable hashes).")
        return {"added": added, "count": len(added), "message": msg}

    def import_capture(self, path):
        if not path or not os.path.isfile(path):
            return {"error": "File not found."}
        return self._ingest(path, os.path.basename(path))

    def import_capture_bytes(self, name, b64):
        """Import a drag-dropped capture whose bytes come over the bridge."""
        try:
            raw = base64.b64decode(b64.split(",")[-1])
        except Exception as e:  # noqa: BLE001
            return {"error": f"Bad file data: {e}"}
        tmp = os.path.join(tempfile.gettempdir(),
                           "ninelives_" + re.sub(r"[^A-Za-z0-9_.-]", "_", name))
        try:
            with open(tmp, "wb") as fh:
                fh.write(raw)
            return self._ingest(tmp, name)
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass

    def get_captures(self):
        return {"captures": settings.get("captures_index", [])}

    def use_capture(self, entry_id):
        for e in settings.get("captures_index", []):
            if e["id"] == entry_id:
                return {"hashfile": e["path"], "mode_id": 22000,
                        "essid": e["essid"]}
        return {"error": "Capture not found."}

    def remove_capture(self, entry_id):
        index = settings.get("captures_index", [])
        kept = [e for e in index if e["id"] != entry_id]
        for e in index:
            if e["id"] == entry_id:
                try:
                    os.remove(e["path"])
                except OSError:
                    pass
        settings.set("captures_index", kept)
        return {"count": len(kept)}

    # ---- command assembly --------------------------------------------------
    def _assemble(self, p):
        path = hc.find_hashcat()
        if p.get("mode_id") is None:
            return None, "Pick a hash type."
        if not p.get("hashfile"):
            return None, "Pick a hash file."
        aid = int(p["attack_id"])
        cmd = [path or "hashcat", "-m", str(p["mode_id"]), "-a", str(aid),
               p["hashfile"]]
        for slot in compat.inputs_for(aid):
            if slot in ("wordlist", "wordlist2"):
                wl = p.get(slot)
                if not wl:
                    return None, f"Pick a {slot}."
                cmd.append(wl)
            elif slot == "mask":
                mask = (p.get("mask") or "").strip()
                if not mask:
                    return None, "Enter a mask."
                cmd.append(mask)
        for o in p.get("options", []):
            opt = self._opt_by_key.get(o.get("key"))
            if not opt:
                continue
            flag = opt.flag or opt.long
            if opt.takes_value:
                if o.get("value"):
                    cmd += [flag, o["value"]]
            else:
                cmd.append(flag)
        if not any(o.get("key") == "--potfile-disable" for o in p.get("options", [])):
            cmd += ["--potfile-path", POTFILE]
        return cmd, None

    def build_command(self, p):
        cmd, err = self._assemble(p)
        return {"error": err} if err else {"command": subprocess.list2cmdline(cmd)}

    def run(self, p):
        if self.window is None:
            return {"error": "Cracking runs in the NineLives desktop app. "
                             "This hosted instance is explore + extract only."}
        if self.proc:
            return {"error": "A crack is already running."}
        if not hc.find_hashcat():
            return {"error": "hashcat not installed (Settings - install/update)."}
        cmd, err = self._assemble(p)
        if err:
            return {"error": err}

        def worker():
            try:
                # Run from hashcat's work dir: it looks for its OpenCL kernels /
                # modules relative to the cwd and writes its runtime files there,
                # so running from DATA_DIR made every crack exit instantly with
                # "./OpenCL/: No such file or directory".
                self.proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, cwd=hc.hashcat_workdir())
                for line in self.proc.stdout:
                    self._emit("hbOutput", line)
                self.proc.wait()
            except Exception as e:  # noqa: BLE001
                self._emit("hbOutput", f"[error] {e}\n")
            finally:
                self.proc = None
                self._emit("hbDone")

        threading.Thread(target=worker, daemon=True).start()
        return {"command": subprocess.list2cmdline(cmd)}

    def stop(self):
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:  # noqa: BLE001
                pass
        return {"ok": True}

    def show_recovered(self, p):
        path = hc.find_hashcat()
        if not path:
            return {"text": "hashcat not installed."}
        if p.get("mode_id") is None or not p.get("hashfile"):
            return {"text": "Pick a hash type and file first."}
        args = ["-m", str(p["mode_id"]), p["hashfile"], "--show",
                "--potfile-path", POTFILE]
        out = hc._run_text(path, args, timeout=30)
        return {"text": (out.stdout if out else "") or ""}

    # ---- updates -----------------------------------------------------------
    def check_update(self):
        try:
            return updater.check()
        except Exception as e:  # noqa: BLE001
            return {"current": "", "latest": "", "update_available": False,
                    "error": str(e)}

    def install_update(self, version):
        if self.window is None:
            return {"error": "Updates install in the desktop app only."}

        def worker():
            try:
                ver = updater.install(
                    version, progress=lambda m: self._emit("hbOutput",
                                                            f"[update] {m}\n"))
                self._emit("hbOutput", f"[update] done: hashcat {ver}\n")
                self.modes = hc.refresh_hash_modes() or self.modes
                self._mode_by_id = {m["id"]: m for m in self.modes}
            except Exception as e:  # noqa: BLE001
                self._emit("hbOutput", f"[update] failed: {e}\n")

        threading.Thread(target=worker, daemon=True).start()
        return {"started": True}

    # ---- app self-update ---------------------------------------------------
    def check_self_update(self):
        return selfupdate.check()

    def install_self_update(self):
        if self.window is None:
            return {"error": "Updates install in the desktop app only."}
        info = selfupdate.check()
        if not info.get("available") or not info.get("asset"):
            return {"error": "No update available for this platform."}
        asset = info["asset"]

        def worker():
            try:
                res = selfupdate.download_and_launch(
                    asset["url"], asset["name"],
                    progress=lambda m: self._emit("hbOutput", f"[app-update] {m}\n"))
                self._emit("hbOutput", f"[app-update] saved {res['path']}\n")
                if res.get("quit"):
                    self._emit("hbOutput",
                               "[app-update] launching installer; closing NineLives…\n")
                    # Force a full process exit so the installer can replace the
                    # running (otherwise locked) files; destroy() from a worker
                    # thread is unreliable and may leave the process alive.
                    import time
                    time.sleep(1.0)   # let the message reach the UI first
                    os._exit(0)
                else:
                    self._emit("hbOutput",
                               "[app-update] downloaded the new AppImage; "
                               "replace the current one to finish.\n")
            except Exception as e:  # noqa: BLE001
                self._emit("hbOutput", f"[app-update] failed: {e}\n")

        threading.Thread(target=worker, daemon=True).start()
        return {"started": True, "latest": info["latest"]}
