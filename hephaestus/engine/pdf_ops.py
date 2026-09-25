"""Core PDF operations for Hephaestus.

Every public function takes a `progress` callback ``(fraction, message)`` so the
GUI can show determinate progress. All functions return the list of files they
produced.
"""

from __future__ import annotations

import os
import re
from typing import Callable, List, Optional, Sequence, Tuple

from .mupdf_compat import fitz

Progress = Callable[[float, str], None]


def _nop(_fraction: float, _message: str = "") -> None:
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_page_ranges(spec: str, page_count: int) -> List[int]:
    """Parse '1-3,5,8-' into a sorted list of 0-based page indices."""
    pages: List[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)?\s*-\s*(\d+)?", part)
        if m:
            start = int(m.group(1)) if m.group(1) else 1
            end = int(m.group(2)) if m.group(2) else page_count
            for p in range(max(1, start), min(page_count, end) + 1):
                pages.append(p - 1)
        elif part.isdigit():
            p = int(part)
            if 1 <= p <= page_count:
                pages.append(p - 1)
        else:
            raise ValueError(f"Cannot understand page range: '{part}'")
    if not pages:
        raise ValueError("No valid pages in range specification.")
    return sorted(set(pages))


def unique_path(directory: str, base: str, ext: str) -> str:
    """Return a non-colliding file path inside *directory*."""
    candidate = os.path.join(directory, f"{base}{ext}")
    n = 2
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base} ({n}){ext}")
        n += 1
    return candidate


def open_doc(path: str) -> "fitz.Document":
    """Open a PDF with a friendly error for missing/corrupt files."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")
    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise RuntimeError(
            f"Could not open '{os.path.basename(path)}' as a PDF ({exc}). "
            "Try the Repair PDF tool first."
        ) from exc
    if doc.needs_pass:
        raise RuntimeError(
            f"'{os.path.basename(path)}' is password-protected. "
            "Use the Unlock PDF tool first."
        )
    return doc


def _opacity_png(image_path: str, opacity: float, rotate: float = 0.0) -> str:
    """Return a temp PNG copy of *image_path* whose alpha channel is scaled by
    *opacity* (and optionally rotated), so insert_image yields translucency
    without needing PyMuPDF opacity support."""
    import tempfile
    from PIL import Image

    img = Image.open(image_path).convert("RGBA")
    alpha = img.getchannel("A").point(lambda v: int(v * max(0.0, min(1.0, opacity))))
    img.putalpha(alpha)
    if rotate:
        img = img.rotate(rotate, expand=True, resample=Image.BICUBIC)
    fd, tmp = tempfile.mkstemp(suffix=".png", prefix="hephaestus_wm_")
    os.close(fd)
    img.save(tmp)
    return tmp


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def merge_pdfs(paths: Sequence[str], out_path: str,
               progress: Progress = _nop) -> List[str]:
    if len(paths) < 1:
        raise ValueError("Add at least one PDF to merge.")
    out = fitz.open()
    total = len(paths)
    for i, path in enumerate(paths):
        progress(i / total, f"Merging {os.path.basename(path)} ...")
        src = open_doc(path)
        try:
            out.insert_pdf(src)
        finally:
            src.close()
    progress(0.95, "Writing merged document ...")
    out.save(out_path, garbage=3, deflate=True)
    out.close()
    progress(1.0, "Done")
    return [out_path]


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------

def split_pdf(path: str, out_dir: str, mode: str,
              ranges: str = "1-", every_n: int = 1,
              progress: Progress = _nop) -> List[str]:
    """Split modes: 'ranges' (one file per comma-separated range),
    'extract' (a single file with the listed pages), 'all' (one file per
    page), 'every_n' (chunks of N pages)."""
    doc = open_doc(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    outputs: List[str] = []
    try:
        n = doc.page_count
        if mode == "extract":
            keep = parse_page_ranges(ranges, n)
            out = fitz.open()
            out.insert_pdf(doc, from_page=0, to_page=-1)
            out.select(keep)
            dest = unique_path(out_dir, f"{stem} (extracted)", ".pdf")
            out.save(dest, garbage=3, deflate=True)
            out.close()
            outputs.append(dest)
            progress(1.0, "Done")
            return outputs

        groups: List[Tuple[str, List[int]]] = []
        if mode == "ranges":
            for part in ranges.split(","):
                part = part.strip()
                if not part:
                    continue
                pages = parse_page_ranges(part, n)
                safe = re.sub(r"[^\w\-]+", "_", part).strip("_")
                groups.append((safe, pages))
        elif mode == "all":
            groups = [(str(i + 1), [i]) for i in range(n)]
        elif mode == "every_n":
            every_n = max(1, int(every_n))
            for start in range(0, n, every_n):
                chunk = list(range(start, min(n, start + every_n)))
                groups.append((f"pages {chunk[0] + 1}-{chunk[-1] + 1}", chunk))
        else:
            raise ValueError(f"Unknown split mode: {mode}")

        if not groups:
            raise ValueError("Nothing to split — check the page ranges.")

        total = len(groups)
        for i, (label, pages) in enumerate(groups):
            progress(i / total, f"Splitting: {label} ...")
            out = fitz.open()
            out.insert_pdf(doc)
            out.select(pages)
            dest = unique_path(out_dir, f"{stem} - {label}", ".pdf")
            out.save(dest, garbage=3, deflate=True)
            out.close()
            outputs.append(dest)
        progress(1.0, "Done")
        return outputs
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Compress
# ---------------------------------------------------------------------------

_COMPRESS_PRESETS = {
    # level: (max image px, jpeg quality)
    "low":    (1920, 85),
    "medium": (1400, 72),
    "high":   (1000, 55),
}


def compress_pdf(path: str, out_path: str, level: str = "medium",
                 progress: Progress = _nop) -> List[str]:
    max_px, quality = _COMPRESS_PRESETS.get(level, _COMPRESS_PRESETS["medium"])
    doc = open_doc(path)
    try:
        n = doc.page_count
        for i in range(n):
            progress(0.85 * i / max(1, n), f"Downsampling images, page {i + 1} of {n} ...")
            page = doc[i]
            try:
                images = page.get_images(full=True)
            except Exception:
                continue
            for img in images:
                xref = img[0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if max(pix.width, pix.height) <= max_px:
                        pix = None
                        continue
                    scale = max_px / float(max(pix.width, pix.height))
                    new_w = max(1, int(pix.width * scale))
                    new_h = max(1, int(pix.height * scale))
                    if pix.alpha:
                        pix = fitz.Pixmap(pix, 0)  # drop alpha
                    from PIL import Image
                    import io
                    raw = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    raw = raw.resize((new_w, new_h), Image.LANCZOS)
                    buf = io.BytesIO()
                    raw.save(buf, format="JPEG", quality=quality, optimize=True)
                    page.replace_image(xref, stream=buf.getvalue())
                except Exception:
                    continue  # exotic image (CMYK/JPX/etc.) — leave as-is
                finally:
                    pix = None
        progress(0.9, "Rewriting document ...")
        doc.save(out_path, garbage=4, deflate=True, deflate_images=True,
                 deflate_fonts=True, clean=True)
    finally:
        doc.close()
    progress(1.0, "Done")
    return [out_path]


# ---------------------------------------------------------------------------
# Rotate
# ---------------------------------------------------------------------------

def rotate_pdf(path: str, out_path: str, angle: int, page_spec: str = "",
               progress: Progress = _nop) -> List[str]:
    doc = open_doc(path)
    try:
        n = doc.page_count
        targets = (parse_page_ranges(page_spec, n) if page_spec.strip()
                   else list(range(n)))
        for k, i in enumerate(targets):
            progress(k / max(1, len(targets)), f"Rotating page {i + 1} ...")
            page = doc[i]
            page.set_rotation((page.rotation + int(angle)) % 360)
        progress(0.95, "Saving ...")
        doc.save(out_path, garbage=3, deflate=True)
    finally:
        doc.close()
    progress(1.0, "Done")
    return [out_path]


# ---------------------------------------------------------------------------
# Organize (reorder / delete / rotate pages)
# ---------------------------------------------------------------------------

def organize_pdf(path: str, out_path: str,
                 page_order: Sequence[int],
                 extra_rotations: Optional[dict] = None,
                 progress: Progress = _nop) -> List[str]:
    """Rebuild the document following *page_order* (0-based indices, repeats
    allowed to duplicate a page). ``extra_rotations`` maps output position ->
    additional clockwise degrees."""
    doc = open_doc(path)
    try:
        out = fitz.open()
        total = len(page_order)
        for pos, src_index in enumerate(page_order):
            progress(pos / max(1, total), f"Placing page {src_index + 1} ...")
            out.insert_pdf(doc, from_page=src_index, to_page=src_index)
        if extra_rotations:
            for pos, deg in extra_rotations.items():
                if 0 <= pos < out.page_count:
                    page = out[pos]
                    page.set_rotation((page.rotation + int(deg)) % 360)
        progress(0.95, "Saving ...")
        out.save(out_path, garbage=3, deflate=True)
        out.close()
    finally:
        doc.close()
    progress(1.0, "Done")
    return [out_path]


# ---------------------------------------------------------------------------
# Page numbers
# ---------------------------------------------------------------------------

_NUM_POSITIONS = {
    "bottom-right":  lambda r, m: fitz.Rect(r.x1 - 220, r.y1 - 18 - m, r.x1 - m, r.y1 - m),
    "bottom-center": lambda r, m: fitz.Rect(r.x0 + r.width / 2 - 110, r.y1 - 18 - m, r.x0 + r.width / 2 + 110, r.y1 - m),
    "bottom-left":   lambda r, m: fitz.Rect(r.x0 + m, r.y1 - 18 - m, r.x0 + m + 220, r.y1 - m),
    "top-right":     lambda r, m: fitz.Rect(r.x1 - 220, r.y0 + m, r.x1 - m, r.y0 + m + 18),
    "top-center":    lambda r, m: fitz.Rect(r.x0 + r.width / 2 - 110, r.y0 + m, r.x0 + r.width / 2 + 110, r.y0 + m + 18),
    "top-left":      lambda r, m: fitz.Rect(r.x0 + m, r.y0 + m, r.x0 + m + 220, r.y0 + m + 18),
}

_ALIGN_FOR = {"bottom-right": 2, "top-right": 2,
              "bottom-center": 1, "top-center": 1,
              "bottom-left": 0, "top-left": 0}

_COLOR_NAMES = {"black": (0, 0, 0), "white": (1, 1, 1), "gray": (0.5, 0.5, 0.5),
                "red": (0.65, 0.1, 0.1), "navy": (0.1, 0.15, 0.4),
                "sepia": (0.44, 0.31, 0.18)}


def add_page_numbers(path: str, out_path: str, position: str = "bottom-right",
                     fmt: str = "Page {p} of {n}", start: int = 1,
                     font_size: float = 10, color: str = "black",
                     margin: float = 24, page_spec: str = "",
                     progress: Progress = _nop) -> List[str]:
    doc = open_doc(path)
    try:
        n = doc.page_count
        targets = (parse_page_ranges(page_spec, n) if page_spec.strip()
                   else list(range(n)))
        rect_fn = _NUM_POSITIONS[position]
        align = _ALIGN_FOR[position]
        rgb = _COLOR_NAMES.get(color, (0, 0, 0))
        for k, i in enumerate(targets):
            progress(k / max(1, len(targets)), f"Numbering page {i + 1} ...")
            page = doc[i]
            text = fmt.replace("{p}", str(start + k)).replace("{n}", str(start + len(targets) - 1))
            box = rect_fn(page.rect, margin)
            page.insert_textbox(box, text, fontsize=font_size, fontname="tiro",
                                color=rgb, align=align)
        progress(0.95, "Saving ...")
        doc.save(out_path, garbage=3, deflate=True)
    finally:
        doc.close()
    progress(1.0, "Done")
    return [out_path]


# ---------------------------------------------------------------------------
# Watermark (text or image)
# ---------------------------------------------------------------------------

_WM_POSITIONS = ("center", "diagonal", "top", "bottom", "tile")


def add_watermark(path: str, out_path: str, kind: str = "text",
                  text: str = "CONFIDENTIAL", image_path: str = "",
                  position: str = "diagonal", opacity: float = 0.25,
                  font_size: float = 60, color: str = "gray",
                  scale: float = 0.3, progress: Progress = _nop) -> List[str]:
    doc = open_doc(path)
    tmp_img: str | None = None
    try:
        rgb = _COLOR_NAMES.get(color, (0.5, 0.5, 0.5))
        if kind == "image" and image_path:
            tmp_img = _opacity_png(image_path, opacity,
                                   rotate=-45 if position == "diagonal" else 0)
        n = doc.page_count
        for i in range(n):
            progress(i / max(1, n), f"Watermarking page {i + 1} ...")
            page = doc[i]
            r = page.rect
            if tmp_img:
                img_w = r.width * scale
                pix = fitz.Pixmap(tmp_img)
                aspect = pix.height / max(1, pix.width)
                img_h = img_w * aspect
                pix = None
                if position in ("center", "diagonal"):
                    x0 = (r.width - img_w) / 2
                    y0 = (r.height - img_h) / 2
                elif position == "top":
                    x0, y0 = (r.width - img_w) / 2, r.height * 0.06
                else:
                    x0, y0 = (r.width - img_w) / 2, r.height - img_h - r.height * 0.06
                rect = fitz.Rect(x0, y0, x0 + img_w, y0 + img_h)
                if position == "diagonal":
                    # rotated art needs a larger rect to stay centred
                    diag = (img_w + img_h) * 0.72
                    rect = fitz.Rect(r.width / 2 - diag / 2, r.height / 2 - diag / 2,
                                     r.width / 2 + diag / 2, r.height / 2 + diag / 2)
                page.insert_image(rect, filename=tmp_img,
                                  keep_proportion=True, overlay=True)
            else:
                shape = page.new_shape()
                if position == "tile":
                    step_y = font_size * 4
                    step_x = font_size * len(text) * 0.75
                    y = 0
                    row = 0
                    while y < r.height + step_y:
                        x = -step_x / 2 if row % 2 else 0
                        while x < r.width + step_x:
                            shape.insert_text(fitz.Point(x, y), text,
                                              fontsize=font_size * 0.5,
                                              fontname="tiro", color=rgb)
                            x += step_x
                        y += step_y
                        row += 1
                    shape.finish(fill_opacity=opacity)
                else:
                    if position == "diagonal":
                        pt = fitz.Point(r.width * 0.18, r.height * 0.62)
                        morph = (fitz.Point(r.width / 2, r.height / 2), fitz.Matrix(-45))
                    elif position == "top":
                        pt = fitz.Point(r.width / 2 - font_size * len(text) * 0.25, r.height * 0.12)
                        morph = None
                    elif position == "bottom":
                        pt = fitz.Point(r.width / 2 - font_size * len(text) * 0.25, r.height * 0.93)
                        morph = None
                    else:  # center
                        pt = fitz.Point(r.width / 2 - font_size * len(text) * 0.25, r.height / 2)
                        morph = None
                    shape.insert_text(pt, text, fontsize=font_size,
                                      fontname="tiro", color=rgb)
                    shape.finish(fill_opacity=opacity, morph=morph)
                shape.commit()
        progress(0.95, "Saving ...")
        doc.save(out_path, garbage=3, deflate=True)
    finally:
        doc.close()
        if tmp_img and os.path.exists(tmp_img):
            try:
                os.remove(tmp_img)
            except OSError:
                pass
    progress(1.0, "Done")
    return [out_path]


# ---------------------------------------------------------------------------
# Protect / Unlock  (via pypdf for standard AES/RC4 encryption)
# ---------------------------------------------------------------------------

def protect_pdf(path: str, out_path: str, user_password: str,
                owner_password: str = "", can_print: bool = True,
                can_modify: bool = False, can_copy: bool = True,
                can_annotate: bool = False, progress: Progress = _nop) -> List[str]:
    from pypdf import PdfReader, PdfWriter
    from pypdf.constants import UserAccessPermissions

    progress(0.2, "Reading document ...")
    reader = PdfReader(path)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            raise RuntimeError("The source PDF is already encrypted.")
    writer = PdfWriter(clone_from=reader)
    perms = UserAccessPermissions(0)
    if can_print:
        perms |= UserAccessPermissions.PRINT
    if can_modify:
        perms |= UserAccessPermissions.MODIFY
    if can_copy:
        perms |= UserAccessPermissions.EXTRACT
    if can_annotate:
        perms |= UserAccessPermissions.ANNOTATE
    progress(0.6, "Encrypting ...")
    try:
        writer.encrypt(user_password=user_password,
                       owner_password=owner_password or user_password,
                       permissions_flag=perms, algorithm="AES-256")
    except Exception:
        # AES needs the optional `cryptography` package; RC4-128 does not.
        writer = PdfWriter(clone_from=reader)
        writer.encrypt(user_password=user_password,
                       owner_password=owner_password or user_password,
                       permissions_flag=perms, algorithm="RC4-128")
    with open(out_path, "wb") as fh:
        writer.write(fh)
    progress(1.0, "Done")
    return [out_path]


def unlock_pdf(path: str, out_path: str, password: str = "",
               progress: Progress = _nop) -> List[str]:
    from pypdf import PdfReader, PdfWriter

    progress(0.2, "Reading document ...")
    reader = PdfReader(path)
    if reader.is_encrypted:
        result = reader.decrypt(password)
        if result == 0:
            raise RuntimeError("Incorrect password — the document could not be unlocked.")
    progress(0.5, "Rewriting without encryption ...")
    writer = PdfWriter(clone_from=reader)
    try:
        writer.remove_links()
    except Exception:
        pass
    with open(out_path, "wb") as fh:
        writer.write(fh)
    # Verify the result really is unencrypted
    check = PdfReader(out_path)
    if check.is_encrypted:
        # Some owners set encryption flags with an empty password: re-save via MuPDF.
        doc = fitz.open(out_path)
        doc.authenticate("")
        tmp = out_path + ".tmp.pdf"
        doc.save(tmp, garbage=3, deflate=True)
        doc.close()
        os.replace(tmp, out_path)
    progress(1.0, "Done")
    return [out_path]


# ---------------------------------------------------------------------------
# Repair
# ---------------------------------------------------------------------------

def repair_pdf(path: str, out_path: str, progress: Progress = _nop) -> List[str]:
    progress(0.2, "Parsing document structure ...")
    doc = None
    try:
        doc = fitz.open(path)
        if doc.needs_pass:
            doc.authenticate("")
        progress(0.5, "Rebuilding pages ...")
        rebuilt = fitz.open()
        n = doc.page_count
        for i in range(n):
            progress(0.5 + 0.4 * i / max(1, n), f"Rebuilding page {i + 1} of {n} ...")
            try:
                rebuilt.insert_pdf(doc, from_page=i, to_page=i)
            except Exception:
                continue  # skip unreadable pages, keep the rest
        if rebuilt.page_count == 0:
            raise RuntimeError("No readable pages could be recovered.")
        rebuilt.save(out_path, garbage=4, deflate=True, clean=True)
        rebuilt.close()
    finally:
        if doc is not None:
            doc.close()
    progress(1.0, "Done")
    return [out_path]


# ---------------------------------------------------------------------------
# Stamp a signature / arbitrary image (used by the Sign tool)
# ---------------------------------------------------------------------------

def stamp_image(path: str, out_path: str,
                stamps: Sequence[dict], progress: Progress = _nop) -> List[str]:
    """stamps: dicts with keys page (0-based), rect (x0,y0,x1,y1 in PDF
    points), image (path to a PNG, ideally with transparency)."""
    doc = open_doc(path)
    try:
        total = max(1, len(stamps))
        for k, st in enumerate(stamps):
            progress(k / total, "Applying signature ...")
            page = doc[int(st["page"])]
            page.insert_image(fitz.Rect(*st["rect"]), filename=st["image"],
                              overlay=True, keep_proportion=True)
        progress(0.9, "Saving ...")
        doc.save(out_path, garbage=3, deflate=True)
    finally:
        doc.close()
    progress(1.0, "Done")
    return [out_path]


# ---------------------------------------------------------------------------
# Add text / image annotations (used by the Edit tool)
# ---------------------------------------------------------------------------

def apply_edits(path: str, out_path: str, edits: Sequence[dict],
                progress: Progress = _nop) -> List[str]:
    """edits: dicts, either {'kind':'text', 'page':int, 'point':(x,y),
    'text':str, 'size':float, 'color':(r,g,b), 'font':'helv'|'tiro'|'it'}
    or {'kind':'image', 'page':int, 'rect':(x0,y0,x1,y1), 'image':path}."""
    doc = open_doc(path)
    try:
        total = max(1, len(edits))
        for k, e in enumerate(edits):
            progress(k / total, "Applying edit ...")
            page = doc[int(e["page"])]
            if e["kind"] == "text":
                page.insert_text(fitz.Point(*e["point"]), e["text"],
                                 fontsize=float(e.get("size", 12)),
                                 fontname=e.get("font", "helv"),
                                 color=tuple(e.get("color", (0, 0, 0))))
            elif e["kind"] == "image":
                page.insert_image(fitz.Rect(*e["rect"]), filename=e["image"],
                                  keep_proportion=True, overlay=True)
        progress(0.9, "Saving ...")
        doc.save(out_path, garbage=3, deflate=True)
    finally:
        doc.close()
    progress(1.0, "Done")
    return [out_path]


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def pdf_info(path: str) -> dict:
    doc = open_doc(path)
    try:
        meta = doc.metadata or {}
        return {
            "pages": doc.page_count,
            "encrypted": bool(doc.is_encrypted and doc.needs_pass),
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "size_bytes": os.path.getsize(path),
        }
    finally:
        doc.close()


def render_page_pixmap(path: str, page_index: int, width_px: int = 120) -> "fitz.Pixmap":
    doc = fitz.open(path)
    try:
        page = doc[page_index]
        zoom = width_px / max(1.0, page.rect.width)
        return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    finally:
        doc.close()
