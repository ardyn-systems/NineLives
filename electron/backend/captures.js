"use strict";
/*
 * NineLives capture extractor — Node port of captures.py (pure JS, no tools).
 *
 * Reads a pcap / pcapng capture (radiotap or raw 802.11), finds WPA/WPA2
 * material (PMKID from message 1, and 4-way-handshake MICs), associates each to
 * its network (BSSID + ESSID), and emits hashcat mode 22000 lines:
 *
 *   WPA*01*PMKID*MAC_AP*MAC_STA*ESSID***                      (PMKID)
 *   WPA*02*MIC*MAC_AP*MAC_STA*ESSID*ANONCE*EAPOL*MESSAGEPAIR   (EAPOL)
 *
 * Behaviour matches captures.py one-for-one; validated against the public
 * wpa-Induction fixture (ESSID "Coherer", passphrase "Induction").
 */

const fs = require("fs");

const LINKTYPE_IEEE802_11 = 105;
const LINKTYPE_IEEE802_11_RADIOTAP = 127;

const LLC_EAPOL = Buffer.from([0xaa, 0xaa, 0x03, 0x00, 0x00, 0x00, 0x88, 0x8e]);

function hex(buf) {
  return Buffer.from(buf).toString("hex");
}
function macHex(buf) {
  // colon-separated, matching Python's bytes.hex(":")
  return Array.from(buf, (b) => b.toString(16).padStart(2, "0")).join(":");
}
function isAllZero(buf) {
  for (const b of buf) if (b !== 0) return false;
  return true;
}
function stripZeros(buf) {
  // mimic Python bytes.strip(b"\x00"): true if any non-zero byte remains
  return !isAllZero(buf);
}

// ----- capture readers: yield {linktype, pkt(Buffer)} -----
function* iterPcap(data) {
  if (data.length < 24) return;
  const magic = data.subarray(0, 4);
  let le;
  const m = magic.toString("hex");
  if (m === "d4c3b2a1" || m === "4d3cb2a1") le = true;
  else if (m === "a1b2c3d4" || m === "a1b23c4d") le = false;
  else return;
  const u32 = (o) => (le ? data.readUInt32LE(o) : data.readUInt32BE(o));
  const linktype = u32(20);
  let off = 24;
  const n = data.length;
  while (off + 16 <= n) {
    const caplen = u32(off + 8);
    off += 16;
    if (caplen < 0 || off + caplen > n) break;
    yield { linktype, pkt: data.subarray(off, off + caplen) };
    off += caplen;
  }
}

function* iterPcapng(data) {
  let off = 0;
  const n = data.length;
  const ifLinktypes = [];
  while (off + 12 <= n) {
    const btype = data.readUInt32LE(off);
    const blen = data.readUInt32LE(off + 4);
    if (blen < 12 || off + blen > n) break;
    const body = data.subarray(off + 8, off + blen - 4);
    if (btype === 0x00000001) {
      // Interface Description Block
      ifLinktypes.push(body.readUInt16LE(0));
    } else if (btype === 0x00000006) {
      // Enhanced Packet Block
      const iface = body.readUInt32LE(0);
      const caplen = body.readUInt32LE(12);
      const pkt = body.subarray(20, 20 + caplen);
      const lt = iface < ifLinktypes.length ? ifLinktypes[iface] : LINKTYPE_IEEE802_11;
      yield { linktype: lt, pkt };
    } else if (btype === 0x00000003) {
      // Simple Packet Block
      const caplen = body.readUInt32LE(0);
      const pkt = body.subarray(4, 4 + caplen);
      const lt = ifLinktypes.length ? ifLinktypes[0] : LINKTYPE_IEEE802_11;
      yield { linktype: lt, pkt };
    }
    off += blen;
  }
}

function* readPackets(path) {
  const data = fs.readFileSync(path);
  if (data.length >= 4 && data.subarray(0, 4).toString("hex") === "0a0d0d0a") {
    yield* iterPcapng(data);
  } else {
    yield* iterPcap(data);
  }
}

// ----- 802.11 framing -----
function stripToDot11(linktype, pkt) {
  if (linktype === LINKTYPE_IEEE802_11_RADIOTAP) {
    if (pkt.length < 4) return null;
    const rtlen = pkt.readUInt16LE(2);
    return rtlen <= pkt.length ? pkt.subarray(rtlen) : null;
  }
  if (linktype === LINKTYPE_IEEE802_11) return pkt;
  return null;
}

function parseDot11(f) {
  if (f.length < 24) return null;
  const fc0 = f[0];
  const fc1 = f[1];
  const d = {
    type: (fc0 >> 2) & 0x3,
    subtype: (fc0 >> 4) & 0xf,
    toDs: !!(fc1 & 0x01),
    fromDs: !!(fc1 & 0x02),
    protected: !!(fc1 & 0x40),
    addr1: f.subarray(4, 10),
    addr2: f.subarray(10, 16),
    addr3: f.subarray(16, 22),
  };
  let hdr = 24;
  if (d.toDs && d.fromDs) hdr += 6; // addr4 (WDS)
  if (d.type === 2 && d.subtype & 0x08) hdr += 2; // QoS data
  d.body = f.subarray(hdr);
  return d;
}

// SSID from a beacon/probe-resp/assoc frame body (tagged params after fixed part)
const MGMT_FIXED = { 8: 12, 5: 12, 0: 4, 2: 10, 1: 6, 3: 6 };
function ssidFromMgmt(subtype, body) {
  const fixed = MGMT_FIXED[subtype];
  if (fixed === undefined || body.length < fixed) return null;
  let i = fixed;
  while (i + 2 <= body.length) {
    const tag = body[i];
    const tlen = body[i + 1];
    const val = body.subarray(i + 2, i + 2 + tlen);
    if (tag === 0) return val; // SSID
    i += 2 + tlen;
  }
  return null;
}

// ----- EAPOL-Key parsing -----
function eapolFromBody(body) {
  const idx = body.indexOf(LLC_EAPOL);
  if (idx === -1) return null;
  return body.subarray(idx + LLC_EAPOL.length);
}

function pmkidFromKeydata(kd) {
  let i = 0;
  while (i + 2 <= kd.length) {
    const tag = kd[i];
    const tlen = kd[i + 1];
    const val = kd.subarray(i + 2, i + 2 + tlen);
    if (tag === 0xdd && tlen === 0x14 && val.subarray(0, 4).toString("hex") === "000fac04") {
      const pmkid = val.subarray(4, 20);
      if (!isAllZero(pmkid)) return pmkid;
    }
    i += 2 + tlen;
  }
  return null;
}

function extract(path) {
  const essidByBssid = new Map(); // bssidHex -> essid Buffer
  const handshakes = new Map(); // "apHex|staHex" -> hs

  for (const { linktype, pkt } of readPackets(path)) {
    const f = stripToDot11(linktype, pkt);
    if (!f) continue;
    const d = parseDot11(f);
    if (!d) continue;

    if (d.type === 0 && [8, 5, 0, 2].includes(d.subtype)) {
      const ssid = ssidFromMgmt(d.subtype, d.body);
      if (ssid && stripZeros(ssid)) essidByBssid.set(hex(d.addr3), ssid);
      continue;
    }
    if (d.type !== 2) continue;

    const x = eapolFromBody(d.body);
    if (!x || x.length < 95 || x[1] !== 0x03) continue; // 802.1X type 3 = Key

    const descType = x[4]; // 2 = RSN (WPA2), 254 = WPA1
    const keyInfo = x.readUInt16BE(5);
    const ack = !!(keyInfo & 0x0080);
    const micSet = !!(keyInfo & 0x0100);
    const nonce = x.subarray(17, 49);
    const kdLen = x.length >= 99 ? x.readUInt16BE(97) : 0;
    const keyData = x.subarray(99, 99 + kdLen);

    const ap = d.addr3;
    const sta = Buffer.compare(d.addr1, ap) !== 0 ? d.addr1 : d.addr2;
    const key = hex(ap) + "|" + hex(sta);
    let hs = handshakes.get(key);
    if (!hs) {
      hs = { essid: null, anonce: null, pmkid: null, mic: null, eapol: null, keyver: 2 };
      handshakes.set(key, hs);
    }
    hs.essid = hs.essid || essidByBssid.get(hex(ap)) || null;
    hs.keyver = (keyInfo & 0x07) || hs.keyver;

    if (ack && !micSet) {
      // M1 (from AP)
      hs.anonce = hs.anonce || nonce;
      if (descType === 2) {
        const pm = pmkidFromKeydata(keyData);
        if (pm) hs.pmkid = pm;
      }
    } else if (ack && micSet) {
      // M3 (from AP) also carries ANonce
      hs.anonce = hs.anonce || nonce;
    } else if (micSet && !ack) {
      // M2 / M4 (from STA)
      if (kdLen > 0 && stripZeros(nonce)) {
        const mic = x.subarray(81, 97);
        const frame = Buffer.from(x.subarray(0, 99 + kdLen)); // copy
        frame.fill(0, 81, 97); // zero MIC for the hash
        hs.mic = mic;
        hs.eapol = frame;
      }
    }
  }

  return assemble(essidByBssid, handshakes);
}

function assemble(essidByBssid, handshakes) {
  const networks = new Map(); // bssidColon -> net
  const lines = [];
  for (const [key, hs] of handshakes) {
    const apHex = key.split("|")[0];
    const staHex = key.split("|")[1];
    const essid = hs.essid || essidByBssid.get(apHex);
    if (!essid) continue; // ESSID is the PBKDF2 salt; without it we can't crack
    const apBuf = Buffer.from(apHex, "hex");
    const esx = hex(essid);
    const bssidColon = macHex(apBuf);
    let net = networks.get(bssidColon);
    if (!net) {
      net = { bssid: bssidColon, essid: txt(essid), pmkid: false, handshake: false, lines: [] };
      networks.set(bssidColon, net);
    }
    if (hs.pmkid) {
      const ln = `WPA*01*${hex(hs.pmkid)}*${apHex}*${staHex}*${esx}***`;
      lines.push(ln);
      net.pmkid = true;
      net.lines.push(ln);
    }
    if (hs.anonce && hs.mic && hs.eapol) {
      const ln = `WPA*02*${hex(hs.mic)}*${apHex}*${staHex}*${esx}*${hex(hs.anonce)}*${hex(hs.eapol)}*00`;
      lines.push(ln);
      net.handshake = true;
      net.lines.push(ln);
    }
  }
  return { networks: Array.from(networks.values()), hc22000: lines.join("\n") };
}

function txt(buf) {
  // decode UTF-8, falling back to hex (matches captures.py _txt)
  const s = buf.toString("utf8");
  if (Buffer.from(s, "utf8").equals(Buffer.from(buf))) return s;
  return hex(buf);
}

module.exports = { extract, readPackets };
