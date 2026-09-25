"""Edit PDF: add text and images to pages, with a live preview."""

from __future__ import annotations

import os
import tempfile
import threading
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk
from typing import List, Optional

from ..engine import pdf_ops
from ..engine.mupdf_compat import fitz
from ..theme import (ERROR, OXBLOOD, PARCHMENT,
                     PARCHMENT_DEEP, RULE, RULE_STRONG, SUCCESS, Theme)
from ..widgets import DropZone, StatusFooter

TEXT_FONTS = {
    "Serif (Times)": "tiro",
    "Serif bold": "tibo",
    "Serif italic": "tiit",
    "Sans (Helvetica)": "helv",
    "Sans bold": "hebo",
    "Typewriter": "cour",
}

COLOR_PRESETS = {
    "Black": (0, 0, 0), "Red": (0.65, 0.1, 0.1), "Navy": (0.1, 0.15, 0.4),
    "Sepia": (0.44, 0.31, 0.18), "Gray": (0.45, 0.45, 0.45),
    "White": (1, 1, 1),
}


class Element:
    """A placed annotation, in fractional page coordinates."""

    def __init__(self, kind: str, page: int, fx: float, fy: float):
        self.kind = kind
        self.page = page
        self.fx = fx
        self.fy = fy
        # text
        self.text = ""
        self.size_pt = 14.0
        self.font_key = "Serif (Times)"
        self.color = (0, 0, 0)
        # image
        self.path = ""
        self.wfrac = 0.25


class EditView(ttk.Frame):
    def __init__(self, master, app, spec, theme: Theme):
        super().__init__(master, style="TFrame")
        self.app = app
        self.spec = spec
        self.theme = theme
        self.path: Optional[str] = None
        self.page_count = 0
        self.cur_page = 0
        self._page_photo: Optional[tk.PhotoImage] = None
        self._page_geom = (0, 0, 0, 0)
        self._zoom_px_per_pt = 1.0
        self.elements: List[Element] = []
        self._mode: Optional[str] = None      # None | 'text' | 'image'
        self._pending_image: Optional[str] = None
        self._busy = False
        self._tmpdir = tempfile.mkdtemp(prefix="hephaestus_edit_")
        self._img_cache: dict = {}

        # pending text options
        self.text_var = tk.StringVar(value="")
        self.size_var = tk.StringVar(value="14")
        self.font_var = tk.StringVar(value="Serif (Times)")
        self.color_var = tk.StringVar(value="Black")
        self.img_scale = tk.DoubleVar(value=25.0)

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
        ttk.Label(head, text="Add text and images to any page, then forge a new document",
                  style="Muted.TLabel").grid(row=1, column=2, sticky="")

        # ---------------- body ----------------
        body = ttk.Frame(self, style="TFrame")
        body.grid(row=1, column=0, sticky="nsew", padx=24)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # sidebar
        side = ttk.Frame(body, style="TFrame", width=280)
        side.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        side.grid_propagate(False)

        self.drop = DropZone(side, theme, spec.filetypes, self._on_files,
                             multiple=False, height=86, title="Select a PDF")
        self.drop.pack(fill="x")

        self.panel = ttk.Frame(side, style="TFrame")

        # --- add text box ---
        tbox = tk.LabelFrame(self.panel, text="  Add text  ", bg=PARCHMENT, fg=OXBLOOD,
                             font=theme.font(10, bold=True), bd=0,
                             highlightthickness=1, highlightbackground=RULE,
                             padx=10, pady=8)
        tbox.pack(fill="x", pady=(12, 0))
        self.text_entry = tk.Text(tbox, height=2, width=28, wrap="word", bd=0,
                                  font=theme.font(10), bg=PARCHMENT_DEEP,
                                  highlightthickness=1, highlightbackground=RULE_STRONG)
        self.text_entry.pack(fill="x")
        row = ttk.Frame(tbox, style="TFrame")
        row.pack(fill="x", pady=(6, 0))
        ttk.Label(row, text="Font:", style="TLabel").pack(side="left")
        ttk.Combobox(row, textvariable=self.font_var, values=list(TEXT_FONTS),
                     state="readonly", width=15).pack(side="left", padx=4)
        row2 = ttk.Frame(tbox, style="TFrame")
        row2.pack(fill="x", pady=(4, 0))
        ttk.Label(row2, text="Size:", style="TLabel").pack(side="left")
        ttk.Entry(row2, textvariable=self.size_var, width=5).pack(side="left", padx=4)
        ttk.Label(row2, text="Color:", style="TLabel").pack(side="left", padx=(8, 0))
        cb = ttk.Combobox(row2, textvariable=self.color_var,
                          values=list(COLOR_PRESETS), state="readonly", width=8)
        cb.pack(side="left", padx=4)
        self.custom_color_btn = ttk.Button(row2, text="…", style="Quiet.TButton",
                                           width=3, command=self._choose_color)
        self.custom_color_btn.pack(side="left")
        self.add_text_btn = ttk.Button(tbox, text="✎  Click page to add text",
                                       style="TButton", command=self._begin_text)
        self.add_text_btn.pack(fill="x", pady=(8, 0))

        # --- add image box ---
        ibox = tk.LabelFrame(self.panel, text="  Add image  ", bg=PARCHMENT, fg=OXBLOOD,
                             font=theme.font(10, bold=True), bd=0,
                             highlightthickness=1, highlightbackground=RULE,
                             padx=10, pady=8)
        ibox.pack(fill="x", pady=(12, 0))
        self.img_label = ttk.Label(ibox, text="No image chosen.", style="Muted.TLabel",
                                   wraplength=240)
        self.img_label.pack(fill="x")
        ttk.Button(ibox, text="Choose image…", style="TButton",
                   command=self._choose_image).pack(fill="x", pady=(6, 0))
        srow = ttk.Frame(ibox, style="TFrame")
        srow.pack(fill="x", pady=(6, 0))
        ttk.Label(srow, text="Width:", style="TLabel").pack(side="left")
        tk.Scale(srow, from_=5, to=100, orient="horizontal", variable=self.img_scale,
                 bg=PARCHMENT, troughcolor=PARCHMENT_DEEP, highlightthickness=0,
                 activebackground=OXBLOOD, font=theme.font(8)).pack(
            side="left", fill="x", expand=True, padx=6)
        ttk.Label(srow, text="%", style="Muted.TLabel").pack(side="left")
        self.add_img_btn = ttk.Button(ibox, text="▣  Click page to add image",
                                      style="TButton", command=self._begin_image)
        self.add_img_btn.pack(fill="x", pady=(8, 0))

        # --- elements list ---
        ebox = tk.LabelFrame(self.panel, text="  Placed items  ", bg=PARCHMENT,
                             fg=OXBLOOD, font=theme.font(10, bold=True), bd=0,
                             highlightthickness=1, highlightbackground=RULE,
                             padx=10, pady=8)
        ebox.pack(fill="both", expand=True, pady=(12, 0))
        self.elist = tk.Listbox(ebox, height=6, bd=0, activestyle="none",
                                font=theme.font(9), bg=PARCHMENT_DEEP,
                                highlightthickness=1, highlightbackground=RULE_STRONG,
                                selectbackground=OXBLOOD, selectforeground="#F7EFDD",
                                exportselection=False)
        self.elist.pack(fill="both", expand=True)
        self.elist.bind("<<ListboxSelect>>", self._elist_select)
        erow = ttk.Frame(ebox, style="TFrame")
        erow.pack(fill="x", pady=(6, 0))
        ttk.Button(erow, text="Delete", style="Quiet.TButton",
                   command=self._delete_selected).pack(side="left", padx=(0, 6))
        ttk.Button(erow, text="Clear all", style="Quiet.TButton",
                   command=self._clear_all).pack(side="left")

        # save
        self.save_btn = ttk.Button(self.panel, text="⚒  Forge — Save edited PDF",
                                   style="Accent.TButton", command=self.save)
        self.save_btn.pack(fill="x", pady=(12, 0))

        # viewer
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
        self.mode_label = ttk.Label(nav, text="", style="Muted.TLabel")
        self.mode_label.pack(side="right")
        self.view = tk.Canvas(viewer, bg="#5A5145", highlightthickness=0,
                              cursor="crosshair")
        self.view.grid(row=1, column=0, sticky="nsew")
        self.view.bind("<Button-1>", self._view_click)
        self.view.bind("<Configure>", lambda e: self._render_page())

        # footer
        self.footer = StatusFooter(self, theme)
        self.footer.grid(row=2, column=0, sticky="ew", padx=24, pady=(8, 14))
        self.footer.grid_remove()

        self.app.root.bind_all("<Control-v>", self.drop.paste_paths, add="+")

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
        self.elements = []
        self._refresh_elist()
        self.drop.grid_remove()
        self.panel.pack(fill="both", expand=True)
        self.footer.grid()
        self.footer.set_status(f"{self.page_count} page(s) loaded. Add text or images below.")
        self._render_page()

    def _turn(self, delta):
        if not self.path:
            return
        self.cur_page = max(0, min(self.page_count - 1, self.cur_page + delta))
        self._render_page()

    # ------------------------------------------------------------------
    def _render_page(self):
        self.view.delete("all")
        if not self.path:
            return
        vw = max(self.view.winfo_width(), 100)
        vh = max(self.view.winfo_height(), 100)

        def worker():
            try:
                doc = fitz.open(self.path)
                try:
                    page = doc[self.cur_page]
                    pr = page.rect
                    zoom = min((vw - 30) / pr.width, (vh - 30) / pr.height)
                    zoom = max(0.1, zoom)
                    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                    data, pw, ph, real_zoom = pix.tobytes("ppm"), pix.width, pix.height, zoom
                finally:
                    doc.close()
                self.after(0, lambda: self._page_rendered(data, pw, ph, vw, vh, real_zoom))
            except Exception as exc:
                self.after(0, lambda e=exc: self.footer.set_status(
                    f"Render error: {e}", ERROR))

        threading.Thread(target=worker, daemon=True).start()
        self.page_label.configure(text=f"Page {self.cur_page + 1} of {self.page_count}")

    def _page_rendered(self, data, pw, ph, vw, vh, zoom):
        try:
            self._page_photo = tk.PhotoImage(data=data)
        except tk.TclError:
            return
        self._page_geom = (max(10, (vw - pw) // 2), max(10, (vh - ph) // 2), pw, ph)
        self._zoom_px_per_pt = zoom
        x, y, w, h = self._page_geom
        self.view.create_rectangle(x - 3, y - 3, x + w + 3, y + h + 3,
                                   fill="#8A7C66", outline="")
        self.view.create_image(x, y, image=self._page_photo, anchor="nw")
        self._draw_elements()

    def _draw_elements(self):
        self.view.delete("element")
        x, y, w, h = self._page_geom
        for idx, el in enumerate(self.elements):
            if el.page != self.cur_page:
                continue
            px, py = x + el.fx * w, y + el.fy * h
            if el.kind == "text":
                tk_font = self._tk_font_for(el)
                hexc = "#%02x%02x%02x" % tuple(int(c * 255) for c in el.color)
                self.view.create_text(px, py, text=el.text, fill=hexc,
                                      font=tk_font, anchor="nw", tags="element")
                self.view.create_rectangle(px - 2, py - 2, px + 2, py + 2,
                                           fill=OXBLOOD, outline="", tags="element")
            else:
                photo = self._image_preview(el)
                if photo:
                    self.view.create_image(px, py, image=photo, anchor="nw",
                                           tags="element")
                    self.view.create_rectangle(
                        px, py, px + photo.width(), py + photo.height(),
                        outline=OXBLOOD, dash=(2, 3), tags="element")
            self.view.create_text(px + 4, py - 10, text=str(idx + 1),
                                  fill=OXBLOOD, font=self.theme.font(8, bold=True),
                                  anchor="sw", tags="element")

    def _tk_font_for(self, el: Element):
        bold = "bold" in el.font_key
        italic = "italic" in el.font_key
        family = self.theme.serif
        if el.font_key.startswith("Sans"):
            family = "Helvetica"
        elif el.font_key.startswith("Typewriter"):
            family = self.theme.mono
        # negative size = pixels in Tk, so the preview matches the PDF exactly
        size = -max(4, int(el.size_pt * self._zoom_px_per_pt))
        return (family, size,
                "bold italic" if bold and italic else
                ("bold" if bold else ("italic" if italic else "normal")))

    def _image_preview(self, el: Element):
        x, y, w, h = self._page_geom
        target_w = max(2, int(el.wfrac * w))
        key = (el.path, target_w)
        if key in self._img_cache:
            return self._img_cache[key]
        try:
            from PIL import Image
            img = Image.open(el.path)
            aspect = img.height / max(1, img.width)
            img = img.convert("RGBA").resize(
                (target_w, max(2, int(target_w * aspect))), Image.LANCZOS)
            # composite onto white for tk PhotoImage
            bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            img = Image.alpha_composite(bg, img).convert("RGB")
            tmp = os.path.join(self._tmpdir,
                               f"img_{abs(hash(key))}.png")
            img.save(tmp)
            photo = tk.PhotoImage(file=tmp)
            self._img_cache[key] = photo
            return photo
        except Exception:
            return None

    # ------------------------------------------------------------------
    def _choose_color(self):
        rgb, hexv = colorchooser.askcolor(color="#000000", title="Text color",
                                          parent=self)
        if rgb:
            self.color_var.set(hexv)
            self._custom_color = tuple(c / 255.0 for c in rgb)

    _custom_color: Optional[tuple] = None

    def _current_color(self):
        if self._custom_color and self.color_var.get().startswith("#"):
            return self._custom_color
        return COLOR_PRESETS.get(self.color_var.get(), (0, 0, 0))

    def _begin_text(self):
        if not self.path:
            messagebox.showinfo("Hephaestus", "Open a PDF first.", parent=self)
            return
        text = self.text_entry.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("Hephaestus", "Type the text you want to add first.",
                                parent=self)
            return
        try:
            size = float(self.size_var.get())
        except ValueError:
            size = 14.0
        self._pending_text = (text, size, self.font_var.get(), self._current_color())
        self._mode = "text"
        self.mode_label.configure(text="Click on the page to place the text …")
        self.view.configure(cursor="crosshair")

    def _choose_image(self):
        p = filedialog.askopenfilename(
            title="Choose an image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff"),
                       ("All files", "*.*")], parent=self)
        if p:
            self._pending_image = p
            self.img_label.configure(text=os.path.basename(p))

    def _begin_image(self):
        if not self.path:
            messagebox.showinfo("Hephaestus", "Open a PDF first.", parent=self)
            return
        if not self._pending_image:
            messagebox.showinfo("Hephaestus", "Choose an image first.", parent=self)
            return
        self._mode = "image"
        self.mode_label.configure(text="Click on the page to place the image …")

    _pending_text: Optional[tuple] = None

    def _view_click(self, event):
        if not self.path or not self._mode:
            return
        x, y, w, h = self._page_geom
        if not (x <= event.x <= x + w and y <= event.y <= y + h):
            self.mode_label.configure(text="Click inside the page.")
            return
        fx, fy = (event.x - x) / w, (event.y - y) / h
        if self._mode == "text":
            text, size, font_key, color = self._pending_text
            el = Element("text", self.cur_page, fx, fy)
            el.text, el.size_pt, el.font_key, el.color = text, size, font_key, color
        else:
            el = Element("image", self.cur_page, fx, fy)
            el.path = self._pending_image
            el.wfrac = float(self.img_scale.get()) / 100.0
        self.elements.append(el)
        self._mode = None
        self.mode_label.configure(text="")
        self._refresh_elist()
        self._draw_elements()
        self.footer.set_status(f"Added {el.kind} on page {self.cur_page + 1}.", SUCCESS)

    # ------------------------------------------------------------------
    def _refresh_elist(self):
        self.elist.delete(0, "end")
        for i, el in enumerate(self.elements):
            if el.kind == "text":
                desc = el.text.replace("\n", " ")
                if len(desc) > 26:
                    desc = desc[:26] + "…"
                self.elist.insert("end", f"{i + 1}. p{el.page + 1} · text “{desc}”")
            else:
                self.elist.insert("end",
                                  f"{i + 1}. p{el.page + 1} · image {os.path.basename(el.path)}")

    def _elist_select(self, _event=None):
        sel = self.elist.curselection()
        if not sel:
            return
        el = self.elements[sel[0]]
        if el.page != self.cur_page:
            self.cur_page = el.page
            self._render_page()

    def _delete_selected(self):
        sel = self.elist.curselection()
        if not sel:
            return
        del self.elements[sel[0]]
        self._refresh_elist()
        self._draw_elements()

    def _clear_all(self):
        self.elements.clear()
        self._refresh_elist()
        self._draw_elements()

    # ------------------------------------------------------------------
    def save(self):
        if self._busy or not self.path:
            return
        if not self.elements:
            messagebox.showinfo("Hephaestus", "Add at least one text or image first.",
                                parent=self)
            return
        dest = filedialog.asksaveasfilename(
            title="Save edited PDF",
            initialdir=os.path.dirname(self.path),
            initialfile=os.path.splitext(os.path.basename(self.path))[0] + " (edited).pdf",
            defaultextension=".pdf", filetypes=[("PDF document", "*.pdf")],
            parent=self)
        if not dest:
            return
        self._busy = True
        self.save_btn.state(["disabled"])
        self.footer.busy(True)

        edits = self._compile_edits()

        def worker():
            try:
                outputs = pdf_ops.apply_edits(
                    self.path, dest, edits,
                    progress=lambda f, m: self.after(
                        0, lambda: (self.footer.busy(False),
                                    self.footer.set_progress(f),
                                    self.footer.set_status(m))))
                self.after(0, lambda: self._saved(outputs))
            except Exception as exc:
                self.after(0, lambda e=exc: self._failed(e))

        threading.Thread(target=worker, daemon=True).start()

    def _compile_edits(self) -> List[dict]:
        out = []
        doc = fitz.open(self.path)
        try:
            for el in self.elements:
                r = doc[el.page].rect
                if el.kind == "text":
                    x = el.fx * r.width
                    y = el.fy * r.height + el.size_pt  # click = top-left; baseline below
                    out.append({"kind": "text", "page": el.page, "point": (x, y),
                                "text": el.text, "size": el.size_pt,
                                "font": TEXT_FONTS[el.font_key], "color": el.color})
                else:
                    from PIL import Image
                    img = Image.open(el.path)
                    aspect = img.height / max(1, img.width)
                    w = el.wfrac * r.width
                    h = w * aspect
                    x, y = el.fx * r.width, el.fy * r.height
                    out.append({"kind": "image", "page": el.page,
                                "rect": (x, y, x + w, y + h), "image": el.path})
        finally:
            doc.close()
        return out

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
