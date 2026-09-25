"""Reusable Tkinter widgets for Hephaestus."""

from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Callable, List, Sequence

from .theme import (CARD, CARD_HOVER, INK, INK_SOFT, OXBLOOD, PARCHMENT,
                    PARCHMENT_DEEP, RULE, RULE_STRONG, Theme)
from . import icons


# ---------------------------------------------------------------------------
# Scrollable frame
# ---------------------------------------------------------------------------

class ScrollFrame(ttk.Frame):
    """A vertically scrollable ttk.Frame with mouse-wheel support."""

    def __init__(self, master, theme: Theme, bg: str = PARCHMENT, **kw):
        super().__init__(master, style="TFrame", **kw)
        self._canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self._vbar = ttk.Scrollbar(self, orient="vertical",
                                   command=self._canvas.yview,
                                   style="Vertical.TScrollbar")
        self.inner = ttk.Frame(self._canvas, style="TFrame")
        self._window = self._canvas.create_window((0, 0), window=self.inner,
                                                  anchor="nw")
        self._canvas.configure(yscrollcommand=self._vbar.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._vbar.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._bind_mousewheel(self._canvas)
        self._bind_mousewheel(self.inner)

    def _on_inner_configure(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfigure(self._window, width=event.width)

    def _bind_mousewheel(self, widget):
        if not hasattr(self, "_wheel_bound"):
            self._wheel_bound: set = set()

        def _descendants(w):
            yield w
            for ch in w.winfo_children():
                yield from _descendants(ch)

        def bind_all():
            for w in _descendants(self):
                wid = str(w)
                if wid in self._wheel_bound:
                    continue
                self._wheel_bound.add(wid)
                if sys.platform == "darwin":
                    w.bind("<MouseWheel>", _on_wheel_mac, add="+")
                else:
                    w.bind("<MouseWheel>", _on_wheel, add="+")
                    w.bind("<Button-4>", _on_wheel, add="+")
                    w.bind("<Button-5>", _on_wheel, add="+")

        def _on_wheel(event):
            delta = -1 if event.delta > 0 or event.num == 4 else 1
            self._canvas.yview_scroll(int(delta * 2), "units")

        def _on_wheel_mac(event):
            self._canvas.yview_scroll(int(-event.delta), "units")

        self.bind("<Configure>", lambda e: bind_all(), add="+")
        self.inner.bind("<Configure>", lambda e: bind_all(), add="+")
        bind_all()
        self._rebind = bind_all

    def scroll_to_top(self):
        self._canvas.yview_moveto(0)


# ---------------------------------------------------------------------------
# Tool card for the home grid
# ---------------------------------------------------------------------------

class ToolCard(tk.Frame):
    """A parchment index-card for one tool."""

    def __init__(self, master, theme: Theme, tool, on_click: Callable,
                 width: int = 210, height: int = 132):
        super().__init__(master, bg=CARD, highlightbackground=RULE,
                         highlightcolor=RULE_STRONG, highlightthickness=1,
                         bd=0, cursor="hand2", width=width, height=height)
        self.pack_propagate(False)
        self.theme = theme
        self.tool = tool
        self._on_click = on_click

        accent = tool.category_color
        self.icon_canvas = tk.Canvas(self, width=44, height=44, bg=CARD,
                                     highlightthickness=0)
        self.icon_canvas.pack(pady=(14, 6))
        icons.draw_icon(self.icon_canvas, tool.icon, 44, ink="#2B2119", accent=accent)

        self.title = tk.Label(self, text=tool.name, bg=CARD, fg=INK,
                              font=theme.font(11, bold=True))
        self.title.pack()

        self.blurb = tk.Label(self, text=tool.blurb, bg=CARD, fg=INK_SOFT,
                              font=theme.font(8), wraplength=width - 24,
                              justify="center")
        self.blurb.pack(padx=10, pady=(2, 8))

        # colored top edge, like a filing-tab
        self.tab = tk.Frame(self, bg=accent, height=3)
        self.tab.place(x=0, y=0, relwidth=1)

        for w in (self, self.icon_canvas, self.title, self.blurb, self.tab):
            w.bind("<Enter>", self._hover_on)
            w.bind("<Leave>", self._hover_off)
            w.bind("<Button-1>", self._click)

    def _set_bg(self, color):
        self.configure(bg=color)
        for w in (self.icon_canvas, self.title, self.blurb):
            try:
                w.configure(bg=color)
            except tk.TclError:
                pass

    def _hover_on(self, _e):
        self._set_bg(CARD_HOVER)
        self.configure(highlightcolor=OXBLOOD)

    def _hover_off(self, _e):
        self._set_bg(CARD)
        self.configure(highlightcolor=RULE_STRONG)

    def _click(self, _e):
        self._on_click(self.tool)


# ---------------------------------------------------------------------------
# File list with ordering controls
# ---------------------------------------------------------------------------

class FileList(ttk.Frame):
    """Ordered list of chosen files with remove / reorder buttons."""

    def __init__(self, master, theme: Theme, ordered: bool = True, on_change=None):
        super().__init__(master, style="TFrame")
        self.theme = theme
        self.ordered = ordered
        self.paths: List[str] = []
        self.on_change = on_change

        self.listbox = tk.Listbox(self, activestyle="none", bd=0,
                                  highlightthickness=1,
                                  highlightbackground=RULE_STRONG,
                                  selectbackground=OXBLOOD,
                                  selectforeground="#F7EFDD",
                                  font=theme.font(10), height=6,
                                  exportselection=False)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.listbox.yview,
                           style="Vertical.TScrollbar")
        sb.pack(side="left", fill="y")
        self.listbox.configure(yscrollcommand=sb.set)

        btns = ttk.Frame(self, style="TFrame")
        btns.pack(side="left", fill="y", padx=(8, 0))
        ttk.Button(btns, text="Remove", style="Quiet.TButton",
                   command=self.remove_selected).pack(fill="x", pady=2)
        ttk.Button(btns, text="Clear", style="Quiet.TButton",
                   command=self.clear).pack(fill="x", pady=2)
        if ordered:
            ttk.Button(btns, text="Move ▲", style="Quiet.TButton",
                       command=lambda: self._move(-1)).pack(fill="x", pady=2)
            ttk.Button(btns, text="Move ▼", style="Quiet.TButton",
                       command=lambda: self._move(1)).pack(fill="x", pady=2)

    def _refresh(self):
        self.listbox.delete(0, "end")
        for i, p in enumerate(self.paths):
            self.listbox.insert("end", f"{i + 1}.  {os.path.basename(p)}")
        if self.on_change:
            self.on_change()

    def add_files(self, files: Sequence[str]):
        added = False
        for f in files:
            f = os.path.abspath(f)
            if f not in self.paths and os.path.isfile(f):
                self.paths.append(f)
                added = True
        if added:
            self._refresh()

    def remove_selected(self):
        sel = list(self.listbox.curselection())
        if not sel:
            return
        for i in reversed(sel):
            del self.paths[i]
        self._refresh()

    def clear(self):
        self.paths.clear()
        self._refresh()

    def _move(self, delta):
        sel = self.listbox.curselection()
        if not sel:
            return
        i = sel[0]
        j = i + delta
        if 0 <= j < len(self.paths):
            self.paths[i], self.paths[j] = self.paths[j], self.paths[i]
            self._refresh()
            self.listbox.selection_set(j)


# ---------------------------------------------------------------------------
# Drop / browse zone
# ---------------------------------------------------------------------------

class DropZone(tk.Canvas):
    """Click-to-browse zone; also accepts OS drag & drop when tkinterdnd2 is
    available, and clipboard pastes of file paths (Ctrl+V)."""

    def __init__(self, master, theme: Theme, filetypes: Sequence[tuple],
                 on_files: Callable[[List[str]], None],
                 multiple: bool = True, height: int = 120,
                 title: str = "Choose files"):
        super().__init__(master, height=height, bg=PARCHMENT_DEEP,
                         highlightthickness=1, highlightbackground=RULE_STRONG,
                         cursor="hand2")
        self.theme = theme
        self.filetypes = list(filetypes)
        self.on_files = on_files
        self.multiple = multiple
        self.title = title
        self._hover = False
        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", lambda e: self.browse())
        self._redraw()

    def _set_hover(self, on: bool):
        self._hover = on
        self.configure(bg=CARD_HOVER if on else PARCHMENT_DEEP)
        self._redraw()

    def _redraw(self):
        self.delete("all")
        w = max(self.winfo_width(), 100)
        h = max(self.winfo_height(), 60)
        color = OXBLOOD if self._hover else INK_SOFT
        # dashed border
        self.create_rectangle(6, 6, w - 6, h - 6, outline=color, dash=(6, 4), width=1)
        self.create_text(w / 2, h / 2 - 14, text=self.title,
                         fill=INK, font=self.theme.font(12, bold=True))
        hint = "click to browse  ·  drop files here  ·  Ctrl+V to paste paths"
        self.create_text(w / 2, h / 2 + 12, text=hint,
                         fill=INK_SOFT, font=self.theme.font(9, italic=True))

    def browse(self):
        if self.multiple:
            files = filedialog.askopenfilenames(title=self.title,
                                                filetypes=self.filetypes)
        else:
            one = filedialog.askopenfilename(title=self.title,
                                             filetypes=self.filetypes)
            files = (one,) if one else ()
        if files:
            self.on_files(list(files))

    def paste_paths(self, event=None):
        """Handle Ctrl+V: accept file paths from the clipboard.

        Never hijacks ordinary text pasting inside Entry/Text widgets.
        """
        try:
            focus = self.focus_get()
            if focus is not None and focus.winfo_class() in (
                    "Entry", "TEntry", "Text", "TCombobox", "Spinbox", "TSpinbox"):
                return
        except Exception:
            pass
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return
        paths = []
        for chunk in _split_clipboard_paths(text):
            chunk = chunk.strip().strip('"').strip("'")
            if chunk and os.path.exists(chunk):
                paths.append(chunk)
        if paths:
            self.on_files(paths)


def _split_clipboard_paths(text: str) -> List[str]:
    """Split clipboard text into paths, handling quoted Windows paths."""
    out, cur, in_q = [], "", False
    for ch in text:
        if ch == '"':
            in_q = not in_q
            cur += ch
        elif ch in "\r\n" and not in_q:
            if cur.strip():
                out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    if len(out) == 1 and "\t" in out[0]:  # file-manager copy uses tabs
        out = out[0].split("\t")
    return out


# ---------------------------------------------------------------------------
# Status / progress footer
# ---------------------------------------------------------------------------

class StatusFooter(ttk.Frame):
    """Progress bar + status line + result actions, shared by tool panels."""

    def __init__(self, master, theme: Theme):
        super().__init__(master, style="TFrame")
        self.theme = theme
        self.columnconfigure(0, weight=1)

        self.progress = ttk.Progressbar(self, mode="determinate", maximum=100)
        self.progress.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))

        self.status = tk.Label(self, text="Ready.", anchor="w", justify="left",
                               bg=PARCHMENT, fg=INK_SOFT,
                               font=theme.font(10, italic=True), wraplength=600)
        self.status.grid(row=1, column=0, sticky="ew")

        self.open_btn = ttk.Button(self, text="Open output folder",
                                   style="TButton", command=self._open_folder)
        self.open_btn.grid(row=1, column=2, sticky="e", padx=(8, 0))
        self.open_btn.state(["disabled"])
        self._outputs: List[str] = []

    def set_status(self, text: str, color: str = INK_SOFT):
        self.status.configure(text=text, fg=color)

    def set_progress(self, fraction: float):
        self.progress.configure(mode="determinate",
                                value=max(0.0, min(100.0, fraction * 100)))

    def busy(self, on: bool):
        if on:
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate")

    def set_outputs(self, outputs: Sequence[str]):
        self._outputs = list(outputs)
        if outputs:
            self.open_btn.state(["!disabled"])

    def _open_folder(self):
        if not self._outputs:
            return
        folder = os.path.dirname(self._outputs[0]) or "."
        open_path(folder)


def open_path(path: str):
    """Open a file/folder with the OS default application."""
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}" >/dev/null 2>&1 &')
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def hrule(master, color: str = RULE, thickness: int = 1):
    f = tk.Frame(master, bg=color, height=thickness)
    return f


def label_entry_row(master, theme: Theme, label: str, default: str = "",
                    show: str = "", width: int = 28) -> tuple:
    """A 'Label: [Entry]' row; returns (frame, entry_var)."""
    row = ttk.Frame(master, style="TFrame")
    lbl = ttk.Label(row, text=label, style="TLabel", width=20, anchor="w")
    lbl.pack(side="left")
    var = tk.StringVar(value=default)
    ent = ttk.Entry(row, textvariable=var, width=width, show=show)
    ent.pack(side="left", fill="x", expand=True)
    return row, var
