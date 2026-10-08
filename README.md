# NineLives

<p align="center">
  <img src="brand/ninelives-master.png" alt="NineLives" width="380">
</p>

A push-button GUI front-end for **hashcat**, for authorized password auditing —
WPA/WPA2 handshakes/PMKIDs from your own access points, and other hashes from
systems you're explicitly scoped to test.

It wraps hashcat (doesn't replace it) and stays in sync with it: the hash-type
list and options come from hashcat itself, and the bundled hashcat engine
auto-updates. Pick a hash type, pick an attack, pick a wordlist from a dropdown,
click Run.

**Download:** [Releases](https://github.com/ardyn-systems/NineLives/releases)
(Windows installer/portable, Linux AppImage/tarball).
**Docs:** [User guide](docs/user-guide.md) · [Hosting](docs/hosting.md).
Any UI change updates the guide + screenshots in the same PR
(`python docs/screenshots.py`).

> **NineLives is an Electron app** (Chromium + a Node backend) as of v1.0.0 —
> see [`electron/`](electron/README.md). Releases on the
> [Releases page](https://github.com/ardyn-systems/NineLives/releases) are the
> Electron installers (Windows NSIS `.exe`, Linux AppImage), and they ship a
> **bundled example** (a sample WPA capture + a demo wordlist) so a fresh install
> cracks out of the box. The original Python build (pywebview + a local server)
> is kept in this repo for reference but is no longer shipped; the sections below
> that reference `ninelives.py`/`api.py` describe that archived build.

## Design goals (and how they're met)

| Goal | How |
|------|-----|
| One codebase → Windows **and** Ubuntu builds | Python + a web UI in a pywebview window; per-OS PyInstaller bundles |
| Bundles hashcat, **updates when hashcat updates** | `updater.py` checks hashcat's releases and installs into `vendor/` |
| Options stay current automatically | `hashcat_iface.py` parses `hashcat --help` for the live hash-mode catalog (cached, with a static fallback) |
| SecLists from **dropdowns**, no uploading | `wordlists.py` indexes the bundled starter set, on-demand downloads, and your own SecLists folder |
| **Suggested wordlists** per hash type | `wordlists.Catalog.suggest()` maps the hash family → best-first lists (★ in the dropdown) |
| **Every option explained** | `compat.py` carries plain-English descriptions + examples (shown inline and on hover) |
| **Stackable options, no guessing** | `compat.py` encodes the attack-mode → compatible-option matrix; the UI shows only options that legally combine with the chosen `-a` mode |

## Modules

```
ninelives.py       launcher: starts the local server and shows it in a window
server.py          HTTP server + /api/* dispatch and the event stream
webui/             NetSeer-styled front-end — index.html, styles.css, app.js
api.py             the backend the server calls (crack, extract, catalog, …)
hashcat_iface.py   locate/run hashcat; parse --help → live hash catalog
compat.py          attack-mode ↔ stackable-option matrix + explanations
wordlists.py       SecLists catalog (bundled + downloaded + your own) + suggestions
wordlist_dl.py     on-demand wordlist downloads (rockyou etc.) into the data dir
updater.py         check/install hashcat releases into vendor/
themes.py          NetSeer theme tokens (terrain/midnight/daylight/blueprint)
settings.py        shared JSON settings
cracker.py         optional pure-Python WPA engine (works with no hashcat)
```

**Architecture (like NetSeer).** The desktop app runs a small HTTP server on
`127.0.0.1` and shows it in a window (WebView2 on Windows, WebKitGTK on Linux,
falling back to your default browser). The page talks to the backend over HTTP
(`fetch`), and server-pushed output (live hashcat lines, catalog refresh,
download progress) streams back over a long-poll of `/api/events`. There is no
JS↔Python bridge, so a slow window start can't strand the UI. The same server,
run with `--host`, is the public explore-and-extract deployment — where cracking
and filesystem actions are disabled. `webui/styles.css` carries NetSeer's four
shipping themes as `[data-theme]` token sets (easter-egg themes excluded).

Inspect the stackability matrix without the GUI:

```bash
python compat.py          # dump attack modes and their compatible options
python hashcat_iface.py   # show the hash-mode catalog (live or fallback)
```

## Requirements

- **Python 3.8+**
- **pywebview** (`pip install pywebview`)
  - Windows: uses the built-in Edge **WebView2** runtime (present on Win 10/11); needs `pythonnet`
  - Ubuntu: `sudo apt install python3-gi gir1.2-webkit2-4.1` (or `-4.0` on older releases)
- **hashcat** — bundle it (below) or install it; the app also finds a system copy
- For bundling/updating hashcat: `py7zr` (`pip install py7zr`) or a `7z`/`7za` CLI

## Run from source

```bash
python ninelives.py
```

First launch asks for authorized-use confirmation. If hashcat isn't present yet,
the dropdowns still work offline from the static catalog; install hashcat from
the **Settings** tab (**Check / install update**) or bundle it first.

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
> The Windows installer clears the previously bundled `vendor\` on upgrade (see
> `[InstallDelete]` in `installer.iss`), so upgrading from an older build drops
> its large bundled lists rather than leaving them behind. Lists you downloaded
> yourself live under `%LOCALAPPDATA%\NineLives` and are never touched.

## Build + installer

- **Windows:** `powershell -ExecutionPolicy Bypass -File build_windows.ps1`
  → `dist\NineLives\NineLives.exe`, and (with [Inno Setup 6](https://jrsoftware.org/isdl.php)
  installed) a double-click installer `dist\NineLives-Setup.exe`.
  Flags: `-Full` (bundle all of SecLists), `-NoFetch` (reuse existing `vendor/`).
- **Ubuntu:** `bash build_linux.sh` → `dist/NineLives/NineLives` and
  `dist/NineLives-linux-x86_64.tar.gz`.

(PyInstaller isn't a cross-compiler — build the Windows bundle on Windows and the
Linux bundle on Ubuntu, from this same source tree.)

## Releases (CI)

`.github/workflows/build.yml` builds both installers on every `v*` tag and
attaches them to a GitHub Release — so "download and install" is just grabbing
`NineLives-Setup.exe` from the Releases page. Each release re-fetches hashcat, so
tagging a release picks up the latest hashcat automatically.

```bash
git tag v0.1.0 && git push origin v0.1.0   # triggers the release build
```

## Workflow

1. **New? Hit the ? (Guide)** in the top bar (it opens itself on first launch) and
   use **Try the demo** to crack the bundled Coherer capture.
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

It records each startup step (last line = where it got stuck), so it pinpoints
launch problems that leave no visible error. A healthy launch starts the local
server (`desktop: serving http://127.0.0.1:…`), then shows the window
(`window shown (WebView2 ready)`, `page loaded`) and the page boots
(`js: boot: done`). If the window line never arrives and a `WARN window not
shown after 25s` line follows, the embedded WebView2 browser stalled — and the
app falls back to opening in your default browser. The companion `pywebview.log`
in the same folder logs the browser's own startup steps.

All writable runtime data lives in that `NineLives` folder, not the install
directory: settings, potfile, extracted captures, hashcat updates, the WebView2
browser-data folder, and the two logs above. The app also switches its working
directory there on launch, because WebView2 writes into the working directory
and a double-click would otherwise leave it read-only.

Cracks run from a `hcwork` subfolder there, which links in hashcat's read-only
shared folders (`OpenCL`, `modules`, `rules`, …) and holds its compiled-kernel
cache. hashcat resolves those relative to the working directory and writes its
runtime files there, so running from the read-only install dir would make a
crack exit immediately with `./OpenCL/: No such file or directory`.

## Scope

Only for hashes from equipment you own or are explicitly authorized to test.
