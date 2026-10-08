"use strict";
/* Bridge the renderer to the Node backend over IPC. Exposes window.nlapi:
 *   nlapi.invoke(method, ...args) -> Promise(result)
 *   nlapi.onEvent(cb)             -> cb({fn, args}) for each server-pushed event
 * app.js prefers this bridge when present, else falls back to HTTP fetch. */

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("nlapi", {
  invoke: (method, ...args) => ipcRenderer.invoke("nl-invoke", method, args),
  onEvent: (cb) => {
    ipcRenderer.on("nl-event", (_e, ev) => {
      try {
        cb(ev);
      } catch {
        /* ignore */
      }
    });
  },
});
