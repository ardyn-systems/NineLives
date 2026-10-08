"use strict";
/*
 * De-risk test for the pcap→WPA-22000 extractor port.
 *
 * Validates electron/backend/captures.js against:
 *  1. the known ground truth of the wpa-Induction fixture (ESSID "Coherer"), and
 *  2. the Python captures.py output on the same file — byte-for-byte, so the
 *     Node port is a faithful replacement, not merely "close".
 *
 * Run: node electron/test/captures.test.js   (exit 0 = pass)
 */

const path = require("path");
const assert = require("assert");
const { execFileSync } = require("child_process");
const captures = require("../backend/captures");

const REPO = path.resolve(__dirname, "..", "..");
const FIXTURE = path.join(REPO, "tests", "fixtures", "wpa-Induction.pcap");

function pass(name) {
  console.log("PASS " + name);
}

// 1) ground truth
const res = captures.extract(FIXTURE);
const byEssid = Object.fromEntries(res.networks.map((n) => [n.essid, n]));
assert.ok(byEssid["Coherer"], "expected the Coherer network");
assert.strictEqual(byEssid["Coherer"].bssid, "00:0c:41:82:b2:55", "Coherer BSSID");
assert.ok(byEssid["Coherer"].handshake, "expected a 4-way handshake");
assert.ok(res.hc22000.includes("WPA*02*"), "expected a 22000 EAPOL line");
pass("Coherer handshake extracted");

// 2) byte-for-byte parity with captures.py
const py = execFileSync(
  "python",
  ["-c", "import json,captures,sys; print(json.dumps(captures.extract(sys.argv[1])))", FIXTURE],
  { cwd: REPO, encoding: "utf8" }
);
const ref = JSON.parse(py);
assert.strictEqual(res.hc22000, ref.hc22000, "hc22000 must match captures.py exactly");
assert.strictEqual(
  JSON.stringify(res.networks),
  JSON.stringify(ref.networks),
  "networks must match captures.py exactly"
);
pass("byte-for-byte parity with captures.py");

console.log("\nall captures port tests passed");
