"""Generic tool panel: builds an entire tool UI from a ToolSpec."""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

from ..theme import (ERROR, INK_SOFT, OXBLOOD, PARCHMENT, RULE, SUCCESS,
                     Theme)
from ..tools import Option, ToolSpec
from ..widgets import DropZone, FileList, ScrollFrame, StatusFooter, open_path


class OptionForm(ttk.Frame):
    """Renders Option specs into widgets; collects values into a dict."""

    def __init__(self, master, theme: Theme, options: List[Option]):
        super().__init__(master, style="TFrame")
        self.theme = theme
        self.options = options
        self.values: Dict[str, object] = {}
        self._widgets: Dict[str, tuple] = {}
        self._rows: Dict[str, ttk.Frame] = {}
        self.columnconfigure(1, weight=1)

        for i, opt in enumerate(options):
            row = ttk.Frame(self, style="TFrame")
            row.grid(row=i, column=0, columnspan=2, sticky="ew", pady=3)
            row.columnconfigure(1, weight=1)
            self._rows[opt.key] = row

            lbl = ttk.Label(row, text=opt.label, style="TLabel", anchor="w")
            lbl.grid(row=0, column=0, sticky="w", padx=(0, 12))

            if opt.kind == "choice":
                var = tk.StringVar(value=str(opt.default if opt.default is not None
                                             else (opt.values[0] if opt.values else "")))
                w = ttk.Combobox(row, textvariable=var, values=list(opt.values),
                                 state="readonly")
                w.grid(row=0, column=1, sticky="ew")
                self._widgets[opt.key] = ("choice", var, w)

            elif opt.kind == "check":
                var = tk.BooleanVar(value=bool(opt.default))
                w = ttk.Checkbutton(row, variable=var, text="")
                w.grid(row=0, column=1, sticky="w")
                self._widgets[opt.key] = ("check", var, w)

            elif opt.kind == "number":
                var = tk.StringVar(value=str(opt.default if opt.default is not None else ""))
                w = ttk.Entry(row, textvariable=var, width=10)
                w.grid(row=0, column=1, sticky="w")
                self._widgets[opt.key] = ("number", var, w)

            elif opt.kind == "password":
                var = tk.StringVar(value="")
                w = ttk.Entry(row, textvariable=var, show="•", width=28)
                w.grid(row=0, column=1, sticky="w")
                self._widgets[opt.key] = ("password", var, w)

            elif opt.kind == "file":
                var = tk.StringVar(value=str(opt.default or ""))
                frame = ttk.Frame(row, style="TFrame")
                frame.grid(row=0, column=1, sticky="ew")
                frame.columnconfigure(0, weight=1)
                ent = ttk.Entry(frame, textvariable=var)
                ent.grid(row=0, column=0, sticky="ew")

                def _browse(v=var):
                    p = filedialog.askopenfilename(
                        title=opt.label,
                        filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.gif *.tif *.webp"),
                                   ("All files", "*.*")])
                    if p:
                        v.set(p)
                ttk.Button(frame, text="Browse…", style="Quiet.TButton",
                           command=_browse).grid(row=0, column=1, padx=(6, 0))
                self._widgets[opt.key] = ("file", var, ent)

            else:  # text
                var = tk.StringVar(value=str(opt.default if opt.default is not None else ""))
                w = ttk.Entry(row, textvariable=var)
                w.grid(row=0, column=1, sticky="ew")
                self._widgets[opt.key] = ("text", var, w)

            if opt.hint:
                hint = ttk.Label(row, text=opt.hint, style="Muted.TLabel")
                hint.grid(row=1, column=1, sticky="w", pady=(1, 0))

            for var_key in ("choice", "check"):
                pass
            # live-update dependent visibility
            kind, var, _w = self._widgets[opt.key]
            if kind in ("choice", "check", "text", "file"):
                var.trace_add("write", lambda *_a: self.refresh_visibility())

        # trace every var so values stay fresh
        for key, (kind, var, _w) in self._widgets.items():
            var.trace_add("write", lambda *_a: self._collect())
        self.refresh_visibility()
        self._collect()

    def _collect(self):
        for key, (kind, var, _w) in self._widgets.items():
            if kind == "check":
                self.values[key] = bool(var.get())
            elif kind == "number":
                raw = str(var.get()).strip()
                try:
                    self.values[key] = float(raw) if "." in raw else int(raw)
                except ValueError:
                    self.values[key] = raw
            else:
                self.values[key] = var.get()

    def refresh_visibility(self):
        self._collect()
        for opt in self.options:
            row = self._rows.get(opt.key)
            if row is None:
                continue
            visible = True
            if opt.show_if is not None:
                try:
                    visible = bool(opt.show_if(self.values))
                except Exception:
                    visible = True
            if visible:
                row.grid()
            else:
                row.grid_remove()

    def get_values(self) -> Dict[str, object]:
        self._collect()
        return dict(self.values)


class ToolPanel(ttk.Frame):
    """Full-screen panel for one ToolSpec."""

    def __init__(self, master, app, spec: ToolSpec, theme: Theme):
        super().__init__(master, style="TFrame")
        self.app = app
        self.spec = spec
        self.theme = theme
        self._busy = False
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ---- header -------------------------------------------------------
        head = ttk.Frame(self, style="TFrame")
        head.grid(row=0, column=0, sticky="ew", padx=24, pady=(18, 8))
        head.columnconfigure(2, weight=1)

        ttk.Button(head, text="⟵  All tools", style="Quiet.TButton",
                   command=app.go_home).grid(row=0, column=0, sticky="w")

        title = ttk.Label(head, text=spec.name, style="Heading.TLabel")
        title.grid(row=0, column=2, sticky="")
        blurb = ttk.Label(head, text=spec.blurb, style="Muted.TLabel")
        blurb.grid(row=1, column=2, sticky="")

        tk.Frame(head, bg=spec.category_color, width=4).grid(
            row=0, column=1, rowspan=2, sticky="ns", padx=(14, 18))

        tk.Frame(self, bg=RULE, height=1).grid(row=1, column=0, sticky="ew",
                                               padx=24)
        self.rowconfigure(2, weight=1)

        # ---- body ----------------------------------------------------------
        body = ScrollFrame(self, theme)
        body.grid(row=2, column=0, sticky="nsew", padx=24, pady=8)
        body.rowconfigure(0, weight=1)
        inner = body.inner
        inner.columnconfigure(0, weight=1)

        # warning banner for external deps
        self.warn_var = tk.StringVar(value="")
        self.warn_label = tk.Label(inner, textvariable=self.warn_var,
                                   bg="#F6E3C5", fg="#6B4A12", anchor="w",
                                   justify="left", font=theme.font(10),
                                   padx=12, pady=10, wraplength=760)
        self.warn_label.grid(row=0, column=0, sticky="ew", pady=(4, 10))
        self.warn_label.grid_remove()

        # drop zone
        self.drop = DropZone(inner, theme, spec.filetypes, self._on_files,
                             multiple=spec.multiple,
                             title=spec.input_title)
        self.drop.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        # file list
        self.filelist = FileList(inner, theme, ordered=spec.multiple)
        if spec.multiple:
            self.filelist.grid(row=2, column=0, sticky="ew", pady=(0, 12))

        # options
        self.form: Optional[OptionForm] = None
        if spec.options:
            box = tk.LabelFrame(inner, text="  Options  ", bg=PARCHMENT, fg=OXBLOOD,
                                font=theme.font(11, bold=True), bd=0,
                                highlightthickness=1, highlightbackground=RULE,
                                padx=14, pady=10)
            box.grid(row=3, column=0, sticky="ew", pady=(0, 12))
            self.form = OptionForm(box, theme, spec.options)
            self.form.pack(fill="x", expand=True)

        # output folder
        outbox = tk.LabelFrame(inner, text="  Output  ", bg=PARCHMENT, fg=OXBLOOD,
                               font=theme.font(11, bold=True), bd=0,
                               highlightthickness=1, highlightbackground=RULE,
                               padx=14, pady=10)
        outbox.grid(row=4, column=0, sticky="ew", pady=(0, 6))
        outrow = ttk.Frame(outbox, style="TFrame")
        outrow.pack(fill="x")
        outrow.columnconfigure(1, weight=1)
        self.out_mode = tk.StringVar(value="same")
        ttk.Radiobutton(outrow, text="Same folder as source",
                        variable=self.out_mode, value="same",
                        command=self._out_mode_changed).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(outrow, text="Choose folder:",
                        variable=self.out_mode, value="choose",
                        command=self._out_mode_changed).grid(row=1, column=0, sticky="w")
        self.out_var = tk.StringVar(value="")
        self.out_entry = ttk.Entry(outrow, textvariable=self.out_var, state="disabled")
        self.out_entry.grid(row=1, column=1, sticky="ew", padx=8)
        self.out_browse = ttk.Button(outrow, text="Browse…", style="Quiet.TButton",
                                     command=self._browse_out, state="disabled")
        self.out_browse.grid(row=1, column=2)
        self.ask_each = tk.BooleanVar(value=False)
        if spec.multiple:
            ttk.Checkbutton(outrow, text="Ask for destination when finished",
                            variable=self.ask_each).grid(row=2, column=0,
                                                         columnspan=3, sticky="w",
                                                         pady=(6, 0))

        # run button
        runrow = ttk.Frame(inner, style="TFrame")
        runrow.grid(row=5, column=0, sticky="ew", pady=(4, 8))
        self.run_btn = ttk.Button(runrow, text=f"⚒  Forge — {spec.name}",
                                  style="Accent.TButton", command=self.run)
        self.run_btn.pack(side="left")
        self.reset_btn = ttk.Button(runrow, text="Start over", style="Quiet.TButton",
                                    command=self.reset)
        self.reset_btn.pack(side="left", padx=10)

        # footer
        self.footer = StatusFooter(self, theme)
        self.footer.grid(row=3, column=0, sticky="ew", padx=24, pady=(4, 16))

        # paste support + external dep check
        self.app.root.bind_all("<Control-v>", self.drop.paste_paths, add="+")
        if spec.needs_external:
            from ..tools import external_checker
            msg = external_checker(spec.needs_external)()
            if msg:
                self.warn_var.set(msg)
                self.warn_label.grid()

        self.filelist.on_change = self._files_changed
        self._files_changed()

    # ------------------------------------------------------------------
    def _out_mode_changed(self):
        if self.out_mode.get() == "choose":
            self.out_entry.configure(state="normal")
            self.out_browse.configure(state="normal")
            if not self.out_var.get():
                self._browse_out()
        else:
            self.out_entry.configure(state="disabled")
            self.out_browse.configure(state="disabled")

    def _browse_out(self):
        d = filedialog.askdirectory(title="Choose output folder")
        if d:
            self.out_var.set(d)
            self.out_mode.set("choose")
            self._out_mode_changed()

    def _on_files(self, files: List[str]):
        valid = []
        for f in files:
            if os.path.isdir(f):
                for name in sorted(os.listdir(f)):
                    p = os.path.join(f, name)
                    if os.path.isfile(p) and self._ext_ok(p, folders_only=True):
                        valid.append(p)
            elif self._ext_ok(f):
                valid.append(f)
        if not self.spec.multiple:
            valid = valid[:1]
            if valid:
                self.filelist.clear()
        self.filelist.add_files(valid)

    def _ext_ok(self, path: str, folders_only: bool = False) -> bool:
        """Match against the *specific* extensions (ignoring the All-files
        wildcard) so folder scans never pick up junk."""
        exts = set()
        for label, pattern in self.spec.filetypes:
            if folders_only and label.lower().startswith("all"):
                continue
            for tok in pattern.split():
                if tok.startswith("*.") and tok != "*.*":
                    exts.add(tok[1:].lower())
        return os.path.splitext(path)[1].lower() in exts

    def _files_changed(self):
        n = len(self.filelist.paths)
        if self.spec.multiple:
            self.footer.set_status(f"{n} file(s) ready." if n else
                                   "Add files to begin.")
        else:
            first = self.filelist.paths[0] if n else None
            if first:
                try:
                    from ..engine import pdf_ops
                    info = pdf_ops.pdf_info(first)
                    size_mb = info["size_bytes"] / (1024 * 1024)
                    extra = "  ·  password-protected" if info["encrypted"] else ""
                    self.footer.set_status(
                        f"{info['pages']} page(s)  ·  {size_mb:.2f} MB{extra}")
                except Exception:
                    self.footer.set_status("File selected.")
            else:
                self.footer.set_status("Add a file to begin.")

    def reset(self):
        self.filelist.clear()
        self.footer.set_outputs([])
        self.footer.set_status("Ready.")

    def _resolve_out_dir(self) -> str:
        if self.out_mode.get() == "choose" and self.out_var.get():
            d = self.out_var.get()
        else:
            src = self.filelist.paths[0] if self.filelist.paths else None
            d = os.path.dirname(src) if src else os.path.expanduser("~")
        os.makedirs(d, exist_ok=True)
        return d

    # ------------------------------------------------------------------
    def run(self):
        if self._busy:
            return
        spec = self.spec
        files = list(self.filelist.paths)
        if not files:
            messagebox.showwarning("Hephaestus", "Please add at least one file first.",
                                   parent=self)
            return
        if spec.multiple and len(files) < 2 and spec.id == "merge":
            messagebox.showwarning("Hephaestus", "Merging needs at least two PDFs.",
                                   parent=self)
            return
        opts = self.form.get_values() if self.form else {}
        out_dir = self._resolve_out_dir()

        self._busy = True
        self.run_btn.state(["disabled"])
        self.footer.busy(True)
        self.footer.set_status("Working …")

        def progress(fraction, message=""):
            self.after(0, lambda: (self.footer.busy(False),
                                   self.footer.set_progress(fraction),
                                   self.footer.set_status(message or "Working …",
                                                          INK_SOFT)))

        def worker():
            try:
                outputs = spec.runner(files, opts, out_dir, progress)
                self.after(0, lambda: self._finished(outputs))
            except Exception as exc:
                self.after(0, lambda e=exc: self._failed(e))

        threading.Thread(target=worker, daemon=True).start()

    def _finished(self, outputs: List[str]):
        self._busy = False
        self.run_btn.state(["!disabled"])
        self.footer.busy(False)
        self.footer.set_progress(1.0)
        self.footer.set_outputs(outputs)
        if len(outputs) == 1:
            size_mb = os.path.getsize(outputs[0]) / (1024 * 1024)
            self.footer.set_status(
                f"Done — {os.path.basename(outputs[0])} ({size_mb:.2f} MB)", SUCCESS)
        else:
            self.footer.set_status(f"Done — {len(outputs)} files created.", SUCCESS)
        if self.ask_each.get() and outputs:
            dest = filedialog.asksaveasfilename(
                title="Save result as…", initialdir=os.path.dirname(outputs[0]),
                initialfile=os.path.basename(outputs[0]), parent=self)
            if dest:
                import shutil
                shutil.move(outputs[0], dest)
                outputs = [dest] + outputs[1:]
                self.footer.set_outputs(outputs)
        # offer to open
        if outputs:
            open_folder = messagebox.askyesno(
                "Hephaestus", "Finished! Open the output folder?", parent=self)
            if open_folder:
                open_path(os.path.dirname(outputs[0]) or ".")

    def _failed(self, exc: Exception):
        self._busy = False
        self.run_btn.state(["!disabled"])
        self.footer.busy(False)
        self.footer.set_status(f"Failed: {exc}", ERROR)
        messagebox.showerror("Hephaestus — something went wrong", str(exc),
                             parent=self)

    def destroy(self):
        try:
            self.app.root.unbind_all("<Control-v>")
        except Exception:
            pass
        super().destroy()
