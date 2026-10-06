#!/usr/bin/env python3
"""
HashBench theming - applies a NetSeer theme (themes.py) to the ttk UI.

NetSeer's look: Segoe UI, flat panels with 1px lines, rounded-feel accent
buttons, muted secondary text, a single accent color per theme. Four themes
ship (terrain/midnight/daylight/blueprint); switching re-applies tokens live.

Module-level color globals (BG, PANEL, TEXT, ACCENT, ...) reflect the current
theme after apply() and are used for the handful of non-ttk widgets (the log
console, tooltips). ttk widgets restyle automatically when apply() re-runs.
"""

import tkinter.font as tkfont
from tkinter import ttk

import settings
import themes

# current theme id + token globals (populated by apply())
CURRENT = themes.DEFAULT
BG = PANEL = RAISED = HOVER = LINE = LINE_STRONG = "#000000"
TEXT = MUTED = FAINT = ACCENT = ACCENT_HOVER = ON_ACCENT = "#ffffff"
ACCENT_SOFT = DANGER = DANGER_SOFT = SELECT = "#000000"
# legacy aliases referenced by app.py's non-ttk widgets
CYAN = GREEN = ACCENT
DIM = MUTED

_FONTS = {}


def _pick(root, prefs, size, weight="normal"):
    fams = set(tkfont.families(root))
    for p in prefs:
        if p in fams:
            return (p, size, weight)
    return (prefs[-1], size, weight)


def fonts(root):
    """NetSeer uses Segoe UI for text and Cascadia Mono/Consolas for code."""
    if not _FONTS:
        ui = ["Segoe UI", "Inter", "system-ui", "Helvetica Neue", "Arial"]
        mono = ["Cascadia Mono", "Consolas", "Courier New"]
        _FONTS["display"] = _pick(root, ui, 15, "bold")
        _FONTS["section"] = _pick(root, ui, 9, "bold")
        _FONTS["tab"] = _pick(root, ui, 10)
        _FONTS["body"] = _pick(root, ui, 10)
        _FONTS["bodybold"] = _pick(root, ui, 10, "bold")
        _FONTS["mono"] = _pick(root, mono, 10)
    return _FONTS


def theme_choices():
    """[(id, 'Name - note'), ...] in NetSeer's menu order."""
    out = []
    for tid in themes.ORDER:
        t = themes.THEMES[tid]
        out.append((tid, f"{t['name']} - {t['note']}"))
    return out


def _set_globals(tk_):
    g = globals()
    for k, v in tk_.items():
        g[k.upper()] = v
    g["CYAN"] = g["GREEN"] = tk_["accent"]
    g["DIM"] = tk_["muted"]


def apply(root, theme_id=None):
    """Apply a theme to the Tk root and return the ttk.Style."""
    global CURRENT
    theme_id = theme_id or settings.get("ui_theme", themes.DEFAULT)
    if theme_id not in themes.THEMES:
        theme_id = themes.DEFAULT
    CURRENT = theme_id
    t = themes.get(theme_id)["tokens"]
    _set_globals(t)
    settings.set("ui_theme", theme_id)

    f = fonts(root)
    root.configure(bg=t["bg"])
    root.option_add("*TCombobox*Listbox.background", t["raised"])
    root.option_add("*TCombobox*Listbox.foreground", t["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", t["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", t["on_accent"])
    root.option_add("*TCombobox*Listbox.font", f["body"])

    st = ttk.Style(root)
    st.theme_use("clam")

    st.configure(".", background=t["bg"], foreground=t["text"],
                 fieldbackground=t["raised"], bordercolor=t["line"],
                 font=f["body"], focuscolor=t["accent"])
    st.configure("TFrame", background=t["bg"])
    st.configure("TLabel", background=t["bg"], foreground=t["text"], font=f["body"])
    st.configure("Hint.TLabel", background=t["bg"], foreground=t["muted"],
                 font=f["body"])
    st.configure("Label.TLabel", background=t["bg"], foreground=t["muted"],
                 font=f["body"])
    st.configure("Group.TLabel", background=t["bg"], foreground=t["muted"],
                 font=f["section"])
    st.configure("Display.TLabel", background=t["bg"], foreground=t["text"],
                 font=f["display"])
    st.configure("Accentc.TLabel", background=t["bg"], foreground=t["accent"],
                 font=f["body"])

    # Cards (labelframes): 1px line border on the base bg, muted caption.
    st.configure("TLabelframe", background=t["bg"], bordercolor=t["line"],
                 relief="solid", borderwidth=1)
    st.configure("TLabelframe.Label", background=t["bg"], foreground=t["muted"],
                 font=f["section"])

    # Buttons: NetSeer .btn (raised fill, line-strong border) + .btn.primary.
    st.configure("TButton", background=t["raised"], foreground=t["text"],
                 bordercolor=t["line_strong"], relief="solid", borderwidth=1,
                 padding=(12, 6), font=f["body"])
    st.map("TButton", background=[("active", t["hover"]), ("disabled", t["panel"])],
           bordercolor=[("active", t["faint"])],
           foreground=[("disabled", t["faint"])])

    st.configure("Accent.TButton", background=t["accent"], foreground=t["on_accent"],
                 bordercolor=t["accent"], font=f["bodybold"], padding=(14, 7))
    st.map("Accent.TButton",
           background=[("active", t["accent_hover"]), ("disabled", t["panel"])],
           bordercolor=[("active", t["accent_hover"])],
           foreground=[("disabled", t["faint"])])

    st.configure("Stop.TButton", background=t["raised"], foreground=t["danger"],
                 bordercolor=t["line_strong"])
    st.map("Stop.TButton", background=[("active", t["danger_soft"])],
           foreground=[("active", t["danger"])])

    st.configure("TEntry", fieldbackground=t["raised"], foreground=t["text"],
                 insertcolor=t["accent"], bordercolor=t["line_strong"])
    st.configure("TCombobox", fieldbackground=t["raised"], background=t["raised"],
                 foreground=t["text"], arrowcolor=t["muted"],
                 bordercolor=t["line_strong"])
    st.map("TCombobox", fieldbackground=[("readonly", t["raised"])],
           foreground=[("readonly", t["text"])])

    st.configure("TCheckbutton", background=t["bg"], foreground=t["text"],
                 font=f["body"])
    st.map("TCheckbutton", foreground=[("active", t["text"])],
           indicatorcolor=[("selected", t["accent"]), ("!selected", t["raised"])])
    st.configure("TRadiobutton", background=t["bg"], foreground=t["text"],
                 font=f["body"])
    st.map("TRadiobutton", foreground=[("active", t["text"])],
           indicatorcolor=[("selected", t["accent"]), ("!selected", t["raised"])])

    # Tabs: active = text color + accent underline feel (bg lifts to panel).
    st.configure("TNotebook", background=t["bg"], bordercolor=t["line"],
                 tabmargins=(2, 4, 2, 0))
    st.configure("TNotebook.Tab", background=t["bg"], foreground=t["muted"],
                 bordercolor=t["line"], padding=(16, 8), font=f["tab"])
    st.map("TNotebook.Tab",
           background=[("selected", t["panel"])],
           foreground=[("selected", t["text"]), ("active", t["text"])])

    st.configure("TScrollbar", troughcolor=t["panel"], background=t["line_strong"],
                 bordercolor=t["bg"], arrowcolor=t["muted"])
    st.configure("TSeparator", background=t["line"])
    return st
