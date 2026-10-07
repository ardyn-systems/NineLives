# NineLives — User Guide

NineLives is a push-button console for **hashcat**: pick a hash or capture, pick
an attack, pick a wordlist, and crack — with every option explained and only the
ones that actually combine shown. For **authorized** password auditing of
equipment you own or are explicitly scoped to test.

Screenshots are regenerated with `python docs/screenshots.py` (see
[contributing to the docs](#keeping-the-docs-current)).

## Install

Grab the latest build from the [Releases page](https://github.com/ardyn-systems/NineLives/releases):

- **Windows:** `NineLives-Setup-<ver>.exe` (installer) or
  `NineLives-<ver>-windows-x64-portable.zip` (no install — unzip and run).
- **Linux:** `NineLives-<ver>-x86_64.AppImage` (mark executable and run; needs
  `webkit2gtk` present) or the `-linux-x86_64.tar.gz`.

Each build **bundles hashcat and a small wordlist starter set**, so it cracks out
of the box; grab bigger lists (rockyou etc.) from the Settings tab when you want
them. Verify downloads against `SHA256SUMS-<os>.txt`.

## The Crack tab

![The Crack tab](images/overview.png)

1. **Target** — choose the **Hash file** (e.g. a `.hc22000`) and the **Hash
   type**. The type box is searchable: type `WPA`, `NTLM`, or a mode number.
   The full hash-mode list comes from hashcat itself.
2. **Attack** — pick how candidates are generated. The panels below **adapt to
   this choice**: dictionary shows rule options, mask modes show charsets, and so
   on — so you never guess which flags combine.
3. **Inputs** — pick a wordlist (or type a mask). Wordlists come from your
   SecLists folder, with ★ suggestions for the chosen hash type shown first.
4. **Options** — every stackable option for the attack, each with a plain-English
   explanation. Tick what you want.
5. **Run crack** — streams hashcat's live output into the console. **Show
   command** previews the exact hashcat command; **Show recovered** lists cracked
   results.

## Captures — turn a packet capture into hashes

![The Captures tab](images/captures.png)

Drop a **`.pcap` / `.pcapng` / `.cap`** (or **Browse**). NineLives extracts any
WPA/WPA2 **PMKID** and **4-way handshakes**, groups them by network (ESSID +
BSSID), and lists them with **PMKID / handshake** badges. Click **Use in Crack**
to load a network straight into the Crack tab as mode `22000`.

(CSV / Kismet netxml are survey metadata and carry no crackable hashes.)

## Themes

![The theme menu](images/theme-menu.png)

Six themes from the **Theme** menu — **Synthwave** (default) and **Cyberpunk**
neon, plus Terrain, Midnight, Daylight, and Blueprint. Your choice is remembered.

## Settings

![The Settings tab](images/settings.png)

- **Wordlists** — installed builds ship a small **starter set**. Use **Download**
  next to a list (rockyou, xato-10M, darkc0de) to fetch the bigger lists from the
  SecLists project; they land in your data dir and appear in the dropdowns
  automatically. Or point the folder box at your own SecLists checkout — all
  three sources feed the dropdowns. (Downloads run in the desktop app, not the
  hosted demo.)
- **hashcat** — check for and install hashcat updates.
- **NineLives** — shows the version and checks the project's GitHub releases for
  app updates.

## Hosted mode

NineLives can also run as a web server for an **explore + extract** deployment
(import a capture, download the `.hc22000`) — cracking stays in the desktop app.
See [hosting.md](hosting.md).

## Troubleshooting

If NineLives won't start or hangs, open the startup log — its last line shows
where it stopped:

- **Windows:** `%LOCALAPPDATA%\NineLives\startup.log`
- **Linux:** `~/.local/share/NineLives/startup.log`

A healthy launch ends with `window shown (WebView2 ready)` followed by `page
loaded`. If instead the log stops at `calling webview.start()` and then shows
`WARN window not shown after 25s`, the embedded browser (WebView2) stalled while
starting up — the companion `pywebview.log` in the same folder records the
browser's own startup steps, and its last line pinpoints where. A first launch
right after installing can be slow while the OS finishes indexing the new files;
if it still won't show a window on later launches, send both logs.

That same `NineLives` folder holds your settings, potfile, extracted captures,
and the WebView2 browser data (it's kept out of the install directory so nothing
needs admin rights).

## Authorized use

Only use NineLives against hashes and captures from equipment you own or are
explicitly authorized to test.

## Keeping the docs current

Any change to the UI should update this guide and its screenshots in the **same
PR**. Regenerate the images with:

```bash
python -m pip install playwright && python -m playwright install chromium
python docs/screenshots.py
```
