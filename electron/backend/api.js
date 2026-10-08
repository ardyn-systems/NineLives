"use strict";
/* Backend API the Electron main process exposes to the renderer over IPC.
 * Node port of the methods api.py serves. Phase 0: initial state, options,
 * themes/settings, and the Captures tab (via the ported extractor). Cracking,
 * wordlist downloads, and hashcat updates arrive in later phases. */

const fs = require("fs");
const path = require("path");
const { EventEmitter } = require("events");
const { spawn, execFile } = require("child_process");

const { DATA_DIR, EXAMPLES_DIR } = require("./paths");
const settings = require("./settings");
const themes = require("./themes");
const compat = require("./compat");
const hashcat = require("./hashcat");
const wordlistsMod = require("./wordlists");
const wordlistDl = require("./wordlist_dl");
const updater = require("./updater");
const selfupdate = require("./selfupdate");
const captures = require("./captures");

const APP_VERSION = require("../package.json").version;
const CAPT_DIR = path.join(DATA_DIR, "captures");
const HASH_DIR = path.join(DATA_DIR, "hashes");
const POTFILE = path.join(DATA_DIR, "ninelives.potfile");

function quoteArg(a) {
  return /[\s"]/.test(a) ? '"' + a.replace(/"/g, '\\"') + '"' : a;
}
function cmdToString(cmd) {
  return cmd.map(quoteArg).join(" ");
}

class Api extends EventEmitter {
  constructor() {
    super();
    this.catalog = new wordlistsMod.Catalog();
    this.catalog.scan();
    this.modes = hashcat.loadHashModes();
    this.modeById = new Map(this.modes.map((m) => [m.id, m]));
    this.optByKey = new Map(compat.OPTIONS.map((o) => [o.long || o.flag, o]));
    this.proc = null;
    this._refreshed = false;
    fs.mkdirSync(CAPT_DIR, { recursive: true });
    fs.mkdirSync(HASH_DIR, { recursive: true });
    this._seedExamples();
  }

  // On first run, preload the bundled sample capture so a fresh install can
  // crack straight away (with the bundled wpa-demo wordlist) — Coherer → Induction.
  _seedExamples() {
    try {
      if (settings.get("examples_seeded")) return;
      const sample = path.join(EXAMPLES_DIR, "Coherer-sample.hc22000");
      if (!fs.existsSync(sample)) return;
      const index = settings.get("captures_index", []) || [];
      if (!index.some((e) => e.id === "Coherer-sample.hc22000")) {
        index.push({
          id: "Coherer-sample.hc22000", source: "bundled example (wpa-Induction)",
          essid: "Coherer", bssid: "00:0c:41:82:b2:55", pmkid: true, handshake: true,
          path: sample, imported: "sample", sample: true,
        });
        settings.set("captures_index", index);
      }
      settings.set("examples_seeded", true);
    } catch {
      /* ignore */
    }
  }

  // Background: run the slow hashcat probes (--help, --version) off the UI path
  // and push the full catalog + version to the page. Never blocks get_init.
  _refreshCatalog() {
    const p = hashcat.findHashcat();
    if (!p) return;
    const wd = hashcat.hashcatWorkdir();
    execFile(p, ["--help"], { cwd: wd, timeout: 40000, maxBuffer: 64 * 1024 * 1024 }, (err, stdout) => {
      const modes = hashcat.parseHashModesText(stdout || "");
      if (modes.length) {
        hashcat.cacheHashModes(modes);
        this.modes = modes;
        this.modeById = new Map(this.modes.map((m) => [m.id, m]));
      }
      execFile(p, ["--version"], { cwd: wd, timeout: 20000 }, (e2, vOut) => {
        const m = /\d+\.\d+(?:\.\d+)?/.exec(vOut || "");
        this._emit("hbCatalog", this.modes, m ? m[0] : "");
      });
    });
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
    if (p && !this._refreshed) {
      this._refreshed = true;
      setImmediate(() => this._refreshCatalog());
    }
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

  // ---- crack ------------------------------------------------------------
  _assemble(p) {
    const hcPath = hashcat.findHashcat();
    if (p.mode_id == null) return [null, "Pick a hash type."];
    if (!p.hashfile) return [null, "Pick a hash file."];
    const aid = parseInt(p.attack_id, 10);
    const cmd = [hcPath || "hashcat", "-m", String(p.mode_id), "-a", String(aid), p.hashfile];
    for (const slot of compat.inputsFor(aid)) {
      if (slot === "wordlist" || slot === "wordlist2") {
        const wl = p[slot];
        if (!wl) return [null, `Pick a ${slot}.`];
        cmd.push(wl);
      } else if (slot === "mask") {
        const mask = (p.mask || "").trim();
        if (!mask) return [null, "Enter a mask."];
        cmd.push(mask);
      }
    }
    for (const o of p.options || []) {
      const opt = this.optByKey.get(o.key);
      if (!opt) continue;
      const flag = opt.flag || opt.long;
      if (opt.takes_value) {
        if (o.value) cmd.push(flag, o.value);
      } else {
        cmd.push(flag);
      }
    }
    if (!(p.options || []).some((o) => o.key === "--potfile-disable")) cmd.push("--potfile-path", POTFILE);
    return [cmd, null];
  }

  build_command(p) {
    const [cmd, err] = this._assemble(p);
    return err ? { error: err } : { command: cmdToString(cmd) };
  }

  run(p) {
    if (this.proc) return { error: "A crack is already running." };
    if (!hashcat.findHashcat()) return { error: "hashcat not installed (Settings - install/update)." };
    const [cmd, err] = this._assemble(p);
    if (err) return { error: err };
    let proc;
    try {
      proc = spawn(cmd[0], cmd.slice(1), { cwd: hashcat.hashcatWorkdir() });
    } catch (e) {
      return { error: `Could not start hashcat: ${e.message || e}` };
    }
    this.proc = proc;
    let buf = "";
    const onData = (chunk) => {
      buf += chunk.toString();
      let idx;
      while ((idx = buf.indexOf("\n")) >= 0) {
        this._emit("hbOutput", buf.slice(0, idx + 1));
        buf = buf.slice(idx + 1);
      }
    };
    proc.stdout.on("data", onData);
    proc.stderr.on("data", onData);
    proc.on("close", () => {
      if (buf) this._emit("hbOutput", buf);
      this.proc = null;
      this._emit("hbDone");
    });
    proc.on("error", (e) => {
      this._emit("hbOutput", `[error] ${e.message}\n`);
      this.proc = null;
      this._emit("hbDone");
    });
    return { command: cmdToString(cmd) };
  }

  stop() {
    if (this.proc) {
      try {
        this.proc.kill();
      } catch {
        /* ignore */
      }
    }
    return { ok: true };
  }

  show_recovered(p) {
    const hcPath = hashcat.findHashcat();
    if (!hcPath) return { text: "hashcat not installed." };
    if (p.mode_id == null || !p.hashfile) return { text: "Pick a hash type and file first." };
    const { spawnSync } = require("child_process");
    const r = spawnSync(hcPath, ["-m", String(p.mode_id), p.hashfile, "--show", "--potfile-path", POTFILE],
      { cwd: hashcat.hashcatWorkdir(), encoding: "utf8", timeout: 30000 });
    return { text: (r.stdout || "") };
  }

  // ---- downloadable wordlists -------------------------------------------
  list_wordlist_downloads() {
    return { items: wordlistDl.catalog() };
  }

  install_wordlist(itemId) {
    (async () => {
      try {
        this._emit("hbWordlistStatus", itemId, "starting…");
        await wordlistDl.install(itemId, (m) => {
          this._emit("hbOutput", `[wordlist] ${m}\n`);
          this._emit("hbWordlistStatus", itemId, m);
        });
        this.catalog.scan();
        this._emit("hbOutput", `[wordlist] done (${this.catalog.allEntries().length} wordlists indexed)\n`);
        this._emit("hbWordlists", this.catalog.allEntries().length);
        this._emit("hbWordlistStatus", itemId, "installed");
      } catch (e) {
        this._emit("hbOutput", `[wordlist] failed: ${e.message || e}\n`);
        this._emit("hbWordlistStatus", itemId, `failed: ${e.message || e}`);
      }
    })();
    return { started: true };
  }

  // ---- hashcat updates --------------------------------------------------
  async check_update() {
    try {
      return await updater.check();
    } catch (e) {
      return { current: "", latest: "", update_available: false, error: String(e.message || e) };
    }
  }

  install_update(version) {
    (async () => {
      try {
        const ver = await updater.install(version, (m) => this._emit("hbOutput", `[update] ${m}\n`));
        this._emit("hbOutput", `[update] done: hashcat ${ver}\n`);
        const modes = hashcat.refreshHashModes();
        if (modes.length) {
          this.modes = modes;
          this.modeById = new Map(this.modes.map((m) => [m.id, m]));
        }
      } catch (e) {
        this._emit("hbOutput", `[update] failed: ${e.message || e}\n`);
      }
    })();
    return { started: true };
  }

  // ---- app self-update --------------------------------------------------
  async check_self_update() {
    return await selfupdate.check();
  }

  install_self_update() {
    (async () => {
      const info = await selfupdate.check();
      if (!info.available || !info.asset) {
        this._emit("hbOutput", "[app-update] no update available for this platform.\n");
        return;
      }
      try {
        const res = await selfupdate.downloadAndLaunch(info.asset.url, info.asset.name,
          (m) => this._emit("hbOutput", `[app-update] ${m}\n`));
        this._emit("hbOutput", `[app-update] saved ${res.path}\n`);
        if (res.quit) {
          this._emit("hbOutput", "[app-update] launching installer; closing NineLives…\n");
          this.emit("quit");
        }
      } catch (e) {
        this._emit("hbOutput", `[app-update] failed: ${e.message || e}\n`);
      }
    })();
    return { started: true, latest: APP_VERSION };
  }
}

module.exports = { Api, CAPT_DIR, HASH_DIR };
