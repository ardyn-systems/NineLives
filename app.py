#!/usr/bin/env python3
"""
HashBench GUI - a push-button front-end for hashcat.

Everything the user sees is driven by the backend engines so it stays in sync
with hashcat automatically:
  * hash-type dropdown      <- hashcat_iface.load_hash_modes() (live --help/cache)
  * attack-mode selector    <- compat.ATTACK_MODES
  * which options to show    <- compat.options_for(attack_mode)  (stackable only)
  * wordlist dropdowns       <- wordlists.Catalog (SecLists), with suggestions
  * update button            <- updater.check()/install()

For AUTHORIZED password auditing of equipment you own or are scoped to test.
"""

import os
import queue
import threading
import subprocess
import multiprocessing as mp

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

import settings
import compat
import theme
import wordlists
import hashcat_iface as hc
import updater

APP_DIR = hc.APP_DIR
POTFILE = os.path.join(APP_DIR, "hashbench.potfile")


# --------------------------------------------------------------------------- #
# Small tooltip helper
# --------------------------------------------------------------------------- #
class Tip:
    def __init__(self, widget, text):
        self.widget, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _e):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(self.tip, text=self.text, justify="left",
                       bg=theme.PANEL, fg=theme.DIM, relief="solid",
                       borderwidth=1, highlightbackground=theme.CYAN,
                       highlightthickness=1, wraplength=420,
                       font=theme.fonts(self.widget)["body"])
        lbl.pack(ipadx=4, ipady=2)

    def _hide(self, _e):
        if self.tip:
            self.tip.destroy()
            self.tip = None


# --------------------------------------------------------------------------- #
# Main window
# --------------------------------------------------------------------------- #
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HashBench - push-button hashcat")
        self.geometry("1040x780")
        self.minsize(900, 640)
        self.style = theme.apply(self)

        self.catalog = wordlists.Catalog()
        self.catalog.scan()
        self.modes = hc.load_hash_modes()
        self.mode_by_label = {}
        self.proc = None
        self.out_q = queue.Queue()
        self.option_widgets = []   # (Opt, var, entry_or_None)
        self.input_vars = {}       # slot -> widget/var accessors

        if not settings.get("acknowledged"):
            self.after(80, self._consent)

        self._build_statusbar()
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tab_crack = ttk.Frame(nb)
        self.tab_set = ttk.Frame(nb)
        nb.add(self.tab_crack, text="Crack")
        nb.add(self.tab_set, text="Settings")
        self._build_crack(self.tab_crack)
        self._build_settings(self.tab_set)

        self._rebuild_dynamic()
        self.after(120, self._drain)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # --- consent ----------------------------------------------------------
    def _consent(self):
        ok = messagebox.askyesno(
            "Authorized use",
            "HashBench audits hashes from equipment you own or are explicitly "
            "authorized to test.\n\nConfirm you'll use it only that way?")
        if not ok:
            self.destroy()
            raise SystemExit(0)
        settings.set("acknowledged", True)

    # --- status bar -------------------------------------------------------
    def _build_statusbar(self):
        header = ttk.Frame(self)
        header.pack(fill="x", padx=12, pady=(12, 2))
        ttk.Label(header, text="HASHBENCH", style="Display.TLabel").pack(side="left")
        ttk.Label(header, text="  hashcat control console",
                  style="Hint.TLabel").pack(side="left", pady=(10, 0))
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=12, pady=(2, 0))

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=12, pady=6)
        self.hc_status = tk.StringVar()
        self._refresh_hc_status()
        ttk.Label(bar, textvariable=self.hc_status,
                  style="Accentc.TLabel").pack(side="left")
        ttk.Button(bar, text="Check for updates",
                   command=self._check_updates).pack(side="right")

    def _refresh_hc_status(self):
        path = hc.find_hashcat()
        if path:
            self.hc_status.set(f"hashcat: {updater.current_version() or '?'}  "
                               f"({path})")
        else:
            self.hc_status.set("hashcat: NOT installed - use Settings to "
                               "install/update, or the dropdowns still work offline")

    # --- crack tab --------------------------------------------------------
    def _build_crack(self, f):
        pad = dict(padx=6, pady=4)
        r = 0
        ttk.Label(f, text="Hash file:").grid(row=r, column=0, sticky="w", **pad)
        self.hash_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.hash_var).grid(row=r, column=1,
                                                      columnspan=2, sticky="we", **pad)
        ttk.Button(f, text="Browse...", command=self._pick_hash).grid(
            row=r, column=3, **pad)

        r += 1
        ttk.Label(f, text="Hash type:").grid(row=r, column=0, sticky="w", **pad)
        self.mode_var = tk.StringVar()
        self.mode_cb = ttk.Combobox(f, textvariable=self.mode_var, state="normal")
        self._load_mode_values()
        self.mode_cb.grid(row=r, column=1, sticky="we", **pad)
        self.mode_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_mode_change())
        self.mode_cb.bind("<KeyRelease>", self._filter_modes)
        self.mode_hint = ttk.Label(f, text="", style="Hint.TLabel")
        self.mode_hint.grid(row=r, column=2, columnspan=2, sticky="w", **pad)

        r += 1
        ttk.Label(f, text="Attack:").grid(row=r, column=0, sticky="w", **pad)
        self.attack_var = tk.IntVar(value=0)
        af = ttk.Frame(f)
        af.grid(row=r, column=1, columnspan=3, sticky="w", **pad)
        for m in compat.ATTACK_MODES:
            ttk.Radiobutton(af, text=f"-a {m['id']}  {m['name']}",
                            variable=self.attack_var, value=m["id"],
                            command=self._rebuild_dynamic).pack(anchor="w")
        self.attack_desc = ttk.Label(f, text="", style="Accentc.TLabel",
                                      wraplength=760)
        r += 1
        self.attack_desc.grid(row=r, column=1, columnspan=3, sticky="w", **pad)

        # dynamic inputs (wordlists / mask)
        r += 1
        self.inputs_frame = ttk.LabelFrame(f, text="Inputs")
        self.inputs_frame.grid(row=r, column=0, columnspan=4, sticky="we", **pad)

        # stackable options (scrollable)
        r += 1
        optwrap = ttk.LabelFrame(f, text="Options that stack with this attack")
        optwrap.grid(row=r, column=0, columnspan=4, sticky="nsew", **pad)
        self.opt_canvas = tk.Canvas(optwrap, height=220, highlightthickness=0)
        sb = ttk.Scrollbar(optwrap, orient="vertical",
                           command=self.opt_canvas.yview)
        self.opt_inner = ttk.Frame(self.opt_canvas)
        self.opt_inner.bind("<Configure>", lambda _e: self.opt_canvas.configure(
            scrollregion=self.opt_canvas.bbox("all")))
        self.opt_canvas.create_window((0, 0), window=self.opt_inner, anchor="nw")
        self.opt_canvas.configure(yscrollcommand=sb.set)
        self.opt_canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        r += 1
        bf = ttk.Frame(f)
        bf.grid(row=r, column=0, columnspan=4, sticky="w", **pad)
        self.run_btn = ttk.Button(bf, text="  RUN CRACK  ", command=self._run,
                                   style="Accent.TButton")
        self.run_btn.pack(side="left")
        self.stop_btn = ttk.Button(bf, text="Stop", command=self._stop,
                                   state="disabled", style="Stop.TButton")
        self.stop_btn.pack(side="left", padx=6)
        ttk.Button(bf, text="Show command",
                   command=self._show_cmd).pack(side="left", padx=6)
        ttk.Button(bf, text="Show recovered",
                   command=self._show_recovered).pack(side="left")

        r += 1
        self.log = scrolledtext.ScrolledText(
            f, height=12, bg=theme.PANEL, fg=theme.GREEN,
            insertbackground=theme.CYAN, borderwidth=1, relief="solid",
            highlightthickness=0, font=theme.fonts(self)["mono"])
        self.log.grid(row=r, column=0, columnspan=4, sticky="nsew", **pad)
        f.columnconfigure(1, weight=1)
        f.rowconfigure(r, weight=1)

    def _load_mode_values(self, filter_text=""):
        self.mode_by_label = {}
        vals = []
        ft = filter_text.lower()
        for m in self.modes:
            label = f"{m['id']:>6}  {m['name']}  [{m['category']}]"
            if ft and ft not in label.lower():
                continue
            self.mode_by_label[label] = m
            vals.append(label)
        self.mode_cb["values"] = vals
        if vals and not self.mode_var.get():
            self.mode_var.set(vals[0])

    def _filter_modes(self, event):
        # don't hijack arrow/enter selection
        if event.keysym in ("Up", "Down", "Return", "Escape"):
            return
        self._load_mode_values(self.mode_var.get())
        self.mode_cb.event_generate("<Down>") if self.mode_cb["values"] else None

    def _current_mode(self):
        return self.mode_by_label.get(self.mode_var.get())

    def _on_mode_change(self):
        m = self._current_mode()
        if not m:
            return
        hint = ""
        if hc.find_hashcat():
            ex = hc.example_hash(m["id"])
            hint = f"example: {ex[:40]}..." if ex else ""
        self.mode_hint.config(text=hint)
        self._refresh_wordlist_suggestions()

    # --- dynamic inputs + options ----------------------------------------
    def _rebuild_dynamic(self):
        aid = self.attack_var.get()
        self.attack_desc.config(text=compat.explain_mode(aid))
        self._build_inputs(aid)
        self._build_options(aid)

    def _build_inputs(self, aid):
        for w in self.inputs_frame.winfo_children():
            w.destroy()
        self.input_vars = {}
        slots = compat.inputs_for(aid)
        row = 0
        for i, slot in enumerate(slots):
            if slot in ("wordlist", "wordlist2"):
                lbl = "Wordlist" + (" (left)" if aid == 1 and slot == "wordlist"
                                    else " (right)" if aid == 1 else "")
                ttk.Label(self.inputs_frame, text=lbl + ":").grid(
                    row=row, column=0, sticky="w", padx=6, pady=4)
                var = tk.StringVar()
                cb = ttk.Combobox(self.inputs_frame, textvariable=var,
                                  width=70, state="normal")
                cb.grid(row=row, column=1, sticky="we", padx=6, pady=4)
                self.input_vars[slot] = ("wordlist", var, cb)
            elif slot == "mask":
                ttk.Label(self.inputs_frame, text="Mask:").grid(
                    row=row, column=0, sticky="w", padx=6, pady=4)
                var = tk.StringVar(value="?d?d?d?d?d?d?d?d")
                ent = ttk.Entry(self.inputs_frame, textvariable=var, width=40)
                ent.grid(row=row, column=1, sticky="w", padx=6, pady=4)
                Tip(ent, "?l lower  ?u upper  ?d digit  ?s symbol  ?a all  "
                         "?1-?4 custom charsets")
                self.input_vars[slot] = ("mask", var, ent)
            row += 1
        self.inputs_frame.columnconfigure(1, weight=1)
        self._refresh_wordlist_suggestions()

    def _refresh_wordlist_suggestions(self):
        m = self._current_mode()
        suggested, fam = ([], "")
        if m:
            suggested, fam = self.catalog.suggest(m)
        all_entries = self.catalog.all_entries()
        self._wl_path_by_label = {}
        values = []
        if suggested:
            for e in suggested:
                lbl = f"★ {e['name']}  [{e['category']}]"
                self._wl_path_by_label[lbl] = e["path"]
                values.append(lbl)
            values.append("─" * 30)
        for e in all_entries:
            lbl = f"{e['name']}  [{e['category']}]"
            self._wl_path_by_label[lbl] = e["path"]
            values.append(lbl)
        for slot, tup in self.input_vars.items():
            if tup[0] == "wordlist":
                cb = tup[2]
                cb["values"] = values
                if not all_entries:
                    cb.set("(set SecLists folder in Settings)")
        # a short note about what family we matched
        if m and hasattr(self, "mode_hint"):
            note = self.mode_hint.cget("text")
            fam_txt = f"suggested: {fam}" if suggested else \
                ("no SecLists indexed" if not all_entries else f"({fam})")
            self.mode_hint.config(text=(note + "   " if note else "") + fam_txt)

    def _build_options(self, aid):
        for w in self.opt_inner.winfo_children():
            w.destroy()
        self.option_widgets = []
        groups = compat.grouped_options_for(aid)
        for grp, opts in groups.items():
            ttk.Label(self.opt_inner, text=grp.upper(),
                      style="Group.TLabel").pack(anchor="w", pady=(8, 2))
            for o in opts:
                row = ttk.Frame(self.opt_inner)
                row.pack(fill="x", anchor="w")
                var = tk.BooleanVar()
                flagtxt = (o.flag + ", " if o.flag else "") + o.long
                cb = ttk.Checkbutton(row, text=flagtxt, variable=var, width=28)
                cb.pack(side="left", anchor="w")
                Tip(cb, o.desc + (f"\n\nExample: {o.example}" if o.example else ""))
                entry = None
                if o.takes_value:
                    entry = ttk.Entry(row, width=16)
                    entry.pack(side="left", padx=4)
                    if o.example:
                        ph = o.example.split()[-1]
                        entry.insert(0, ph)
                        entry.config(foreground="#999")
                ttk.Label(row, text=o.desc, style="Hint.TLabel",
                          wraplength=520).pack(side="left", padx=6)
                self.option_widgets.append((o, var, entry))

    # --- command assembly -------------------------------------------------
    def _wordlist_path(self, slot):
        tup = self.input_vars.get(slot)
        if not tup:
            return None
        label = tup[1].get()
        return getattr(self, "_wl_path_by_label", {}).get(label, label or None)

    def _build_cmd(self, require_hashcat=True):
        path = hc.find_hashcat()
        if require_hashcat and not path:
            messagebox.showerror("No hashcat",
                                 "hashcat isn't installed. Install it from the "
                                 "Settings tab first.")
            return None
        m = self._current_mode()
        if not m:
            messagebox.showerror("No hash type", "Pick a hash type.")
            return None
        hashfile = self.hash_var.get().strip()
        if not hashfile:
            messagebox.showerror("No hash file", "Pick a hash file.")
            return None

        aid = self.attack_var.get()
        cmd = [path or "hashcat", "-m", str(m["id"]), "-a", str(aid), hashfile]

        # inputs in the order this attack mode expects
        slots = compat.inputs_for(aid)
        for slot in slots:
            if slot in ("wordlist", "wordlist2"):
                wl = self._wordlist_path(slot)
                if not wl or not os.path.isfile(wl):
                    messagebox.showerror("Wordlist", f"Pick a valid {slot}.")
                    return None
                cmd.append(wl)
            elif slot == "mask":
                mask = self.input_vars[slot][1].get().strip()
                if not mask:
                    messagebox.showerror("Mask", "Enter a mask.")
                    return None
                cmd.append(mask)

        # stacked options
        for o, var, entry in self.option_widgets:
            if not var.get():
                continue
            flag = o.flag or o.long
            if o.takes_value:
                val = entry.get().strip() if entry else ""
                if val:
                    cmd += [flag, val]
            else:
                cmd.append(flag)

        # always keep a shared potfile unless the user disabled it
        if not any(o.long == "--potfile-disable" and v.get()
                   for o, v, _ in self.option_widgets):
            cmd += ["--potfile-path", POTFILE]
        return cmd

    def _show_cmd(self):
        cmd = self._build_cmd(require_hashcat=False)
        if cmd:
            self.log.insert("end", "\n$ " + subprocess.list2cmdline(cmd) + "\n")
            self.log.see("end")

    # --- run --------------------------------------------------------------
    def _run(self):
        if self.proc:
            messagebox.showinfo("Busy", "A crack is already running.")
            return
        cmd = self._build_cmd()
        if not cmd:
            return
        self.log.insert("end", "\n=== starting ===\n$ "
                        + subprocess.list2cmdline(cmd) + "\n")
        self.log.see("end")
        self.run_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        def worker():
            try:
                self.proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, cwd=APP_DIR)
                for line in self.proc.stdout:
                    self.out_q.put(line)
                self.proc.wait()
            except Exception as e:  # noqa: BLE001
                self.out_q.put(f"[error] {e}\n")
            finally:
                self.proc = None
                self.out_q.put(("__done__",))

        threading.Thread(target=worker, daemon=True).start()

    def _stop(self):
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:  # noqa: BLE001
                pass
            self.log.insert("end", "\n[stopped]\n")

    def _drain(self):
        try:
            while True:
                item = self.out_q.get_nowait()
                if isinstance(item, tuple) and item and item[0] == "__done__":
                    self.run_btn.config(state="normal")
                    self.stop_btn.config(state="disabled")
                    self.log.insert("end", "\n=== finished ===\n")
                    continue
                self.log.insert("end", item)
                self.log.see("end")
        except queue.Empty:
            pass
        self.after(120, self._drain)

    def _show_recovered(self):
        path = hc.find_hashcat()
        if not path:
            messagebox.showinfo("No hashcat", "Install hashcat first.")
            return
        cmd = self._build_cmd(require_hashcat=False)
        if not cmd:
            return
        show = [cmd[0]] + cmd[1:cmd.index("-a")] + ["--show",
                "--potfile-path", POTFILE, self.hash_var.get().strip()]
        out = hc._run_text(cmd[0], cmd[1:] + ["--show"], timeout=30)
        text = (out.stdout if out else "") or "(nothing recovered yet)"
        win = tk.Toplevel(self)
        win.title("Recovered")
        win.geometry("560x380")
        t = scrolledtext.ScrolledText(win)
        t.pack(fill="both", expand=True)
        t.insert("end", text)

    def _pick_hash(self):
        p = filedialog.askopenfilename(
            title="Select hash file",
            filetypes=[("hashcat capture", "*.hc22000 *.22000 *.hash *.txt"),
                       ("All files", "*.*")])
        if p:
            self.hash_var.set(p)

    # --- settings tab -----------------------------------------------------
    def _build_settings(self, f):
        pad = dict(padx=8, pady=6)
        ttk.Label(f, text="SecLists / wordlists folder:").grid(
            row=0, column=0, sticky="w", **pad)
        self.sl_var = tk.StringVar(value=settings.get("seclists_root", ""))
        ttk.Entry(f, textvariable=self.sl_var, width=66).grid(
            row=0, column=1, sticky="we", **pad)
        ttk.Button(f, text="Browse...", command=self._pick_seclists).grid(
            row=0, column=2, **pad)
        self.sl_count = ttk.Label(f, text=f"{len(self.catalog.all_entries())} "
                                  "wordlists indexed")
        self.sl_count.grid(row=1, column=1, sticky="w", **pad)
        ttk.Button(f, text="Rescan", command=self._rescan).grid(
            row=1, column=2, **pad)

        ttk.Separator(f, orient="horizontal").grid(
            row=2, column=0, columnspan=3, sticky="we", pady=10)

        ttk.Label(f, text="hashcat:").grid(row=3, column=0, sticky="w", **pad)
        self.hcpath_var = tk.StringVar(value=hc.find_hashcat())
        ttk.Entry(f, textvariable=self.hcpath_var, width=66).grid(
            row=3, column=1, sticky="we", **pad)
        ttk.Button(f, text="Check / install update",
                   command=self._check_updates).grid(row=3, column=2, **pad)
        ttk.Label(f, text=f"Bundled location: {hc.VENDOR_DIR}",
                  style="Hint.TLabel").grid(row=4, column=1, sticky="w", **pad)
        f.columnconfigure(1, weight=1)

    def _pick_seclists(self):
        d = filedialog.askdirectory(title="Pick your SecLists folder")
        if d:
            self.sl_var.set(d)
            self._rescan()

    def _rescan(self):
        self.catalog.set_root(self.sl_var.get().strip())
        self.sl_count.config(text=f"{len(self.catalog.all_entries())} "
                             "wordlists indexed")
        self._refresh_wordlist_suggestions()

    def _check_updates(self):
        self.log_set = getattr(self, "log", None)
        def work():
            self.out_q.put("\n[update] checking hashcat releases...\n")
            try:
                info = updater.check()
            except Exception as e:  # noqa: BLE001
                self.out_q.put(f"[update] check failed: {e}\n")
                return
            self.out_q.put(f"[update] current={info['current'] or 'none'} "
                           f"latest={info['latest'] or '?'}\n")
            if not info["update_available"]:
                self.out_q.put("[update] up to date (or offline).\n")
                return
            if not self._ask_install(info):
                return
            try:
                ver = updater.install(info["latest"],
                                      progress=lambda m: self.out_q.put(
                                          f"[update] {m}\n"))
                self.out_q.put(f"[update] done: hashcat {ver}\n")
                self.modes = hc.load_hash_modes(refresh=True)
                self.after(0, self._post_update_refresh)
            except Exception as e:  # noqa: BLE001
                self.out_q.put(f"[update] install failed: {e}\n")
        threading.Thread(target=work, daemon=True).start()

    def _ask_install(self, info):
        # messagebox must run on the main thread
        result = {"ok": False}
        done = threading.Event()
        def ask():
            result["ok"] = messagebox.askyesno(
                "Update hashcat",
                f"Install hashcat {info['latest']} "
                f"(have {info['current'] or 'none'})?\n\n"
                "Downloads the official release from hashcat.net.")
            done.set()
        self.after(0, ask)
        done.wait()
        return result["ok"]

    def _post_update_refresh(self):
        self._load_mode_values()
        self._refresh_hc_status()
        self.hcpath_var.set(hc.find_hashcat())

    def _on_close(self):
        if self.proc and not messagebox.askyesno(
                "Quit", "A crack is running. Stop and quit?"):
            return
        self._stop()
        self.destroy()


def main():
    mp.freeze_support()
    App().mainloop()


if __name__ == "__main__":
    main()
