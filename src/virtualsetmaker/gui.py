"""A small tkinter GUI: pick Shot Designer .hcw files, export Unreal scripts.

Pure stdlib (tkinter ships with python.org installs on Windows), and the same
build core as the CLI (:func:`virtualsetmaker.build.build_hcw`), so the two
front ends can never drift apart. Launch via ``vsm gui`` or the ``vsm-gui``
entry point (console-free on Windows).
"""

from __future__ import annotations

import json
import os
import traceback

import tkinter as tk
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText

from .build import build_hcw, default_output_name

SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".virtualsetmaker.json")


def _load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_settings(settings: dict) -> None:
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
            json.dump(settings, fh, indent=2)
    except OSError:
        pass  # persistence is best-effort only


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.settings = _load_settings()
        root.title("virtualSetmaker — Shot Designer → Unreal")
        root.geometry("680x560")
        root.minsize(560, 460)

        pad = {"padx": 8, "pady": 4}

        # --- input files ------------------------------------------------
        files_frame = ttk.LabelFrame(root, text="Shot Designer files (.hcw)")
        files_frame.pack(fill="both", expand=False, **pad)

        self.file_list = tk.Listbox(files_frame, height=6, selectmode="extended")
        self.file_list.pack(side="left", fill="both", expand=True, padx=(8, 4), pady=8)

        btns = ttk.Frame(files_frame)
        btns.pack(side="right", fill="y", padx=(4, 8), pady=8)
        ttk.Button(btns, text="Add Files…", command=self.add_files).pack(fill="x", pady=2)
        ttk.Button(btns, text="Remove", command=self.remove_selected).pack(fill="x", pady=2)
        ttk.Button(btns, text="Clear", command=self.clear_files).pack(fill="x", pady=2)

        # --- output folder ------------------------------------------------
        out_frame = ttk.LabelFrame(root, text="Export to folder")
        out_frame.pack(fill="x", **pad)
        self.out_var = tk.StringVar(value=self.settings.get("output_dir", os.path.expanduser("~")))
        ttk.Entry(out_frame, textvariable=self.out_var).pack(
            side="left", fill="x", expand=True, padx=(8, 4), pady=8
        )
        ttk.Button(out_frame, text="Browse…", command=self.pick_output).pack(
            side="right", padx=(4, 8), pady=8
        )

        # --- options -----------------------------------------------------
        opt_frame = ttk.Frame(root)
        opt_frame.pack(fill="x", **pad)
        ttk.Label(opt_frame, text="Shot Designer units per meter:").pack(side="left")
        self.upm_var = tk.StringVar(value=str(self.settings.get("units_per_meter", 100)))
        ttk.Spinbox(opt_frame, from_=1, to=10000, textvariable=self.upm_var, width=8).pack(
            side="left", padx=6
        )
        ttk.Label(opt_frame, text="(default 100 = 1 unit is 1 cm)").pack(side="left")

        self.export_btn = ttk.Button(opt_frame, text="Export Unreal Script(s)", command=self.export)
        self.export_btn.pack(side="right")

        # --- log -----------------------------------------------------------
        log_frame = ttk.LabelFrame(root, text="Log")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log = ScrolledText(log_frame, height=12, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, padx=8, pady=8)
        self.log.tag_configure("err", foreground="#b00020")
        self.log.tag_configure("warn", foreground="#8a6d00")
        self.log.tag_configure("ok", foreground="#006400")

        ttk.Label(
            root,
            text='Run in Unreal 5.6:  Output Log → switch "Cmd" to "Python" →  py "C:\\path\\to\\Scene_unreal.py"',
        ).pack(fill="x", padx=10, pady=(0, 8))

    # --- actions ------------------------------------------------------------
    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Choose Shot Designer scenes",
            initialdir=self.settings.get("input_dir", os.path.expanduser("~")),
            filetypes=[("Shot Designer scenes", "*.hcw"), ("All files", "*.*")],
        )
        for p in paths:
            if p and p not in self.file_list.get(0, "end"):
                self.file_list.insert("end", p)
        if paths:
            self.settings["input_dir"] = os.path.dirname(paths[0])
            _save_settings(self.settings)

    def remove_selected(self) -> None:
        for idx in reversed(self.file_list.curselection()):
            self.file_list.delete(idx)

    def clear_files(self) -> None:
        self.file_list.delete(0, "end")

    def pick_output(self) -> None:
        chosen = filedialog.askdirectory(
            title="Choose export folder", initialdir=self.out_var.get() or os.path.expanduser("~")
        )
        if chosen:
            self.out_var.set(chosen)

    def export(self) -> None:
        files = list(self.file_list.get(0, "end"))
        outdir = self.out_var.get().strip()
        if not files:
            self._log("Add at least one .hcw file first.", "err")
            return
        if not outdir:
            self._log("Choose an export folder first.", "err")
            return
        try:
            os.makedirs(outdir, exist_ok=True)
        except OSError as exc:
            self._log(f"Cannot create export folder: {exc}", "err")
            return
        try:
            upm = float(self.upm_var.get())
            if upm <= 0:
                raise ValueError
        except ValueError:
            self._log("Units per meter must be a positive number.", "err")
            return

        self.settings["output_dir"] = outdir
        self.settings["units_per_meter"] = upm
        _save_settings(self.settings)

        ok = 0
        for path in files:
            out_path = os.path.join(outdir, default_output_name(path))
            try:
                report = build_hcw(path, out_path, units_per_meter=upm)
            except Exception as exc:  # surface, don't crash the app
                self._log(f"FAILED  {os.path.basename(path)}: {exc}", "err")
                traceback.print_exc()
                continue
            ok += 1
            self._log(f"OK  {os.path.basename(path)} → {out_path}", "ok")
            self._log(f"      {report.summary()}")
            for w in report.warnings:
                self._log(f"      warning: {w}", "warn")
            for kind in report.unmatched_kinds:
                self._log(f"      note: no blockout recipe for {kind!r} (generic cube used)", "warn")
        self._log(f"Done: {ok}/{len(files)} exported.\n", "ok" if ok == len(files) else "warn")

    def _log(self, line: str, tag: str = "") -> None:
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n", tag or ())
        self.log.see("end")
        self.log.configure(state="disabled")


def main() -> int:
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
