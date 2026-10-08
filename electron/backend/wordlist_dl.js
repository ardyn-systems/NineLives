"use strict";
/* On-demand wordlist downloads — Node port of wordlist_dl.py.
 * Installs into the writable per-user wordlists dir; the catalog indexes them. */

const fs = require("fs");
const path = require("path");
const zlib = require("zlib");
const { DOWNLOADED } = require("./wordlists");
const { downloadToFile, downloadToBuffer } = require("./download");

const RAW = "https://raw.githubusercontent.com/danielmiessler/SecLists/master/";
const SECLISTS_REPO = "https://github.com/danielmiessler/SecLists";

const CATALOG = [
  { id: "rockyou", name: "rockyou.txt", desc: "14.3M real leaked passwords. Best first try for WPA and most hashes — start here.",
    size: "≈134 MB", kind: "tgz", url: RAW + "Passwords/Leaked-Databases/rockyou.txt.tar.gz",
    member: "rockyou.txt", subpath: "Leaked-Databases/rockyou.txt" },
  { id: "xato-10m", name: "xato-net-10-million-passwords.txt", desc: "~5M passwords (Mark Burnett's corpus). A broad general-purpose follow-up when rockyou misses.",
    size: "≈48 MB", kind: "txt", url: RAW + "Passwords/Common-Credentials/xato-net-10-million-passwords.txt",
    subpath: "Common-Credentials/xato-net-10-million-passwords.txt" },
  { id: "darkc0de", name: "darkc0de.txt", desc: "~1.7M mixed passwords. Extra coverage for WPA and web logins.",
    size: "≈15 MB", kind: "txt", url: RAW + "Passwords/darkc0de.txt", subpath: "darkc0de.txt" },
  { id: "seclists-full", name: "SecLists (full collection)",
    desc: "The entire SecLists repo (multi-GB). Clone it, then point the folder above at your checkout.",
    size: "multi-GB", kind: "link", url: SECLISTS_REPO },
];

function target(item) {
  return path.join(DOWNLOADED, item.subpath);
}
function installed(item) {
  if (item.kind === "link") return false;
  try {
    return fs.statSync(target(item)).isFile();
  } catch {
    return false;
  }
}
function catalog() {
  return CATALOG.map((it) => ({
    id: it.id, name: it.name, desc: it.desc, size: it.size, kind: it.kind, url: it.url, installed: installed(it),
  }));
}
function byId(id) {
  return CATALOG.find((it) => it.id === id) || null;
}

// Extract one member (by name suffix) from a gzipped tar buffer → dest.
function extractTgzMember(buf, memberSuffix, dest) {
  const tar = zlib.gunzipSync(buf);
  let off = 0;
  while (off + 512 <= tar.length) {
    const header = tar.subarray(off, off + 512);
    const name = header.subarray(0, 100).toString("utf8").replace(/\0.*$/, "");
    if (name === "") break; // end-of-archive (zero block)
    const sizeStr = header.subarray(124, 136).toString("utf8").replace(/\0.*$/, "").trim();
    const size = parseInt(sizeStr, 8) || 0;
    const dataStart = off + 512;
    if (name.endsWith(memberSuffix)) {
      fs.writeFileSync(dest, tar.subarray(dataStart, dataStart + size));
      return true;
    }
    off = dataStart + Math.ceil(size / 512) * 512;
  }
  return false;
}

async function install(id, progress) {
  const item = byId(id);
  if (!item) throw new Error(`unknown wordlist: ${id}`);
  if (item.kind === "link") throw new Error(`${item.name} is not an in-app download; clone it from ${item.url}.`);
  const dest = target(item);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  if (item.kind === "tgz") {
    if (progress) progress(`fetching ${item.name}…`);
    const buf = await downloadToBuffer(item.url, (p) => progress && progress(`downloading… ${p}%`));
    if (progress) progress("extracting…");
    if (!extractTgzMember(buf, item.member, dest)) throw new Error(`${item.member} not found in archive`);
  } else {
    if (progress) progress(`fetching ${item.name}…`);
    await downloadToFile(item.url, dest, (p) => progress && progress(`downloading… ${p}%`));
  }
  if (progress) progress(`installed ${item.name}.`);
  return dest;
}

module.exports = { CATALOG, catalog, installed, install };
