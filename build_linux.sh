#!/usr/bin/env bash
# Build the Ubuntu/Linux NineLives bundle (tarball).
#
# Prereqs:  sudo apt install p7zip-full git python3-gi gir1.2-webkit2-4.1
#           (gir1.2-webkit2-4.0 on older Ubuntu) — pywebview's GTK/WebKit backend
#           python3 -m pip install pyinstaller py7zr pywebview
#
# Usage:    bash build_linux.sh            # curated wordlists
#           bash build_linux.sh --full     # entire SecLists (large)
#           NOFETCH=1 bash build_linux.sh  # skip (re)downloading
set -euo pipefail
cd "$(dirname "$0")"

python3 -m pip install --quiet --upgrade pyinstaller py7zr pywebview

if [ "${NOFETCH:-0}" != "1" ]; then
  echo "== Fetching latest hashcat (into vendor/hashcat) =="
  python3 fetch_hashcat.py
  echo "== Fetching wordlists (into vendor/wordlists) =="
  if [ "${1:-}" = "--full" ]; then python3 fetch_wordlists.py --full; \
     else python3 fetch_wordlists.py; fi
fi

ADD_DATA=(--add-data "webui:webui")
if [ -d vendor ]; then ADD_DATA+=(--add-data "vendor:vendor"); fi

echo "== Building with PyInstaller =="
pyinstaller --noconfirm --windowed --name NineLives \
  --collect-all webview \
  "${ADD_DATA[@]}" \
  ninelives.py

echo "== Packaging tarball =="
( cd dist && tar czf NineLives-linux-x86_64.tar.gz NineLives )
echo "Built: dist/NineLives/NineLives"
echo "Tarball: dist/NineLives-linux-x86_64.tar.gz"
