"use strict";
/* NineLives Electron main process.
 *
 * Opens a BrowserWindow, loads the existing web UI (webui/), and exposes the
 * Node backend (backend/api.js) to the renderer over IPC — no local HTTP
 * server, no pywebview. Push events (crack output, etc.) are forwarded to the
 * renderer on the 'nl-event' channel. */

const path = require("path");
const { app, BrowserWindow, ipcMain } = require("electron");

// In dev, bundled resources (webui/, vendor/) live in the repo root. In a
// packaged build this is set to process.resourcesPath by the builder.
process.env.NINELIVES_APP_DIR = process.env.NINELIVES_APP_DIR || path.resolve(__dirname, "..");

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
  win.loadFile(path.join(__dirname, "..", "webui", "index.html"));
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
        const ok = r.booted && r.themes >= 4 && r.attacks >= 1 && r.modes >= 1;
        process.exitCode = ok ? 0 : 1;
      } catch (e) {
        console.log("SMOKE error " + (e && e.message));
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

  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  app.quit();
});
