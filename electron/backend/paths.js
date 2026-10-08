"use strict";
/* Filesystem locations — Node port of paths.py.
 * APP_DIR: where the app's bundled resources live (set by the Electron main
 * process via NINELIVES_APP_DIR; defaults to the repo for dev).
 * DATA_DIR: per-user writable dir for settings, potfile, captures, caches. */

const os = require("os");
const path = require("path");
const fs = require("fs");

const APP_DIR = process.env.NINELIVES_APP_DIR || path.resolve(__dirname, "..", "..");
const EXAMPLES_DIR = path.join(APP_DIR, "examples"); // bundled sample capture + wordlist

function dataDir() {
  let root;
  if (process.platform === "win32") root = process.env.LOCALAPPDATA || os.homedir();
  else if (process.platform === "darwin") root = path.join(os.homedir(), "Library", "Application Support");
  else root = process.env.XDG_DATA_HOME || path.join(os.homedir(), ".local", "share");
  const d = path.join(root, "NineLives");
  try {
    fs.mkdirSync(d, { recursive: true });
  } catch {
    return APP_DIR;
  }
  return d;
}

const DATA_DIR = dataDir();

module.exports = { APP_DIR, DATA_DIR, EXAMPLES_DIR };
