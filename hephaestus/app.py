"""Hephaestus — the main application window.

Home screen: a catalog of tool cards grouped by category, with live search.
Navigation swaps the content area between Home, generic ToolPanels, and the
three interactive views (Organize / Sign / Edit).
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk
from typing import List, Optional

from . import __version__, icons
from .theme import (INK, INK_SOFT, OXBLOOD, PARCHMENT, PARCHMENT_DEEP,
                    RULE, RULE_STRONG, Theme, apply_ttk_style)
from .tools import CATEGORY_TITLES, ToolSpec, build_catalog
from .widgets import ScrollFrame, ToolCard
from .views.tool_panel import ToolPanel

APP_TITLE = "Hephaestus — The Document Forge"


class HomeView(ttk.Frame):
    def __init__(self, master, app: "HephaestusApp", theme: Theme,
                 catalog: List[ToolSpec]):
        super().__init__(master, style="TFrame")
        self.app = app
        self.theme = theme
        self.catalog = catalog
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.scroll = ScrollFrame(self, theme)
        self.scroll.grid(row=0, column=0, sticky="nsew")
        inner = self.scroll.inner
        inner.columnconfigure(0, weight=1)

        self._cards: List[tuple] = []  # (ToolSpec, ToolCard, section_frame)
        self._sections: List[tuple] = []
        self._grid_width = 0
        self._build(inner)
        self.scroll._canvas.bind("<Configure>", self._on_width)

    def _on_width(self, event):
        if abs(event.width - self._grid_width) > 40:
            self._grid_width = event.width
            self._relayout()

    def _build(self, inner):
        # intro strip
        intro = tk.Frame(inner, bg=PARCHMENT)
        intro.grid(row=0, column=0, sticky="ew", pady=(18, 6), padx=8)
        tk.Label(intro, bg=PARCHMENT, fg=INK, font=self.theme.font(15, bold=True),
                 text="The Forge Floor").pack(side="left")
        tk.Label(intro, bg=PARCHMENT, fg=INK_SOFT,
                 font=self.theme.font(10, italic=True),
                 text="— every tool below works on your own machine; no file ever leaves it."
                 ).pack(side="left", padx=(10, 0), pady=(4, 0))

        row = 1
        for cat_key, cat_title in CATEGORY_TITLES:
            tools = [t for t in self.catalog if t.category == cat_key]
            if not tools:
                continue
            sec = tk.Frame(inner, bg=PARCHMENT)
            sec.grid(row=row, column=0, sticky="ew", pady=(16, 4), padx=8)
            row += 1
            accent = tools[0].category_color
            tk.Frame(sec, bg=accent, width=4, height=20).pack(side="left")
            tk.Label(sec, bg=PARCHMENT, fg=accent, text="  " + cat_title.upper(),
                     font=self.theme.font(12, bold=True)).pack(side="left")
            tk.Frame(sec, bg=RULE, height=1).pack(side="left", fill="x",
                                                  expand=True, padx=(12, 0))
            grid = tk.Frame(inner, bg=PARCHMENT)
            grid.grid(row=row, column=0, sticky="ew", padx=8)
            row += 1
            self._sections.append((cat_key, sec, grid, tools))

        self._relayout()

    def _relayout(self):
        for _cat, _sec, grid, tools in self._sections:
            for child in grid.winfo_children():
                child.destroy()
        self._cards = []
        width = max(self.scroll._canvas.winfo_width(), 640)
        per_row = max(2, min(6, int((width - 24) // 226)))
        for cat_key, _sec, grid, tools in self._sections:
            visible = [t for t in tools if self._matches(t)]
            if not visible:
                continue
            for i, tool in enumerate(visible):
                card = ToolCard(grid, self.theme, tool, self.app.open_tool,
                                width=210, height=128)
                r, c = divmod(i, per_row)
                card.grid(row=r, column=c, padx=8, pady=8, sticky="n")
                self._cards.append((tool, card, grid))
        # hide empty section headers
        for cat_key, sec, grid, tools in self._sections:
            any_visible = any(self._matches(t) for t in tools)
            if any_visible:
                sec.grid()
                grid.grid()
            else:
                sec.grid_remove()
                grid.grid_remove()

    def _matches(self, tool: ToolSpec) -> bool:
        q = self.app.search_var.get().strip().lower()
        if not q:
            return True
        return (q in tool.name.lower() or q in tool.blurb.lower()
                or q in tool.id.lower())

    def refresh(self):
        self._relayout()
        self.scroll.scroll_to_top()


class HephaestusApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.theme = Theme(root)
        apply_ttk_style(self.theme)
        self.catalog = build_catalog()
        self.search_var = tk.StringVar()
        self._current: Optional[ttk.Frame] = None

        root.title(APP_TITLE)
        root.configure(bg=PARCHMENT)
        w, h = 1200, 780
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2)}")
        root.minsize(980, 640)
        self._set_window_icon()

        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        self._build_header()
        self.content = ttk.Frame(root, style="TFrame")
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)
        self._build_statusbar()

        self.home = HomeView(self.content, self, self.theme, self.catalog)
        self.home.grid(row=0, column=0, sticky="nsew")
        self._current = self.home

        root.bind("<Escape>", lambda e: self.go_home())
        self._announce_deps()

    # ------------------------------------------------------------------
    def _set_window_icon(self):
        try:
            from PIL import Image, ImageTk
            here = os.path.dirname(os.path.abspath(__file__))
            for cand in (os.path.join(here, "..", "assets", "icon_64.png"),
                         os.path.join(sys._MEIPASS, "assets", "icon_64.png")):
                if os.path.isfile(cand):
                    img = Image.open(cand).convert("RGBA")
                    img = img.resize((64, 64), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.root.iconphoto(True, photo)
                    self._icon_ref = photo
                    return
        except Exception:
            pass

    def _build_header(self):
        head = tk.Frame(self.root, bg=PARCHMENT, height=84)
        head.grid(row=0, column=0, sticky="ew", padx=24, pady=(16, 4))
        head.columnconfigure(2, weight=1)

        seal = tk.Canvas(head, width=52, height=52, bg=PARCHMENT,
                         highlightthickness=0)
        seal.grid(row=0, column=0, rowspan=2, sticky="w")
        icons.draw_seal(seal, 52)

        title = tk.Label(head, text="Hephaestus", bg=PARCHMENT, fg=INK,
                         font=self.theme.font(26, bold=True))
        title.grid(row=0, column=1, sticky="w", padx=(14, 0))
        tagline = tk.Label(head, text="T H E   D O C U M E N T   F O R G E",
                           bg=PARCHMENT, fg=OXBLOOD,
                           font=self.theme.font(9))
        tagline.grid(row=1, column=1, sticky="w", padx=(16, 0))

        # search + about
        right = ttk.Frame(head, style="TFrame")
        right.grid(row=0, column=3, rowspan=2, sticky="e")
        srow = ttk.Frame(right, style="TFrame")
        srow.pack(anchor="e")
        ttk.Label(srow, text="Seek a tool:", style="Muted.TLabel").pack(
            side="left", padx=(0, 6))
        ent = ttk.Entry(srow, textvariable=self.search_var, width=22)
        ent.pack(side="left")
        ttk.Button(srow, text="✕", style="Quiet.TButton", width=3,
                   command=lambda: (self.search_var.set(""),)).pack(side="left")
        self.search_var.trace_add("write", lambda *_: self._on_search())
        ttk.Button(right, text="About & Diagnostics…", style="Quiet.TButton",
                   command=self.show_about).pack(anchor="e", pady=(6, 0))

        tk.Frame(self.root, bg=RULE_STRONG, height=2).grid(
            row=1, column=0, sticky="new", padx=0)

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=PARCHMENT_DEEP, height=26)
        bar.grid(row=2, column=0, sticky="ew")
        tk.Frame(bar, bg=RULE, height=1).pack(side="top", fill="x")
        self.status_text = tk.Label(
            bar, bg=PARCHMENT_DEEP, fg=INK_SOFT, anchor="w", padx=14,
            font=self.theme.font(9, italic=True),
            text=f"{len(self.catalog)} tools at the anvil · everything runs locally on this machine")
        self.status_text.pack(side="left", fill="x", expand=True)
        tk.Label(bar, bg=PARCHMENT_DEEP, fg=INK_SOFT, padx=14,
                 font=self.theme.font(9),
                 text=f"v{__version__}").pack(side="right")

    def _on_search(self):
        if isinstance(self._current, HomeView):
            self._current.refresh()

    # ------------------------------------------------------------------
    def open_tool(self, spec: ToolSpec):
        if self._current is not None:
            self._current.destroy()
        if spec.custom_view == "organize":
            from .views.organize_view import OrganizeView
            view = OrganizeView(self.content, self, spec, self.theme)
        elif spec.custom_view == "sign":
            from .views.sign_view import SignView
            view = SignView(self.content, self, spec, self.theme)
        elif spec.custom_view == "edit":
            from .views.edit_view import EditView
            view = EditView(self.content, self, spec, self.theme)
        else:
            view = ToolPanel(self.content, self, spec, self.theme)
        view.grid(row=0, column=0, sticky="nsew")
        self._current = view
        self.status_text.configure(text=f"{spec.name} — {spec.blurb}")

    def go_home(self):
        if self._current is self.home:
            return
        if self._current is not None:
            self._current.destroy()
        self.home = HomeView(self.content, self, self.theme, self.catalog)
        self.home.grid(row=0, column=0, sticky="nsew")
        self._current = self.home
        self.status_text.configure(
            text=f"{len(self.catalog)} tools at the anvil · everything runs locally on this machine")

    # ------------------------------------------------------------------
    def _announce_deps(self):
        """One-time courtesy check for the optional external engines."""
        from .engine import ocr, office
        missing = []
        if office.find_soffice() is None:
            missing.append("LibreOffice  (Office ⇄ PDF, HTML → PDF, PDF/A conversions)")
        if ocr.find_tesseract() is None:
            missing.append("Tesseract OCR  (scanned-PDF text recognition)")
        if missing:
            self.status_text.configure(
                text="Note: " + " · ".join(missing) +
                     " not installed — those tools will show install instructions.")

    def show_about(self):
        from .engine import ocr, office
        win = tk.Toplevel(self.root)
        win.title("About Hephaestus")
        win.configure(bg=PARCHMENT)
        win.transient(self.root)
        win.resizable(False, False)
        w, h = 560, 520
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        seal = tk.Canvas(win, width=72, height=72, bg=PARCHMENT,
                         highlightthickness=0)
        seal.pack(pady=(22, 6))
        icons.draw_seal(seal, 72)

        tk.Label(win, text="Hephaestus", bg=PARCHMENT, fg=INK,
                 font=self.theme.font(22, bold=True)).pack()
        tk.Label(win, text=f"The Document Forge · version {__version__}",
                 bg=PARCHMENT, fg=INK_SOFT,
                 font=self.theme.font(10, italic=True)).pack()

        body = tk.Label(
            win, justify="left", bg=PARCHMENT, fg=INK,
            font=self.theme.font(10), wraplength=w - 80,
            text=(
                "\nA private, offline workshop for PDF documents — merging,\n"
                "splitting, compressing, converting, signing, securing and more.\n"
                "Your files never leave this machine.\n\n"
                "Built with PyMuPDF, pypdf, Pillow and Tkinter.\n"
                "Named for the smith-god who forged wonders in his workshop."))
        body.pack(padx=40, anchor="w")

        # diagnostics
        diag = tk.LabelFrame(win, text="  Workshop diagnostics  ", bg=PARCHMENT,
                             fg=OXBLOOD, font=self.theme.font(10, bold=True),
                             bd=0, highlightthickness=1, highlightbackground=RULE,
                             padx=14, pady=8)
        diag.pack(fill="x", padx=40, pady=(10, 0))
        soffice = office.find_soffice()
        tesser = ocr.find_tesseract()
        rows = [
            ("Core PDF engine (PyMuPDF/pypdf)", "ready", ""),
            ("Image engine (Pillow)", "ready", ""),
            ("LibreOffice (Office ⇄ PDF, HTML, PDF/A)",
             "ready" if soffice else "missing", soffice or ""),
            ("Tesseract OCR (scanned → searchable)",
             "ready" if tesser else "missing", tesser or ""),
        ]
        for name, state, detail in rows:
            r = tk.Frame(diag, bg=PARCHMENT)
            r.pack(fill="x", pady=2)
            color = "#3F6B35" if state == "ready" else "#9A2B1E"
            tk.Label(r, text="●", fg=color, bg=PARCHMENT,
                     font=self.theme.font(10)).pack(side="left")
            tk.Label(r, text="  " + name, bg=PARCHMENT, fg=INK,
                     font=self.theme.font(10)).pack(side="left")
            if detail:
                tk.Label(r, text=f"   ({detail})", bg=PARCHMENT, fg=INK_SOFT,
                         font=self.theme.font(8)).pack(side="left")
        tk.Label(diag, bg=PARCHMENT, fg=INK_SOFT, justify="left", anchor="w",
                 font=self.theme.font(9, italic=True), wraplength=w - 130,
                 text=("Missing engines are free to install — see README.md for "
                       "links. Everything else works without them.")).pack(
            fill="x", pady=(6, 0))

        ttk.Button(win, text="Close", style="TButton",
                   command=win.destroy).pack(pady=16)
        win.grab_set()


def _try_dnd_root():
    """Use tkinterdnd2's root when available (enables native file drag & drop)."""
    try:
        from tkinterdnd2 import TkinterDnD
        return TkinterDnD.Tk()
    except Exception:
        return tk.Tk()


def main():
    root = _try_dnd_root()
    app = HephaestusApp(root)

    # native drag & drop onto the whole window when tkinterdnd2 is present
    try:
        from tkinterdnd2 import DND_FILES
        root.drop_target_register(DND_FILES)

        def _on_drop(event):
            paths = root.tk.splitlist(event.data)
            pdfs = [p for p in paths if p.lower().endswith(".pdf")]
            target = pdfs[0] if pdfs else (paths[0] if paths else None)
            if not target:
                return
            if isinstance(app._current, HomeView):
                ext = os.path.splitext(target)[1].lower()
                spec = None
                if ext == ".pdf":
                    spec = next((t for t in app.catalog if t.id == "merge"), None)
                elif ext in (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".webp"):
                    spec = next((t for t in app.catalog if t.id == "img2pdf"), None)
                elif ext in (".doc", ".docx", ".odt", ".rtf"):
                    spec = next((t for t in app.catalog if t.id == "word2pdf"), None)
                elif ext in (".ppt", ".pptx", ".odp"):
                    spec = next((t for t in app.catalog if t.id == "ppt2pdf"), None)
                elif ext in (".xls", ".xlsx", ".ods", ".csv"):
                    spec = next((t for t in app.catalog if t.id == "excel2pdf"), None)
                elif ext in (".html", ".htm"):
                    spec = next((t for t in app.catalog if t.id == "html2pdf"), None)
                if spec:
                    app.open_tool(spec)
                    view = app._current
                    if hasattr(view, "_on_files"):
                        view._on_files([target])
            else:
                view = app._current
                if hasattr(view, "_on_files"):
                    view._on_files(paths)

        root.dnd_bind("<<Drop>>", _on_drop)
    except Exception:
        pass

    root.mainloop()


if __name__ == "__main__":
    main()
