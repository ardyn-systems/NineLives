"use strict";
/* hashcat locate + static catalog — partial Node port of hashcat_iface.py.
 * Phase 0: locate the binary and serve the static hash-mode catalog so the UI
 * boots. Running hashcat (spawn + stream) and the live --help catalog land in
 * Phase 1. */

const fs = require("fs");
const path = require("path");
const { APP_DIR, DATA_DIR } = require("./paths");

const VENDOR_DIR = path.join(APP_DIR, "vendor", "hashcat"); // bundled (read-only)
const UPDATE_DIR = path.join(DATA_DIR, "vendor", "hashcat"); // self-update target

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

function loadHashModes() {
  return STATIC_HASH_MODES.slice();
}

module.exports = { findHashcat, currentVersion, loadHashModes, VENDOR_DIR, UPDATE_DIR, STATIC_HASH_MODES };
