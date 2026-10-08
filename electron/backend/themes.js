"use strict";
/* Theme metadata — Node port of themes.py. The actual colors live in
 * webui/styles.css as [data-theme] token sets; the UI only needs each theme's
 * id/name/note/swatch here (same shape get_init sent before). */

const THEMES = {
  synthwave: { name: "Synthwave", note: "Neon synthwave (default)", swatch: ["#0a0a14", "#22d3ee", "#ff4df0", "#a78bfa"] },
  cyberpunk: { name: "Cyberpunk", note: "High-voltage magenta", swatch: ["#0c0a10", "#ff2bd6", "#30e0ff", "#f7ff3c"] },
  terrain: { name: "Terrain", note: "Warm topographic", swatch: ["#15140f", "#e0a84a", "#9cc27a", "#7fb6c9"] },
  midnight: { name: "Midnight", note: "Low-glare navy", swatch: ["#0b1220", "#2dd4bf", "#fbbf24", "#38bdf8"] },
  daylight: { name: "Daylight", note: "Light, good for printing", swatch: ["#f4f5f7", "#2563eb", "#0d9488", "#d97706"] },
  blueprint: { name: "Blueprint", note: "Engineering grid", swatch: ["#0f2a4a", "#ffffff", "#ffd479", "#8fd3ff"] },
};
// terrain first (NetSeer's default, for a consistent feel across the apps),
// then NineLives' own synthwave/cyberpunk, then the rest of NetSeer's set.
const ORDER = ["terrain", "midnight", "daylight", "blueprint", "synthwave", "cyberpunk"];
const DEFAULT = "terrain";

module.exports = { THEMES, ORDER, DEFAULT };
