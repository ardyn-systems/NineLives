# NineLives — Electron

This is the **shipping** NineLives app (as of v1.0.0): Electron (Chromium) with a
Node backend. Releases are built and published by [`.github/workflows/electron.yml`](../.github/workflows/electron.yml)
on `v*` tags. The original Python build at the repo root is kept for reference but
is no longer shipped.

A fresh install ships a **bundled example** ([`../examples/`](../examples)) — a
sample WPA capture (pre-loaded in Captures) and a demo wordlist — so it cracks
`Coherer` → `Induction` out of the box with no setup.

## Layout

```
electron/
  main.js            Electron main process (window + IPC)
  preload.js         contextBridge → window.nlapi (invoke + event push)
  backend/           Node port of the Python backend
    captures.js        pcap/pcapng → WPA 22000 extractor (port of captures.py)
    compat.js          attack-mode ↔ option matrix (port of compat.py)
    wordlists.js       SecLists catalog + suggestions (port of wordlists.py)
    hashcat.js         locate hashcat + static catalog (partial hashcat_iface.py)
    themes.js          theme metadata (port of themes.py)
    settings.js        JSON settings (port of settings.py)
    paths.js           APP_DIR / DATA_DIR
    api.js             the methods the renderer calls (port of api.py)
  test/
    captures.test.js   byte-for-byte parity of captures.js vs captures.py
```

The renderer reuses the existing `../webui/` (index.html, styles.css, app.js);
`app.js` prefers the Electron `window.nlapi` bridge and falls back to HTTP fetch
for the Python build, so one UI serves both during the migration.

## Run / test

```bash
cd electron
npm install            # fetches Electron (binary via its postinstall)
npm start              # launch the app
npm test               # captures parity test (needs python on PATH)
NINELIVES_SMOKE=1 npm run smoke   # boot the window headless-ish, print state, exit
```

## Status

- **Phase 0 (this):** scaffold + Node backend foundation (settings, themes,
  compat, wordlists catalog, static hash catalog) + the **Captures tab working**
  (pcap import via the ported extractor) + the window boots the UI over IPC.
  The pcap extractor is validated byte-for-byte against `captures.py`.
- **Phase 1 ✅:** hashcat run + **live output streaming** (spawn → `hbOutput`/
  `hbDone` over IPC), the live `--help` catalog (background refresh → `hbCatalog`),
  and `hashcatWorkdir` (OpenCL junctions via `fs.symlinkSync('junction')`).
  Proven in the Electron window: a crack streams its output and recovers the
  Coherer passphrase (`Induction`).
- **Phase 2 ✅:** wordlist downloads (`wordlist_dl.js`, incl. a minimal tar.gz
  extractor for rockyou), hashcat updater (`updater.js`, 7z CLI), and self-update
  check (`selfupdate.js`), all streaming progress over IPC. A shared
  redirect-following HTTP helper (`download.js`) backs them.
- **Phase 3 ✅:** packaging with electron-builder (NSIS installer + AppImage),
  `extraResources` for webui/vendor, and a CI workflow (`.github/workflows/
  electron.yml`) that builds the installers and smoke-tests the **packaged** app
  (captures parity test too). hashcat/wordlists are stubbed here; full vendor
  bundling + release wiring land at cutover.
- **Phase 4 ✅:** cutover — Electron is the shipped app (v1.0.0); bundled examples
  for out-of-box cracking; `v*` tags build + release the Electron installers; the
  Python build is archived.
