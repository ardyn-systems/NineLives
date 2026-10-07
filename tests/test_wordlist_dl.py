"""
Tests for the on-demand wordlist downloader and multi-root catalog scan.

No network: these cover the catalog shape, the `installed` flag, and that
wordlists.Catalog indexes the bundled + downloaded dirs together.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import wordlists
import wordlist_dl


def test_catalog_shape_and_installed_flag():
    items = wordlist_dl.catalog()
    assert items, "expected a non-empty download catalog"
    ids = {i["id"] for i in items}
    assert "rockyou" in ids
    for it in items:
        for key in ("id", "name", "desc", "size", "kind", "installed"):
            assert key in it, f"{it.get('id')} missing {key}"
    # Nothing downloaded in a clean checkout, so real file-backed items are not
    # installed; the external "link" item is never "installed".
    link = next(i for i in items if i["kind"] == "link")
    assert link["installed"] is False


def test_installed_true_when_file_present(tmp_path, monkeypatch):
    dest = tmp_path / "wl"
    monkeypatch.setattr(wordlist_dl, "DEST", str(dest))
    rockyou = next(it for it in wordlist_dl.CATALOG if it["id"] == "rockyou")
    target = dest / rockyou["subpath"]
    assert wordlist_dl.installed(rockyou) is False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("password\n", encoding="utf-8")
    assert wordlist_dl.installed(rockyou) is True


def test_catalog_scans_bundled_and_downloaded(tmp_path, monkeypatch):
    bundled = tmp_path / "bundled"
    downloaded = tmp_path / "downloaded"
    (bundled / "WiFi-WPA").mkdir(parents=True)
    (downloaded / "Leaked-Databases").mkdir(parents=True)
    (bundled / "WiFi-WPA" / "starter.txt").write_text("a\nb\n", encoding="utf-8")
    (downloaded / "Leaked-Databases" / "rockyou.txt").write_text("c\n", encoding="utf-8")

    monkeypatch.setattr(wordlists, "BUNDLED_WORDLISTS", str(bundled))
    monkeypatch.setattr(wordlists, "DOWNLOADED_WORDLISTS", str(downloaded))

    cat = wordlists.Catalog()
    cat.root = ""  # no user SecLists folder
    n = cat.scan()
    names = {e["name"] for e in cat.all_entries()}
    assert n == 2
    assert {"starter.txt", "rockyou.txt"} <= names


def test_scan_dedups_same_file_across_roots(tmp_path, monkeypatch):
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "list.txt").write_text("x\n", encoding="utf-8")
    # user root and bundled both point at the same folder
    monkeypatch.setattr(wordlists, "BUNDLED_WORDLISTS", str(shared))
    monkeypatch.setattr(wordlists, "DOWNLOADED_WORDLISTS", str(shared))
    cat = wordlists.Catalog()
    cat.root = str(shared)
    n = cat.scan()
    assert n == 1, "the same file reached via several roots should list once"


if __name__ == "__main__":
    test_catalog_shape_and_installed_flag()
    print("catalog shape: OK")
