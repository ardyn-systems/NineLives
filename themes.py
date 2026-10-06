#!/usr/bin/env python3
"""
NetSeer theme tokens, ported from NetSeer's web UI (src/netseer/web/styles.css).

These are the four shipping themes NetSeer exposes in its theme menu
(terrain / midnight / daylight / blueprint). The easter-egg themes
(matrix / neon / darkside), which NetSeer only reveals once unlocked, are
deliberately excluded.

Each theme is a flat token set; the UI reads only tokens, so switching themes
is just swapping this dict. `accent_soft` is stored as a solid hex
approximation of NetSeer's translucent accent (Tk has no alpha on fills).
"""

THEMES = {
    "terrain": {
        "name": "Terrain", "note": "Warm topographic", "scheme": "dark",
        "swatch": ["#15140f", "#e0a84a", "#9cc27a", "#7fb6c9"],
        "tokens": {
            "bg": "#15140f", "panel": "#1c1a14", "raised": "#25221a",
            "hover": "#2d2a20", "line": "#36312a", "line_strong": "#4a4436",
            "text": "#efe8d8", "muted": "#a89f88", "faint": "#7b735f",
            "accent": "#e0a84a", "accent_hover": "#eab866", "on_accent": "#2a1d05",
            "accent_soft": "#352a19", "danger": "#e57a6b", "danger_soft": "#3a211c",
            "select": "#f5d38a",
        },
    },
    "midnight": {
        "name": "Midnight", "note": "Low-glare navy", "scheme": "dark",
        "swatch": ["#0b1220", "#2dd4bf", "#fbbf24", "#38bdf8"],
        "tokens": {
            "bg": "#0b1220", "panel": "#101a2b", "raised": "#162238",
            "hover": "#1c2a43", "line": "#22324c", "line_strong": "#31476a",
            "text": "#e6edf7", "muted": "#8fa1bd", "faint": "#66779a",
            "accent": "#2dd4bf", "accent_hover": "#5eead4", "on_accent": "#042420",
            "accent_soft": "#123230", "danger": "#fb7185", "danger_soft": "#3a1c24",
            "select": "#99f6e4",
        },
    },
    "daylight": {
        "name": "Daylight", "note": "Light, good for printing", "scheme": "light",
        "swatch": ["#f4f5f7", "#2563eb", "#0d9488", "#d97706"],
        "tokens": {
            "bg": "#f4f5f7", "panel": "#ffffff", "raised": "#f7f8fa",
            "hover": "#eef1f5", "line": "#e1e5eb", "line_strong": "#c9d0da",
            "text": "#18212f", "muted": "#5b6676", "faint": "#8a94a3",
            "accent": "#2563eb", "accent_hover": "#1d4fd8", "on_accent": "#ffffff",
            "accent_soft": "#e7eefc", "danger": "#dc2626", "danger_soft": "#fbe9e9",
            "select": "#cfe0ff",
        },
    },
    "blueprint": {
        "name": "Blueprint", "note": "Engineering grid", "scheme": "dark",
        "swatch": ["#0f2a4a", "#ffffff", "#ffd479", "#8fd3ff"],
        "tokens": {
            "bg": "#0d2644", "panel": "#102d50", "raised": "#14365f",
            "hover": "#19406f", "line": "#24507f", "line_strong": "#3567a0",
            "text": "#eaf2ff", "muted": "#a3bddf", "faint": "#7896bd",
            "accent": "#ffffff", "accent_hover": "#dfeaff", "on_accent": "#0d2644",
            "accent_soft": "#1b3a5f", "danger": "#ff9b8f", "danger_soft": "#3a211f",
            "select": "#ffd479",
        },
    },
}

# NetSeer's menu order; also the default.
ORDER = ["terrain", "midnight", "daylight", "blueprint"]
DEFAULT = "terrain"


def get(theme_id):
    return THEMES.get(theme_id, THEMES[DEFAULT])
