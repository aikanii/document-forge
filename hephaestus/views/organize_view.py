"""Organize PDF: visual page manager with drag-to-reorder thumbnails."""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

from ..engine import pdf_ops
from ..engine.mupdf_compat import fitz
from ..theme import (CARD, ERROR, INK, INK_SOFT, OXBLOOD,
                     PARCHMENT_DEEP, RULE, RULE_STRONG, SUCCESS, Theme)
from ..widgets import DropZone, StatusFooter

THUMB_W = 110          # thumbnail width in px
THUMB_PAD = 12
PAGE_GAP = 14


class PageRef:
    """One slot in the output document."""
    __slots__ = ("src_index", "rotation")

    def __init__(self, src_index: int, rotation: int = 0):
        self.src_index = src_index
        self.rotation = rotation % 360


class OrganizeView(ttk.Frame):
    def __init__(self, master, app, spec, theme: Theme):
        super().__init__(master, style="TFrame")
        self.app = app
        self.spec = spec
        self.theme = theme
        self.path: Optional[str] = None
        self.pages: List[PageRef] = []
        self._pixmaps: dict = {}          # src_index -> PhotoImage
        self._cards: List[tk.Frame] = []  # thumbnail cards in display order
        self._selected: List[int] = []    # positions
        self._busy = False
        self._drag = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ---------------- header ----------------
        head = ttk.Frame(self, style="TFrame")
        head.grid(row=0, column=0, sticky="ew", padx=24, pady=(18, 8))
        head.columnconfigure(2, weight=1)
        ttk.Button(head, text="⟵  All tools", style="Quiet.TButton",
                   command=app.go_home).grid(row=0, column=0, sticky="w")
        tk.Frame(head, bg=spec.category_color, width=4).grid(
            row=0, column=1, rowspan=2, sticky="ns", padx=(14, 18))
        ttk.Label(head, text=spec.name, style="Heading.TLabel").grid(
            row=0, column=2, sticky="")
        self.subtitle = ttk.Label(head, text="Open a PDF to arrange its pages",
                                  style="Muted.TLabel")
        self.subtitle.grid(row=1, column=2, sticky="")

        # ---------------- body ----------------
        body = ttk.Frame(self, style="TFrame")
        body.grid(row=1, column=0, sticky="nsew", padx=24)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        # drop zone (until a file is open)
        self.drop = DropZone(body, theme, spec.filetypes, self._on_files,
                             multiple=False, title="Select a PDF")
        self.drop.grid(row=0, column=0, sticky="ew")

        # toolbar
        self.toolbar = ttk.Frame(body, style="TFrame")
        self.toolbar.grid(row=0, column=0, sticky="ew")
        self.toolbar.grid_remove()
        tb = self.toolbar
        self.file_label = ttk.Label(tb, text="", style="TLabel")
        self.file_label.pack(side="left")
        for text, cmd in (
                ("Open…", self.open_file),
                ("◀ Move left", lambda: self.move(-1)),
                ("Move right ▶", lambda: self.move(1)),
                ("↻ Rotate", self.rotate_sel),
                ("⧉ Duplicate", self.duplicate_sel),
                ("✕ Delete", self.delete_sel),
                ("⇄ Reverse", self.reverse_all),
                ("Select all", self.select_all),
        ):
            ttk.Button(tb, text=text, style="Quiet.TButton",
                       command=cmd).pack(side="left", padx=2)

        # thumbnail canvas
        wrap = tk.Frame(body, bg=PARCHMENT_DEEP, highlightthickness=1,
                        highlightbackground=RULE_STRONG)
        wrap.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self.canvas = tk.Canvas(wrap, bg=PARCHMENT_DEEP, highlightthickness=0)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview,
                            style="Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        def _thumb_wheel(event):
            delta = -1 if getattr(event, "delta", 0) > 0 or \
                getattr(event, "num", 0) == 4 else 1
            self.canvas.yview_scroll(int(delta * 3), "units")
        self.canvas.bind("<MouseWheel>", _thumb_wheel)
        self.canvas.bind("<Button-4>", _thumb_wheel)
        self.canvas.bind("<Button-5>", _thumb_wheel)
        self.strip = tk.Frame(self.canvas, bg=PARCHMENT_DEEP)
        self._strip_win = self.canvas.create_window((0, 0), window=self.strip,
                                                    anchor="nw")
        self.strip.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self._layout())
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        # drag & drop reorder bindings on canvas
        self.canvas.bind("<B1-Motion>", self._on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_release)

        # ---------------- footer ----------------
        foot = ttk.Frame(self, style="TFrame")
        foot.grid(row=2, column=0, sticky="ew", padx=24, pady=(8, 16))
        foot.columnconfigure(1, weight=1)
        self.save_btn = ttk.Button(foot, text="⚒  Forge — Save organized PDF",
                                   style="Accent.TButton", command=self.save)
        self.save_btn.grid(row=0, column=0, sticky="w")
        self.save_btn.state(["disabled"])
        self.footer = StatusFooter(foot, theme)
        self.footer.grid(row=0, column=1, sticky="ew", padx=(16, 0))
        self.footer.grid_remove()

        self.app.root.bind_all("<Control-v>", self.drop.paste_paths, add="+")

    # ------------------------------------------------------------------
    def _on_files(self, files):
        pdfs = [f for f in files if f.lower().endswith(".pdf")]
        if pdfs:
            self.load(pdfs[0])

    def open_file(self):
        p = filedialog.askopenfilename(title="Select a PDF", filetypes=self.spec.filetypes)
        if p:
            self.load(p)

    def load(self, path: str):
        try:
            doc = fitz.open(path)
            if doc.needs_pass:
                doc.close()
                messagebox.showerror("Hephaestus",
                                     "This PDF is password-protected. Unlock it first.",
                                     parent=self)
                return
            n = doc.page_count
            doc.close()
        except Exception as exc:
            messagebox.showerror("Hephaestus", f"Could not open that PDF:\n{exc}",
                                 parent=self)
            return
        self.path = path
        self.pages = [PageRef(i) for i in range(n)]
        self._pixmaps = {}
        self._selected = []
        self._render_thumbs_async()
        self.drop.grid_remove()
        self.toolbar.grid()
        self.footer.grid()
        self.save_btn.state(["!disabled"])
        self.file_label.configure(
            text=f"{os.path.basename(path)}  ·  {n} page(s)")
        self.subtitle.configure(text="Drag pages to reorder · click to select (Ctrl/Shift for multi)")
        self.footer.set_status("Arrange the pages, then forge the result.")

    # ------------------------------------------------------------------
    def _render_thumbs_async(self):
        """Render thumbnails on a worker thread; UI stays responsive."""
        path = self.path
        n = len(self.pages)

        def worker():
            imgs = {}
            for i in range(n):
                try:
                    pix = pdf_ops.render_page_pixmap(path, i, THUMB_W)
                    imgs[i] = pix.tobytes("ppm")
                except Exception:
                    imgs[i] = None
                self.after(0, lambda i=i, done=len(imgs): self._thumb_progress(done, n))
            self.after(0, lambda: self._thumbs_ready(imgs))

        threading.Thread(target=worker, daemon=True).start()
        self._build_cards_placeholder()

    def _thumb_progress(self, done, total):
        self.footer.set_status(f"Rendering page previews … {done}/{total}")
        self.footer.set_progress(done / max(1, total))

    def _thumbs_ready(self, imgs: dict):
        for src_index, ppm in imgs.items():
            if ppm:
                try:
                    self._pixmaps[src_index] = tk.PhotoImage(data=ppm)
                except tk.TclError:
                    pass
        self.footer.set_status(f"{len(self.pages)} page(s) ready — arrange away.")
        self.footer.set_progress(1.0)
        self._layout(rebuild=True)

    # ------------------------------------------------------------------
    def _build_cards_placeholder(self):
        for c in self._cards:
            c.destroy()
        self._cards = []
        for pos in range(len(self.pages)):
            card = tk.Frame(self.strip, bg=CARD, highlightthickness=2,
                            highlightbackground=RULE, cursor="hand2")
            img = tk.Label(card, bg=CARD, fg=INK_SOFT, text="…",
                           font=self.theme.font(10))
            img.pack(padx=6, pady=(6, 2))
            num = tk.Label(card, bg=CARD, fg=INK, text="",
                           font=self.theme.font(9, bold=True))
            num.pack(pady=(0, 4))
            self._cards.append(card)
            for w in (card, img, num):
                w.bind("<Button-1>", lambda e, p=pos: self._on_card_click(p, e))
                w.bind("<B1-Motion>", self._on_drag_motion)
                w.bind("<ButtonRelease-1>", self._on_drag_release)
        self._layout()

    def _layout(self, rebuild: bool = False):
        """Flow thumbnail cards into rows inside the canvas."""
        width = max(self.canvas.winfo_width(), 200)
        cell_w = THUMB_W + 2 * THUMB_PAD + PAGE_GAP
        per_row = max(1, int(width // cell_w))
        if rebuild:
            self._build_cards_placeholder()
        for pos, card in enumerate(self._cards):
            r, cix = divmod(pos, per_row)
            x = cix * cell_w + THUMB_PAD
            y = r * (THUMB_W * 1.42 + 56) + THUMB_PAD
            card.place(x=x, y=y)
            self._paint_card(pos)
        rows = (len(self._cards) + per_row - 1) // per_row
        h = rows * (THUMB_W * 1.42 + 56) + THUMB_PAD * 2
        self.strip.configure(width=width, height=max(h, 120))
        self.strip.event_generate("<Configure>")

    def _paint_card(self, pos: int):
        card = self._cards[pos]
        ref = self.pages[pos]
        img_label = card.winfo_children()[0]
        num_label = card.winfo_children()[1]
        pix = self._pixmaps.get(ref.src_index)
        if pix:
            img_label.configure(image=pix, text="")
            # rotate preview
            if ref.rotation:
                img_label.configure(image=self._rotated(ref.src_index, ref.rotation))
        else:
            img_label.configure(image="", text="page " + str(ref.src_index + 1))
        rot_note = f"  ↻{ref.rotation}°" if ref.rotation else ""
        num_label.configure(text=f"{pos + 1}  (src {ref.src_index + 1}){rot_note}")
        sel = pos in self._selected
        card.configure(highlightbackground=OXBLOOD if sel else RULE,
                       bg="#FFF6E2" if sel else CARD)
        for w in (img_label, num_label):
            w.configure(bg="#FFF6E2" if sel else CARD)

    def _rotated(self, src_index: int, rotation: int):
        key = (src_index, rotation)
        cached = self._pixmaps.get(key)
        if cached:
            return cached
        base = self._pixmaps.get(src_index)
        if base is None:
            return None
        # PhotoImage has no rotate; re-render rotated via MuPDF
        def render():
            doc = fitz.open(self.path)
            try:
                page = doc[src_index]
                page.set_rotation((page.rotation + rotation) % 360)
                zoom = THUMB_W / max(1.0, page.rect.width)
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                return tk.PhotoImage(data=pix.tobytes("ppm"))
            finally:
                doc.close()
        img = render()
        self._pixmaps[key] = img
        return img

    # ------------------------------------------------------------------
    def _on_card_click(self, pos: int, event):
        if event.state & 0x0004:  # Ctrl
            if pos in self._selected:
                self._selected.remove(pos)
            else:
                self._selected.append(pos)
        elif event.state & 0x0001:  # Shift
            if self._selected:
                lo, hi = sorted((self._selected[0], pos))
                self._selected = list(range(lo, hi + 1))
        else:
            self._selected = [pos]
        self._drag = {"from": pos, "moved": False}
        self._repaint()

    def _on_canvas_click(self, event):
        if not self.canvas.find_overlapping(event.x, event.y, event.x, event.y):
            self._selected = []
            self._repaint()

    def _on_drag_motion(self, event):
        if self._drag is None:
            return
        self._drag["moved"] = True
        x = self.canvas.canvasx(event.x_root - self.canvas.winfo_rootx())
        y = self.canvas.canvasy(event.y_root - self.canvas.winfo_rooty())
        self._drag["target"] = self._position_at(x, y)
        self.canvas.configure(cursor="fleur")

    def _on_drag_release(self, event):
        self.canvas.configure(cursor="")
        if not self._drag:
            return
        drag, self._drag = self._drag, None
        if not drag.get("moved"):
            return
        x = self.canvas.canvasx(event.x_root - self.canvas.winfo_rootx())
        y = self.canvas.canvasy(event.y_root - self.canvas.winfo_rooty())
        target = self._position_at(x, y)
        if target is None or not self._selected:
            return
        moving = sorted(self._selected)
        items = [self.pages[i] for i in moving]
        for i in reversed(moving):
            del self.pages[i]
        insert_at = min(target, len(self.pages))
        for k, item in enumerate(items):
            self.pages.insert(insert_at + k, item)
        self._selected = list(range(insert_at, insert_at + len(items)))
        self._layout(rebuild=True)
        self.footer.set_status("Pages reordered.")

    def _position_at(self, x: float, y: float) -> Optional[int]:
        width = max(self.canvas.winfo_width(), 200)
        cell_w = THUMB_W + 2 * THUMB_PAD + PAGE_GAP
        per_row = max(1, int(width // cell_w))
        row_h = THUMB_W * 1.42 + 56
        cix = int((x - THUMB_PAD) // cell_w)
        r = int((y - THUMB_PAD) // row_h)
        if cix < 0 or r < 0:
            return 0
        pos = r * per_row + min(cix, per_row - 1)
        return max(0, min(pos, len(self.pages)))

    def _repaint(self):
        for pos in range(len(self._cards)):
            self._paint_card(pos)

    # ------------------------------------------------------------------
    def move(self, delta: int):
        if not self._selected:
            return
        order = sorted(self._selected, reverse=(delta > 0))
        changed = False
        for pos in order:
            j = pos + delta
            if 0 <= j < len(self.pages):
                self.pages[pos], self.pages[j] = self.pages[j], self.pages[pos]
                changed = True
        if changed:
            self._selected = sorted({p + delta for p in self._selected
                                     if 0 <= p + delta < len(self.pages)})
            self._layout(rebuild=True)

    def rotate_sel(self):
        if not self._selected:
            return
        for pos in self._selected:
            self.pages[pos].rotation = (self.pages[pos].rotation + 90) % 360
        self._repaint()

    def duplicate_sel(self):
        if not self._selected:
            return
        for pos in sorted(self._selected):
            src = self.pages[pos]
            self.pages.insert(pos + 1, PageRef(src.src_index, src.rotation))
        self._layout(rebuild=True)
        self.footer.set_status("Duplicated selected page(s).")

    def delete_sel(self):
        if not self._selected:
            return
        if len(self._selected) == len(self.pages):
            messagebox.showinfo("Hephaestus", "At least one page must remain.",
                                parent=self)
            return
        for pos in sorted(self._selected, reverse=True):
            del self.pages[pos]
        self._selected = []
        self._layout(rebuild=True)
        self.footer.set_status(f"{len(self.pages)} page(s) remain.")

    def reverse_all(self):
        self.pages.reverse()
        self._selected = []
        self._layout(rebuild=True)

    def select_all(self):
        self._selected = list(range(len(self.pages)))
        self._repaint()

    # ------------------------------------------------------------------
    def save(self):
        if self._busy or not self.path:
            return
        dest = filedialog.asksaveasfilename(
            title="Save organized PDF",
            initialdir=os.path.dirname(self.path),
            initialfile=os.path.splitext(os.path.basename(self.path))[0] +
                        " (organized).pdf",
            defaultextension=".pdf",
            filetypes=[("PDF document", "*.pdf")], parent=self)
        if not dest:
            return
        self._busy = True
        self.save_btn.state(["disabled"])
        self.footer.busy(True)

        order = [p.src_index for p in self.pages]
        rots = {pos: p.rotation for pos, p in enumerate(self.pages) if p.rotation}

        def worker():
            try:
                outputs = pdf_ops.organize_pdf(self.path, dest, order,
                                               extra_rotations=rots,
                                               progress=lambda f, m: self.after(
                                                   0, lambda: (self.footer.busy(False),
                                                               self.footer.set_progress(f),
                                                               self.footer.set_status(m))))
                self.after(0, lambda: self._saved(outputs))
            except Exception as exc:
                self.after(0, lambda e=exc: self._save_failed(e))

        threading.Thread(target=worker, daemon=True).start()

    def _saved(self, outputs):
        self._busy = False
        self.save_btn.state(["!disabled"])
        self.footer.busy(False)
        self.footer.set_outputs(outputs)
        self.footer.set_status(f"Saved: {os.path.basename(outputs[0])}", SUCCESS)
        if messagebox.askyesno("Hephaestus", "Saved! Open the output folder?",
                               parent=self):
            from ..widgets import open_path
            open_path(os.path.dirname(outputs[0]) or ".")

    def _save_failed(self, exc):
        self._busy = False
        self.save_btn.state(["!disabled"])
        self.footer.busy(False)
        self.footer.set_status(f"Failed: {exc}", ERROR)
        messagebox.showerror("Hephaestus", str(exc), parent=self)

    def destroy(self):
        try:
            self.app.root.unbind_all("<Control-v>")
        except Exception:
            pass
        super().destroy()
