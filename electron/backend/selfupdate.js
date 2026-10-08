"use strict";
/* NineLives in-app self-updater — Node port of selfupdate.py.
 * Checks GitHub releases vs the running version and (desktop only) downloads the
 * right asset for this OS. Note: the asset matcher targets the current release
 * names; electron-builder's output names are finalised in Phase 3 packaging. */

const os = require("os");
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");
const { getJson, downloadToFile } = require("./download");

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

async function downloadAndLaunch(assetUrl, name, progress) {
  const dest = path.join(os.tmpdir(), name);
  await downloadToFile(assetUrl, dest, (p) => progress && progress(`downloading… ${p}%`));
  if (process.platform === "win32" && name.toLowerCase().endsWith(".exe")) {
    spawn(dest, [], { detached: true, stdio: "ignore" }).unref();
    return { path: dest, quit: true };
  }
  try {
    fs.chmodSync(dest, 0o755);
  } catch {
    /* ignore */
  }
  return { path: dest, quit: false };
}

module.exports = { check, downloadAndLaunch, APP_VERSION };
