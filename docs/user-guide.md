# NineLives — User Guide

NineLives is a push-button console for **hashcat**: pick a hash or capture, pick
an attack, pick a wordlist, and crack — with every option explained and only the
ones that actually combine shown. For **authorized** password auditing of
equipment you own or are explicitly scoped to test.

Screenshots are regenerated with `python docs/screenshots.py` (see
[contributing to the docs](#keeping-the-docs-current)).

> As of v1.0.0, NineLives is an **Electron** app. A fresh install ships a
> **bundled example** — a sample *Coherer* WPA capture (pre-loaded in Captures)
> and a demo wordlist — so you can crack it immediately: **Captures → Use in
> Crack → pick `wpa-demo.txt` → Run** recovers `Induction`. The workflow below
> (Crack, Captures, Themes, Settings) is unchanged. See
> [`electron/README.md`](../electron/README.md) for the app internals.

## Install

Grab the latest build from the [Releases page](https://github.com/ardyn-systems/NineLives/releases):

- **Windows:** `NineLives-Setup-<ver>.exe` (installer).
- **Linux:** `NineLives-<ver>-x86_64.AppImage` (mark executable and run).

Each build **bundles hashcat and a small wordlist starter set**, so it cracks out
of the box; grab bigger lists (rockyou etc.) from Settings (the cog) when you want
them. Verify downloads against `SHA256SUMS-<os>.txt`.

New to NineLives? The **? (Take the tour)** button in the top bar launches a
guided **spotlight tour** — it dims the screen and highlights each control in
turn (Target, hash type, attack, inputs, options, Run, Captures, the cog), with
**Back / Next** and the arrow keys. It runs automatically the first time you open
NineLives, and you can replay it any time from the **?** button or **Settings ›
Help › Take the tour**.

## The Crack tab

![The Crack tab](images/overview.png)

1. **Target** — set the **Hash file** and the **Hash type**. For WPA, import a
   capture on the **Captures** tab and click **Use in Crack** to fill this in
   automatically; for other hashes, **Choose…** a hash file (it's copied into
   your data folder). The hash type is organized so you don't scroll 500+ modes:
   pick a **category** (starting with **★ Common**), then the **mode** from the
   second dropdown — or ignore both and **search** by name or number (`WPA`,
   `NTLM`, `1000`). The full list comes from hashcat itself.
2. **Attack** — pick how candidates are generated. The panels below **adapt to
   this choice**: dictionary shows rule options, mask modes show charsets, and so
   on — so you never guess which flags combine.
3. **Inputs** — pick a wordlist (or type a mask). Wordlists come from your
   SecLists folder, with ★ suggestions for the chosen hash type shown first.
4. **Options** — only the options that stack with the chosen attack, grouped into
   collapsible sections with **plain-language labels**. Flip a **toggle** to turn
   one on; options with set choices (workload, device type, output format) are
   **dropdowns**, and picking a value flips the toggle on for you — so there's
   almost nothing to type. The raw hashcat flag is shown in small type under each
   label for reference.
5. **Run crack** — a plain-language **status bar** shows what's happening
   (preparing, cracking with a progress bar, speed, estimate, and recovered
   count), ending in **Cracked! 🎉** or **Finished — not found**. The raw hashcat
   output is tucked behind **Show console**; **Show command** previews the exact
   command; **Show recovered** lists cracked results.

## Captures — turn a packet capture into hashes

![The Captures tab](images/captures.png)

Drop a **`.pcap` / `.pcapng` / `.cap`** (or **Browse**). NineLives extracts any
WPA/WPA2 **PMKID** and **4-way handshakes**, groups them by network (ESSID +
BSSID), and lists them with **PMKID / handshake** badges. Click **Use in Crack**
to load a network straight into the Crack tab as mode `22000`.

(CSV / Kismet netxml are survey metadata and carry no crackable hashes.)

## Themes

![The theme grid](images/settings.png)

Six themes, chosen from the swatch grid in **Settings › General** (the cog) —
**Synthwave** (default) and **Cyberpunk** neon, plus Terrain, Midnight, Daylight,
and Blueprint. Your choice is remembered.

## Settings

Open Settings from the **cog (⚙)** in the top bar — it opens as a dialog with a
left-hand menu of sections: **General**, **Wordlists**, **Integrations**,
**Updates**, **Help**, and **About**.

![The Settings dialog](images/settings.png)

- **General**
  - **Theme** — pick any of the six themes from the swatch grid; your choice is
    remembered.
  - **Graphics card** — choose which device hashcat cracks on. **Automatic**
    (default) uses every device it detects, which already includes your dedicated
    GPU. On a laptop with both an integrated and a dedicated GPU, pick the
    dedicated card (or **All GPUs only**) for full speed. **Refresh** re-detects;
    if only a CPU shows up, install your GPU's vendor driver.
- **Wordlists** — installed builds ship a small **starter set**. Use **Download**
  next to a list (rockyou, xato-10M, darkc0de) to fetch the bigger lists from the
  SecLists project; they land in your data dir and appear in the dropdowns
  automatically. Or point the folder box at your own SecLists checkout — all
  sources feed the dropdowns. (Downloads run in the desktop app, not the hosted
  demo.)
- **Integrations** — a placeholder for future companion-app features (pushing
  hashes/captures straight into NineLives).
- **Updates**
  - **NineLives app** — press **Check for updates** to list every version on
    GitHub. Each shows **Update** (newer), **Roll back** (older, folded under
    *Earlier versions*), or **Reinstall** (the one you have), plus **Notes**.
    Choosing one opens a short wizard that **downloads that version, verifies it
    against GitHub's SHA-256 checksum, installs it, and reopens NineLives** — on
    Windows the install runs silently. **Check for updates when NineLives opens**
    (on by default) quietly checks at most once a day and flags a new release with
    a dot on the cog and a **New** badge; nothing installs until you choose it.
    (In the hosted demo, the actions link to the Releases page.)
  - **hashcat engine** — check for and install hashcat updates.
- **Help** — **Take the tour** (replays the spotlight tour), **User guide**,
  **Report a problem** (opens a GitHub issue), and **Demo** (jumps to the bundled
  Coherer capture).
- **About** — what NineLives is, the app + hashcat versions, the source link, and
  the open-source components it's built with.

## Hosted mode

NineLives can also run as a web server for an **explore + extract** deployment
(import a capture, download the `.hc22000`) — cracking stays in the desktop app.
The desktop app is Electron; the hosted web server is a small Python service. See
[hosting.md](hosting.md).

## Troubleshooting

NineLives is an **Electron** app (Chromium + a Node backend). It records its
boot steps to a startup log — the last line shows where it stopped:

- **Windows:** `%LOCALAPPDATA%\NineLives\startup.log`
- **Linux:** `~/.local/share/NineLives/startup.log`

A healthy launch ends with `js: boot: done`. If it never gets there, the log's
last line points at the step that stalled — include it when you report a problem.
A first launch right after installing can be slow while the OS finishes indexing
the new files; if it still won't open on later launches, send the log.

That same `NineLives` folder holds your writable runtime data — settings, the
potfile, extracted captures, downloaded wordlists, and hashcat updates — kept out
of the install directory so nothing needs admin rights.

Cracks run from a `hcwork` subfolder there, which links in hashcat's read-only
shared folders (`OpenCL`, `modules`, `rules`, …) and holds its compiled-kernel
cache — hashcat resolves those relative to its working directory, so running it
from the read-only install dir would make a crack exit immediately with
`./OpenCL/: No such file or directory`.

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
