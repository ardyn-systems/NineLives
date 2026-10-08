"use strict";
/* Backend API the Electron main process exposes to the renderer over IPC.
 * Node port of the methods api.py serves. Phase 0: initial state, options,
 * themes/settings, and the Captures tab (via the ported extractor). Cracking,
 * wordlist downloads, and hashcat updates arrive in later phases. */

const fs = require("fs");
const path = require("path");
const { EventEmitter } = require("events");

const { DATA_DIR } = require("./paths");
const settings = require("./settings");
const themes = require("./themes");
const compat = require("./compat");
const hashcat = require("./hashcat");
const wordlistsMod = require("./wordlists");
const captures = require("./captures");

const APP_VERSION = require("../package.json").version;
const CAPT_DIR = path.join(DATA_DIR, "captures");
const HASH_DIR = path.join(DATA_DIR, "hashes");

class Api extends EventEmitter {
  constructor() {
    super();
    this.catalog = new wordlistsMod.Catalog();
    this.catalog.scan();
    this.modes = hashcat.loadHashModes();
    this.modeById = new Map(this.modes.map((m) => [m.id, m]));
    fs.mkdirSync(CAPT_DIR, { recursive: true });
    fs.mkdirSync(HASH_DIR, { recursive: true });
  }

  _emit(fn, ...args) {
    this.emit("event", { fn, args });
  }

  log(msg) {
    // Mirror the Python side's js log breadcrumb to a file for diagnostics.
    try {
      fs.appendFileSync(path.join(DATA_DIR, "startup.log"), `js: ${msg}\n`);
    } catch {
      /* ignore */
    }
    return { ok: true };
  }

  get_init() {
    const p = hashcat.findHashcat();
    return {
      themes: themes.ORDER.map((t) => ({ id: t, name: themes.THEMES[t].name, note: themes.THEMES[t].note, swatch: themes.THEMES[t].swatch })),
      current_theme: settings.get("ui_theme", themes.DEFAULT),
      acknowledged: !!settings.get("acknowledged"),
      attack_modes: compat.ATTACK_MODES.map((m) => ({ id: m.id, name: m.name, desc: m.desc, inputs: m.inputs })),
      hash_modes: this.modes,
      hashcat: { present: !!p, version: p ? hashcat.currentVersion() : "" },
      seclists_root: this.catalog.root,
      wordlists_count: this.catalog.allEntries().length,
      hosted: false, // Electron desktop app is always full capability
      app_version: APP_VERSION,
    };
  }

  acknowledge() {
    settings.set("acknowledged", true);
    return { ok: true };
  }

  get_options(attackId) {
    const groups = compat.groupedOptionsFor(parseInt(attackId, 10));
    const out = [];
    for (const [grp, opts] of groups) {
      out.push({
        group: grp,
        options: opts.map((o) => ({ key: o.long || o.flag, flag: o.flag, long: o.long, takes_value: o.takes_value, desc: o.desc, example: o.example })),
      });
    }
    return { groups: out };
  }

  suggest_wordlists(modeId) {
    const m = modeId != null ? this.modeById.get(parseInt(modeId, 10)) : null;
    let picks = [];
    let fam = "";
    if (m) {
      const r = this.catalog.suggest(m);
      picks = r.picks;
      fam = r.fam;
    }
    const entry = (e) => ({ label: `${e.name}  [${e.category}]`, path: e.path });
    return { family: fam, suggested: picks.map(entry), all: this.catalog.allEntries().map(entry) };
  }

  set_theme(themeId) {
    settings.set("ui_theme", themeId);
    return { ok: true };
  }

  set_seclists(p) {
    this.catalog.setRoot(p || "");
    return { count: this.catalog.allEntries().length };
  }

  // ---- captures ----------------------------------------------------------
  _ingest(filePath, source) {
    let res;
    try {
      res = captures.extract(filePath);
    } catch (e) {
      return { error: `Could not parse capture: ${e.message || e}` };
    }
    const index = settings.get("captures_index", []) || [];
    const byId = new Map(index.map((e) => [e.id, e]));
    const added = [];
    for (const net of res.networks) {
      const lines = net.lines || [];
      if (!lines.length) continue;
      const safe = (net.essid || net.bssid).replace(/[^A-Za-z0-9_.-]/g, "_");
      const bss = net.bssid.replace(/:/g, "");
      const fname = `${safe}_${bss}.hc22000`;
      const fpath = path.join(CAPT_DIR, fname);
      fs.writeFileSync(fpath, lines.join("\n") + "\n");
      const entry = { id: fname, source, essid: net.essid, bssid: net.bssid, pmkid: net.pmkid, handshake: net.handshake, path: fpath, imported: new Date().toISOString().slice(0, 16).replace("T", " ") };
      byId.set(entry.id, entry);
      added.push(entry);
    }
    settings.set("captures_index", Array.from(byId.values()));
    const message = added.length
      ? `Imported ${added.length} network(s) from ${source}.`
      : `No WPA hashes found in ${source} (metadata-only formats carry no crackable hashes).`;
    return { added, count: added.length, message };
  }

  import_capture_bytes(name, b64) {
    let raw;
    try {
      raw = Buffer.from(String(b64).split(",").pop(), "base64");
    } catch (e) {
      return { error: `Bad file data: ${e.message || e}` };
    }
    const tmp = path.join(require("os").tmpdir(), "ninelives_" + name.replace(/[^A-Za-z0-9_.-]/g, "_"));
    try {
      fs.writeFileSync(tmp, raw);
      return this._ingest(tmp, name);
    } finally {
      try {
        fs.unlinkSync(tmp);
      } catch {
        /* ignore */
      }
    }
  }

  import_hash_bytes(name, b64) {
    let raw;
    try {
      raw = Buffer.from(String(b64).split(",").pop(), "base64");
    } catch (e) {
      return { error: `Bad file data: ${e.message || e}` };
    }
    const safe = name.replace(/[^A-Za-z0-9_.-]/g, "_") || "hashes.txt";
    const dest = path.join(HASH_DIR, safe);
    try {
      fs.writeFileSync(dest, raw);
    } catch (e) {
      return { error: `Could not save hash file: ${e.message || e}` };
    }
    return { path: dest, name: safe };
  }

  get_captures() {
    return { captures: settings.get("captures_index", []) || [] };
  }

  use_capture(entryId) {
    for (const e of settings.get("captures_index", []) || []) {
      if (e.id === entryId) return { hashfile: e.path, mode_id: 22000, essid: e.essid };
    }
    return { error: "Capture not found." };
  }

  remove_capture(entryId) {
    const index = settings.get("captures_index", []) || [];
    const kept = index.filter((e) => e.id !== entryId);
    for (const e of index) {
      if (e.id === entryId) {
        try {
          fs.unlinkSync(e.path);
        } catch {
          /* ignore */
        }
      }
    }
    settings.set("captures_index", kept);
    return { count: kept.length };
  }

  // ---- stubs filled in later phases --------------------------------------
  list_wordlist_downloads() {
    return { items: [] }; // Phase 2
  }
  build_command() {
    return { error: "Cracking is not wired up in this build yet." };
  }
  run() {
    return { error: "Cracking arrives in the next migration phase." };
  }
  stop() {
    return { ok: true };
  }
  show_recovered() {
    return { text: "" };
  }
  check_update() {
    return { current: hashcat.currentVersion(), latest: "", update_available: false };
  }
  install_update() {
    return { error: "Not available yet." };
  }
  install_wordlist() {
    return { error: "Not available yet." };
  }
  check_self_update() {
    return { available: false, current: APP_VERSION };
  }
  install_self_update() {
    return { error: "Not available yet." };
  }
}

module.exports = { Api, CAPT_DIR, HASH_DIR };
