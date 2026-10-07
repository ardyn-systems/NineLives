# Hosting NineLives

NineLives runs two ways from one codebase:

- **Desktop app** (default) — the full console, **including cracking**, in a
  pywebview window with bundled hashcat. This is the normal way to use it.
- **Hosted server** — the same web UI served over HTTP for an
  **explore + extract** deployment: browse the interface, import a capture to
  pull its WPA/WPA2 hashes, and **download the `.hc22000`** to crack locally.

> **Cracking is intentionally disabled when hosted.** There's no server-side
> hashcat and no GPU, and a public crack endpoint would be an abuse risk. The
> backend reports `hosted` whenever there's no desktop window and refuses
> `run`/`install`; the UI hides those controls and offers a download instead.

## Run the server locally

```bash
python ninelives.py --host 0.0.0.0 --port 8000
# then open http://localhost:8000
```

It's pure standard library — no extra dependencies for server mode.

## Deploy to Render (free plan)

The repo ships a [`render.yaml`](../render.yaml) blueprint.

1. Push the repo to GitHub (already at `ardyn-systems/NineLives`).
2. In Render: **New → Blueprint**, pick the repo. Render reads `render.yaml`
   and creates a free **web service** named `ninelives`.
3. It builds (nothing to install) and starts
   `python ninelives.py --host 0.0.0.0 --port $PORT`, with a health check at
   `/api/health`. Every push to the default branch auto-redeploys.

### Environment

| Var | Default | Meaning |
|-----|---------|---------|
| `NINELIVES_HOSTED` | `1` (in render.yaml) | Public mode marker (explore + extract). |
| `NINELIVES_MAX_UPLOAD_MB` | `20` | Reject capture uploads larger than this (free tier is 512 MB RAM). |

## Endpoints

- `GET /` and static assets — the web UI.
- `GET /api/health` — `{status, name, version, hosted}` (Render health check).
- `POST /api/<method>` — JSON args array; the same API the desktop bridge uses
  (FS-path and crack methods are excluded or disabled when hosted).
- `GET /api/download?id=<capture-id>` — the extracted `.hc22000` for a network.
