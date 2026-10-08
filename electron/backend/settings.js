"use strict";
/* Shared JSON settings — Node port of settings.py. Stored in DATA_DIR. */

const fs = require("fs");
const path = require("path");
const { DATA_DIR } = require("./paths");

const FILE = path.join(DATA_DIR, "settings.json");

function readAll() {
  try {
    return JSON.parse(fs.readFileSync(FILE, "utf8"));
  } catch {
    return {};
  }
}

function get(key, fallback = null) {
  const all = readAll();
  return Object.prototype.hasOwnProperty.call(all, key) ? all[key] : fallback;
}

function set(key, value) {
  const all = readAll();
  all[key] = value;
  try {
    fs.writeFileSync(FILE, JSON.stringify(all, null, 2), "utf8");
  } catch {
    /* ignore */
  }
}

module.exports = { get, set, FILE };
