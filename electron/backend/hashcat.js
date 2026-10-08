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
// hashcat 6 listed modes in `--help` under "[ Hash modes ]"; hashcat 7 moved the
// full table to `-hh` under "[ Hash Modes ]" (capital M). Match either, then
// read "<id> | <name> | <category>" rows until the next "- [ … ]" section.
function parseHashModesText(stdout) {
  if (!stdout) return [];
  const modes = [];
  let inSection = false;
  for (const line of stdout.split(/\r?\n/)) {
    if (!inSection) {
      if (line.toLowerCase().includes("[ hash modes ]")) inSection = true;
      continue;
    }
    if (line.trim().startsWith("- [")) break; // next section
    const m = MODE_ROW.exec(line);
    if (m && m[2].toLowerCase() !== "name") {
      modes.push({ id: parseInt(m[1], 10), name: m[2].trim(), category: m[3].trim() });
    }
  }
  return modes;
}
function parseHashModes(p) {
  p = p || findHashcat();
  if (!p) return [];
  // -hh emits the full hash-mode table on hashcat 7 (and still works on 6).
  const r = spawnSync(p, ["-hh"], { cwd: hashcatWorkdir(), encoding: "utf8", timeout: 40000 });
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

// Parse `hashcat -I` (backend info) into a flat device list. Handles the
// CUDA / HIP / Metal / OpenCL sections and their "Backend Device ID #N" blocks.
// CUDA/HIP/Metal devices are GPUs; OpenCL devices carry an explicit Type.
function parseDevicesText(stdout) {
  const devices = [];
  let backend = "";
  let cur = null;
  const flush = () => { if (cur) { devices.push(cur); cur = null; } };
  for (const raw of (stdout || "").split(/\r?\n/)) {
    const line = raw.trimEnd();
    const bk = line.match(/^\s*(CUDA|HIP|Metal|OpenCL)\s+Info:/i);
    if (bk) { flush(); backend = bk[1]; continue; }
    if (/OpenCL Platform ID #/i.test(line)) { flush(); continue; }
    const dev = line.match(/Backend Device ID #(\d+)(?:\s*\(Alias:\s*#(\d+)\))?/i);
    if (dev) {
      flush();
      cur = { id: parseInt(dev[1], 10), backend,
        name: "", type: /opencl/i.test(backend) ? "" : "GPU",
        alias: dev[2] ? parseInt(dev[2], 10) : null };
      continue;
    }
    if (!cur) continue;
    const nm = line.match(/^\s*Name\.*\s*:\s*(.+)$/);
    if (nm) { cur.name = nm[1].trim(); continue; }
    const ty = line.match(/^\s*Type\.*\s*:\s*(\w+)/);
    if (ty) {
      const t = ty[1].toUpperCase();
      cur.type = t.includes("GPU") ? "GPU" : t.includes("CPU") ? "CPU" : ty[1];
    }
  }
  flush();
  // Drop OpenCL aliases of a CUDA/HIP device (same physical card, lower-id
  // primary wins), then de-dupe by id and sort.
  const seen = new Map();
  for (const d of devices) {
    if (d.alias) continue;
    if (d.id && !seen.has(d.id)) { delete d.alias; seen.set(d.id, d); }
  }
  return [...seen.values()].sort((a, b) => a.id - b.id);
}

function listDevices(p) {
  p = p || findHashcat();
  if (!p) return { devices: [], error: "hashcat not found" };
  try {
    const r = spawnSync(p, ["-I"], { cwd: hashcatWorkdir(), encoding: "utf8", timeout: 30000 });
    const out = `${r.stdout || ""}\n${r.stderr || ""}`;
    return { devices: parseDevicesText(out) };
  } catch (e) {
    return { devices: [], error: e.message || String(e) };
  }
}

module.exports = {
  findHashcat, currentVersion, loadHashModes, version, parseHashModes, parseHashModesText,
  cacheHashModes, hashcatWorkdir, listDevices, parseDevicesText,
  VENDOR_DIR, UPDATE_DIR, WORKDIR, CATALOG_CACHE, STATIC_HASH_MODES,
};
