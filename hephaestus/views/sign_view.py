"""Sign PDF: draw/type/import a signature, then stamp it on pages.

Signature rasterization is done with PIL directly (no Ghostscript needed):
drawn strokes are replayed from their captured points, typed signatures are
rendered with a serif font, and imported images are normalized to RGBA PNG.
"""

from __future__ import annotations

import os
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional, Tuple

from ..engine import pdf_ops
from ..engine.mupdf_compat import fitz
from ..theme import (ERROR, INK_SOFT, OXBLOOD, PARCHMENT,
                     PARCHMENT_DEEP, RULE, RULE_STRONG, SUCCESS, Theme)
from ..widgets import DropZone, StatusFooter

PEN_COLORS = {"Ink black": "#1A1A1A", "Indigo blue": "#1F3A6E",
              "Oxblood red": "#7A1F1F", "Forest green": "#2E5339"}

TYPE_FONTS = ["Script italic", "Serif bold", "Serif regular", "Typewriter"]


def _find_serif_ttf(bold: bool = False, italic: bool = False) -> Optional[str]:
    """Locate a Times-like TTF for typed signatures."""
    names = []
    if italic and bold:
        names += ["timesbi.ttf", "LiberationSerif-BoldItalic.ttf", "DejaVuSerif-BoldItalic.ttf"]
    elif italic:
        names += ["timesi.ttf", "LiberationSerif-Italic.ttf", "DejaVuSerif-Italic.ttf"]
    elif bold:
        names += ["timesbd.ttf", "LiberationSerif-Bold.ttf", "DejaVuSerif-Bold.ttf"]
    else:
        names += ["times.ttf", "LiberationSerif-Regular.ttf", "DejaVuSerif.ttf"]
    roots = []
    if os.name == "nt":
        roots.append(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    else:
        roots += ["/usr/share/fonts", "/usr/local/share/fonts",
                  os.path.expanduser("~/.fonts"),
                  "/System/Library/Fonts", "/Library/Fonts"]
    for root in roots:
        for dirpath, _dirs, files in os.walk(root):
            for n in names:
                if n in files:
                    return os.path.join(dirpath, n)
            # stop deep walks early on huge trees
            if dirpath.count(os.sep) - root.count(os.sep) > 4:
                files.clear()
    return None


def _find_mono_ttf() -> Optional[str]:
    for root in (["/usr/share/fonts", "/usr/local/share/fonts"] if os.name != "nt"
                 else [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")]):
        for dirpath, _dirs, files in os.walk(root):
            for n in ("cour.ttf", "LiberationMono-Regular.ttf", "DejaVuSansMono.ttf"):
                if n in files:
                    return os.path.join(dirpath, n)
    return None


class Stroke:
    def __init__(self, color: str, width: int):
        self.color = color
        self.width = width
        self.points: List[Tuple[float, float]] = []


class Placement:
    """A signature placed on a page, in fractional page coordinates."""
    def __init__(self, page: int, x: float, y: float, w: float):
        self.page = page
        self.x = x
        self.y = y
        self.w = w


class SignView(ttk.Frame):
    def __init__(self, master, app, spec, theme: Theme):
        super().__init__(master, style="TFrame")
        self.app = app
        self.spec = spec
        self.theme = theme
        self.path: Optional[str] = None
        self.page_count = 0
        self.cur_page = 0
        self._page_photo: Optional[tk.PhotoImage] = None
        self._sig_file: Optional[str] = None
        self._strokes: List[Stroke] = []
        self._drawing = False
        self._placements: List[Placement] = []
        self._placing = False
        self._busy = False
        self._zoom_choice: Optional[float] = None
        self._page_geom = (0, 0, 0, 0)
        self._sig_cache: dict = {}
        self._pad_preview_img = None
        self._tmpdir = tempfile.mkdtemp(prefix="hephaestus_sign_")

        self.sig_mode = tk.StringVar(value="draw")
        self.type_var = tk.StringVar(value="")
        self.font_style = tk.StringVar(value="Script italic")
        self.pen_color = tk.StringVar(value="Ink black")
        self.sig_scale = tk.IntVar(value=28)

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
        ttk.Label(head, text=spec.name, style="Heading.TLabel").grid(row=0, column=2)
        ttk.Label(head, text="Draw, type or import your signature — then stamp it where it belongs",
                  style="Muted.TLabel").grid(row=1, column=2, sticky="")

        # ---------------- body ----------------
        body = ttk.Frame(self, style="TFrame")
        body.grid(row=1, column=0, sticky="nsew", padx=24)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        side = ttk.Frame(body, style="TFrame", width=272)
        side.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        side.grid_propagate(False)

        self.drop = DropZone(side, theme, spec.filetypes, self._on_files,
                             multiple=False, height=86, title="Select a PDF")
        self.drop.pack(fill="x")

        self.panel = ttk.Frame(side, style="TFrame")

        # ---- 1. create signature ----
        src = tk.LabelFrame(self.panel, text="  1 · Create signature  ", bg=PARCHMENT,
                            fg=OXBLOOD, font=theme.font(10, bold=True), bd=0,
                            highlightthickness=1, highlightbackground=RULE,
                            padx=10, pady=8)
        src.pack(fill="x", pady=(12, 0))
        ttk.Radiobutton(src, text="Draw with the mouse", variable=self.sig_mode,
                        value="draw", command=self._mode_changed).pack(anchor="w")
        ttk.Radiobutton(src, text="Type it", variable=self.sig_mode,
                        value="type", command=self._mode_changed).pack(anchor="w")
        self.type_row = ttk.Frame(src, style="TFrame")
        ttk.Entry(self.type_row, textvariable=self.type_var, width=16).pack(
            side="left", fill="x", expand=True)
        fcombo = ttk.Combobox(self.type_row, textvariable=self.font_style, width=12,
                              state="readonly", values=TYPE_FONTS)
        fcombo.pack(side="left", padx=(6, 0))
        fcombo.bind("<<ComboboxSelected>>", lambda e: self._render_typed())
        self.type_var.trace_add("write", lambda *_: self._render_typed())
        ttk.Radiobutton(src, text="Import image (PNG/JPG)", variable=self.sig_mode,
                        value="import", command=self._mode_changed).pack(anchor="w")

        self.pad = tk.Canvas(src, height=92, bg="#FFFEF8",
                             highlightthickness=1, highlightbackground=RULE_STRONG,
                             cursor="pencil")
        self.pad.pack(fill="x", pady=(6, 0))
        self.pad.bind("<Button-1>", self._pad_down)
        self.pad.bind("<B1-Motion>", self._pad_move)
        self.pad.bind("<ButtonRelease-1>", self._pad_up)
        self.pad.bind("<Configure>", lambda e: self._redraw_pad_preview())

        color_row = ttk.Frame(src, style="TFrame")
        color_row.pack(fill="x", pady=(6, 0))
        ttk.Label(color_row, text="Ink:", style="Muted.TLabel").pack(side="left")
        self._swatches = {}
        for name, hexv in PEN_COLORS.items():
            sw = tk.Canvas(color_row, width=18, height=18, bg=hexv,
                           highlightthickness=2,
                           highlightbackground=OXBLOOD if name == "Ink black" else RULE,
                           cursor="hand2")
            sw.pack(side="left", padx=3)
            sw.bind("<Button-1>", lambda e, n=name: self._pick_color(n))
            self._swatches[name] = sw
        ttk.Button(src, text="Clear pad", style="Quiet.TButton",
                   command=self._clear_pad).pack(anchor="e", pady=(4, 0))

        # ---- 2. place on pages ----
        place = tk.LabelFrame(self.panel, text="  2 · Place on pages  ", bg=PARCHMENT,
                              fg=OXBLOOD, font=theme.font(10, bold=True), bd=0,
                              highlightthickness=1, highlightbackground=RULE,
                              padx=10, pady=8)
        place.pack(fill="x", pady=(12, 0))
        width_row = ttk.Frame(place, style="TFrame")
        width_row.pack(fill="x")
        ttk.Label(width_row, text="Size:", style="TLabel").pack(side="left")
        tk.Scale(width_row, from_=5, to=80, orient="horizontal",
                 variable=self.sig_scale, bg=PARCHMENT, troughcolor=PARCHMENT_DEEP,
                 highlightthickness=0, activebackground=OXBLOOD,
                 font=theme.font(8)).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Label(width_row, text="% of page", style="Muted.TLabel").pack(side="left")

        self.place_btn = ttk.Button(place, text="✒  Click a page to place signature",
                                    style="TButton", command=self._begin_placing)
        self.place_btn.pack(fill="x", pady=(8, 4))
        ttk.Button(place, text="Remove all placements", style="Quiet.TButton",
                   command=self._clear_placements).pack(fill="x")
        self.place_info = ttk.Label(place, text="No placements yet.",
                                    style="Muted.TLabel", wraplength=230)
        self.place_info.pack(fill="x", pady=(6, 0))

        # ---- 3. save ----
        self.save_btn = ttk.Button(self.panel, text="⚒  Forge — Save signed PDF",
                                   style="Accent.TButton", command=self.save)
        self.save_btn.pack(fill="x", pady=(14, 0))

        # ---- viewer ----
        viewer = tk.Frame(body, bg=PARCHMENT_DEEP, highlightthickness=1,
                          highlightbackground=RULE_STRONG)
        viewer.grid(row=0, column=1, sticky="nsew")
        viewer.columnconfigure(0, weight=1)
        viewer.rowconfigure(1, weight=1)
        nav = ttk.Frame(viewer, style="TFrame")
        nav.grid(row=0, column=0, sticky="ew", padx=8, pady=6)
        ttk.Button(nav, text="◀", style="Quiet.TButton", width=3,
                   command=lambda: self._turn(-1)).pack(side="left")
        self.page_label = ttk.Label(nav, text="No document", style="TLabel")
        self.page_label.pack(side="left", padx=10)
        ttk.Button(nav, text="▶", style="Quiet.TButton", width=3,
                   command=lambda: self._turn(1)).pack(side="left")
        ttk.Label(nav, text="     Zoom:", style="Muted.TLabel").pack(side="left")
        for zlabel, zval in (("Fit", None), ("75%", 0.75), ("100%", 1.0), ("150%", 1.5)):
            ttk.Button(nav, text=zlabel, style="Quiet.TButton", width=5,
                       command=lambda v=zval: self._set_zoom(v)).pack(side="left", padx=1)
        self.mode_label = ttk.Label(nav, text="", style="Muted.TLabel")
        self.mode_label.pack(side="right", padx=8)

        self.view = tk.Canvas(viewer, bg="#5A5145", highlightthickness=0,
                              cursor="crosshair")
        self.view.grid(row=1, column=0, sticky="nsew")
        self.view.bind("<Button-1>", self._view_click)
        self.view.bind("<Configure>", lambda e: self._render_page())

        self.footer = StatusFooter(self, theme)
        self.footer.grid(row=2, column=0, sticky="ew", padx=24, pady=(8, 14))
        self.footer.grid_remove()

        self.app.root.bind_all("<Control-v>", self.drop.paste_paths, add="+")
        self._mode_changed()

    # ------------------------------------------------------------------
    def _on_files(self, files):
        pdfs = [f for f in files if f.lower().endswith(".pdf")]
        if pdfs:
            self.load(pdfs[0])

    def load(self, path: str):
        try:
            doc = fitz.open(path)
            if doc.needs_pass:
                doc.close()
                messagebox.showerror("Hephaestus",
                                     "This PDF is password-protected. Unlock it first.",
                                     parent=self)
                return
            self.page_count = doc.page_count
            doc.close()
        except Exception as exc:
            messagebox.showerror("Hephaestus", f"Could not open that PDF:\n{exc}",
                                 parent=self)
            return
        self.path = path
        self.cur_page = 0
        self._placements = []
        self._update_place_info()
        self.drop.grid_remove()
        self.panel.pack(fill="both", expand=True)
        self.footer.grid()
        self.footer.set_status(f"{self.page_count} page(s) loaded. Create your signature below.")
        self._render_page()

    def _turn(self, delta):
        if not self.path:
            return
        self.cur_page = max(0, min(self.page_count - 1, self.cur_page + delta))
        self._render_page()

    def _set_zoom(self, z):
        self._zoom_choice = z
        self._render_page()

    # ------------------------------------------------------------------
    def _render_page(self):
        self.view.delete("all")
        if not self.path:
            return
        vw = max(self.view.winfo_width(), 100)
        vh = max(self.view.winfo_height(), 100)
        path, pno, zoom_choice = self.path, self.cur_page, self._zoom_choice

        def worker():
            try:
                doc = fitz.open(path)
                try:
                    page = doc[pno]
                    pr = page.rect
                    zoom = (min((vw - 30) / pr.width, (vh - 30) / pr.height)
                            if zoom_choice is None else zoom_choice)
                    zoom = max(0.1, zoom)
                    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                    data, pw, ph = pix.tobytes("ppm"), pix.width, pix.height
                finally:
                    doc.close()
                self.after(0, lambda: self._page_rendered(data, pw, ph, vw, vh))
            except Exception as exc:
                self.after(0, lambda e=exc: self.footer.set_status(
                    f"Render error: {e}", ERROR))

        threading.Thread(target=worker, daemon=True).start()
        self.page_label.configure(text=f"Page {self.cur_page + 1} of {self.page_count}")

    def _page_rendered(self, data, pw, ph, vw, vh):
        try:
            self._page_photo = tk.PhotoImage(data=data)
        except tk.TclError:
            return
        self._page_geom = (max(10, (vw - pw) // 2), max(10, (vh - ph) // 2), pw, ph)
        x, y, w, h = self._page_geom
        self.view.create_rectangle(x - 3, y - 3, x + w + 3, y + h + 3,
                                   fill="#8A7C66", outline="")
        self.view.create_image(x, y, image=self._page_photo, anchor="nw")
        self._sig_cache.clear()
        self._draw_placements()

    # ------------------------------------------------------------------
    def _mode_changed(self):
        mode = self.sig_mode.get()
        if mode == "type":
            self.type_row.pack(fill="x", pady=(4, 0), before=self.pad)
        else:
            self.type_row.pack_forget()
        if mode == "import":
            self._import_image()
        self._redraw_pad_preview()

    def _pick_color(self, name):
        self.pen_color.set(name)
        for n, sw in self._swatches.items():
            sw.configure(highlightbackground=OXBLOOD if n == name else RULE,
                         highlightthickness=2)
        if self.sig_mode.get() == "type":
            self._render_typed()

    def _clear_pad(self):
        self._strokes = []
        self._sig_file = None
        self._redraw_pad_preview()

    def _redraw_pad_preview(self):
        """Repaint the pad canvas from state (strokes / typed text / image)."""
        self.pad.delete("all")
        mode = self.sig_mode.get()
        pw = max(self.pad.winfo_width(), 200)
        if mode == "draw":
            for st in self._strokes:
                if len(st.points) >= 2:
                    self.pad.create_line(*[c for pt in st.points for c in pt],
                                         fill=st.color, width=st.width,
                                         smooth=True, capstyle="round")
        elif mode == "type":
            text = self.type_var.get().strip()
            if text:
                style = self.font_style.get()
                italic = "italic" in style
                bold = "bold" in style
                fam = self.theme.mono if style == "Typewriter" else self.theme.serif
                self.pad.create_text(pw // 2, 46, text=text,
                                     fill=PEN_COLORS[self.pen_color.get()],
                                     font=(fam, 26,
                                           ("bold italic" if bold and italic else
                                            "bold" if bold else
                                            "italic" if italic else "normal")))
        else:  # import
            if self._sig_file:
                try:
                    img = tk.PhotoImage(file=self._sig_file)
                    if img.width() > pw - 16 or img.height() > 84:
                        img = img.subsample(max(1, img.width() // (pw - 16)),
                                            max(1, img.height() // 84))
                    self.pad.create_image(pw // 2, 46, image=img)
                    self._pad_preview_img = img
                except tk.TclError:
                    pass

    def _pad_down(self, event):
        if self.sig_mode.get() != "draw":
            return
        self._drawing = True
        self._strokes.append(Stroke(PEN_COLORS[self.pen_color.get()], 2))
        self._strokes[-1].points.append((event.x, event.y))
        self._redraw_pad_preview()

    def _pad_move(self, event):
        if not self._drawing:
            return
        self._strokes[-1].points.append((event.x, event.y))
        self._redraw_pad_preview()

    def _pad_up(self, _event):
        self._drawing = False
        self._export_signature()

    def _render_typed(self):
        if self.sig_mode.get() != "type":
            return
        self._redraw_pad_preview()
        self._export_signature()

    def _import_image(self):
        p = filedialog.askopenfilename(
            title="Choose a signature image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                       ("All files", "*.*")], parent=self)
        if not p:
            self.sig_mode.set("draw")
            self._redraw_pad_preview()
            return
        try:
            from PIL import Image
            img = Image.open(p).convert("RGBA")
            out = os.path.join(self._tmpdir, "signature.png")
            img.save(out)
            self._sig_file = out
            self._redraw_pad_preview()
            self.footer.set_status("Signature image imported.")
        except Exception as exc:
            messagebox.showerror("Hephaestus", f"Could not load image:\n{exc}",
                                 parent=self)
            self.sig_mode.set("draw")

    # ------------------------------------------------------------------
    def _export_signature(self):
        """Rasterize the current signature (drawn or typed) to RGBA PNG."""
        mode = self.sig_mode.get()
        if mode == "import":
            return
        from PIL import Image, ImageDraw

        W, H = 720, 220
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if mode == "draw":
            if not self._strokes:
                self._sig_file = None
                return
            pad_w = max(self.pad.winfo_width(), 200)
            pad_h = max(self.pad.winfo_height(), 92)
            sx, sy = W / pad_w, H / pad_h
            for st in self._strokes:
                if len(st.points) < 2:
                    if st.points:
                        x, y = st.points[0]
                        draw.ellipse([x * sx - 1.5, y * sy - 1.5,
                                      x * sx + 1.5, y * sy + 1.5], fill=st.color)
                    continue
                pts = [(x * sx, y * sy) for x, y in st.points]
                draw.line(pts, fill=st.color, width=4, joint="curve")
        else:  # type
            text = self.type_var.get().strip()
            if not text:
                self._sig_file = None
                return
            style = self.font_style.get()
            color = PEN_COLORS[self.pen_color.get()]
            size = 84
            ttf = None
            if style == "Typewriter":
                ttf = _find_mono_ttf()
            else:
                ttf = _find_serif_ttf(bold="bold" in style,
                                      italic="italic" in style)
            try:
                from PIL import ImageFont
                fnt = ImageFont.truetype(ttf, size) if ttf else ImageFont.load_default(size)
            except Exception:
                from PIL import ImageFont
                fnt = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), text, font=fnt)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            scale = min(1.6, (W - 40) / max(1, tw))
            if scale != 1.0:
                try:
                    from PIL import ImageFont
                    fnt = ImageFont.truetype(ttf, int(size * scale)) if ttf \
                        else ImageFont.load_default(int(size * scale))
                except Exception:
                    pass
            bbox = draw.textbbox((0, 0), text, font=fnt)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((W - tw) / 2 - bbox[0], (H - th) / 2 - bbox[1]),
                      text, font=fnt, fill=color)

        bbox = img.getbbox()
        if bbox:
            pad = 8
            bbox = (max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                    min(W, bbox[2] + pad), min(H, bbox[3] + pad))
            img = img.crop(bbox)
        out = os.path.join(self._tmpdir, "signature.png")
        img.save(out)
        self._sig_file = out

    # ------------------------------------------------------------------
    def _begin_placing(self):
        if not self.path:
            messagebox.showinfo("Hephaestus", "Open a PDF first.", parent=self)
            return
        if not self._sig_file:
            self._export_signature()
        if not self._sig_file:
            messagebox.showinfo("Hephaestus",
                                "Create a signature first — draw, type, or import one.",
                                parent=self)
            return
        self._placing = True
        self.place_btn.configure(text="Now click on the page …")
        self.mode_label.configure(text="⬇ click the page to stamp")
        self.footer.set_status("Click anywhere on the page to stamp the signature.")

    def _view_click(self, event):
        if not self._placing or not self.path:
            return
        x, y, w, h = self._page_geom
        if not (x <= event.x <= x + w and y <= event.y <= y + h):
            self.footer.set_status("Click inside the page, not the desk.", INK_SOFT)
            return
        self._placements.append(Placement(self.cur_page, (event.x - x) / w,
                                          (event.y - y) / h,
                                          self.sig_scale.get() / 100.0))
        self._placing = False
        self.place_btn.configure(text="✒  Click a page to place signature")
        self.mode_label.configure(text="")
        self._update_place_info()
        self._draw_placements()
        self.footer.set_status(
            f"Signature placed on page {self.cur_page + 1}. Add more, or forge the result.",
            SUCCESS)

    def _update_place_info(self):
        n = len(self._placements)
        pages = sorted({p.page + 1 for p in self._placements})
        self.place_info.configure(
            text="No placements yet." if n == 0 else
            f"{n} placement(s) on page(s): {', '.join(map(str, pages))}")

    def _clear_placements(self):
        self._placements = []
        self._update_place_info()
        self._draw_placements()

    def _sig_aspect(self) -> float:
        from PIL import Image
        img = Image.open(self._sig_file)
        return img.height / max(1, img.width)

    def _draw_placements(self):
        self.view.delete("placement")
        if not self._page_photo or not self._sig_file:
            return
        x, y, w, h = self._page_geom
        aspect = self._sig_aspect()
        for pl in self._placements:
            if pl.page != self.cur_page:
                continue
            pw = pl.w * w
            ph = pw * aspect
            px, py = x + pl.x * w, y + pl.y * h
            photo = self._scaled_sig(int(pw))
            if photo:
                self.view.create_image(px, py, image=photo, anchor="nw",
                                       tags="placement")
            self.view.create_rectangle(px, py, px + pw, py + ph,
                                       outline=OXBLOOD, dash=(2, 3),
                                       tags="placement")

    def _scaled_sig(self, pw: int):
        if pw in self._sig_cache:
            return self._sig_cache[pw]
        try:
            from PIL import Image
            img = Image.open(self._sig_file)
            aspect = img.height / max(1, img.width)
            img = img.resize((max(1, pw), max(1, int(pw * aspect))), Image.LANCZOS)
            # tk.PhotoImage cannot show alpha PNGs correctly on old Tk — composite
            bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            comp = Image.alpha_composite(bg, img)
            comp.putalpha(img.getchannel("A"))
            tmp = os.path.join(self._tmpdir, f"sig_{pw}.png")
            comp.save(tmp)
            photo = tk.PhotoImage(file=tmp)
            self._sig_cache[pw] = photo
            return photo
        except Exception:
            return None

    # ------------------------------------------------------------------
    def save(self):
        if self._busy or not self.path:
            return
        if not self._placements:
            messagebox.showinfo("Hephaestus",
                                "Place your signature on at least one page first.",
                                parent=self)
            return
        if not self._sig_file:
            self._export_signature()
        if not self._sig_file:
            messagebox.showerror("Hephaestus", "No signature to apply.", parent=self)
            return
        dest = filedialog.asksaveasfilename(
            title="Save signed PDF",
            initialdir=os.path.dirname(self.path),
            initialfile=os.path.splitext(os.path.basename(self.path))[0] + " (signed).pdf",
            defaultextension=".pdf", filetypes=[("PDF document", "*.pdf")],
            parent=self)
        if not dest:
            return
        self._busy = True
        self.save_btn.state(["disabled"])
        self.footer.busy(True)

        aspect = self._sig_aspect()
        stamps = []
        doc = fitz.open(self.path)
        try:
            for pl in self._placements:
                r = doc[pl.page].rect
                w = pl.w * r.width
                h = w * aspect
                x, y = pl.x * r.width, pl.y * r.height
                stamps.append({"page": pl.page, "rect": (x, y, x + w, y + h),
                               "image": self._sig_file})
        finally:
            doc.close()
        path = self.path

        def worker():
            try:
                outputs = pdf_ops.stamp_image(
                    path, dest, stamps,
                    progress=lambda f, m: self.after(
                        0, lambda: (self.footer.busy(False),
                                    self.footer.set_progress(f),
                                    self.footer.set_status(m))))
                self.after(0, lambda: self._saved(outputs))
            except Exception as exc:
                self.after(0, lambda e=exc: self._failed(e))

        threading.Thread(target=worker, daemon=True).start()

    def _saved(self, outputs):
        self._busy = False
        self.save_btn.state(["!disabled"])
        self.footer.busy(False)
        self.footer.set_outputs(outputs)
        self.footer.set_status(
            f"Signed document saved: {os.path.basename(outputs[0])}", SUCCESS)
        if messagebox.askyesno("Hephaestus", "Saved! Open the output folder?",
                               parent=self):
            from ..widgets import open_path
            open_path(os.path.dirname(outputs[0]) or ".")

    def _failed(self, exc):
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
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        super().destroy()
