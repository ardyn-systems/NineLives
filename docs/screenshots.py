"""Capture the screenshots in docs/user-guide.md by driving NineLives with Playwright.

    python -m pip install playwright
    python -m playwright install chromium
    python docs/screenshots.py

Starts NineLives in server mode on a spare port (with NINELIVES_DOCS=1 so the
full desktop UI is shown, not the hosted banner), pre-imports the bundled
wpa-Induction sample so the Captures tab has content, walks the app, and writes
PNGs to docs/images/.
"""

from __future__ import annotations

import os
import sys
import time
import socket
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)
VIEWPORT = {"width": 1280, "height": 880}


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _prep() -> None:
    """Seed settings + a sample capture so the UI has content to photograph."""
    import settings
    import api
    settings.set("acknowledged", True)
    settings.set("ui_theme", "synthwave")
    settings.set("captures_index", [])
    fixture = ROOT / "tests" / "fixtures" / "wpa-Induction.pcap"
    api.Api().import_capture(str(fixture))


def _wait_health(base: str, tries: int = 60) -> None:
    for _ in range(tries):
        try:
            urllib.request.urlopen(base + "/api/health", timeout=1)
            return
        except Exception:  # noqa: BLE001
            time.sleep(0.25)


def main() -> int:
    _prep()
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    env = dict(os.environ, NINELIVES_DOCS="1")
    srv = subprocess.Popen(
        [sys.executable, str(ROOT / "ninelives.py"),
         "--host", "127.0.0.1", "--port", str(port)],
        env=env, cwd=str(ROOT))
    try:
        from playwright.sync_api import sync_playwright
        _wait_health(base)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport=VIEWPORT, device_scale_factor=2)
            page.goto(base, wait_until="load")
            page.wait_for_selector("#attack-seg .seg", timeout=15000)
            page.wait_for_timeout(600)

            def shot(name: str) -> None:
                page.screenshot(path=str(OUT / f"{name}.png"))
                print("wrote", OUT / f"{name}.png")

            shot("overview")

            page.click('.tab[data-view="captures"]')
            page.wait_for_timeout(400)
            shot("captures")

            page.click('.tab[data-view="settings"]')
            page.wait_for_timeout(300)
            shot("settings")

            page.click('.tab[data-view="crack"]')
            page.wait_for_timeout(200)
            page.click("#theme-btn")
            page.wait_for_timeout(300)
            shot("theme-menu")

            browser.close()
        return 0
    finally:
        srv.terminate()


if __name__ == "__main__":
    sys.exit(main())
