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

## Design goals (and how they're met)

| Goal | How |
|------|-----|
| One codebase → Windows **and** Ubuntu builds | Python + Tkinter; per-OS PyInstaller bundles |
| Bundles hashcat, **updates when hashcat updates** | `updater.py` checks hashcat's releases and installs into `vendor/` |
| Options stay current automatically | `hashcat_iface.py` parses `hashcat --help` for the live hash-mode catalog (cached, with a static fallback) |
| SecLists from **dropdowns**, no uploading | `wordlists.py` indexes the bundled starter set, on-demand downloads, and your own SecLists folder |
| **Suggested wordlists** per hash type | `wordlists.Catalog.suggest()` maps the hash family → best-first lists (★ in the dropdown) |
| **Every option explained** | `compat.py` carries plain-English descriptions + examples (shown inline and on hover) |
| **Stackable options, no guessing** | `compat.py` encodes the attack-mode → compatible-option matrix; the UI shows only options that legally combine with the chosen `-a` mode |

## Modules

```
ninelives.py       launcher (pywebview desktop window)
webui/             NetSeer-styled front-end — index.html, styles.css, app.js
api.py             JS ↔ Python bridge exposed to the web UI
hashcat_iface.py   locate/run hashcat; parse --help → live hash catalog
compat.py          attack-mode ↔ stackable-option matrix + explanations
wordlists.py       SecLists catalog (bundled + downloaded + your own) + suggestions
wordlist_dl.py     on-demand wordlist downloads (rockyou etc.) into the data dir
updater.py         check/install hashcat releases into vendor/
themes.py          NetSeer theme tokens (terrain/midnight/daylight/blueprint)
settings.py        shared JSON settings
cracker.py         optional pure-Python WPA engine (works with no hashcat)
```

The UI is a real web view: `webui/styles.css` carries NetSeer's four shipping
themes as `[data-theme]` token sets (the easter-egg themes are excluded), and
`api.py` bridges the page to the backend. Theme switching is instant and
persisted.

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

1. **Settings → SecLists folder**: point at your SecLists checkout once; it indexes everything.
2. **Crack tab**: pick the hash file, choose the hash type (searchable), pick an attack mode.
3. The **Inputs** and **Options** panels rebuild for that attack mode — only compatible options appear, each explained.
4. Wordlist dropdowns show ★ suggestions for your hash type first.
5. **Show command** to preview, **Run crack** to go, **Show recovered** to read results.

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
launch problems that leave no visible error. A healthy launch ends with `window
shown (WebView2 ready)` then `page loaded`; if it stops at `calling
webview.start()` and a `WARN window not shown after 25s` line follows, the
embedded WebView2 browser stalled — the companion `pywebview.log` in the same
folder logs the browser's own startup steps (last line = where it stalled).

All writable runtime data lives in that `NineLives` folder, not the install
directory: settings, potfile, extracted captures, hashcat updates, the WebView2
browser-data folder, and the two logs above. The app also switches its working
directory there on launch, because WebView2 writes into the working directory
and a double-click would otherwise leave it read-only.

## Scope

Only for hashes from equipment you own or are explicitly authorized to test.
