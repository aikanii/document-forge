"""OCR: turn a scanned PDF into a searchable PDF using Tesseract."""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
from typing import Callable, List

from .mupdf_compat import fitz
from .pdf_ops import open_doc

Progress = Callable[[float, str], None]


def _nop(_f: float, _m: str = "") -> None:
    pass


class ToolMissingError(RuntimeError):
    """Raised when an external binary (tesseract) is not installed."""


def find_tesseract() -> str | None:
    exe = shutil.which("tesseract")
    if exe:
        return exe
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser("~/AppData/Local/Programs/Tesseract-OCR/tesseract.exe"),
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def tesseract_languages() -> List[str]:
    exe = find_tesseract()
    if not exe:
        return []
    try:
        out = subprocess.run([exe, "--list-langs"], capture_output=True,
                             text=True, timeout=15)
        langs = [l.strip() for l in out.stdout.splitlines()[1:] if l.strip()]
        return langs
    except Exception:
        return []


TESSERACT_HELP = (
    "Tesseract OCR was not found on this system.\n\n"
    "Install it to use the OCR tool:\n"
    "  • Windows: download UB-Mannheim installer from\n"
    "      https://github.com/UB-Mannheim/tesseract/wiki\n"
    "  • macOS:   brew install tesseract\n"
    "  • Linux:   sudo apt install tesseract-ocr  (or dnf/pacman equivalent)\n\n"
    "Then restart Hephaestus."
)


def ocr_pdf(path: str, out_path: str, lang: str = "eng", dpi: int = 300,
            deskew: bool = True, progress: Progress = _nop) -> List[str]:
    """Render each page, OCR it with Tesseract, and rebuild a searchable PDF
    whose visible layer is the original page image."""
    try:
        import pytesseract
    except ImportError as exc:
        raise ToolMissingError("The 'pytesseract' Python package is missing.\n"
                               "Run:  pip install pytesseract") from exc

    exe = find_tesseract()
    if exe is None:
        raise ToolMissingError(TESSERACT_HELP)
    pytesseract.pytesseract.tesseract_cmd = exe

    config = f"--dpi {dpi}" + (" --psm 3" if deskew else " --psm 1")

    doc = open_doc(path)
    tmpdir = tempfile.mkdtemp(prefix="hephaestus_ocr_")
    try:
        n = doc.page_count
        page_pdfs: List[str] = []
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        for i in range(n):
            progress(i / n, f"OCR page {i + 1} of {n} ...")
            pix = doc[i].get_pixmap(matrix=matrix, alpha=False)
            img_bytes = pix.tobytes("png")
            pix = None
            from PIL import Image
            img = Image.open(io.BytesIO(img_bytes))
            pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                img, extension="pdf", lang=lang, config=config)
            img.close()
            page_pdf = os.path.join(tmpdir, f"page_{i:05d}.pdf")
            with open(page_pdf, "wb") as fh:
                fh.write(pdf_bytes)
            page_pdfs.append(page_pdf)
        doc.close()

        progress(0.92, "Assembling searchable document ...")
        if not page_pdfs:
            raise RuntimeError("No pages could be OCR'd.")
        merged = fitz.open()
        for p in page_pdfs:
            src = fitz.open(p)
            merged.insert_pdf(src)
            src.close()
        merged.save(out_path, garbage=3, deflate=True)
        merged.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if not doc.is_closed:
            doc.close()
    progress(1.0, "Done")
    return [out_path]
