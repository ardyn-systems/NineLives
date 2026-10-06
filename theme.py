#!/usr/bin/env python3
"""
HashBench visual theme - matches the NetSeer / Astro Loop "space HUD" look:
near-black navy field, sharp white-bordered panels, cyan/green accents,
blue-gray section labels, wide display headings, monospace values.

Fonts fall back gracefully: if Orbitron / Exo 2 aren't installed the closest
system faces are used. Bundle the .ttf files and install them to pixel-match.
"""

import tkinter.font as tkfont
from tkinter import ttk

# --- palette (from WaveTopPalette) ----------------------------------------- #
BG = "#000011"
PANEL = "#111111"
ROW_ALT = "#181822"
SELECTED = "#16324A"
HUD = "#FFFFFF"
DIM = "#CCCCCC"
MUTED = "#888888"
FAINT = "#444444"
LABEL = "#88AACC"
CYAN = "#00FFFF"
GREEN = "#00FF00"
YELLOW = "#FFFF00"
GOLD = "#FFDD44"
BLUE = "#4488FF"
RED = "#FF4444"
BORDER = "#FFFFFF"

_FONTS = {}


def _pick(root, prefs, size, weight="normal"):
    fams = set(tkfont.families(root))
    for p in prefs:
        if p in fams:
            return (p, size, weight)
    return (prefs[-1], size, weight)


def fonts(root):
    if not _FONTS:
        _FONTS["display"] = _pick(root, ["Orbitron", "Bahnschrift",
                                         "Segoe UI Semibold", "Segoe UI"], 20, "bold")
        _FONTS["section"] = _pick(root, ["Orbitron", "Bahnschrift",
                                         "Segoe UI Semibold", "Segoe UI"], 10, "bold")
        _FONTS["tab"] = _pick(root, ["Orbitron", "Bahnschrift",
                                     "Segoe UI Semibold", "Segoe UI"], 10, "bold")
        _FONTS["body"] = _pick(root, ["Exo 2", "Segoe UI", "Arial"], 10)
        _FONTS["bodybold"] = _pick(root, ["Exo 2", "Segoe UI", "Arial"], 10, "bold")
        _FONTS["mono"] = _pick(root, ["Cascadia Mono", "Consolas",
                                      "Courier New"], 10)
    return _FONTS


def apply(root):
    """Apply the theme to a Tk root and return the ttk.Style."""
    f = fonts(root)
    root.configure(bg=BG)
    # dropdown list colors go through the option database
    root.option_add("*TCombobox*Listbox.background", PANEL)
    root.option_add("*TCombobox*Listbox.foreground", HUD)
    root.option_add("*TCombobox*Listbox.selectBackground", SELECTED)
    root.option_add("*TCombobox*Listbox.selectForeground", CYAN)
    root.option_add("*TCombobox*Listbox.font", f["body"])

    st = ttk.Style(root)
    st.theme_use("clam")

    st.configure(".", background=BG, foreground=HUD, fieldbackground=PANEL,
                 bordercolor=BORDER, font=f["body"], focuscolor=CYAN)
    st.configure("TFrame", background=BG)
    st.configure("TLabel", background=BG, foreground=HUD, font=f["body"])
    st.configure("Hint.TLabel", background=BG, foreground=MUTED, font=f["body"])
    st.configure("Label.TLabel", background=BG, foreground=LABEL, font=f["body"])
    st.configure("Group.TLabel", background=BG, foreground=LABEL,
                 font=f["section"])
    st.configure("Display.TLabel", background=BG, foreground=HUD,
                 font=f["display"])
    st.configure("Accentc.TLabel", background=BG, foreground=CYAN, font=f["body"])

    st.configure("TLabelframe", background=BG, bordercolor=BORDER,
                 relief="solid", borderwidth=1)
    st.configure("TLabelframe.Label", background=BG, foreground=LABEL,
                 font=f["section"])

    st.configure("TButton", background=PANEL, foreground=HUD, bordercolor=BORDER,
                 relief="solid", borderwidth=1, padding=(10, 5), font=f["bodybold"])
    st.map("TButton", background=[("active", SELECTED)],
           foreground=[("active", CYAN)])

    st.configure("Accent.TButton", background=CYAN, foreground=BG,
                 bordercolor=CYAN, font=f["bodybold"], padding=(14, 6))
    st.map("Accent.TButton", background=[("active", GREEN)],
           foreground=[("active", BG)])

    st.configure("Stop.TButton", background=PANEL, foreground=RED,
                 bordercolor=RED)
    st.map("Stop.TButton", background=[("active", "#2a0f0f")],
           foreground=[("active", RED)])

    st.configure("TEntry", fieldbackground=PANEL, foreground=HUD,
                 insertcolor=CYAN, bordercolor=BORDER)
    st.configure("TCombobox", fieldbackground=PANEL, background=PANEL,
                 foreground=HUD, arrowcolor=CYAN, bordercolor=BORDER)
    st.map("TCombobox", fieldbackground=[("readonly", PANEL)],
           foreground=[("readonly", HUD)])

    st.configure("TCheckbutton", background=BG, foreground=DIM, font=f["body"])
    st.map("TCheckbutton", foreground=[("active", HUD)],
           indicatorcolor=[("selected", CYAN), ("!selected", FAINT)])
    st.configure("TRadiobutton", background=BG, foreground=DIM, font=f["body"])
    st.map("TRadiobutton", foreground=[("active", HUD), ("selected", HUD)],
           indicatorcolor=[("selected", CYAN), ("!selected", FAINT)])

    st.configure("TNotebook", background=BG, bordercolor=BORDER, tabmargins=(2, 4, 2, 0))
    st.configure("TNotebook.Tab", background=PANEL, foreground=MUTED,
                 bordercolor=BORDER, padding=(16, 7), font=f["tab"])
    st.map("TNotebook.Tab", background=[("selected", SELECTED)],
           foreground=[("selected", HUD)])

    st.configure("TScrollbar", troughcolor=PANEL, background=FAINT,
                 bordercolor=BG, arrowcolor=DIM)
    st.configure("TSeparator", background=FAINT)
    return st
