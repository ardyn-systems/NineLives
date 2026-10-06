#!/usr/bin/env python3
"""
HashBench capture extractor — pure-Python, no external tools.

Reads a packet capture (pcap / pcapng, incl. radiotap or raw 802.11), finds
WPA/WPA2 material (PMKID from the first handshake message, and 4-way-handshake
MICs), associates each to its network (BSSID + ESSID), and emits hashcat mode
22000 lines:

    WPA*01*PMKID*MAC_AP*MAC_STA*ESSID***                       (PMKID)
    WPA*02*MIC*MAC_AP*MAC_STA*ESSID*ANONCE*EAPOL*MESSAGEPAIR    (EAPOL)

The 22000 line already carries the AP MAC and ESSID, so "associate to a device"
falls out of the format. Verified end-to-end against the public wpa-Induction
sample (ESSID "Coherer", passphrase "Induction").

For AUTHORIZED auditing of captures from networks you own or are scoped to test.
"""

import os
import struct
import binascii

# ----- link-layer types -----
LINKTYPE_ETHERNET = 1
LINKTYPE_IEEE802_11 = 105
LINKTYPE_IEEE802_11_RADIOTAP = 127


# --------------------------------------------------------------------------- #
# Capture file readers -> yield (linktype, packet_bytes)
# --------------------------------------------------------------------------- #
def _iter_pcap(data):
    if len(data) < 24:
        return
    magic = data[:4]
    if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1"):
        end = "<"
    elif magic in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d"):
        end = ">"
    else:
        return
    linktype = struct.unpack(end + "I", data[20:24])[0]
    off = 24
    n = len(data)
    while off + 16 <= n:
        _ts, _tu, caplen, _origlen = struct.unpack(end + "IIII", data[off:off + 16])
        off += 16
        if caplen < 0 or off + caplen > n:
            break
        yield linktype, data[off:off + caplen]
        off += caplen


def _iter_pcapng(data):
    off, n = 0, len(data)
    if_linktypes = []
    while off + 12 <= n:
        btype, blen = struct.unpack("<II", data[off:off + 8])
        if blen < 12 or off + blen > n:
            break
        body = data[off + 8:off + blen - 4]
        if btype == 0x00000001:  # Interface Description Block
            lt = struct.unpack("<H", body[0:2])[0]
            if_linktypes.append(lt)
        elif btype == 0x00000006:  # Enhanced Packet Block
            iface, _th, _tl, caplen, _orig = struct.unpack("<IIIII", body[0:20])
            pkt = body[20:20 + caplen]
            lt = if_linktypes[iface] if iface < len(if_linktypes) else LINKTYPE_IEEE802_11
            yield lt, pkt
        elif btype == 0x00000003:  # Simple Packet Block
            caplen = struct.unpack("<I", body[0:4])[0]
            pkt = body[4:4 + caplen]
            lt = if_linktypes[0] if if_linktypes else LINKTYPE_IEEE802_11
            yield lt, pkt
        off += blen


def read_packets(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:4] == b"\x0a\x0d\x0d\x0a":
        yield from _iter_pcapng(data)
    else:
        yield from _iter_pcap(data)


# --------------------------------------------------------------------------- #
# 802.11 framing
# --------------------------------------------------------------------------- #
def _strip_to_dot11(linktype, pkt):
    if linktype == LINKTYPE_IEEE802_11_RADIOTAP:
        if len(pkt) < 4:
            return None
        rtlen = struct.unpack("<H", pkt[2:4])[0]
        return pkt[rtlen:] if rtlen <= len(pkt) else None
    if linktype == LINKTYPE_IEEE802_11:
        return pkt
    return None  # ethernet handled separately if ever needed


def _mac(b):
    return b


class Dot11:
    __slots__ = ("type", "subtype", "to_ds", "from_ds", "protected",
                 "addr1", "addr2", "addr3", "body")

    @staticmethod
    def parse(f):
        if len(f) < 24:
            return None
        fc0, fc1 = f[0], f[1]
        d = Dot11()
        d.type = (fc0 >> 2) & 0x3
        d.subtype = (fc0 >> 4) & 0xF
        d.to_ds = bool(fc1 & 0x01)
        d.from_ds = bool(fc1 & 0x02)
        d.protected = bool(fc1 & 0x40)
        d.addr1 = f[4:10]
        d.addr2 = f[10:16]
        d.addr3 = f[16:22]
        hdr = 24
        if d.to_ds and d.from_ds:
            hdr += 6  # addr4 (WDS)
        if d.type == 2 and (d.subtype & 0x08):  # QoS data
            hdr += 2
        d.body = f[hdr:]
        return d


# SSID from a beacon/probe-resp/assoc frame body (tagged params after fixed part)
def _ssid_from_mgmt(subtype, body):
    # fixed params before tagged IEs:
    #   beacon(8)/probe-resp(5): 12 bytes (timestamp8 + interval2 + caps2)
    #   assoc-req(0): 4 (caps2 + listen2);  reassoc-req(2): 10
    fixed = {8: 12, 5: 12, 0: 4, 2: 10, 1: 6, 3: 6}.get(subtype)
    if fixed is None or len(body) < fixed:
        return None
    i = fixed
    while i + 2 <= len(body):
        tag, tlen = body[i], body[i + 1]
        val = body[i + 2:i + 2 + tlen]
        if tag == 0:  # SSID
            return val
        i += 2 + tlen
    return None


# --------------------------------------------------------------------------- #
# EAPOL-Key parsing
# --------------------------------------------------------------------------- #
_LLC_EAPOL = b"\xaa\xaa\x03\x00\x00\x00\x88\x8e"


def _eapol_from_body(body):
    """Return the 802.1X frame bytes if this data body carries EAPOL."""
    idx = body.find(_LLC_EAPOL)
    if idx == -1:
        return None
    return body[idx + len(_LLC_EAPOL):]


def _pmkid_from_keydata(kd):
    """Find a PMKID KDE (dd len 00-0F-AC 04 <16>) in key data."""
    i = 0
    while i + 2 <= len(kd):
        tag, tlen = kd[i], kd[i + 1]
        val = kd[i + 2:i + 2 + tlen]
        if tag == 0xDD and tlen == 0x14 and val[:4] == b"\x00\x0f\xac\x04":
            pmkid = val[4:20]
            if pmkid != b"\x00" * 16:
                return pmkid
        i += 2 + tlen
    return None


class _HS:
    def __init__(self):
        self.essid = None
        self.anonce = None
        self.pmkid = None
        self.mic = None
        self.eapol = None       # M2 802.1X frame, MIC zeroed
        self.keyver = 2


def extract(path):
    """Parse a capture → structured networks + hashcat 22000 lines."""
    essid_by_bssid = {}
    handshakes = {}            # (ap, sta) -> _HS

    for linktype, pkt in read_packets(path):
        f = _strip_to_dot11(linktype, pkt)
        if not f:
            continue
        d = Dot11.parse(f)
        if d is None:
            continue

        if d.type == 0 and d.subtype in (8, 5, 0, 2):   # mgmt w/ SSID
            ssid = _ssid_from_mgmt(d.subtype, d.body)
            if ssid:
                bssid = d.addr3
                if ssid.strip(b"\x00"):
                    essid_by_bssid[bssid] = ssid
            continue

        if d.type != 2:
            continue
        x = _eapol_from_body(d.body)
        if not x or len(x) < 95 or x[1] != 0x03:   # 802.1X type 3 = Key
            continue

        desc_type = x[4]               # 2 = RSN (WPA2), 254 = WPA1
        key_info = struct.unpack(">H", x[5:7])[0]
        ack = bool(key_info & 0x0080)
        mic_set = bool(key_info & 0x0100)
        nonce = x[17:49]
        kd_len = struct.unpack(">H", x[97:99])[0] if len(x) >= 99 else 0
        key_data = x[99:99 + kd_len]

        ap = d.addr3
        sta = d.addr1 if d.addr1 != ap else d.addr2
        hs = handshakes.setdefault((ap, sta), _HS())
        hs.essid = hs.essid or essid_by_bssid.get(ap)
        hs.keyver = (key_info & 0x07) or hs.keyver

        if ack and not mic_set:            # M1 (from AP)
            hs.anonce = hs.anonce or nonce
            if desc_type == 2:             # PMKID KDE is RSN(WPA2)-only
                pm = _pmkid_from_keydata(key_data)
                if pm:
                    hs.pmkid = pm
        elif ack and mic_set:              # M3 (from AP) also carries ANonce
            hs.anonce = hs.anonce or nonce
        elif mic_set and not ack:          # M2 / M4 (from STA)
            if kd_len > 0 and nonce.strip(b"\x00"):   # M2 has SNonce + RSN IE
                mic = x[81:97]
                frame = bytearray(x[:99 + kd_len])
                frame[81:97] = b"\x00" * 16            # zero MIC for the hash
                hs.mic = mic
                hs.eapol = bytes(frame)

    return _assemble(essid_by_bssid, handshakes)


def _assemble(essid_by_bssid, handshakes):
    networks = {}
    lines = []
    for (ap, sta), hs in handshakes.items():
        essid = hs.essid or essid_by_bssid.get(ap)
        if not essid:
            continue  # ESSID is the PBKDF2 salt; without it we can't crack
        apx, stax, esx = ap.hex(), sta.hex(), essid.hex()
        net = networks.setdefault(ap.hex(":"), {
            "bssid": ap.hex(":"), "essid": _txt(essid),
            "pmkid": False, "handshake": False, "lines": []})
        if hs.pmkid:
            ln = f"WPA*01*{hs.pmkid.hex()}*{apx}*{stax}*{esx}***"
            lines.append(ln)
            net["pmkid"] = True
            net["lines"].append(ln)
        if hs.anonce and hs.mic and hs.eapol and hs.keyver != 3:
            ln = (f"WPA*02*{hs.mic.hex()}*{apx}*{stax}*{esx}*"
                  f"{hs.anonce.hex()}*{hs.eapol.hex()}*00")
            lines.append(ln)
            net["handshake"] = True
            net["lines"].append(ln)
    return {"networks": list(networks.values()), "hc22000": "\n".join(lines)}


def _txt(b):
    try:
        return b.decode("utf-8")
    except Exception:  # noqa: BLE001
        return b.hex()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: python captures.py <capture.pcap[ng]> [out.hc22000]")
        raise SystemExit(2)
    res = extract(sys.argv[1])
    for net in res["networks"]:
        flags = []
        if net["pmkid"]:
            flags.append("PMKID")
        if net["handshake"]:
            flags.append("handshake")
        print(f"  {net['bssid']}  {net['essid']!r:20} {'+'.join(flags) or '-'}")
    print(f"\n{len(res['hc22000'].splitlines())} hash line(s)")
    if len(sys.argv) > 2 and res["hc22000"]:
        with open(sys.argv[2], "w") as fh:
            fh.write(res["hc22000"] + "\n")
        print("wrote", sys.argv[2])
