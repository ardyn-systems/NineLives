/* NineLives web UI.
   The page is always served by a local (desktop) or hosted NineLives server and
   talks to it over HTTP: api().<method>(...args) POSTs a JSON args array to
   /api/<method>. Server-pushed events (crack output, catalog refresh, download
   status) arrive via a long-poll of /api/events. There is no pywebview bridge,
   so a slow WebView2 start can never strand the UI on "Starting…". */
"use strict";

// Two transports:
//  - Electron: window.nlapi (IPC bridge from preload) — nlapi.invoke(method,…).
//  - Python server build: POST /api/<method> over HTTP (fetch).
// api().<method>(...args) returns a promise either way.
const _fetchApi = new Proxy({}, { get: (_t, name) => (...args) =>
  fetch("/api/" + String(name), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(args),
  }).then((r) => r.json()) });
const _bridgeApi = new Proxy({}, { get: (_t, name) => (...args) =>
  window.nlapi.invoke(String(name), ...args) });
function api() { return (window.nlapi && window.nlapi.invoke) ? _bridgeApi : _fetchApi; }

// Dispatch a server-pushed event to its window.* handler (hbOutput / hbDone /
// hbCatalog / hbWordlistStatus / hbWordlists).
function dispatchEvent(ev) {
  const fn = window[ev && ev.fn];
  if (typeof fn === "function") { try { fn(...(ev.args || [])); } catch (e) { /* ignore */ } }
}
// Electron pushes events over IPC; the HTTP build long-polls /api/events.
function startEvents() {
  if (window.nlapi && window.nlapi.onEvent) { window.nlapi.onEvent(dispatchEvent); return; }
  pollEvents();
}
let _evCursor = 0;
async function pollEvents() {
  for (;;) {
    try {
      const r = await fetch("/api/events?since=" + _evCursor);
      const data = await r.json();
      if (typeof data.cursor === "number") _evCursor = data.cursor;
      for (const ev of data.events || []) dispatchEvent(ev);
    } catch (e) {
      await new Promise((res) => setTimeout(res, 1000));  // server busy/restarting
    }
  }
}
const el = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

// In-page confirm. window.confirm() opens a native WebView2 modal that can hang
// the host window ("Not Responding"), so we use our own overlay instead.
function uiConfirm(message, okLabel = "OK", cancelLabel = "Cancel") {
  return new Promise((resolve) => {
    const m = el("modal");
    el("modal-msg").textContent = message;
    el("modal-ok").textContent = okLabel;
    el("modal-cancel").textContent = cancelLabel;
    m.classList.remove("hidden");
    const finish = (v) => {
      m.classList.add("hidden");
      el("modal-ok").onclick = null;
      el("modal-cancel").onclick = null;
      resolve(v);
    };
    el("modal-ok").onclick = () => finish(true);
    el("modal-cancel").onclick = () => finish(false);
  });
}

const S = {
  themes: [], attackModes: [], hashModes: [],
  modeByLabel: new Map(), modeById: new Map(),
  attackId: 0, optionsMeta: new Map(), // key -> {takes_value}
  wlByValue: new Map(), hosted: false,
};

/* ---------- init ---------- */
const blog = (m) => { try { api().log(m); } catch (e) { /* ignore */ } };
let _booted = false;
let _booting = false;
async function boot() {
  if (_booted || _booting) return;
  _booting = true;
  try {
    blog("boot: start");
    startEvents();              // begin receiving server-pushed events
    await _bootBody();
    _booted = true;
    blog("boot: done");
  } catch (e) {
    // Leave _booted false so a retry can still boot rather than freezing.
    blog("boot: error " + (e && e.message));
  } finally {
    _booting = false;
  }
}
async function _bootBody() {
  const init = await api().get_init();
  blog("boot: got init (hosted=" + !!init.hosted + ", modes=" + (init.hash_modes || []).length + ")");
  S.hosted = !!init.hosted;
  if (!init.acknowledged) {
    blog("boot: showing consent");
    const ok = await uiConfirm(
      "NineLives audits hashes from equipment you own or are explicitly authorized to test.\n\nConfirm you'll use it only that way?",
      "I agree", "Not now");
    blog("boot: consent = " + ok);
    if (ok) api().acknowledge();
  }
  S.themes = init.themes;
  S.attackModes = init.attack_modes;
  S.hashModes = init.hash_modes;
  document.documentElement.dataset.theme = init.current_theme;
  buildThemeMenu(init.current_theme);
  buildHashTypes();
  buildAttackSeg();
  blog("boot: menus built");
  el("status").innerHTML = init.hashcat.present
    ? `hashcat <b>${esc(init.hashcat.version || "?")}</b>`
    : `hashcat <b>not installed</b> — dropdowns work offline`;
  el("seclists").value = init.seclists_root || "";
  el("wl-count").textContent = `${init.wordlists_count} wordlists indexed`;
  el("hc-info").textContent = init.hashcat.present
    ? `Found: ${init.hashcat.version}` : "Not installed yet.";
  if (el("app-version")) el("app-version").textContent = init.app_version || "—";
  await selectAttack(0);
  wireEvents();
  if (S.hosted) applyHostedMode();
  else renderWordlistDownloads();
}
// The page is served by the server, so the backend is already up when we load.
window.addEventListener("load", boot);
if (document.readyState === "complete") boot();  // script ran after load
window.addEventListener("error", (e) => blog("js error: " + (e && e.message)));

function applyHostedMode() {
  el("status").innerHTML = "hosted · <b>explore + extract</b> — crack in the desktop app";
  ["run-btn", "recovered-btn", "pick-hash", "update-btn", "update-btn2",
   "rescan-btn"].forEach((id) => {
    const b = el(id);
    if (b) { b.disabled = true; b.title = "Available in the desktop app"; }
  });
  const sec = el("seclists"); if (sec) sec.disabled = true;
}

/* ---------- theme menu ---------- */
function buildThemeMenu(current) {
  const m = el("theme-menu");
  m.innerHTML = S.themes.map((t) => `
    <button class="item" role="menuitemradio" data-id="${t.id}"
      aria-checked="${t.id === current}">
      <span class="swatch">${t.swatch.map((c) => `<i style="background:${c}"></i>`).join("")}</span>
      <span class="meta">${esc(t.name)}<small>${esc(t.note)}</small></span>
      <span class="check">✓</span>
    </button>`).join("");
  m.querySelectorAll(".item").forEach((b) => b.addEventListener("click", () => {
    const id = b.dataset.id;
    document.documentElement.dataset.theme = id;
    api().set_theme(id);
    m.querySelectorAll(".item").forEach((x) => x.setAttribute("aria-checked", x.dataset.id === id));
    m.classList.add("hidden");
  }));
}

/* ---------- hash types: category → mode (no 500-item scroll) ---------- */
// Most-used modes, surfaced under "★ Common" so you rarely need the full list.
const COMMON_IDS = [22000, 16800, 1000, 0, 100, 1400, 1700, 3200, 1800, 500,
  5600, 13100, 18200, 1500, 22921, 900];

function buildHashTypes() {
  S.modeById = new Map(S.hashModes.map((m) => [m.id, m]));
  S.modesByCat = new Map();
  S.hashModes.forEach((m) => {
    if (!S.modesByCat.has(m.category)) S.modesByCat.set(m.category, []);
    S.modesByCat.get(m.category).push(m);
  });
  const catSel = el("ht-category");
  const prevCat = catSel.value;
  catSel.innerHTML = "";
  const addCat = (val, label) => {
    const o = document.createElement("option"); o.value = val; o.textContent = label; catSel.appendChild(o);
  };
  addCat("__common", "★ Common");
  [...S.modesByCat.keys()].sort((a, b) => a.localeCompare(b)).forEach((c) => addCat(c, c));
  addCat("__all", "All modes");
  catSel.value = [...catSel.options].some((o) => o.value === prevCat) ? prevCat : "__common";
  populateModeSelect();
}

function modesForCategory(cat, filter) {
  let list;
  if (filter) {
    const f = filter.toLowerCase();
    list = S.hashModes.filter((m) => `${m.id} ${m.name} ${m.category}`.toLowerCase().includes(f));
  } else if (cat === "__common") {
    list = COMMON_IDS.map((id) => S.modeById.get(id)).filter(Boolean);
  } else if (cat === "__all") {
    list = S.hashModes.slice();
  } else {
    list = (S.modesByCat.get(cat) || []).slice();
  }
  return list;
}

function populateModeSelect(filter) {
  const modeSel = el("ht-mode");
  const prev = modeSel.value;
  const list = modesForCategory(el("ht-category").value, filter);
  modeSel.innerHTML = "";
  const ph = document.createElement("option");
  ph.value = ""; ph.textContent = list.length ? "— choose a hash type —" : "— no matches —";
  modeSel.appendChild(ph);
  list.forEach((m) => {
    const o = document.createElement("option");
    o.value = String(m.id); o.textContent = `${m.id} — ${m.name}`;
    modeSel.appendChild(o);
  });
  if ([...modeSel.options].some((o) => o.value === prev)) modeSel.value = prev;
  onHashModeChange();
}

function currentMode() {
  const id = parseInt(el("ht-mode").value, 10);
  return (!isNaN(id) && S.modeById.has(id)) ? S.modeById.get(id) : null;
}

function onHashModeChange() {
  const m = currentMode();
  el("type-hint").textContent = m ? `mode ${m.id} · ${m.category}` : "";
  refreshWordlists();
}

// Select a mode by id (used by "Use in Crack"), jumping to its category.
function setHashMode(id) {
  const m = S.modeById.get(id);
  if (!m) return;
  const catSel = el("ht-category");
  el("ht-search").value = "";
  let cat = COMMON_IDS.includes(id) ? "__common" : m.category;
  if (![...catSel.options].some((o) => o.value === cat)) cat = "__all";
  catSel.value = cat;
  populateModeSelect();
  el("ht-mode").value = String(id);
  onHashModeChange();
}

/* ---------- attack modes ---------- */
function buildAttackSeg() {
  el("attack-seg").innerHTML = S.attackModes.map((m) => `
    <button class="seg" data-id="${m.id}"><span class="k">-a ${m.id}</span>${esc(m.name)}</button>`).join("");
  el("attack-seg").querySelectorAll(".seg").forEach((b) =>
    b.addEventListener("click", () => selectAttack(parseInt(b.dataset.id, 10))));
}
async function selectAttack(id) {
  S.attackId = id;
  const m = S.attackModes.find((x) => x.id === id) || S.attackModes[0];
  el("attack-seg").querySelectorAll(".seg").forEach((b) =>
    b.classList.toggle("active", parseInt(b.dataset.id, 10) === id));
  el("attack-desc").textContent = m.desc;
  buildInputs(m.inputs);
  const data = await api().get_options(id);
  buildOptions(data.groups);
  await refreshWordlists();
}

/* ---------- inputs (wordlists / mask) ---------- */
function buildInputs(inputs) {
  const host = el("inputs");
  host.innerHTML = "";
  inputs.forEach((slot, i) => {
    if (slot === "wordlist" || slot === "wordlist2") {
      const label = S.attackId === 1
        ? (slot === "wordlist" ? "Wordlist (left)" : "Wordlist (right)") : "Wordlist";
      const row = document.createElement("div");
      row.className = "row";
      row.innerHTML = `<label class="field grow">${label}
        <select data-slot="${slot}"></select></label>`;
      host.appendChild(row);
    } else if (slot === "mask") {
      const row = document.createElement("div");
      row.className = "row";
      row.innerHTML = `<label class="field grow">Mask
        <input type="text" data-slot="mask" value="?d?d?d?d?d?d?d?d"></label>
        <span class="hint" style="align-self:flex-end">?l lower ?u upper ?d digit ?s symbol ?a all</span>`;
      host.appendChild(row);
    }
  });
}
async function refreshWordlists() {
  const m = currentMode();
  const sel = document.querySelectorAll('#inputs select[data-slot]');
  if (!sel.length) return;
  const data = await api().suggest_wordlists(m ? m.id : null);
  S.wlByValue = new Map();
  let html = "";
  if (data.suggested.length) {
    html += `<optgroup label="★ Suggested for ${esc(data.family)}">`;
    data.suggested.forEach((e) => { S.wlByValue.set(e.path, e); html += `<option value="${esc(e.path)}">${esc(e.label)}</option>`; });
    html += `</optgroup>`;
  }
  if (data.all.length) {
    html += `<optgroup label="All wordlists">`;
    data.all.forEach((e) => { S.wlByValue.set(e.path, e); html += `<option value="${esc(e.path)}">${esc(e.label)}</option>`; });
    html += `</optgroup>`;
  } else if (!data.suggested.length) {
    html = `<option value="">(set SecLists folder in Settings)</option>`;
  }
  sel.forEach((s) => { s.innerHTML = html; });
}

/* ---------- options ---------- */
function buildOptions(groups) {
  S.optionsMeta = new Map();
  let count = 0;
  const host = el("options");
  host.innerHTML = groups.map((g) => `
    <div class="optgroup"><h3>${esc(g.group)}</h3>
      ${g.options.map((o) => {
        S.optionsMeta.set(o.key, o); count++;
        const flag = (o.flag ? o.flag + ", " : "") + o.long;
        const val = o.takes_value
          ? `<input class="val" type="text" data-val="${esc(o.key)}" placeholder="${esc((o.example || "").split(" ").pop())}">`
          : `<span></span>`;
        return `<div class="opt">
          <input type="checkbox" data-opt="${esc(o.key)}" title="${esc(o.desc)}">
          <span class="flag" title="${esc(o.desc)}">${esc(flag)}</span>
          ${val}
          <span class="desc">${esc(o.desc)}</span></div>`;
      }).join("")}</div>`).join("");
  el("opt-count").textContent = `${count}`;
}

/* ---------- command / run ---------- */
function gatherParams() {
  const m = currentMode();
  const opts = [];
  document.querySelectorAll('#options input[data-opt]').forEach((cb) => {
    if (!cb.checked) return;
    const key = cb.dataset.opt;
    let value = "";
    const vi = document.querySelector(`#options input[data-val="${CSS.escape(key)}"]`);
    if (vi) value = vi.value.trim();
    opts.push({ key, value });
  });
  const getSlot = (slot) => {
    const node = document.querySelector(`#inputs [data-slot="${slot}"]`);
    return node ? node.value : null;
  };
  return {
    mode_id: m ? m.id : null,
    attack_id: S.attackId,
    hashfile: el("hashfile").value.trim(),
    wordlist: getSlot("wordlist"),
    wordlist2: getSlot("wordlist2"),
    mask: getSlot("mask"),
    options: opts,
  };
}
function out(text, cls) {
  const c = el("console");
  const span = document.createElement("span");
  if (cls) span.className = cls;
  span.textContent = text;
  c.appendChild(span);
  c.scrollTop = c.scrollHeight;
}
window.hbOutput = (line) => { out(line); parseCrackStatus(line); };
window.hbDone = () => {
  el("run-btn").disabled = false; el("stop-btn").disabled = true;
  out("\n=== finished ===\n", "cmd");
  finishStatus();
};

/* ---------- plain-language crack status (parses hashcat's --status output) ---------- */
let _crack = null;
function startStatus() {
  _crack = { pct: 0, speed: "", eta: "", recovered: "", status: "Running" };
  const card = el("crack-status");
  card.classList.remove("hidden");
  el("cs-state").textContent = "Starting…"; el("cs-state").className = "cs-state";
  el("cs-recovered").textContent = "";
  el("cs-fill").style.width = "0%";
  el("cs-meta").textContent = "Preparing the GPU… the first run compiles kernels and can take ~30 seconds.";
}
function parseCrackStatus(line) {
  if (!_crack) return;
  let m;
  if ((m = /Status\.+:\s*([A-Za-z]+)/.exec(line))) _crack.status = m[1];
  if ((m = /Progress\.+:\s*\d+\/\d+\s*\(([\d.]+)%\)/.exec(line))) _crack.pct = parseFloat(m[1]);
  if ((m = /Speed\.#\*\.+:\s*([\d.]+\s*[kMGT]?H\/s)/.exec(line))) _crack.speed = m[1].replace(/\s+/g, " ").trim();
  if ((m = /Recovered\.+:\s*(\d+)\/(\d+)/.exec(line))) _crack.recovered = `${m[1]} of ${m[2]}`;
  if ((m = /Time\.Estimated\.+:.*\(([^)]+)\)/.exec(line))) _crack.eta = m[1];
  renderStatus();
}
function renderStatus() {
  if (!_crack) return;
  el("cs-fill").style.width = Math.min(100, _crack.pct) + "%";
  if (/Running/i.test(_crack.status)) { el("cs-state").textContent = "Cracking…"; el("cs-state").className = "cs-state running"; }
  el("cs-recovered").textContent = _crack.recovered ? "Recovered " + _crack.recovered : "";
  const bits = [];
  if (_crack.pct) bits.push(Math.round(_crack.pct) + "%");
  if (_crack.speed) bits.push(_crack.speed);
  if (_crack.eta && /Running/i.test(_crack.status)) bits.push("~" + _crack.eta + " left");
  if (bits.length) el("cs-meta").textContent = bits.join("  ·  ");
}
function finishStatus() {
  if (!_crack) return;
  const cracked = _crack.recovered && !/^0 of/.test(_crack.recovered);
  const s = el("cs-state");
  if (cracked) { s.textContent = "Cracked! 🎉"; s.className = "cs-state ok"; el("cs-fill").style.width = "100%"; el("cs-meta").textContent = "Password recovered — click Show recovered."; }
  else if (/Exhausted/i.test(_crack.status)) { s.textContent = "Finished — not found in this wordlist"; s.className = "cs-state"; el("cs-fill").style.width = "100%"; }
  else if (/Quit|Abort/i.test(_crack.status)) { s.textContent = "Stopped"; s.className = "cs-state"; }
  else { s.textContent = "Finished"; s.className = "cs-state"; }
}
// Background hashcat probe finished: swap in the full hash-mode list + version.
window.hbCatalog = (modes, version) => {
  if (Array.isArray(modes) && modes.length) { S.hashModes = modes; buildHashTypes(); }
  if (!S.hosted) el("status").innerHTML = version
    ? `hashcat <b>${esc(version)}</b>` : "hashcat <b>ready</b>";
};
// A wordlist download reported progress / a terminal state for one item.
window.hbWordlistStatus = (id, msg) => {
  const row = document.querySelector(`.wl-dl[data-id="${CSS.escape(id)}"]`);
  if (!row) return;
  const st = row.querySelector(".wl-dl-status");
  if (st) st.textContent = msg;
  const done = msg === "installed";
  const failed = /^failed/.test(msg);
  const btn = row.querySelector(".wl-dl-btn");
  if (btn) {
    btn.disabled = done;
    btn.textContent = done ? "Installed ✓" : failed ? "Retry" : "Downloading…";
  }
  row.classList.toggle("done", done);
};
// Catalog re-indexed after a download: update the count and the dropdowns.
window.hbWordlists = (count) => {
  el("wl-count").textContent = `${count} wordlists indexed`;
  refreshWordlists();
};

/* ---------- events ---------- */
function wireEvents() {
  el("theme-btn").addEventListener("click", (e) => {
    e.stopPropagation(); el("theme-menu").classList.toggle("hidden");
  });
  document.addEventListener("click", () => el("theme-menu").classList.add("hidden"));

  const VIEWS = ["crack", "captures"];
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
    const v = t.dataset.view;
    document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === t));
    VIEWS.forEach((name) => el("view-" + name).classList.toggle("hidden", name !== v));
    if (v === "captures") renderCaptures();
  }));

  // --- Settings dialog (cog) ---
  const sOverlay = el("settings-overlay");
  const openSettings = () => { sOverlay.classList.remove("hidden"); renderWordlistDownloads(); };
  const closeSettings = () => sOverlay.classList.add("hidden");
  el("settings-btn").addEventListener("click", openSettings);
  el("settings-close").addEventListener("click", closeSettings);
  sOverlay.addEventListener("click", (e) => { if (e.target === sOverlay) closeSettings(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSettings(); });

  // --- Window controls (frameless Electron window) ---
  if (window.nlwin) {
    el("win-min").addEventListener("click", () => window.nlwin.control("min"));
    el("win-max").addEventListener("click", () => window.nlwin.control("max"));
    el("win-close").addEventListener("click", () => window.nlwin.control("close"));
    window.nlwin.onState((max) => document.body.classList.toggle("maximized", !!max));
  } else {
    const wc = el("window-controls"); if (wc) wc.style.display = "none";
  }

  // --- captures import ---
  el("pick-capture").addEventListener("click", async (e) => {
    e.stopPropagation();
    const f = await pickFile(".pcap,.pcapng,.cap");
    if (!f) return;
    el("cap-msg").textContent = "reading " + f.name + "…";
    afterImport(await api().import_capture_bytes(f.name, f.b64));
  });
  const dz = el("dropzone");
  ["dragover", "dragenter"].forEach((ev) => dz.addEventListener(ev, (e) => {
    e.preventDefault(); dz.classList.add("drag");
  }));
  ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => {
    e.preventDefault(); dz.classList.remove("drag");
  }));
  dz.addEventListener("drop", async (e) => {
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (!f) return;
    el("cap-msg").textContent = "reading " + f.name + "…";
    const b64 = await fileToB64(f);
    afterImport(await api().import_capture_bytes(f.name, b64));
  });

  el("ht-category").addEventListener("change", () => { el("ht-search").value = ""; populateModeSelect(); });
  el("ht-mode").addEventListener("change", onHashModeChange);
  el("ht-search").addEventListener("input", () => populateModeSelect(el("ht-search").value.trim() || undefined));

  el("pick-hash").addEventListener("click", async () => {
    const f = await pickFile(".hc22000,.hccapx,.txt,.hash,.lst,*");
    if (!f) return;
    const r = await api().import_hash_bytes(f.name, f.b64);
    if (r.error) return out("\n[!] " + r.error + "\n", "err");
    if (r.path) el("hashfile").value = r.path;
  });
  el("rescan-btn").addEventListener("click", rescan);

  const showConsole = (on) => {
    const c = el("console"); const t = el("console-toggle");
    const vis = on === undefined ? c.classList.contains("hidden") : on;
    c.classList.toggle("hidden", !vis);
    t.textContent = vis ? "Hide console" : "Show console";
  };
  el("console-toggle").addEventListener("click", () => showConsole());

  el("cmd-btn").addEventListener("click", async () => {
    const r = await api().build_command(gatherParams());
    out(r.error ? "\n[!] " + r.error + "\n" : "\n$ " + r.command + "\n", r.error ? "err" : "cmd");
    showConsole(true);
  });
  el("run-btn").addEventListener("click", async () => {
    const r = await api().run(gatherParams());
    if (r.error) { startStatus(); el("cs-state").textContent = "Couldn't start"; el("cs-state").className = "cs-state err"; el("cs-meta").textContent = r.error; el("cs-fill").style.width = "0%"; out("\n[!] " + r.error + "\n", "err"); return; }
    el("run-btn").disabled = true; el("stop-btn").disabled = false;
    startStatus();
    out("\n=== starting ===\n$ " + r.command + "\n", "cmd");
  });
  el("stop-btn").addEventListener("click", () => api().stop());
  el("recovered-btn").addEventListener("click", async () => {
    const r = await api().show_recovered(gatherParams());
    out("\n--- recovered ---\n" + (r.text || "(nothing yet)") + "\n");
    showConsole(true);
  });

  const doUpdate = async () => {
    out("\n[update] checking…\n", "cmd");
    const info = await api().check_update();
    out(`[update] current=${info.current || "none"} latest=${info.latest || "?"}\n`);
    if (!info.update_available) return out("[update] up to date (or offline).\n");
    if (!(await uiConfirm(`Install hashcat ${info.latest}? Downloads from hashcat.net.`,
                          "Install"))) return;
    await api().install_update(info.latest);
  };
  el("update-btn2").addEventListener("click", doUpdate);

  const appBtn = el("app-update-btn");
  if (appBtn) appBtn.addEventListener("click", async () => {
    el("app-update-msg").textContent = "checking…";
    const r = await api().check_self_update();
    if (r.error) { el("app-update-msg").textContent = r.error; return; }
    if (!r.available) {
      el("app-update-msg").textContent = `Up to date (v${r.current}).`; return;
    }
    if (S.hosted) {
      el("app-update-msg").innerHTML =
        `v${esc(r.latest)} available — <a href="${esc(r.url)}" target="_blank">download from Releases</a>.`;
      return;
    }
    if (await uiConfirm(`NineLives v${r.latest} is available (you have v${r.current}).\n\n`
                + "Download and install now? The app will close to run the installer.", "Update")) {
      el("app-update-msg").textContent = `installing v${r.latest}…`;
      out(`\n[app-update] updating to v${r.latest}…\n`, "cmd");
      await api().install_self_update();
    }
  });
}
async function rescan() {
  const r = await api().set_seclists(el("seclists").value.trim());
  el("wl-count").textContent = `${r.count} wordlists indexed`;
  await refreshWordlists();
}

async function renderWordlistDownloads() {
  const box = el("wl-downloads");
  if (!box) return;
  let items = [];
  try { items = (await api().list_wordlist_downloads()).items || []; }
  catch (e) { return; }
  box.innerHTML =
    `<p class="wl-head">Download more wordlists</p>
     <p class="wl-note">⚠ Needs an internet connection. Lists are downloaded from the
       <a href="https://github.com/danielmiessler/SecLists" target="_blank" rel="noopener">SecLists project</a>
       (github.com/danielmiessler/SecLists) and saved to your data folder.</p>`;
  items.forEach((it) => {
    const row = document.createElement("div");
    row.className = "wl-dl";
    row.dataset.id = it.id;
    if (it.installed) row.classList.add("done");
    const action = it.kind === "link"
      ? `<a class="btn wl-dl-btn" href="${esc(it.url)}" target="_blank" rel="noopener">Get it ↗</a>`
      : `<button class="btn wl-dl-btn"${it.installed ? " disabled" : ""}>${it.installed ? "Installed ✓" : "Download"}</button>`;
    row.innerHTML =
      `<div class="wl-dl-info"><b>${esc(it.name)}</b> <span class="wl-dl-size">${esc(it.size)}</span>`
      + `<div class="wl-dl-desc">${esc(it.desc)}</div>`
      + `<div class="wl-dl-status hint"></div></div>${action}`;
    const btn = row.querySelector("button.wl-dl-btn");
    if (btn) btn.addEventListener("click", () => startWordlistDownload(it, btn));
    box.appendChild(row);
  });
}

async function startWordlistDownload(it, btn) {
  if (!(await uiConfirm(`Download ${it.name} (${it.size})?\n\nFetched from the SecLists project over HTTPS.`,
                        "Download"))) return;
  btn.disabled = true; btn.textContent = "Downloading…";
  out(`\n[wordlist] downloading ${it.name}…\n`, "cmd");
  const r = await api().install_wordlist(it.id);
  if (r && r.error) {
    btn.disabled = false; btn.textContent = "Download";
    out(`[wordlist] ${r.error}\n`, "err");
  }
}

/* ---------- captures ---------- */
function fileToB64(file) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(r.result);
    r.onerror = rej;
    r.readAsDataURL(file);
  });
}
// Open the OS file chooser via a hidden <input> and return {name, b64} or null.
// (Replaces the old native pywebview dialog; we upload bytes to the server.)
function pickFile(accept) {
  return new Promise((resolve) => {
    const inp = document.createElement("input");
    inp.type = "file";
    if (accept) inp.accept = accept;
    inp.style.display = "none";
    document.body.appendChild(inp);
    let done = false;
    const finish = async (f) => {
      if (done) return; done = true;
      inp.remove();
      resolve(f ? { name: f.name, b64: await fileToB64(f) } : null);
    };
    inp.addEventListener("change", () => finish(inp.files && inp.files[0]));
    // If the dialog is cancelled there's no reliable event; a focus check clears it.
    window.addEventListener("focus", () => setTimeout(() => {
      if (!done && !(inp.files && inp.files.length)) finish(null);
    }, 500), { once: true });
    inp.click();
  });
}
function afterImport(r) {
  if (!r) return;
  el("cap-msg").textContent = r.error ? ("Error: " + r.error) : (r.message || "");
  if (!r.error) renderCaptures();
}
async function renderCaptures() {
  const { captures } = await api().get_captures();
  const host = el("captures-list");
  if (!captures || !captures.length) {
    host.innerHTML = '<p class="hint">No captures imported yet.</p>';
    return;
  }
  host.innerHTML = captures.map((c) => `
    <div class="cap-row">
      <div class="cap-main">
        <span class="cap-essid">${esc(c.essid || "(hidden SSID)")}</span>
        <span class="cap-sub">${esc(c.bssid)} · ${esc(c.source)} · ${esc(c.imported)}</span>
      </div>
      <span class="cap-badges">
        ${c.pmkid ? '<span class="badge ok">PMKID</span>' : ""}
        ${c.handshake ? '<span class="badge ok">handshake</span>' : ""}
      </span>
      <span class="spacer"></span>
      ${S.hosted
        ? `<a class="btn small primary" href="/api/download?id=${encodeURIComponent(c.id)}" download>Download .hc22000</a>`
        : `<button class="btn small primary" data-use="${esc(c.id)}">Use in Crack</button>`}
      <button class="btn small ghost" data-del="${esc(c.id)}">Remove</button>
    </div>`).join("");
  host.querySelectorAll("[data-use]").forEach((b) =>
    b.addEventListener("click", () => useCapture(b.dataset.use)));
  host.querySelectorAll("[data-del]").forEach((b) =>
    b.addEventListener("click", async () => {
      await api().remove_capture(b.dataset.del); renderCaptures();
    }));
}
async function useCapture(id) {
  const r = await api().use_capture(id);
  if (r.error) { el("cap-msg").textContent = r.error; return; }
  el("hashfile").value = r.hashfile;
  setHashMode(r.mode_id);
  document.querySelector('.tab[data-view="crack"]').click();
  out(`\n[capture] loaded ${r.essid || ""} → ${r.hashfile}\n`, "cmd");
}
