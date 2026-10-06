#!/usr/bin/env python3
"""
HashBench built-in WPA/WPA2 cracking engine.

Pure standard-library (hashlib/hmac/multiprocessing) implementation of the
PMKID and 4-way-handshake MIC checks, so the app can crack WPA/WPA2-PSK
captures with no external hashcat install and identical behavior on Windows
and Linux.

It consumes the same hashcat `-m 22000` line format produced by
`hcxpcapngtool`, so your existing capture workflow is unchanged:

    WPA*TYPE*PMKID_OR_MIC*MAC_AP*MAC_STA*ESSID*ANONCE*EAPOL*MESSAGEPAIR

TYPE 01 = PMKID, TYPE 02 = EAPOL (4-way handshake MIC).

For AUTHORIZED auditing of networks you own or are scoped to test.
"""

import os
import sys
import hmac
import time
import hashlib
import binascii
import multiprocessing as mp


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def _unhex(s):
    return binascii.unhexlify(s) if s else b""


class Target:
    """One crackable item parsed from an hc22000 line."""

    def __init__(self, kind, mac_ap, mac_sta, essid, pmkid=None,
                 mic=None, anonce=None, eapol=None, keyver=2):
        self.kind = kind            # "pmkid" or "eapol"
        self.mac_ap = mac_ap        # 6 bytes
        self.mac_sta = mac_sta      # 6 bytes
        self.essid = essid          # bytes (used as PBKDF2 salt)
        self.pmkid = pmkid          # 16 bytes
        self.mic = mic              # 16 bytes
        self.anonce = anonce        # 32 bytes
        self.eapol = eapol          # full 802.1X frame, MIC field zeroed
        self.keyver = keyver        # 1=HMAC-MD5, 2=HMAC-SHA1, 3=AES-CMAC

    @property
    def essid_str(self):
        try:
            return self.essid.decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return repr(self.essid)

    def label(self):
        return f"[{self.kind}] {self.essid_str} ({self.mac_ap.hex(':')})"

    # --- the actual crypto check -----------------------------------------
    def pmk(self, passphrase):
        return hashlib.pbkdf2_hmac(
            "sha1", passphrase.encode("utf-8", "ignore"), self.essid, 4096, 32)

    def check(self, passphrase, pmk=None):
        """Return True if passphrase matches this capture."""
        if pmk is None:
            pmk = self.pmk(passphrase)
        if self.kind == "pmkid":
            calc = hmac.new(pmk, b"PMK Name" + self.mac_ap + self.mac_sta,
                            hashlib.sha1).digest()[:16]
            return calc == self.pmkid
        # 4-way handshake: derive KCK, recompute MIC over the EAPOL frame
        if self.keyver == 3:
            return False  # AES-128-CMAC not supported by built-in engine
        snonce = self.eapol[17:49]
        amac, smac = self.mac_ap, self.mac_sta
        b = (min(amac, smac) + max(amac, smac)
             + min(self.anonce, snonce) + max(self.anonce, snonce))
        ptk = _prf512(pmk, b"Pairwise key expansion", b)
        kck = ptk[:16]
        digest = hashlib.md5 if self.keyver == 1 else hashlib.sha1
        calc = hmac.new(kck, self.eapol, digest).digest()[:16]
        return calc == self.mic


def _prf512(key, label, data):
    """IEEE 802.11 PRF-512 used to expand the PMK into the PTK."""
    out = b""
    i = 0
    while len(out) < 64:
        out += hmac.new(key, label + b"\x00" + data + bytes([i]),
                        hashlib.sha1).digest()
        i += 1
    return out[:64]


def parse_hc22000(path):
    """Parse an hc22000 file into a list of Target objects."""
    targets = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line.startswith("WPA*"):
                continue
            p = line.split("*")
            if len(p) < 9:
                continue
            _, typ, h3, mac_ap, mac_sta, essid, anonce, eapol, _mp = p[:9]
            mac_ap, mac_sta = _unhex(mac_ap), _unhex(mac_sta)
            essid = _unhex(essid)
            if typ == "01":
                targets.append(Target("pmkid", mac_ap, mac_sta, essid,
                                      pmkid=_unhex(h3)))
            elif typ == "02":
                eapol_b = bytearray(_unhex(eapol))
                keyver = 2
                if len(eapol_b) >= 7:
                    key_info = int.from_bytes(eapol_b[5:7], "big")
                    keyver = key_info & 0x07 or 2
                # zero the 16-byte MIC field (offset 81) before recomputing
                if len(eapol_b) >= 97:
                    eapol_b[81:97] = b"\x00" * 16
                targets.append(Target("eapol", mac_ap, mac_sta, essid,
                                      mic=_unhex(h3), anonce=_unhex(anonce),
                                      eapol=bytes(eapol_b), keyver=keyver))
    return targets


# --------------------------------------------------------------------------- #
# Wordlist iteration
# --------------------------------------------------------------------------- #
def iter_words(paths):
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    w = line.rstrip("\r\n")
                    if w:
                        yield w
        except OSError:
            continue


def _chunks(iterable, size):
    buf = []
    for item in iterable:
        buf.append(item)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


# --- multiprocessing worker (module-level so it pickles on Windows) -------- #
_WORKER_TARGET = None


def _init_worker(target):
    global _WORKER_TARGET
    _WORKER_TARGET = target


def _scan_chunk(words):
    t = _WORKER_TARGET
    for w in words:
        if t.check(w):
            return w
    return None


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
def crack(target, wordlist_paths, progress=None, should_stop=None,
          workers=None, chunk_size=2000):
    """
    Try every word against `target`.

    progress(tried, found_or_None, rate) is called periodically.
    should_stop() -> bool lets a GUI cancel.
    Returns the matching passphrase, or None.
    """
    if not workers:
        workers = max(1, os.cpu_count() or 1)
    start = time.time()
    tried = 0

    # Single-process path (simpler, used when workers == 1)
    if workers == 1:
        for w in iter_words(wordlist_paths):
            if should_stop and should_stop():
                return None
            tried += 1
            if target.check(w):
                if progress:
                    progress(tried, w, tried / max(1e-6, time.time() - start))
                return w
            if progress and tried % 1000 == 0:
                progress(tried, None, tried / max(1e-6, time.time() - start))
        if progress:
            progress(tried, None, tried / max(1e-6, time.time() - start))
        return None

    # Parallel path
    pool = mp.Pool(processes=workers, initializer=_init_worker,
                   initargs=(target,))
    try:
        chunk_iter = _chunks(iter_words(wordlist_paths), chunk_size)
        for result in pool.imap_unordered(_scan_chunk, chunk_iter):
            if should_stop and should_stop():
                pool.terminate()
                return None
            tried += chunk_size
            if result is not None:
                pool.terminate()
                if progress:
                    progress(tried, result,
                             tried / max(1e-6, time.time() - start))
                return result
            if progress:
                progress(tried, None, tried / max(1e-6, time.time() - start))
        return None
    finally:
        pool.close()
        pool.join()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _cli(argv):
    if len(argv) < 3:
        print("usage: python cracker.py <hash.hc22000> <wordlist> [wordlist2 ...]")
        return 2
    targets = parse_hc22000(argv[1])
    if not targets:
        print("No WPA targets parsed from", argv[1])
        return 1
    wordlists = argv[2:]
    for t in targets:
        print(f"\n>>> {t.label()}")

        def prog(tried, found, rate):
            if found is None:
                print(f"\r    tried {tried:,}  ({rate:,.0f}/s)", end="", flush=True)

        hit = crack(t, wordlists, progress=prog)
        print()
        if hit:
            print(f"    [+] RECOVERED: {hit}")
        else:
            print("    [-] not found in supplied wordlist(s)")
    return 0


if __name__ == "__main__":
    mp.freeze_support()
    sys.exit(_cli(sys.argv))
