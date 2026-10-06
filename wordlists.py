#!/usr/bin/env python3
"""
HashBench wordlist catalog + hash-aware suggestions.

Point it once at your SecLists checkout (Settings in the GUI). It indexes every
wordlist into a browsable catalog for the dropdowns, and - given the hash mode
you're cracking - surfaces the lists most likely to work first, so you're not
scrolling thousands of files.

No uploading: everything comes from the SecLists folder you already have.
"""

import os
import settings

WORDLIST_EXTS = (".txt", ".lst", ".dic", ".wordlist")

# Wordlists shipped inside the app bundle (populated at build time by
# fetch_wordlists.py). Used by default when the user hasn't set their own root.
BUNDLED_WORDLISTS = os.path.join(settings.APP_DIR, "vendor", "wordlists")

# Curated "best first" picks by SecLists relative path. If a file exists in the
# user's checkout it's offered as a top suggestion for the matching hash family.
# Paths are matched case-insensitively and by suffix, so minor layout drift in
# SecLists releases still resolves.
CURATED = {
    "wifi": [
        "Passwords/WiFi-WPA/probable-v2-wpa-top4800.txt",
        "Passwords/WiFi-WPA/probable-v2-wpa-top62.txt",
        "Passwords/Leaked-Databases/rockyou.txt",
        "Passwords/WiFi-WPA/darkc0de.txt",
    ],
    "os_creds": [
        "Passwords/Leaked-Databases/rockyou.txt",
        "Passwords/Common-Credentials/10-million-password-list-top-1000000.txt",
        "Passwords/Common-Credentials/best1050.txt",
        "Usernames/top-usernames-shortlist.txt",
    ],
    "raw_fast": [
        "Passwords/Leaked-Databases/rockyou.txt",
        "Passwords/xato-net-10-million-passwords.txt",
        "Passwords/Common-Credentials/10-million-password-list-top-1000000.txt",
    ],
    "web": [
        "Passwords/Leaked-Databases/rockyou.txt",
        "Passwords/Common-Credentials/10k-most-common.txt",
    ],
    "general": [
        "Passwords/Leaked-Databases/rockyou.txt",
    ],
}


def _family_for(mode):
    """Map a hash mode (dict with name/category) to a curated family key."""
    name = (mode.get("name") or "").lower()
    cat = (mode.get("category") or "").lower()
    if "wpa" in name or "pmkid" in name or "eapol" in name:
        return "wifi"
    if any(k in name for k in ("ntlm", "kerberos", "crypt", "dcc", "netntlm")) \
            or "operating system" in cat:
        return "os_creds"
    if any(k in name for k in ("md5", "sha1", "sha2", "md4")) or "raw hash" in cat:
        return "raw_fast"
    if "http" in name or "web" in name:
        return "web"
    return "general"


class Catalog:
    def __init__(self):
        # user-chosen root wins; otherwise fall back to bundled wordlists
        self.root = settings.get("seclists_root", "")
        if not self.root and os.path.isdir(BUNDLED_WORDLISTS):
            self.root = BUNDLED_WORDLISTS
        self.index = []  # list of {name, path, category, size}

    # --- discovery --------------------------------------------------------
    def set_root(self, path):
        self.root = path
        settings.set("seclists_root", path)
        self.scan()

    def scan(self):
        """Index every wordlist under the SecLists root, grouped by folder."""
        self.index = []
        if not self.root or not os.path.isdir(self.root):
            return 0
        for dirpath, _dirs, files in os.walk(self.root):
            for f in files:
                if f.lower().endswith(WORDLIST_EXTS):
                    full = os.path.join(dirpath, f)
                    try:
                        size = os.path.getsize(full)
                    except OSError:
                        size = 0
                    self.index.append({
                        "name": f,
                        "path": full,
                        "category": os.path.basename(dirpath) or "misc",
                        "size": size,
                    })
        self.index.sort(key=lambda e: (e["category"].lower(), e["name"].lower()))
        return len(self.index)

    # --- lookups ----------------------------------------------------------
    def all_entries(self):
        return self.index

    def categories(self):
        return sorted({e["category"] for e in self.index})

    def _resolve_curated(self, rel):
        """Find a curated relative path within the index by suffix match."""
        rel_norm = rel.replace("\\", "/").lower()
        tail = rel_norm.split("/")[-1]
        # exact suffix match first, then filename-only match
        for e in self.index:
            p = e["path"].replace("\\", "/").lower()
            if p.endswith(rel_norm):
                return e
        for e in self.index:
            if e["name"].lower() == tail:
                return e
        return None

    def suggest(self, mode):
        """Return (suggested_entries, family) for a hash mode dict."""
        fam = _family_for(mode)
        picks, seen = [], set()
        for rel in CURATED.get(fam, []):
            e = self._resolve_curated(rel)
            if e and e["path"] not in seen:
                picks.append(e)
                seen.add(e["path"])
        return picks, fam
