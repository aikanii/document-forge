"""PDF <-> image conversions."""

from __future__ import annotations

import os
from typing import Callable, List, Sequence

from .mupdf_compat import fitz
from .pdf_ops import open_doc, parse_page_ranges, unique_path

Progress = Callable[[float, str], None]


def _nop(_f: float, _m: str = "") -> None:
    pass


IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp")

PAGE_SIZES = {  # portrait, in PDF points
    "A4": (595.28, 841.89),
    "Letter": (612.0, 792.0),
    "Legal": (612.0, 1008.0),
    "A3": (841.89, 1190.55),
    "A5": (419.53, 595.28),
}


def pdf_to_images(path: str, out_dir: str, fmt: str = "jpg", dpi: int = 150,
                  page_spec: str = "", progress: Progress = _nop) -> List[str]:
    """Render each page of *path* to an image file; returns list of outputs."""
    fmt = fmt.lower().lstrip(".")
    if fmt not in ("jpg", "jpeg", "png"):
        raise ValueError("Only JPG and PNG output are supported.")
    doc = open_doc(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    outputs: List[str] = []
    try:
        n = doc.page_count
        pages = (parse_page_ranges(page_spec, n) if page_spec.strip()
                 else list(range(n)))
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pad = max(2, len(str(n)))
        for k, i in enumerate(pages):
            progress(k / max(1, len(pages)), f"Rendering page {i + 1} ...")
            pix = doc[i].get_pixmap(matrix=matrix, alpha=(fmt == "png"))
            if len(pages) == 1 and n == 1:
                name = f"{stem}.{fmt}"
            else:
                name = f"{stem} - page {str(i + 1).zfill(pad)}.{fmt}"
            dest = unique_path(out_dir, os.path.splitext(name)[0], "." + fmt)
            pix.save(dest, jpg_quality=92 if fmt in ("jpg", "jpeg") else None)
            outputs.append(dest)
            pix = None
    finally:
        doc.close()
    progress(1.0, "Done")
    return outputs


def images_to_pdf(paths: Sequence[str], out_path: str,
                  page_size: str = "Fit to image", margin: float = 0,
                  progress: Progress = _nop) -> List[str]:
    """Compose images (any mix of formats) into one PDF, in order."""
    from PIL import Image

    if not paths:
        raise ValueError("Add at least one image.")
    doc = fitz.open()
    try:
        total = len(paths)
        for k, path in enumerate(paths):
            progress(k / total, f"Adding {os.path.basename(path)} ...")
            img = Image.open(path)
            # Flatten transparency onto white so the PDF looks right.
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
                img = Image.alpha_composite(bg, img).convert("RGB")
            iw, ih = img.size
            img.close()

            if page_size == "Fit to image":
                # image size in points at 96 dpi + margins
                pw, ph = iw * 72.0 / 96.0 + 2 * margin, ih * 72.0 / 96.0 + 2 * margin
            else:
                pw, ph = PAGE_SIZES.get(page_size, PAGE_SIZES["A4"])

            page = doc.new_page(width=pw, height=ph)
            avail_w, avail_h = pw - 2 * margin, ph - 2 * margin
            scale = min(avail_w / iw, avail_h / ih)
            w, h = iw * scale, ih * scale
            x0 = (pw - w) / 2.0
            y0 = (ph - h) / 2.0
            page.insert_image(fitz.Rect(x0, y0, x0 + w, y0 + h), filename=path)
        progress(0.95, "Saving ...")
        doc.save(out_path, garbage=3, deflate=True)
    finally:
        doc.close()
    progress(1.0, "Done")
    return [out_path]
