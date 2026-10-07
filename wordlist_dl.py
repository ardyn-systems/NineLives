#!/usr/bin/env python3
"""
NineLives on-demand wordlist downloader.

The app bundles only a small starter set (so the installer stays lean and first
launch is fast). The big lists — rockyou and friends — are fetched on request
from Settings into the writable per-user wordlists dir, where the catalog picks
them up alongside the bundled set.

Nothing here runs automatically: the GUI calls install() when the user clicks a
download. Downloads are always an explicit user action, over HTTPS from the
SecLists project.
"""

import os
import io
import tarfile
import shutil
import tempfile
import urllib.request

import wordlists

# Downloads land in the writable per-user dir (the install dir is read-only);
# wordlists.Catalog indexes this alongside the bundled starter set.
DEST = wordlists.DOWNLOADED_WORDLISTS
RAW = "https://raw.githubusercontent.com/danielmiessler/SecLists/master/"
SECLISTS_REPO = "https://github.com/danielmiessler/SecLists"
UA = {"User-Agent": "NineLives-wordlist-dl"}

# The downloadable catalog. `subpath` is where the list lands under DEST (and so
# how it shows up in the dropdowns). `kind`: "txt" is a plain file; "tgz" is a
# gzipped tarball from which `member` is extracted; "link" is not downloaded
# in-app (too large / needs git) and is surfaced as a link instead.
CATALOG = [
    {
        "id": "rockyou",
        "name": "rockyou.txt",
        "desc": "14.3M real leaked passwords — the classic WPA/general list.",
        "size": "≈134 MB",
        "kind": "tgz",
        "url": RAW + "Passwords/Leaked-Databases/rockyou.txt.tar.gz",
        "member": "rockyou.txt",
        "subpath": "Leaked-Databases/rockyou.txt",
    },
    {
        "id": "xato-10m",
        "name": "xato-net-10-million-passwords.txt",
        "desc": "Mark Burnett's ~5M-password corpus — broad general-purpose list.",
        "size": "≈48 MB",
        "kind": "txt",
        "url": RAW + "Passwords/Common-Credentials/xato-net-10-million-passwords.txt",
        "subpath": "Common-Credentials/xato-net-10-million-passwords.txt",
    },
    {
        "id": "darkc0de",
        "name": "darkc0de.txt",
        "desc": "Long-standing WPA/web mixed list (~1.7M entries).",
        "size": "≈15 MB",
        "kind": "txt",
        "url": RAW + "Passwords/darkc0de.txt",
        "subpath": "darkc0de.txt",
    },
    {
        "id": "seclists-full",
        "name": "SecLists (full collection)",
        "desc": "The entire SecLists repo (multi-GB). Clone it, then point the "
                "folder above at your checkout.",
        "size": "multi-GB",
        "kind": "link",
        "url": SECLISTS_REPO,
    },
]


def _target(item):
    return os.path.join(DEST, item["subpath"])


def installed(item):
    """True if this list is already present in the download dir."""
    return item.get("kind") != "link" and os.path.isfile(_target(item))


def catalog():
    """The downloadable catalog with an `installed` flag on each item."""
    out = []
    for it in CATALOG:
        entry = {k: it[k] for k in ("id", "name", "desc", "size", "kind", "url")}
        entry["installed"] = installed(it)
        out.append(entry)
    return out


def _by_id(item_id):
    for it in CATALOG:
        if it["id"] == item_id:
            return it
    return None


def _download(url, dest, progress=None, timeout=120):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        total = int(r.headers.get("Content-Length", 0))
        got = 0
        with open(dest, "wb") as fh:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                fh.write(chunk)
                got += len(chunk)
                if progress and total:
                    progress(f"downloading… {got * 100 // total}%")
    return dest


def install(item_id, progress=None):
    """Download `item_id` into the per-user wordlists dir. Returns the installed
    file path. `progress(msg)` receives human-readable status lines."""
    item = _by_id(item_id)
    if not item:
        raise ValueError(f"unknown wordlist: {item_id!r}")
    if item["kind"] == "link":
        raise ValueError(f"{item['name']} is not an in-app download; clone it "
                         f"from {item['url']}.")
    target = _target(item)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmpdir = tempfile.mkdtemp(prefix="ninelives_wl_")
    try:
        if item["kind"] == "tgz":
            if progress:
                progress(f"fetching {item['name']}…")
            arc = _download(item["url"], os.path.join(tmpdir, "wl.tar.gz"),
                            progress=progress)
            if progress:
                progress("extracting…")
            with open(arc, "rb") as fh, \
                    tarfile.open(fileobj=io.BytesIO(fh.read()), mode="r:gz") as tf:
                member = next((m for m in tf.getmembers()
                               if m.name.endswith(item["member"])), None)
                if not member:
                    raise RuntimeError(f"{item['member']} not found in archive")
                with tf.extractfile(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        else:  # plain txt
            if progress:
                progress(f"fetching {item['name']}…")
            _download(item["url"], target, progress=progress)
        if progress:
            progress(f"installed {item['name']}.")
        return target
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    import json
    print(json.dumps(catalog(), indent=2))
