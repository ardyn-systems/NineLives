#!/usr/bin/env python3
"""
HashBench launcher.

The app is split into focused modules:
  app.py            - the Tkinter GUI (push-button front-end)
  hashcat_iface.py  - locate/run hashcat, parse --help into a live hash catalog
  compat.py         - attack-mode <-> stackable-option matrix (+ explanations)
  wordlists.py      - SecLists catalog + hash-aware suggestions
  updater.py        - check/install hashcat releases into vendor/
  settings.py       - shared JSON settings
  cracker.py        - optional pure-Python WPA engine (works without hashcat)

Run:  python hashbench.py
"""

from app import main

if __name__ == "__main__":
    main()
