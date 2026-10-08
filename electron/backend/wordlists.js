"use strict";
/* Wordlist catalog + hash-aware suggestions — Node port of wordlists.py
 * (+ the downloadable catalog from wordlist_dl.py). */

const fs = require("fs");
const path = require("path");
const { APP_DIR, DATA_DIR, EXAMPLES_DIR } = require("./paths");
const settings = require("./settings");

const EXTS = new Set([".txt", ".lst", ".dic", ".wordlist"]);
const BUNDLED = path.join(APP_DIR, "vendor", "wordlists");
const DOWNLOADED = path.join(DATA_DIR, "wordlists");

const CURATED = {
  wifi: ["Passwords/WiFi-WPA/probable-v2-wpa-top4800.txt", "Passwords/WiFi-WPA/probable-v2-wpa-top62.txt",
    "Passwords/Leaked-Databases/rockyou.txt", "Passwords/WiFi-WPA/darkc0de.txt"],
  os_creds: ["Passwords/Leaked-Databases/rockyou.txt", "Passwords/Common-Credentials/10-million-password-list-top-1000000.txt",
    "Passwords/Common-Credentials/best1050.txt", "Usernames/top-usernames-shortlist.txt"],
  raw_fast: ["Passwords/Leaked-Databases/rockyou.txt", "Passwords/xato-net-10-million-passwords.txt",
    "Passwords/Common-Credentials/10-million-password-list-top-1000000.txt"],
  web: ["Passwords/Leaked-Databases/rockyou.txt", "Passwords/Common-Credentials/10k-most-common.txt"],
  general: ["Passwords/Leaked-Databases/rockyou.txt"],
};

function familyFor(mode) {
  const name = (mode.name || "").toLowerCase();
  const cat = (mode.category || "").toLowerCase();
  if (name.includes("wpa") || name.includes("pmkid") || name.includes("eapol")) return "wifi";
  if (["ntlm", "kerberos", "crypt", "dcc", "netntlm"].some((k) => name.includes(k)) || cat.includes("operating system")) return "os_creds";
  if (["md5", "sha1", "sha2", "md4"].some((k) => name.includes(k)) || cat.includes("raw hash")) return "raw_fast";
  if (name.includes("http") || name.includes("web")) return "web";
  return "general";
}

class Catalog {
  constructor() {
    this.root = settings.get("seclists_root", "") || "";
    this.index = [];
  }
  roots() {
    const out = [];
    for (const r of [this.root, BUNDLED, DOWNLOADED, EXAMPLES_DIR]) {
      if (r && isDir(r) && !out.includes(r)) out.push(r);
    }
    return out;
  }
  setRoot(p) {
    this.root = p || "";
    settings.set("seclists_root", this.root);
    this.scan();
  }
  scan() {
    this.index = [];
    const seen = new Set();
    for (const root of this.roots()) {
      walk(root, (full) => {
        const ext = path.extname(full).toLowerCase();
        if (!EXTS.has(ext)) return;
        const key = path.resolve(full).toLowerCase();
        if (seen.has(key)) return;
        seen.add(key);
        let size = 0;
        try {
          size = fs.statSync(full).size;
        } catch {
          /* ignore */
        }
        this.index.push({ name: path.basename(full), path: full, category: path.basename(path.dirname(full)) || "misc", size });
      });
    }
    this.index.sort((a, b) => (a.category.toLowerCase() + a.name.toLowerCase()).localeCompare(b.category.toLowerCase() + b.name.toLowerCase()));
    return this.index.length;
  }
  allEntries() {
    return this.index;
  }
  resolveCurated(rel) {
    const relNorm = rel.replace(/\\/g, "/").toLowerCase();
    const tail = relNorm.split("/").pop();
    for (const e of this.index) {
      if (e.path.replace(/\\/g, "/").toLowerCase().endsWith(relNorm)) return e;
    }
    for (const e of this.index) {
      if (e.name.toLowerCase() === tail) return e;
    }
    return null;
  }
  suggest(mode) {
    const fam = familyFor(mode);
    const picks = [];
    const seen = new Set();
    for (const rel of CURATED[fam] || []) {
      const e = this.resolveCurated(rel);
      if (e && !seen.has(e.path)) {
        picks.push(e);
        seen.add(e.path);
      }
    }
    return { picks, fam };
  }
}

function isDir(p) {
  try {
    return fs.statSync(p).isDirectory();
  } catch {
    return false;
  }
}
function walk(dir, onFile) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) walk(full, onFile);
    else if (e.isFile()) onFile(full);
  }
}

module.exports = { Catalog, BUNDLED, DOWNLOADED };
