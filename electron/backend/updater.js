"use strict";
/* hashcat auto-updater — Node port of updater.py.
 * Checks hashcat's latest release and installs it into the writable UPDATE_DIR
 * (findHashcat prefers that over the bundled copy). The archive is a .7z whose
 * BCJ2 filter needs the real 7-Zip CLI, so extraction shells out to 7z/7za. */

const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");
const hashcat = require("./hashcat");
const { getJson, downloadToFile } = require("./download");

const VENDOR_DIR = hashcat.UPDATE_DIR;
const GITHUB_LATEST = "https://api.github.com/repos/hashcat/hashcat/releases/latest";
const DL_TEMPLATE = (ver) => `https://hashcat.net/files/hashcat-${ver}.7z`;
const FALLBACK = "6.2.6";

const norm = (v) => (v || "").replace(/[^0-9.]/g, "");
const vtuple = (v) => norm(v).split(".").filter((x) => x !== "").map((x) => parseInt(x, 10));
function vgt(a, b) {
  const A = vtuple(a), B = vtuple(b);
  for (let i = 0; i < Math.max(A.length, B.length); i++) {
    const x = A[i] || 0, y = B[i] || 0;
    if (x !== y) return x > y;
  }
  return false;
}

async function latestVersion() {
  try {
    const d = await getJson(GITHUB_LATEST);
    return norm(d.tag_name || "");
  } catch {
    return "";
  }
}

function currentVersion() {
  return hashcat.currentVersion();
}

async function check() {
  const cur = currentVersion();
  const lat = await latestVersion();
  const avail = !!lat && (!cur || vgt(lat, cur));
  return { current: cur, latest: lat, update_available: avail, have_hashcat: !!hashcat.findHashcat() };
}

function find7z() {
  const cands = ["7z", "7za", "C:/Program Files/7-Zip/7z.exe", "C:/Program Files (x86)/7-Zip/7z.exe"];
  for (const c of cands) {
    const r = spawnSync(c, ["--help"], { encoding: "utf8" });
    if (r.status === 0 || (r.stdout || "").length) return c;
  }
  return null;
}

function extract7z(archive, into) {
  const exe = find7z();
  if (!exe) throw new Error("Need 7-Zip (7z/7za) on PATH to extract the hashcat archive (BCJ2 filter).");
  const r = spawnSync(exe, ["x", "-y", `-o${into}`, archive], { encoding: "utf8" });
  if (r.status !== 0) throw new Error(`7z extraction failed: ${(r.stderr || r.stdout || "").slice(0, 200)}`);
}

async function install(version, progress, dest = VENDOR_DIR) {
  version = norm(version) || (await latestVersion()) || FALLBACK;
  const versionFile = path.join(dest, "VERSION");
  fs.mkdirSync(dest, { recursive: true });
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "ninelives_hc_"));
  try {
    if (progress) progress(`fetching hashcat ${version}…`);
    const archive = path.join(tmp, `hashcat-${version}.7z`);
    await downloadToFile(DL_TEMPLATE(version), archive, (p) => progress && progress(`downloading… ${p}%`));
    if (progress) progress("extracting…");
    const staging = path.join(tmp, "x");
    fs.mkdirSync(staging, { recursive: true });
    extract7z(archive, staging);
    // hashcat archives extract to a hashcat-<ver>/ folder; flatten it.
    const entries = fs.readdirSync(staging).map((e) => path.join(staging, e));
    const src = entries.length === 1 && fs.statSync(entries[0]).isDirectory() ? entries[0] : staging;
    if (progress) progress(`installing into ${dest}…`);
    // clear the old copy
    for (const e of fs.readdirSync(dest)) fs.rmSync(path.join(dest, e), { recursive: true, force: true });
    for (const e of fs.readdirSync(src)) fs.renameSync(path.join(src, e), path.join(dest, e));
    fs.writeFileSync(versionFile, version);
    for (const n of ["hashcat.bin", "hashcat"]) {
      const p = path.join(dest, n);
      try {
        if (fs.statSync(p).isFile()) fs.chmodSync(p, 0o755);
      } catch {
        /* ignore */
      }
    }
    if (progress) progress(`installed hashcat ${version}.`);
    return version;
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
}

module.exports = { check, install, latestVersion, currentVersion, VENDOR_DIR };
