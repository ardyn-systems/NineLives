"""
End-to-end test for the pure-Python capture extractor.

Uses the public wpa-Induction sample (Wireshark SampleCaptures; ESSID "Coherer",
passphrase "Induction") as ground truth: the extractor must pull the WPA2 4-way
handshake and the built-in cracker must recover the known passphrase from it.

Run:  python -m pytest tests/ -q      (or: python tests/test_captures.py)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import captures
import cracker

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "wpa-Induction.pcap")


def test_extracts_coherer_handshake():
    res = captures.extract(FIXTURE)
    nets = {n["essid"]: n for n in res["networks"]}
    assert "Coherer" in nets, "expected the Coherer network to be found"
    assert nets["Coherer"]["handshake"], "expected a 4-way handshake"
    assert nets["Coherer"]["bssid"] == "00:0c:41:82:b2:55"


def test_handshake_cracks_to_known_passphrase():
    res = captures.extract(FIXTURE)
    eapol = [t for t in captures_parse(res["hc22000"]) if t.kind == "eapol"]
    assert eapol, "expected an EAPOL target in the 22000 output"
    # tiny wordlist containing the known answer
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write("password\nInduction\nletmein\n")
        wl = fh.name
    try:
        hit = cracker.crack(eapol[0], [wl], workers=1)
    finally:
        os.unlink(wl)
    assert hit == "Induction", f"expected 'Induction', got {hit!r}"


def captures_parse(hc22000_text):
    """Write the 22000 text to a temp file and parse it into Targets."""
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".hc22000", delete=False) as fh:
        fh.write(hc22000_text + "\n")
        path = fh.name
    try:
        return cracker.parse_hc22000(path)
    finally:
        os.unlink(path)


if __name__ == "__main__":
    test_extracts_coherer_handshake()
    print("extract: OK (Coherer handshake found)")
    test_handshake_cracks_to_known_passphrase()
    print("crack:   OK (recovered 'Induction')")
    print("\nall tests passed")
