"use strict";
/* hashcat locate + static catalog — partial Node port of hashcat_iface.py.
 * Phase 0: locate the binary and serve the static hash-mode catalog so the UI
 * boots. Running hashcat (spawn + stream) and the live --help catalog land in
 * Phase 1. */

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const { APP_DIR, DATA_DIR } = require("./paths");

const VENDOR_DIR = path.join(APP_DIR, "vendor", "hashcat"); // bundled (read-only)
const UPDATE_DIR = path.join(DATA_DIR, "vendor", "hashcat"); // self-update target
const CATALOG_CACHE = path.join(DATA_DIR, "hash_modes.cache.json");
const WORKDIR = path.join(DATA_DIR, "hcwork");

function findHashcat() {
  const names = ["hashcat.exe", "hashcat.bin", "hashcat"];
  for (const d of [UPDATE_DIR, VENDOR_DIR]) {
    for (const n of names) {
      const p = path.join(d, n);
      if (safeIsFile(p)) return p;
    }
  }
  // PATH
  const sep = process.platform === "win32" ? ";" : ":";
  for (const dir of (process.env.PATH || "").split(sep)) {
    for (const n of ["hashcat.exe", "hashcat"]) {
      const p = path.join(dir, n);
      if (safeIsFile(p)) return p;
    }
  }
  for (const c of ["C:/hashcat/hashcat.exe", "C:/Program Files/hashcat/hashcat.exe",
    "/usr/bin/hashcat", "/usr/local/bin/hashcat"]) {
    if (safeIsFile(c)) return c;
  }
  return "";
}

function safeIsFile(p) {
  try {
    return fs.statSync(p).isFile();
  } catch {
    return false;
  }
}

// Version stamp written next to the binary (no subprocess), mirrors updater.current_version.
function currentVersion() {
  const p = findHashcat();
  const candidates = [];
  if (p) candidates.push(path.join(path.dirname(p), "VERSION"));
  candidates.push(path.join(UPDATE_DIR, "VERSION"));
  for (const vf of candidates) {
    try {
      const v = fs.readFileSync(vf, "utf8").replace(/[^0-9.]/g, "");
      if (v) return v;
    } catch {
      /* ignore */
    }
  }
  return "";
}

const STATIC_HASH_MODES = [
  { id: 22000, name: "WPA-PBKDF2-PMKID+EAPOL", category: "Network Protocol" },
  { id: 16800, name: "WPA-PMKID-PBKDF2", category: "Network Protocol" },
  { id: 0, name: "MD5", category: "Raw Hash" },
  { id: 100, name: "SHA1", category: "Raw Hash" },
  { id: 1400, name: "SHA2-256", category: "Raw Hash" },
  { id: 1700, name: "SHA2-512", category: "Raw Hash" },
  { id: 1000, name: "NTLM", category: "Operating System" },
  { id: 1800, name: "sha512crypt $6$ (Unix)", category: "Operating System" },
  { id: 500, name: "md5crypt $1$ (Unix)", category: "Operating System" },
  { id: 3200, name: "bcrypt $2*$ (Blowfish)", category: "Operating System" },
  { id: 1500, name: "descrypt (DES Unix)", category: "Operating System" },
  { id: 5600, name: "NetNTLMv2", category: "Network Protocol" },
  { id: 13100, name: "Kerberos 5 TGS-REP (etype 23)", category: "Network Protocol" },
  { id: 18200, name: "Kerberos 5 AS-REP (etype 23)", category: "Network Protocol" },
  { id: 2500, name: "WPA-EAPOL-PBKDF2 (legacy hccapx)", category: "Network Protocol" },
  { id: 900, name: "MD4", category: "Raw Hash" },
  { id: 1100, name: "Domain Cached Credentials (DCC)", category: "Operating System" },
  { id: 2100, name: "Domain Cached Credentials 2 (DCC2)", category: "Operating System" },
  { id: 7500, name: "Kerberos 5 AS-REQ Pre-Auth (etype 23)", category: "Network Protocol" },
  { id: 22921, name: "RSA/DSA/EC/OpenSSH Private Keys", category: "Private Key" },
];

// Instant: cached modes if present, else the static fallback. No subprocess.
function loadHashModes() {
  try {
    const cached = JSON.parse(fs.readFileSync(CATALOG_CACHE, "utf8"));
    if (Array.isArray(cached) && cached.length) return cached;
  } catch {
    /* ignore */
  }
  return STATIC_HASH_MODES.slice();
}

// --- Run directory (OpenCL/modules/... linked from the read-only hashcat dir) --
// Port of hashcat_iface.hashcat_workdir(): hashcat resolves its shared folders
// relative to cwd and writes runtime files there, so we run from a writable dir
// with the shared folders linked in (Windows junctions / POSIX symlinks).
const WORK_SKIP = new Set(["hashcat.exe", "hashcat.bin", "kernels", "hashcat.pid",
  "hashcat.induct", "hashcat.log", "hashcat.restore", "hashcat.dictstat2", "hashcat.potfile"]);

function rmLink(dst) {
  try {
    const st = fs.lstatSync(dst);
    if (st.isSymbolicLink()) fs.unlinkSync(dst);
    else if (st.isDirectory()) fs.rmdirSync(dst);
    else fs.unlinkSync(dst);
  } catch {
    /* ignore (missing) */
  }
}
function linkDir(src, dst) {
  rmLink(dst);
  try {
    fs.symlinkSync(src, dst, process.platform === "win32" ? "junction" : "dir");
  } catch {
    /* ignore */
  }
}
function hashcatWorkdir() {
  try {
    fs.mkdirSync(WORKDIR, { recursive: true });
  } catch {
    return DATA_DIR;
  }
  const p = findHashcat();
  const hcDir = p ? path.dirname(p) : "";
  if (!hcDir || !safeIsDir(hcDir)) return WORKDIR;
  const marker = path.join(WORKDIR, ".hcsrc");
  let prev = "";
  try {
    prev = fs.readFileSync(marker, "utf8").trim();
  } catch {
    /* ignore */
  }
  if (prev === hcDir) return WORKDIR; // already prepared for this hashcat
  for (const name of fs.readdirSync(hcDir)) {
    if (WORK_SKIP.has(name)) continue;
    const src = path.join(hcDir, name);
    const dst = path.join(WORKDIR, name);
    try {
      const st = fs.statSync(src);
      if (st.isDirectory()) linkDir(src, dst);
      else if (st.isFile()) fs.copyFileSync(src, dst);
    } catch {
      /* ignore */
    }
  }
  try {
    fs.writeFileSync(marker, hcDir, "utf8");
  } catch {
    /* ignore */
  }
  return WORKDIR;
}

function safeIsDir(p) {
  try {
    return fs.statSync(p).isDirectory();
  } catch {
    return false;
  }
}

// --- live version + --help catalog (subprocess; call off the UI path) ---------
function version(p) {
  p = p || findHashcat();
  if (!p) return "";
  const r = spawnSync(p, ["--version"], { cwd: hashcatWorkdir(), encoding: "utf8", timeout: 20000 });
  return (r.stdout || "").trim();
}

const MODE_ROW = /^\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*$/;
function parseHashModesText(stdout) {
  if (!stdout) return [];
  const modes = [];
  let inSection = false;
  for (const line of stdout.split(/\r?\n/)) {
    if (line.includes("[ Hash modes ]")) {
      inSection = true;
      continue;
    }
    if (inSection) {
      if (line.trim().startsWith("- [") && !line.includes("Hash modes")) break;
      const m = MODE_ROW.exec(line);
      if (m && m[2].toLowerCase() !== "name") {
        modes.push({ id: parseInt(m[1], 10), name: m[2].trim(), category: m[3].trim() });
      }
    }
  }
  return modes;
}
function parseHashModes(p) {
  p = p || findHashcat();
  if (!p) return [];
  const r = spawnSync(p, ["--help"], { cwd: hashcatWorkdir(), encoding: "utf8", timeout: 40000 });
  return parseHashModesText(r.stdout || "");
}
function cacheHashModes(modes) {
  if (modes && modes.length) {
    try {
      fs.writeFileSync(CATALOG_CACHE, JSON.stringify(modes));
    } catch {
      /* ignore */
    }
  }
}

module.exports = {
  findHashcat, currentVersion, loadHashModes, version, parseHashModes, parseHashModesText,
  cacheHashModes, hashcatWorkdir, VENDOR_DIR, UPDATE_DIR, WORKDIR, CATALOG_CACHE, STATIC_HASH_MODES,
};
