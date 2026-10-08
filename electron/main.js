"use strict";
/* NineLives Electron main process.
 *
 * Opens a BrowserWindow, loads the existing web UI (webui/), and exposes the
 * Node backend (backend/api.js) to the renderer over IPC — no local HTTP
 * server, no pywebview. Push events (crack output, etc.) are forwarded to the
 * renderer on the 'nl-event' channel. */

const path = require("path");
const { app, BrowserWindow, ipcMain } = require("electron");

// Bundled resources (webui/, vendor/): the repo root in dev, process.resourcesPath
// in a packaged build (electron-builder copies them there via extraResources).
// Must be set before requiring the backend, which reads it through paths.js.
const RES_DIR = app.isPackaged ? process.resourcesPath : path.resolve(__dirname, "..");
process.env.NINELIVES_APP_DIR = process.env.NINELIVES_APP_DIR || RES_DIR;
const WEBUI_INDEX = path.join(RES_DIR, "webui", "index.html");

const { Api } = require("./backend/api");

let win = null;
let api = null;

function createWindow() {
  win = new BrowserWindow({
    width: 1120,
    height: 860,
    minWidth: 900,
    minHeight: 640,
    backgroundColor: "#0a0a14",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.loadFile(WEBUI_INDEX);
  if (process.env.NINELIVES_DEBUG) win.webContents.openDevTools({ mode: "detach" });

  // Automated smoke check: once the page has loaded, confirm it booted and
  // reached the backend, print the result, and quit. Used by `npm run smoke`.
  if (process.env.NINELIVES_SMOKE) {
    win.webContents.on("did-finish-load", async () => {
      await new Promise((r) => setTimeout(r, 1500));
      try {
        const out = await win.webContents.executeJavaScript(
          "JSON.stringify({booted:_booted, themes:(S.themes||[]).length, " +
          "attacks:(S.attackModes||[]).length, modes:(S.hashModes||[]).length, " +
          "status:(document.getElementById('status')||{}).textContent})"
        );
        const r = JSON.parse(out);
        console.log("SMOKE " + out);
        process.exitCode = r.booted && r.themes >= 4 && r.attacks >= 1 && r.modes >= 1 ? 0 : 1;
      } catch (e) {
        console.log("SMOKE error " + (e && e.message));
        process.exitCode = 1;
      }
      app.quit();
    });
  }

  // Crack smoke (NINELIVES_SMOKE_CRACK=<wordlist path>): import the Coherer
  // fixture, run a crack from the renderer, and confirm hbOutput streams over
  // IPC into the console and hbDone fires.
  if (process.env.NINELIVES_SMOKE_CRACK) {
    const wl = process.env.NINELIVES_SMOKE_CRACK.replace(/\\/g, "\\\\");
    const capB64 = require("fs").readFileSync(path.join(__dirname, "..", "tests", "fixtures", "wpa-Induction.pcap")).toString("base64");
    win.webContents.on("did-finish-load", async () => {
      await new Promise((r) => setTimeout(r, 1500));
      try {
        await win.webContents.executeJavaScript(
          `(async()=>{ await api().import_capture_bytes("wpa-Induction.pcap","data:;base64,${capB64}");` +
          ` const uc=await api().use_capture("Coherer_000c4182b255.hc22000");` +
          ` document.getElementById('console').innerHTML="";` +
          ` await api().run({mode_id:uc.mode_id,hashfile:uc.hashfile,attack_id:0,wordlist:"${wl}",options:[]}); })()`
        );
        // poll the console for the finished marker
        const t0 = Date.now();
        let txt = "";
        while (Date.now() - t0 < 90000) {
          await new Promise((r) => setTimeout(r, 1000));
          txt = await win.webContents.executeJavaScript("document.getElementById('console').innerText");
          if (/=== finished ===/.test(txt)) break;
        }
        const ok = /Recovered[^\n]*1\//.test(txt) && /=== finished ===/.test(txt);
        console.log("SMOKE_CRACK chars=" + txt.length + " recovered=" + /Recovered[^\n]*1\//.test(txt) + " finished=" + /=== finished ===/.test(txt));
        process.exitCode = ok ? 0 : 1;
      } catch (e) {
        console.log("SMOKE_CRACK error " + (e && e.message));
        process.exitCode = 1;
      }
      app.quit();
    });
  }
}

app.whenReady().then(() => {
  api = new Api();
  // renderer → backend
  ipcMain.handle("nl-invoke", async (_e, method, args) => {
    const fn = api[method];
    if (typeof fn !== "function") return { error: `unknown method: ${method}` };
    try {
      return await fn.apply(api, args || []);
    } catch (e) {
      return { error: `${e && e.name}: ${e && e.message}` };
    }
  });
  // backend → renderer (push events)
  api.on("event", (ev) => {
    if (win && !win.isDestroyed()) win.webContents.send("nl-event", ev);
  });
  // backend asked to quit (e.g. to let the self-update installer replace files)
  api.on("quit", () => setTimeout(() => app.quit(), 1000));

  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  app.quit();
});
