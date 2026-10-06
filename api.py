#!/usr/bin/env python3
"""
JS API exposed to the HashBench web UI (webui/) via pywebview.

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

import settings
import compat
import wordlists
import updater
import themes
import captures
import hashcat_iface as hc

POTFILE = os.path.join(hc.APP_DIR, "hashbench.potfile")
CAPT_DIR = os.path.join(hc.APP_DIR, "captures")


class Api:
    def __init__(self):
        self.window = None
        self.catalog = wordlists.Catalog()
        self.catalog.scan()
        self.modes = hc.load_hash_modes()
        self._mode_by_id = {m["id"]: m for m in self.modes}
        self._opt_by_key = {(o.long or o.flag): o for o in compat.OPTIONS}
        self.proc = None
        os.makedirs(CAPT_DIR, exist_ok=True)

    def bind(self, window):
        self.window = window

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
        path = hc.find_hashcat()
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
                           "hashbench_" + re.sub(r"[^A-Za-z0-9_.-]", "_", name))
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
        if self.proc:
            return {"error": "A crack is already running."}
        if not hc.find_hashcat():
            return {"error": "hashcat not installed (Settings - install/update)."}
        cmd, err = self._assemble(p)
        if err:
            return {"error": err}

        def worker():
            try:
                self.proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, cwd=hc.APP_DIR)
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
        def worker():
            try:
                ver = updater.install(
                    version, progress=lambda m: self._emit("hbOutput",
                                                            f"[update] {m}\n"))
                self._emit("hbOutput", f"[update] done: hashcat {ver}\n")
                self.modes = hc.load_hash_modes(refresh=True)
                self._mode_by_id = {m["id"]: m for m in self.modes}
            except Exception as e:  # noqa: BLE001
                self._emit("hbOutput", f"[update] failed: {e}\n")

        threading.Thread(target=worker, daemon=True).start()
        return {"started": True}
