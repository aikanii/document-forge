"""Hand-drawn style canvas icons for Hephaestus tools.

Every icon is drawn with vector primitives in an 'ink on parchment' style —
a page silhouette plus a distinguishing mark. This keeps the app free of
binary icon assets and matches the manuscript theme.
"""

from __future__ import annotations

import math
import tkinter as tk


def _page(c: tk.Canvas, s: float, ox: float, oy: float, w: float, h: float,
          ink: str, accent: str, fold: bool = True, lw: int = 2) -> tuple:
    """Draw a page outline; returns the inner rect (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = ox + w * 0.22, oy + h * 0.10, ox + w * 0.78, oy + h * 0.90
    f = min(w, h) * 0.16  # fold size
    if fold:
        c.create_polygon(x0, y0, x1 - f, y0, x1, y0 + f, x1, y1, x0, y1,
                         outline=ink, width=lw, fill="")
        c.create_line(x1 - f, y0, x1 - f, y0 + f, x1, y0 + f,
                      fill=ink, width=lw)
    else:
        c.create_rectangle(x0, y0, x1, y1, outline=ink, width=lw, fill="")
    return x0, y0, x1, y1


def _lines(c: tk.Canvas, x0, y0, x1, y1, ink, n=3, top=0.35, lw=1):
    """Small text lines on a page."""
    span = (y1 - y0) * (0.75 - top)
    step = span / max(1, n)
    yy = y0 + (y1 - y0) * top
    for i in range(n):
        w = (x1 - x0) * (0.62 if i == n - 1 else 0.5)
        c.create_line(x0 + (x1 - x0) * 0.25, yy,
                      x0 + (x1 - x0) * 0.25 + w, yy, fill=ink, width=lw)
        yy += step


def _arrow(c: tk.Canvas, x0, y0, x1, y1, color, lw=2, head=5):
    c.create_line(x0, y0, x1, y1, fill=color, width=lw)
    ang = math.atan2(y1 - y0, x1 - x0)
    for da in (2.6, -2.6):
        c.create_line(x1, y1, x1 - head * math.cos(ang + da),
                      y1 - head * math.sin(ang + da), fill=color, width=lw)


ICON_PAINTERS = {}


def icon(name):
    def deco(fn):
        ICON_PAINTERS[name] = fn
        return fn
    return deco


# ---------------------------------------------------------------------------

@icon("merge")
def _merge(c, s, ink, accent):
    x0, y0, x1, y1 = _page(c, s, s * 0.02, s * 0.10, s * 0.62, s * 0.80, ink, accent)
    _lines(c, x0, y0, x1, y1, ink, n=3)
    x0b, y0b, x1b, y1b = _page(c, s, s * 0.36, s * 0.22, s * 0.62, s * 0.80, ink, accent)
    c.create_rectangle(x0b, y0b, x1b, y1b, outline=ink, width=2)
    _arrow(c, s * 0.50, s * 0.90, s * 0.50, s * 0.80, accent, lw=2, head=4)


@icon("split")
def _split(c, s, ink, accent):
    x0, y0, x1, y1 = _page(c, s, s * 0.18, s * 0.06, s * 0.64, s * 0.72, ink, accent)
    mid = (x0 + x1) / 2
    c.create_line(mid, y0 + 4, mid, y1 - 4, fill=accent, width=2, dash=(4, 3))
    # scissors at the bottom
    cy = s * 0.88
    c.create_oval(mid - s * 0.14, cy - s * 0.05, mid - s * 0.04, cy + s * 0.05,
                  outline=ink, width=2)
    c.create_oval(mid + s * 0.04, cy - s * 0.05, mid + s * 0.14, cy + s * 0.05,
                  outline=ink, width=2)
    c.create_line(mid - s * 0.09, cy - s * 0.04, mid + s * 0.05, cy - s * 0.16,
                  fill=ink, width=2)
    c.create_line(mid + s * 0.09, cy - s * 0.04, mid - s * 0.05, cy - s * 0.16,
                  fill=ink, width=2)


@icon("compress")
def _compress(c, s, ink, accent):
    x0, y0, x1, y1 = _page(c, s, s * 0.22, s * 0.18, s * 0.56, s * 0.64, ink, accent)
    _lines(c, x0, y0, x1, y1, ink, n=3)
    _arrow(c, s * 0.50, s * 0.04, s * 0.50, s * 0.15, accent, head=5)
    _arrow(c, s * 0.50, s * 0.96, s * 0.50, s * 0.85, accent, head=5)
    _arrow(c, s * 0.06, s * 0.50, s * 0.17, s * 0.50, accent, head=5)
    _arrow(c, s * 0.94, s * 0.50, s * 0.83, s * 0.50, accent, head=5)


@icon("organize")
def _organize(c, s, ink, accent):
    for i, (dx, dy) in enumerate(((0.30, 0.04), (0.16, 0.16), (0.02, 0.28))):
        col = accent if i == 0 else ink
        c.create_rectangle(s * dx + s * 0.16, s * dy + s * 0.10,
                           s * dx + s * 0.48, s * dy + s * 0.52,
                           outline=col, width=2)
    _arrow(c, s * 0.72, s * 0.30, s * 0.72, s * 0.66, accent, head=5)
    c.create_line(s * 0.62, s * 0.78, s * 0.82, s * 0.78, fill=ink, width=2)


@icon("rotate")
def _rotate(c, s, ink, accent):
    x0, y0, x1, y1 = _page(c, s, s * 0.24, s * 0.20, s * 0.52, s * 0.60, ink, accent)
    cx, cy, r = s * 0.5, s * 0.5, s * 0.40
    c.create_arc(cx - r, cy - r, cx + r, cy + r, start=60, extent=240,
                 style="arc", outline=accent, width=3)
    ax, ay = cx + r * math.cos(math.radians(60)), cy - r * math.sin(math.radians(60))
    c.create_polygon(ax, ay, ax - s * 0.09, ay - s * 0.02, ax - s * 0.02, ay + s * 0.08,
                     fill=accent, outline=accent)


@icon("pagenum")
def _pagenum(c, s, ink, accent):
    x0, y0, x1, y1 = _page(c, s, s * 0.14, s * 0.06, s * 0.60, s * 0.76, ink, accent)
    _lines(c, x0, y0, x1, y1, ink, n=3, top=0.28)
    c.create_text(s * 0.56, s * 0.74, text="#", fill=accent,
                  font=("Times New Roman", int(s * 0.22), "bold"))


@icon("watermark")
def _watermark(c, s, ink, accent):
    x0, y0, x1, y1 = _page(c, s, s * 0.14, s * 0.06, s * 0.60, s * 0.76, ink, accent)
    _lines(c, x0, y0, x1, y1, ink, n=3, top=0.28)
    c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text="W", fill=accent,
                  angle=40, font=("Times New Roman", int(s * 0.34), "bold"))


@icon("sign")
def _sign(c, s, ink, accent):
    x0, y0, x1, y1 = _page(c, s, s * 0.14, s * 0.06, s * 0.60, s * 0.76, ink, accent)
    _lines(c, x0, y0, x1, y1, ink, n=2, top=0.26)
    # signature squiggle
    yy = y0 + (y1 - y0) * 0.66
    c.create_line(x0 + (x1 - x0) * 0.22, yy,
                  x0 + (x1 - x0) * 0.34, yy - s * 0.08,
                  x0 + (x1 - x0) * 0.42, yy + s * 0.05,
                  x0 + (x1 - x0) * 0.56, yy - s * 0.10,
                  x0 + (x1 - x0) * 0.66, yy,
                  smooth=True, fill=accent, width=2)
    # quill
    c.create_line(s * 0.86, s * 0.30, s * 0.62, s * 0.62, fill=ink, width=2)
    c.create_polygon(s * 0.86, s * 0.30, s * 0.94, s * 0.10, s * 0.76, s * 0.20,
                     fill=ink, outline=ink)


@icon("edit")
def _edit(c, s, ink, accent):
    x0, y0, x1, y1 = _page(c, s, s * 0.12, s * 0.06, s * 0.58, s * 0.74, ink, accent)
    _lines(c, x0, y0, x1, y1, ink, n=3, top=0.28)
    # pencil
    c.create_polygon(s * 0.58, s * 0.90, s * 0.92, s * 0.50, s * 0.98, s * 0.58,
                     s * 0.66, s * 0.96, fill=accent, outline=ink)
    c.create_line(s * 0.58, s * 0.90, s * 0.52, s * 0.98, fill=ink, width=2)


@icon("protect")
def _protect(c, s, ink, accent):
    x0, y0, x1, y1 = _page(c, s, s * 0.18, s * 0.04, s * 0.64, s * 0.72, ink, accent)
    _lines(c, x0, y0, x1, y1, ink, n=2, top=0.24)
    bx, by = s * 0.5, s * 0.72
    c.create_rectangle(bx - s * 0.17, by, bx + s * 0.17, by + s * 0.22,
                       fill=accent, outline=ink, width=2)
    c.create_arc(bx - s * 0.10, by - s * 0.14, bx + s * 0.10, by + s * 0.06,
                 start=0, extent=180, style="arc", outline=ink, width=3)


@icon("unlock")
def _unlock(c, s, ink, accent):
    x0, y0, x1, y1 = _page(c, s, s * 0.18, s * 0.04, s * 0.64, s * 0.72, ink, accent)
    _lines(c, x0, y0, x1, y1, ink, n=2, top=0.24)
    bx, by = s * 0.5, s * 0.72
    c.create_rectangle(bx - s * 0.17, by, bx + s * 0.17, by + s * 0.22,
                       fill=accent, outline=ink, width=2)
    c.create_arc(bx - s * 0.10, by - s * 0.14, bx + s * 0.10, by + s * 0.06,
                 start=30, extent=210, style="arc", outline=ink, width=3)


@icon("repair")
def _repair(c, s, ink, accent):
    x0, y0, x1, y1 = _page(c, s, s * 0.18, s * 0.06, s * 0.64, s * 0.78, ink, accent)
    _lines(c, x0, y0, x1, y1, ink, n=2, top=0.24)
    # wrench
    c.create_line(s * 0.56, s * 0.86, s * 0.84, s * 0.56, fill=accent, width=4)
    c.create_arc(s * 0.74, s * 0.42, s * 0.96, s * 0.64, start=120, extent=270,
                 style="arc", outline=accent, width=4)


@icon("ocr")
def _ocr(c, s, ink, accent):
    x0, y0, x1, y1 = _page(c, s, s * 0.18, s * 0.06, s * 0.64, s * 0.74, ink, accent)
    _lines(c, x0, y0, x1, y1, ink, n=2, top=0.24)
    # eye with scanning line
    ex, ey = s * 0.5, s * 0.86
    c.create_arc(ex - s * 0.20, ey - s * 0.11, ex + s * 0.20, ey + s * 0.11,
                 start=0, extent=180, style="arc", outline=accent, width=3)
    c.create_arc(ex - s * 0.20, ey - s * 0.11, ex + s * 0.20, ey + s * 0.11,
                 start=180, extent=180, style="arc", outline=accent, width=3)
    c.create_oval(ex - s * 0.05, ey - s * 0.05, ex + s * 0.05, ey + s * 0.05,
                  fill=accent, outline=accent)


@icon("to_word")
def _to_word(c, s, ink, accent):
    _to_office(c, s, ink, accent, "W", "#2B579A")


@icon("to_ppt")
def _to_ppt(c, s, ink, accent):
    _to_office(c, s, ink, accent, "P", "#B7472A")


@icon("to_excel")
def _to_excel(c, s, ink, accent):
    _to_office(c, s, ink, accent, "X", "#217346")


def _to_office(c, s, ink, accent, letter, tint):
    x0, y0, x1, y1 = _page(c, s, s * 0.08, s * 0.14, s * 0.52, s * 0.86, ink, accent)
    _lines(c, x0, y0, x1, y1, ink, n=3, top=0.24)
    c.create_oval(s * 0.52, s * 0.52, s * 0.96, s * 0.96, fill=tint, outline=ink, width=2)
    c.create_text(s * 0.74, s * 0.74, text=letter, fill="#FFFFFF",
                  font=("Times New Roman", int(s * 0.24), "bold"))


@icon("from_word")
def _from_word(c, s, ink, accent):
    _from_office(c, s, ink, accent, "W", "#2B579A")


@icon("from_ppt")
def _from_ppt(c, s, ink, accent):
    _from_office(c, s, ink, accent, "P", "#B7472A")


@icon("from_excel")
def _from_excel(c, s, ink, accent):
    _from_office(c, s, ink, accent, "X", "#217346")


def _from_office(c, s, ink, accent, letter, tint):
    c.create_oval(s * 0.04, s * 0.06, s * 0.44, s * 0.46, fill=tint, outline=ink, width=2)
    c.create_text(s * 0.24, s * 0.26, text=letter, fill="#FFFFFF",
                  font=("Times New Roman", int(s * 0.22), "bold"))
    x0, y0, x1, y1 = _page(c, s, s * 0.38, s * 0.30, s * 0.56, s * 0.68, ink, accent)
    _arrow(c, s * 0.30, s * 0.52, s * 0.44, s * 0.52, accent, head=5)


@icon("pdf_to_jpg")
def _pdf_to_jpg(c, s, ink, accent):
    x0, y0, x1, y1 = _page(c, s, s * 0.06, s * 0.16, s * 0.46, s * 0.84, ink, accent)
    _lines(c, x0, y0, x1, y1, ink, n=3)
    # photo frame with mountain + sun
    fx0, fy0, fx1, fy1 = s * 0.54, s * 0.30, s * 0.96, s * 0.74
    c.create_rectangle(fx0, fy0, fx1, fy1, outline=ink, width=2, fill="#FFFDF6")
    c.create_oval(fx0 + (fx1 - fx0) * 0.62, fy0 + (fy1 - fy0) * 0.12,
                  fx0 + (fx1 - fx0) * 0.80, fy0 + (fy1 - fy0) * 0.34,
                  fill=accent, outline="")
    c.create_polygon(fx0 + 2, fy1 - 2, fx0 + (fx1 - fx0) * 0.38, fy0 + (fy1 - fy0) * 0.45,
                     fx0 + (fx1 - fx0) * 0.62, fy1 - 2,
                     fill=ink, outline="")
    c.create_polygon(fx0 + (fx1 - fx0) * 0.45, fy1 - 2, fx0 + (fx1 - fx0) * 0.70,
                     fy0 + (fy1 - fy0) * 0.55, fx1 - 2, fy1 - 2,
                     fill=accent, outline="")
    _arrow(c, s * 0.44, s * 0.12, s * 0.60, s * 0.24, accent, head=5)


@icon("jpg_to_pdf")
def _jpg_to_pdf(c, s, ink, accent):
    fx0, fy0, fx1, fy1 = s * 0.04, s * 0.28, s * 0.44, s * 0.70
    c.create_rectangle(fx0, fy0, fx1, fy1, outline=ink, width=2, fill="#FFFDF6")
    c.create_oval(fx0 + (fx1 - fx0) * 0.60, fy0 + (fy1 - fy0) * 0.12,
                  fx0 + (fx1 - fx0) * 0.78, fy0 + (fy1 - fy0) * 0.34,
                  fill=accent, outline="")
    c.create_polygon(fx0 + 2, fy1 - 2, fx0 + (fx1 - fx0) * 0.40, fy0 + (fy1 - fy0) * 0.45,
                     fx1 - 2, fy1 - 2, fill=ink, outline="")
    x0, y0, x1, y1 = _page(c, s, s * 0.54, s * 0.16, s * 0.42, s * 0.68, ink, accent)
    _lines(c, x0, y0, x1, y1, ink, n=3)
    _arrow(c, s * 0.40, s * 0.22, s * 0.56, s * 0.14, accent, head=5)


@icon("html_to_pdf")
def _html_to_pdf(c, s, ink, accent):
    c.create_text(s * 0.26, s * 0.5, text="</>", fill=ink,
                  font=("Times New Roman", int(s * 0.22), "bold"))
    _arrow(c, s * 0.46, s * 0.5, s * 0.58, s * 0.5, accent, head=5)
    x0, y0, x1, y1 = _page(c, s, s * 0.60, s * 0.14, s * 0.38, s * 0.72, ink, accent)
    _lines(c, x0, y0, x1, y1, ink, n=3)


@icon("pdfa")
def _pdfa(c, s, ink, accent):
    x0, y0, x1, y1 = _page(c, s, s * 0.14, s * 0.04, s * 0.58, s * 0.70, ink, accent)
    _lines(c, x0, y0, x1, y1, ink, n=2, top=0.24)
    c.create_oval(s * 0.50, s * 0.52, s * 0.96, s * 0.98, outline=accent, width=3,
                  fill="#FFFDF6")
    c.create_text(s * 0.73, s * 0.75, text="A", fill=accent,
                  font=("Times New Roman", int(s * 0.26), "bold"))


def draw_icon(canvas: tk.Canvas, name: str, size: int,
              ink: str = "#2B2119", accent: str = "#7A1F1F") -> None:
    """Clear *canvas* and paint the named icon scaled to *size* px."""
    canvas.delete("all")
    canvas.configure(width=size, height=size, highlightthickness=0)
    painter = ICON_PAINTERS.get(name)
    if painter is None:
        canvas.create_text(size / 2, size / 2, text="?", fill=ink,
                           font=("Times New Roman", size // 2))
        return
    painter(canvas, float(size), ink, accent)


def draw_seal(canvas: tk.Canvas, size: int, seal_color: str = "#8C2F24",
              letter_color: str = "#F3ECDB", letter: str = "H") -> None:
    """The Hephaestus wax-seal logo."""
    canvas.delete("all")
    canvas.configure(width=size, height=size, highlightthickness=0, bg=canvas["bg"])
    r = size / 2
    # irregular wax blob
    pts = []
    for i in range(36):
        a = math.radians(i * 10)
        rr = r * (0.94 + 0.06 * math.sin(i * 2.4))
        pts += [r + rr * math.cos(a), r + rr * math.sin(a)]
    canvas.create_polygon(pts, fill=seal_color, outline="", smooth=True)
    canvas.create_oval(r * 0.30, r * 0.30, r * 1.70, r * 1.70,
                       outline=letter_color, width=max(2, size // 28))
    canvas.create_text(r, r, text=letter, fill=letter_color,
                       font=("Times New Roman", int(size * 0.44), "bold"))
