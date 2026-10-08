# NineLives

<p align="center">
  <img src="brand/ninelives-master.png" alt="NineLives" width="380">
</p>

A push-button GUI front-end for **hashcat**, for authorized password auditing.

It wraps hashcat (doesn't replace it) and stays in sync with it: the hash-type
list and options come from hashcat itself, and the bundled hashcat engine
auto-updates. Pick a hash type, pick an attack, pick a wordlist from a dropdown,
click Run.

**Download:** [Releases](https://github.com/ardyn-systems/NineLives/releases)
(Windows installer/portable, Linux AppImage/tarball).
**Docs:** [User guide](docs/user-guide.md) · [Hosting](docs/hosting.md).
Any UI change updates the guide + screenshots in the same PR
(`python docs/screenshots.py`).

> **The desktop app is an Electron app** (Chromium + a Node backend) as of
> v1.0.0 — see [`electron/`](electron/README.md). Releases are the Electron
> installers (Windows NSIS `.exe`, Linux AppImage), and they ship a **bundled
> example** (a sample WPA capture + a demo wordlist) so a fresh install cracks out
> of the box. The repo also keeps the original **Python** code: it no longer
> builds the desktop app, but it still powers the **hosted** web deployment
> (`ninelives.py --host`, see [Hosted / server mode](#hosted--server-mode)).

## Design goals (and how they're met)

| Goal | How |
|------|-----|
| One codebase → Windows **and** Ubuntu builds | Electron + a Node backend; `electron-builder` makes the NSIS installer and the AppImage |
| Bundles hashcat, **updates when hashcat updates** | `electron/backend/updater.js` checks hashcat's releases and installs into `vendor/` |
| Options stay current automatically | `electron/backend/hashcat.js` parses `hashcat -hh` for the live hash-mode catalog (cached, with a static fallback) |
| SecLists from **dropdowns**, no uploading | `electron/backend/wordlists.js` indexes the bundled starter set, on-demand downloads, and your own SecLists folder |
| **Suggested wordlists** per hash type | the wordlist catalog maps the hash family → best-first lists (★ in the dropdown) |
| **Every option explained** | `electron/backend/compat.js` carries plain-language labels + descriptions (shown inline and on hover) |
| **Stackable options, no guessing** | `electron/backend/compat.js` encodes the attack-mode → compatible-option matrix; the UI shows only options that legally combine with the chosen `-a` mode |
| **Updates itself**, safely | `electron/backend/selfupdate.js` lists GitHub releases and installs a chosen version after verifying its SHA-256 checksum |

## Modules

**Desktop app (Electron):**

```
electron/main.js      Electron main: window + IPC (nl-invoke) and event push (nl-event)
electron/preload.js   exposes nlapi.invoke / nlapi.onEvent to the page
electron/backend/     the Node backend the UI calls:
  api.js              crack, extract, catalog, settings, updates, device list
  hashcat.js          locate/run hashcat; parse -hh → live hash catalog; hashcat -I devices
  compat.js           attack-mode ↔ stackable-option matrix + plain-language labels
  wordlists.js        SecLists catalog (bundled + downloaded + your own) + suggestions
  wordlist_dl.js      on-demand wordlist downloads (rockyou etc.)
  updater.js          check/install hashcat releases into vendor/
  selfupdate.js       in-app NineLives updater (GitHub releases, checksum-verified)
  captures.js         extract WPA/WPA2 PMKID + 4-way handshakes from pcap/cap
  themes.js settings.js paths.js download.js   theme tokens, JSON settings, paths, HTTPS helpers
webui/                the shared front-end — index.html, styles.css, app.js
```

**Hosted web server (Python):** `ninelives.py --host` serves `webui/` over HTTP
for the explore + extract deployment; `server.py`, `api.py`, `compat.py`,
`wordlists.py`, etc. are its backend — a Python mirror of the Node modules that
shares the same `webui/`.

**Architecture.** The **desktop app** is Electron: a Chromium window loads
`webui/`, and the page calls the Node backend over Electron IPC
(`nlapi.invoke` → `ipcMain.handle("nl-invoke")`), with server-pushed output
(live hashcat lines, catalog refresh, download progress) streamed back on the
`nl-event` channel. No pywebview, no local HTTP server, no JS↔Python bridge.

The **hosted** deployment instead runs the Python server (`ninelives.py --host`),
serving the same `webui/` over HTTP for explore + extract — cracking and
filesystem actions are disabled there. `webui/styles.css` carries the six
shipping themes as `[data-theme]` token sets (easter-egg themes excluded).

The attack-mode ↔ option matrix lives in `electron/backend/compat.js` (and its
Python twin `compat.py`); `python compat.py` dumps it to the terminal.

## Requirements

- **To use it:** nothing — download the installer/AppImage from
  [Releases](https://github.com/ardyn-systems/NineLives/releases). hashcat and a
  starter wordlist set are bundled.
- **To build the desktop app:** **Node 18+** and npm.
- **To run the hosted server / from source (Python):** **Python 3.8+** (standard
  library only); `py7zr` or a `7z`/`7za` CLI only if you bundle/update hashcat.

## Run from source

Desktop app (Electron):

```bash
cd electron && npm install && npm start
```

First launch asks for authorized-use confirmation. If hashcat isn't present yet,
the dropdowns still work offline from the static catalog; install hashcat from
**Settings → Updates** (or bundle it first). The hosted Python server is under
[Hosted / server mode](#hosted--server-mode).

## Hosted / server mode

The same UI can run as a web server for an **explore + extract** deployment —
import a capture, pull its WPA hashes, and download the `.hc22000`. **Cracking
is disabled when hosted** (no server-side hashcat/GPU); it stays in the desktop
app.

```bash
python ninelives.py --host 0.0.0.0 --port 8000   # then open http://localhost:8000
```

### Live demo (Render)

One-click deploy your own hosted instance with the included
[`render.yaml`](render.yaml):

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/ardyn-systems/NineLives)

Render reads the blueprint and spins up a free **explore + extract** web
service (no GPU, no server-side cracking). Full details in
[docs/hosting.md](docs/hosting.md).

## Bundling: hashcat + a wordlist starter set ship inside the app

The build fetches these into `vendor/` and embeds them, so an installed copy
cracks out of the box:

```bash
python fetch_hashcat.py          # latest hashcat (binary + rules) -> vendor/hashcat/
python fetch_wordlists.py        # small STARTER wordlists (~8 MB) -> vendor/wordlists/
python fetch_wordlists.py --full # OR the entire SecLists (multi-GB installer)
```

> hashcat ships **rules**, not wordlists. The big wordlists (rockyou, SecLists)
> are large, so the default bundle is only a **small starter set** (top WPA +
> common-credential lists, a few MB) — this keeps the installer lean and avoids
> a slow first launch while antivirus scans a 130 MB rockyou. The big lists are
> **downloaded on demand** from the **Settings** tab (`wordlist_dl.py`) into the
> writable per-user data dir, where the catalog indexes them automatically. Use
> `--full` to bake all of SecLists into the build instead, or point Settings at
> your own SecLists folder.
>
> The Electron installer replaces the bundled `vendor/` on upgrade, so updating
> drops the old bundled lists rather than leaving them behind. Lists you
> downloaded yourself live under `%LOCALAPPDATA%\NineLives` and are never touched.

## Build + installer

NineLives is an **Electron** app (as of v1.0.0); builds use **electron-builder**
from the `electron/` directory:

```bash
cd electron && npm install && npm run dist   # -> electron/dist/
```

- **Windows:** produces the NSIS installer `NineLives-Setup-<ver>.exe`.
- **Linux:** produces `NineLives-<ver>-x86_64.AppImage` (mark executable and run).

Each build bundles hashcat + the wordlist starter set from `electron/vendor/`.
(electron-builder isn't a cross-compiler — build the Windows target on Windows and
the Linux target on Ubuntu.)

The legacy **Python/PyInstaller** build (`build_windows.ps1`, `build_linux.sh`,
`.github/workflows/build.yml`) is archived — kept in the repo for reference but no
longer the shipping path.

## Releases (CI)

`.github/workflows/electron.yml` builds the Windows + Linux targets on every `v*`
tag and attaches them to a GitHub Release, alongside `SHA256SUMS-windows.txt` /
`SHA256SUMS-linux.txt` — so "download and install" is just grabbing
`NineLives-Setup-<ver>.exe` (or the `.AppImage`) from the Releases page.

```bash
git tag v1.1.0 && git push origin v1.1.0   # triggers the release build
```

## Workflow

1. **New? Take the tour** — the **?** in the top bar launches a guided
   spotlight tour (it runs itself on first launch); **Settings → Help → Demo**
   cracks the bundled Coherer capture.
2. **Settings (cog)**: optionally point at your SecLists checkout once, or download
   bigger lists — it indexes everything.
3. **Crack tab**: pick the hash file, then the hash type — choose a **category**
   (★ Common first) and **mode**, or just **search** by name/number.
4. The **Inputs** and **Options** panels rebuild for the chosen attack mode — only
   compatible options appear, as plain-language **toggles** and **dropdowns** (pick
   a value and the toggle flips on), grouped into collapsible sections.
5. **Run crack** to go: a plain-language **status bar** tracks progress; the raw
   hashcat output lives behind **Show console**. **Show command** previews the exact
   command; **Show recovered** reads results.

## Roadmap / fine-tuning

- Benchmark + ETA readout (`hashcat -b`) so you know if a mask is realistic
- Session save/restore surfaced as buttons (`--session`/`--restore`)
- Capture tab wrapping `hcxdumptool → hcxpcapngtool` (clientless PMKID; no deauth)
- Rule-file dropdown from hashcat's bundled `rules/`
- Per-mode example-hash preview and auto hash-type detection

## Troubleshooting

If the app won't start, hangs, or behaves oddly, check the startup log:

```
%LOCALAPPDATA%\NineLives\startup.log        (Windows)
~/.local/share/NineLives/startup.log        (Linux)
```

It records each boot step (last line = where it got stuck), so it pinpoints
launch problems that leave no visible error. A healthy launch ends with
`js: boot: done`; if it never gets there, the last line points at the step that
stalled — include it when you report a problem.

All writable runtime data lives in that `NineLives` folder, not the install
directory: settings, the potfile, extracted captures, downloaded wordlists,
hashcat updates, and the startup log — kept out of the install directory so
nothing needs admin rights.

Cracks run from a `hcwork` subfolder there, which links in hashcat's read-only
shared folders (`OpenCL`, `modules`, `rules`, …) and holds its compiled-kernel
cache. hashcat resolves those relative to the working directory and writes its
runtime files there, so running from the read-only install dir would make a
crack exit immediately with `./OpenCL/: No such file or directory`.

## Scope

Only for hashes from equipment you own or are explicitly authorized to test.
