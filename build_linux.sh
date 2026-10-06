#!/usr/bin/env bash
# Build the Ubuntu/Linux HashBench bundle (tarball).
#
# Prereqs:  sudo apt install python3-tk p7zip-full git
#           python3 -m pip install pyinstaller py7zr
#
# Usage:    bash build_linux.sh            # curated wordlists
#           bash build_linux.sh --full     # entire SecLists (large)
#           NOFETCH=1 bash build_linux.sh  # skip (re)downloading
set -euo pipefail
cd "$(dirname "$0")"

python3 -m pip install --quiet --upgrade pyinstaller py7zr

if [ "${NOFETCH:-0}" != "1" ]; then
  echo "== Fetching latest hashcat (into vendor/hashcat) =="
  python3 fetch_hashcat.py
  echo "== Fetching wordlists (into vendor/wordlists) =="
  if [ "${1:-}" = "--full" ]; then python3 fetch_wordlists.py --full; \
     else python3 fetch_wordlists.py; fi
  echo "== Fetching fonts (into vendor/fonts) =="
  python3 fetch_fonts.py
fi

ADD_DATA=()
if [ -d vendor ]; then ADD_DATA+=(--add-data "vendor:vendor"); fi

echo "== Building with PyInstaller =="
pyinstaller --noconfirm --windowed --name HashBench \
  --collect-submodules tkinter \
  "${ADD_DATA[@]}" \
  hashbench.py

echo "== Packaging tarball =="
( cd dist && tar czf HashBench-linux-x86_64.tar.gz HashBench )
echo "Built: dist/HashBench/HashBench"
echo "Tarball: dist/HashBench-linux-x86_64.tar.gz"
