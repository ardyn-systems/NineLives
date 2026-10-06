/* HashBench web UI — talks to the Python backend via window.pywebview.api. */
"use strict";

const api = () => window.pywebview.api;
const el = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

const S = {
  themes: [], attackModes: [], hashModes: [],
  modeByLabel: new Map(), modeById: new Map(),
  attackId: 0, optionsMeta: new Map(), // key -> {takes_value}
  wlByValue: new Map(),
};

/* ---------- init ---------- */
window.addEventListener("pywebviewready", async () => {
  const init = await api().get_init();
  if (!init.acknowledged) {
    if (confirm("HashBench audits hashes from equipment you own or are explicitly authorized to test.\n\nConfirm you'll use it only that way?"))
      api().acknowledge();
  }
  S.themes = init.themes;
  S.attackModes = init.attack_modes;
  S.hashModes = init.hash_modes;
  document.documentElement.dataset.theme = init.current_theme;
  buildThemeMenu(init.current_theme);
  buildHashTypes();
  buildAttackSeg();
  el("status").innerHTML = init.hashcat.present
    ? `hashcat <b>${esc(init.hashcat.version || "?")}</b>`
    : `hashcat <b>not installed</b> — dropdowns work offline`;
  el("seclists").value = init.seclists_root || "";
  el("wl-count").textContent = `${init.wordlists_count} wordlists indexed`;
  el("hc-info").textContent = init.hashcat.present
    ? `Found: ${init.hashcat.version}` : "Not installed yet.";
  await selectAttack(0);
  wireEvents();
});

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

/* ---------- hash types ---------- */
function buildHashTypes() {
  const dl = el("hashtypes");
  dl.innerHTML = "";
  S.hashModes.forEach((m) => {
    const label = `${m.id}  ${m.name}  [${m.category}]`;
    S.modeByLabel.set(label, m);
    S.modeById.set(m.id, m);
    const o = document.createElement("option");
    o.value = label;
    dl.appendChild(o);
  });
}
function currentMode() {
  const v = el("hashtype").value.trim();
  if (S.modeByLabel.has(v)) return S.modeByLabel.get(v);
  const num = parseInt(v, 10);
  if (!isNaN(num) && S.modeById.has(num)) return S.modeById.get(num);
  return null;
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
window.hbOutput = (line) => out(line);
window.hbDone = () => { el("run-btn").disabled = false; el("stop-btn").disabled = true; out("\n=== finished ===\n", "cmd"); };

/* ---------- events ---------- */
function wireEvents() {
  el("theme-btn").addEventListener("click", (e) => {
    e.stopPropagation(); el("theme-menu").classList.toggle("hidden");
  });
  document.addEventListener("click", () => el("theme-menu").classList.add("hidden"));

  const VIEWS = ["crack", "captures", "settings"];
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
    const v = t.dataset.view;
    document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === t));
    VIEWS.forEach((name) => el("view-" + name).classList.toggle("hidden", name !== v));
    if (v === "captures") renderCaptures();
  }));

  // --- captures import ---
  el("pick-capture").addEventListener("click", async (e) => {
    e.stopPropagation();
    const p = await api().pick_file("capture");
    if (p) afterImport(await api().import_capture(p));
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

  el("hashtype").addEventListener("change", async () => {
    const m = currentMode();
    el("type-hint").textContent = m ? `mode ${m.id} · ${m.category}` : "";
    await refreshWordlists();
  });

  el("pick-hash").addEventListener("click", async () => {
    const p = await api().pick_file("hashfile");
    if (p) el("hashfile").value = p;
  });
  el("pick-seclists").addEventListener("click", async () => {
    const p = await api().pick_file("folder");
    if (p) { el("seclists").value = p; await rescan(); }
  });
  el("rescan-btn").addEventListener("click", rescan);

  el("cmd-btn").addEventListener("click", async () => {
    const r = await api().build_command(gatherParams());
    if (r.error) return out("\n[!] " + r.error + "\n", "err");
    out("\n$ " + r.command + "\n", "cmd");
  });
  el("run-btn").addEventListener("click", async () => {
    const r = await api().run(gatherParams());
    if (r.error) return out("\n[!] " + r.error + "\n", "err");
    el("run-btn").disabled = true; el("stop-btn").disabled = false;
    out("\n=== starting ===\n$ " + r.command + "\n", "cmd");
  });
  el("stop-btn").addEventListener("click", () => api().stop());
  el("recovered-btn").addEventListener("click", async () => {
    const r = await api().show_recovered(gatherParams());
    out("\n--- recovered ---\n" + (r.text || "(nothing yet)") + "\n");
  });
  el("clear-btn").addEventListener("click", () => { el("console").innerHTML = ""; });

  const doUpdate = async () => {
    out("\n[update] checking…\n", "cmd");
    const info = await api().check_update();
    out(`[update] current=${info.current || "none"} latest=${info.latest || "?"}\n`);
    if (!info.update_available) return out("[update] up to date (or offline).\n");
    if (!confirm(`Install hashcat ${info.latest}? Downloads from hashcat.net.`)) return;
    await api().install_update(info.latest);
  };
  el("update-btn").addEventListener("click", doUpdate);
  el("update-btn2").addEventListener("click", doUpdate);
}
async function rescan() {
  const r = await api().set_seclists(el("seclists").value.trim());
  el("wl-count").textContent = `${r.count} wordlists indexed`;
  await refreshWordlists();
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
      <button class="btn small primary" data-use="${esc(c.id)}">Use in Crack</button>
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
  const m = S.modeById.get(r.mode_id);
  if (m) {
    el("hashtype").value = `${m.id}  ${m.name}  [${m.category}]`;
    el("hashtype").dispatchEvent(new Event("change"));
  }
  document.querySelector('.tab[data-view="crack"]').click();
  out(`\n[capture] loaded ${r.essid || ""} → ${r.hashfile}\n`, "cmd");
}
