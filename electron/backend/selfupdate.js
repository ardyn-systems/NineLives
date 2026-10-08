"use strict";
/* NineLives in-app self-updater — Node port of selfupdate.py.
 * Checks GitHub releases vs the running version and (desktop only) downloads the
 * right asset for this OS. Note: the asset matcher targets the current release
 * names; electron-builder's output names are finalised in Phase 3 packaging. */

const os = require("os");
const path = require("path");
const fs = require("fs");
const crypto = require("crypto");
const { spawn } = require("child_process");
const { getJson, downloadToFile, downloadToBuffer } = require("./download");

const APP_VERSION = require("../package.json").version;
const REPO = "ardyn-systems/NineLives";
const GH_LATEST = `https://api.github.com/repos/${REPO}/releases/latest`;

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

async function latestRelease() {
  try {
    const d = await getJson(GH_LATEST);
    return {
      tag: d.tag_name || "",
      version: norm(d.tag_name || ""),
      notes: d.body || "",
      url: d.html_url || "",
      assets: (d.assets || []).map((a) => ({ name: a.name, url: a.browser_download_url, size: a.size || 0 })),
    };
  } catch {
    return null;
  }
}

function platformAsset(assets) {
  if (process.platform === "win32") {
    return assets.find((a) => /setup/i.test(a.name) && a.name.toLowerCase().endsWith(".exe")) || null;
  }
  if (process.platform === "linux") {
    return assets.find((a) => a.name.toLowerCase().endsWith(".appimage")) || null;
  }
  return null;
}

async function check() {
  const cur = APP_VERSION;
  const rel = await latestRelease();
  if (!rel || !rel.version) return { current: cur, latest: "", available: false, error: "Could not reach GitHub releases." };
  const available = vgt(rel.version, cur);
  return { current: cur, latest: rel.version, available, notes: rel.notes, url: rel.url, asset: available ? platformAsset(rel.assets) : null };
}

// Download the update asset to a temp file, but DON'T install it yet. Returns
// the local path once complete (apply() runs it later, on "Restart NineLives").
async function download(assetUrl, name, progress) {
  const dest = path.join(os.tmpdir(), name);
  await downloadToFile(assetUrl, dest, (p) => progress && progress(`downloading… ${p}%`));
  if (process.platform !== "win32") {
    try { fs.chmodSync(dest, 0o755); } catch { /* ignore */ }
  }
  return dest;
}

// Apply a previously-downloaded update with no user input, then the caller quits
// so the installer can replace files and relaunch.
//  - Windows: run the NSIS installer silently (/S) — no wizard; it closes the
//    running app, installs, and relaunches NineLives.
//  - Linux: launch the downloaded AppImage (the new version) detached.
function applyInstaller(dest) {
  const args = process.platform === "win32" && dest.toLowerCase().endsWith(".exe")
    ? ["/S"] : [];
  spawn(dest, args, { detached: true, stdio: "ignore" }).unref();
  return true;
}

// -1 / 0 / 1 comparison of two version strings.
function compareVersions(a, b) {
  if (vgt(a, b)) return 1;
  if (vgt(b, a)) return -1;
  return 0;
}

// Every published release (newest first), for the version list + rollback.
async function listReleases() {
  const arr = await getJson(`https://api.github.com/repos/${REPO}/releases?per_page=40`);
  if (!Array.isArray(arr)) return [];
  return arr.filter((d) => !d.draft).map((d) => ({
    tag: d.tag_name || "",
    version: norm(d.tag_name || ""),
    name: d.name || d.tag_name || "",
    body: d.body || "",
    url: d.html_url || "",
    date: d.published_at || d.created_at || "",
    prerelease: !!d.prerelease,
    assets: (d.assets || []).map((a) => ({ name: a.name, url: a.browser_download_url, size: a.size || 0 })),
  }));
}

function sumsAssetFor(assets) {
  const want = process.platform === "win32" ? "windows" : process.platform === "linux" ? "linux" : null;
  if (!want) return null;
  return assets.find((a) => /sha256sums/i.test(a.name) && a.name.toLowerCase().includes(want)) || null;
}

function sha256File(file) {
  return new Promise((resolve, reject) => {
    const h = crypto.createHash("sha256");
    const s = fs.createReadStream(file);
    s.on("error", reject);
    s.on("data", (d) => h.update(d));
    s.on("end", () => resolve(h.digest("hex")));
  });
}

// Find a filename's expected hash in a SHA256SUMS file ("<hex>  name" / "<hex> *name").
function expectedHash(sumsText, filename) {
  for (const line of (sumsText || "").split(/\r?\n/)) {
    const m = line.trim().match(/^([0-9a-f]{64})\s+\*?(.+)$/i);
    if (m && m[2].trim() === filename) return m[1].toLowerCase();
  }
  return null;
}

// Download a specific release's asset for this OS and verify its SHA-256 against
// the release's SHA256SUMS file. Resolves to the staged path; throws a message.
// progress(status, pct): status is "downloading" | "verifying".
async function prepare(tag, progress) {
  const releases = await listReleases();
  const rel = releases.find((r) => r.tag === tag || r.version === norm(tag));
  if (!rel) throw new Error("That version isn't on GitHub anymore.");
  const asset = platformAsset(rel.assets);
  if (!asset) throw new Error("No download is available for this platform.");
  if (progress) progress("downloading", 0);
  const dest = path.join(os.tmpdir(), asset.name);
  await downloadToFile(asset.url, dest, (p) => progress && progress("downloading", p));
  let verified = false;
  const sums = sumsAssetFor(rel.assets);
  if (sums) {
    if (progress) progress("verifying", 100);
    const want = expectedHash((await downloadToBuffer(sums.url)).toString("utf8"), asset.name);
    if (want) {
      const got = await sha256File(dest);
      if (got !== want) {
        try { fs.unlinkSync(dest); } catch { /* ignore */ }
        throw new Error("The download's checksum didn't match — it may be corrupted. Try again.");
      }
      verified = true;
    }
  }
  if (process.platform !== "win32") { try { fs.chmodSync(dest, 0o755); } catch { /* ignore */ } }
  return { path: dest, tag: rel.tag, version: rel.version, verified };
}

module.exports = {
  check, download, applyInstaller, APP_VERSION,
  listReleases, prepare, compareVersions, platformAsset, expectedHash,
};
