"""Declarative registry of every Hephaestus tool.

A ToolSpec describes inputs, options, and the engine function to run; the
generic ToolPanel builds the whole UI from it. The three interactive tools
(Organize, Sign, Edit) declare `custom_view` instead and get bespoke panels.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence

from .engine import image_ops, ocr, office, pdf_ops

PDF_TYPES = [("PDF documents", "*.pdf"), ("All files", "*.*")]
IMAGE_TYPES = [("Images", "*.jpg *.jpeg *.png *.bmp *.gif *.tif *.tiff *.webp"),
               ("All files", "*.*")]
WORD_TYPES = [("Word documents", "*.doc *.docx *.odt *.rtf"), ("All files", "*.*")]
PPT_TYPES = [("PowerPoint decks", "*.ppt *.pptx *.odp"), ("All files", "*.*")]
EXCEL_TYPES = [("Excel workbooks", "*.xls *.xlsx *.ods *.csv"), ("All files", "*.*")]
HTML_TYPES = [("Web pages", "*.html *.htm"), ("All files", "*.*")]


@dataclass
class Option:
    key: str
    label: str
    kind: str            # 'choice' | 'check' | 'number' | 'text' | 'password' | 'file'
    values: Sequence = ()
    default: object = None
    hint: str = ""
    show_if: Optional[Callable[[dict], bool]] = None  # dynamic visibility


@dataclass
class ToolSpec:
    id: str
    name: str
    blurb: str
    category: str        # key into theme.CATEGORY_COLORS
    icon: str
    filetypes: Sequence[tuple]
    multiple: bool = False
    options: List[Option] = field(default_factory=list)
    runner: Optional[Callable] = None          # (files, opts, out_dir, progress) -> [paths]
    custom_view: Optional[str] = None          # 'organize' | 'sign' | 'edit'
    out_suffix: str = " (processed)"
    out_ext: str = ".pdf"
    needs_external: str = ""                   # 'libreoffice' | 'tesseract' | ''

    @property
    def category_color(self) -> str:
        from .theme import CATEGORY_COLORS
        return CATEGORY_COLORS.get(self.category, "#7A1F1F")

    @property
    def input_title(self) -> str:
        return "Select PDFs" if self.multiple else "Select a file"


# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------

def _stem(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def run_merge(files, opts, out_dir, progress):
    dest = pdf_ops.unique_path(out_dir, "Merged", ".pdf")
    return pdf_ops.merge_pdfs(files, dest, progress)


def run_split(files, opts, out_dir, progress):
    mode = {"One file per range": "ranges",
            "One file per page": "all",
            "Chunks of N pages": "every_n",
            "Extract selected pages into one file": "extract"}[opts["mode"]]
    return pdf_ops.split_pdf(files[0], out_dir, mode,
                             ranges=opts.get("ranges", "1-"),
                             every_n=int(opts.get("every_n", 1)),
                             progress=progress)


def run_compress(files, opts, out_dir, progress):
    level = {"Low compression — best quality": "low",
             "Recommended compression": "medium",
             "Extreme compression — smallest file": "high"}[opts["level"]]
    dest = pdf_ops.unique_path(out_dir, _stem(files[0]) + " (compressed)", ".pdf")
    return pdf_ops.compress_pdf(files[0], dest, level, progress)


def run_rotate(files, opts, out_dir, progress):
    angle = {"90° clockwise": 90, "180°": 180,
             "90° counter-clockwise": 270}[opts["angle"]]
    dest = pdf_ops.unique_path(out_dir, _stem(files[0]) + " (rotated)", ".pdf")
    return pdf_ops.rotate_pdf(files[0], dest, angle,
                              page_spec=opts.get("pages", ""), progress=progress)


def run_pagenum(files, opts, out_dir, progress):
    dest = pdf_ops.unique_path(out_dir, _stem(files[0]) + " (numbered)", ".pdf")
    return pdf_ops.add_page_numbers(
        files[0], dest, position=opts["position"], fmt=opts["format"],
        start=int(opts.get("start", 1)), font_size=float(opts.get("size", 10)),
        color=opts["color"], margin=float(opts.get("margin", 24)),
        page_spec=opts.get("pages", ""), progress=progress)


def run_watermark(files, opts, out_dir, progress):
    dest = pdf_ops.unique_path(out_dir, _stem(files[0]) + " (watermarked)", ".pdf")
    return pdf_ops.add_watermark(
        files[0], dest, kind=opts["wm_type"], text=opts.get("wm_text", ""),
        image_path=opts.get("wm_image", ""), position=opts["position"],
        opacity=float(opts.get("opacity", 0.25)),
        font_size=float(opts.get("size", 60)), color=opts["color"],
        scale=float(opts.get("scale", 0.3)), progress=progress)


def run_protect(files, opts, out_dir, progress):
    if not opts.get("password"):
        raise ValueError("Please enter a password.")
    dest = pdf_ops.unique_path(out_dir, _stem(files[0]) + " (protected)", ".pdf")
    return pdf_ops.protect_pdf(
        files[0], dest, opts["password"], owner_password=opts.get("owner", ""),
        can_print=opts.get("perm_print", True),
        can_modify=opts.get("perm_modify", False),
        can_copy=opts.get("perm_copy", True),
        can_annotate=opts.get("perm_annotate", False), progress=progress)


def run_unlock(files, opts, out_dir, progress):
    dest = pdf_ops.unique_path(out_dir, _stem(files[0]) + " (unlocked)", ".pdf")
    return pdf_ops.unlock_pdf(files[0], dest, password=opts.get("password", ""),
                              progress=progress)


def run_repair(files, opts, out_dir, progress):
    dest = pdf_ops.unique_path(out_dir, _stem(files[0]) + " (repaired)", ".pdf")
    return pdf_ops.repair_pdf(files[0], dest, progress=progress)


def run_pdf_to_images(files, opts, out_dir, progress):
    fmt = opts["format"].lower()
    dpi = int(opts["dpi"])
    return image_ops.pdf_to_images(files[0], out_dir, fmt=fmt, dpi=dpi,
                                   page_spec=opts.get("pages", ""),
                                   progress=progress)


def run_images_to_pdf(files, opts, out_dir, progress):
    dest = pdf_ops.unique_path(out_dir, "Images", ".pdf")
    return image_ops.images_to_pdf(files, dest, page_size=opts["page_size"],
                                   margin=float(opts.get("margin", 0)),
                                   progress=progress)


def run_ocr(files, opts, out_dir, progress):
    dest = pdf_ops.unique_path(out_dir, _stem(files[0]) + " (OCR)", ".pdf")
    return ocr.ocr_pdf(files[0], dest, lang=opts["language"],
                       dpi=int(opts["dpi"]), progress=progress)


def run_office_to_pdf(files, opts, out_dir, progress):
    return office.office_to_pdf(files, out_dir, progress=progress)


def run_html_to_pdf(files, opts, out_dir, progress):
    return office.html_to_pdf(files, out_dir, progress=progress)


def run_pdf_to_office(target):
    def _run(files, opts, out_dir, progress):
        return office.pdf_to_office(files[0], target, out_dir, progress=progress)
    return _run


def run_pdfa(files, opts, out_dir, progress):
    return office.pdf_to_pdfa(files, out_dir, version=opts["version"],
                              progress=progress)


def external_checker(kind: str) -> Callable[[], Optional[str]]:
    """Returns a function that yields an error message if the external
    dependency is missing (checked lazily when the tool panel opens)."""
    def _check() -> Optional[str]:
        if kind == "libreoffice" and office.find_soffice() is None:
            return office.LIBREOFFICE_HELP
        if kind == "tesseract" and ocr.find_tesseract() is None:
            return ocr.TESSERACT_HELP
        return None
    return _check


# ---------------------------------------------------------------------------
# The catalog
# ---------------------------------------------------------------------------

def build_catalog() -> List[ToolSpec]:
    tools: List[ToolSpec] = []

    # ---- Compose & Arrange -------------------------------------------------
    tools.append(ToolSpec(
        id="merge", name="Merge PDF",
        blurb="Combine PDFs into one document, in your order",
        category="compose", icon="merge", filetypes=PDF_TYPES, multiple=True,
        runner=run_merge))

    tools.append(ToolSpec(
        id="split", name="Split PDF",
        blurb="Cut a PDF into ranges, single pages, or even chunks",
        category="compose", icon="split", filetypes=PDF_TYPES,
        options=[
            Option("mode", "Mode", "choice",
                   ["One file per range", "Extract selected pages into one file",
                    "One file per page", "Chunks of N pages"],
                   default="One file per range"),
            Option("ranges", "Page ranges", "text", default="1-3, 5, 8-",
                   hint="e.g. 1-3, 5, 8-",
                   show_if=lambda o: o["mode"] in ("One file per range",
                                                   "Extract selected pages into one file")),
            Option("every_n", "Pages per chunk", "number", default=2,
                   show_if=lambda o: o["mode"] == "Chunks of N pages"),
        ],
        runner=run_split))

    tools.append(ToolSpec(
        id="organize", name="Organize PDF",
        blurb="Reorder, rotate, duplicate and remove pages visually",
        category="compose", icon="organize", filetypes=PDF_TYPES,
        custom_view="organize"))

    tools.append(ToolSpec(
        id="rotate", name="Rotate PDF",
        blurb="Turn all pages — or only the ones you choose",
        category="compose", icon="rotate", filetypes=PDF_TYPES,
        options=[
            Option("angle", "Rotation", "choice",
                   ["90° clockwise", "180°", "90° counter-clockwise"],
                   default="90° clockwise"),
            Option("pages", "Pages", "text", default="",
                   hint="blank = all pages; e.g. 1-3, 7"),
        ],
        runner=run_rotate))

    tools.append(ToolSpec(
        id="pagenum", name="Page Numbers",
        blurb="Stamp page numbers with your own format and placement",
        category="compose", icon="pagenum", filetypes=PDF_TYPES,
        options=[
            Option("position", "Position", "choice",
                   ["bottom-right", "bottom-center", "bottom-left",
                    "top-right", "top-center", "top-left"], default="bottom-right"),
            Option("format", "Format", "text", default="Page {p} of {n}",
                   hint="{p} = page no., {n} = total"),
            Option("start", "Start at", "number", default=1),
            Option("size", "Font size", "number", default=10),
            Option("color", "Color", "choice",
                   ["black", "gray", "red", "navy", "sepia", "white"], default="black"),
            Option("margin", "Margin (pt)", "number", default=24),
            Option("pages", "Pages", "text", default="", hint="blank = all pages"),
        ],
        runner=run_pagenum))

    tools.append(ToolSpec(
        id="watermark", name="Watermark",
        blurb="Stamp text or an image over your pages",
        category="compose", icon="watermark", filetypes=PDF_TYPES,
        options=[
            Option("wm_type", "Watermark", "choice", ["text", "image"], default="text"),
            Option("wm_text", "Text", "text", default="CONFIDENTIAL",
                   show_if=lambda o: o["wm_type"] == "text"),
            Option("wm_image", "Image file", "file", default="",
                   show_if=lambda o: o["wm_type"] == "image"),
            Option("position", "Position", "choice",
                   ["diagonal", "center", "top", "bottom", "tile"], default="diagonal"),
            Option("size", "Font size", "number", default=60,
                   show_if=lambda o: o["wm_type"] == "text"),
            Option("scale", "Image width (fraction of page)", "number", default=0.3,
                   show_if=lambda o: o["wm_type"] == "image"),
            Option("color", "Text color", "choice",
                   ["gray", "black", "red", "navy", "sepia", "white"], default="gray",
                   show_if=lambda o: o["wm_type"] == "text"),
            Option("opacity", "Opacity (0–1)", "number", default=0.25),
        ],
        runner=run_watermark))

    # ---- Optimize & Restore ------------------------------------------------
    tools.append(ToolSpec(
        id="compress", name="Compress PDF",
        blurb="Shrink file size while keeping the document readable",
        category="optimize", icon="compress", filetypes=PDF_TYPES,
        options=[
            Option("level", "Compression", "choice",
                   ["Low compression — best quality", "Recommended compression",
                    "Extreme compression — smallest file"],
                   default="Recommended compression"),
        ],
        runner=run_compress))

    tools.append(ToolSpec(
        id="repair", name="Repair PDF",
        blurb="Salvage a damaged PDF and rebuild it page by page",
        category="optimize", icon="repair", filetypes=PDF_TYPES,
        runner=run_repair))

    tools.append(ToolSpec(
        id="ocr", name="OCR PDF",
        blurb="Make scanned documents searchable with Tesseract",
        category="optimize", icon="ocr", filetypes=PDF_TYPES,
        options=[
            Option("language", "Language", "choice",
                   ["eng", "spa", "fra", "deu", "ita", "por", "nld", "pol", "tur",
                    "eng+spa", "eng+fra", "eng+deu"], default="eng"),
            Option("dpi", "Scan resolution", "choice", ["200", "300", "400"],
                   default="300"),
        ],
        runner=run_ocr, needs_external="tesseract"))

    # ---- Convert to PDF ----------------------------------------------------
    tools.append(ToolSpec(
        id="word2pdf", name="Word to PDF",
        blurb="Convert DOC, DOCX, ODT and RTF documents",
        category="to_pdf", icon="from_word", filetypes=WORD_TYPES, multiple=True,
        runner=run_office_to_pdf, needs_external="libreoffice",
        out_ext=""))

    tools.append(ToolSpec(
        id="ppt2pdf", name="PowerPoint to PDF",
        blurb="Convert PPT, PPTX and ODP presentations",
        category="to_pdf", icon="from_ppt", filetypes=PPT_TYPES, multiple=True,
        runner=run_office_to_pdf, needs_external="libreoffice",
        out_ext=""))

    tools.append(ToolSpec(
        id="excel2pdf", name="Excel to PDF",
        blurb="Convert XLS, XLSX, ODS and CSV spreadsheets",
        category="to_pdf", icon="from_excel", filetypes=EXCEL_TYPES, multiple=True,
        runner=run_office_to_pdf, needs_external="libreoffice",
        out_ext=""))

    tools.append(ToolSpec(
        id="img2pdf", name="JPG to PDF",
        blurb="Bind images into a single PDF document",
        category="to_pdf", icon="jpg_to_pdf", filetypes=IMAGE_TYPES, multiple=True,
        options=[
            Option("page_size", "Page size", "choice",
                   ["Fit to image", "A4", "Letter", "Legal", "A3", "A5"],
                   default="Fit to image"),
            Option("margin", "Margin (pt)", "number", default=0),
        ],
        runner=run_images_to_pdf))

    tools.append(ToolSpec(
        id="html2pdf", name="HTML to PDF",
        blurb="Save web pages as polished PDF documents",
        category="to_pdf", icon="html_to_pdf", filetypes=HTML_TYPES, multiple=True,
        runner=run_html_to_pdf, needs_external="libreoffice",
        out_ext=""))

    # ---- Convert from PDF --------------------------------------------------
    tools.append(ToolSpec(
        id="pdf2word", name="PDF to Word",
        blurb="Turn PDFs into editable DOCX documents",
        category="from_pdf", icon="to_word", filetypes=PDF_TYPES,
        runner=run_pdf_to_office("docx"), needs_external="libreoffice",
        out_ext=".docx"))

    tools.append(ToolSpec(
        id="pdf2ppt", name="PDF to PowerPoint",
        blurb="Turn PDFs into editable PPTX presentations",
        category="from_pdf", icon="to_ppt", filetypes=PDF_TYPES,
        runner=run_pdf_to_office("pptx"), needs_external="libreoffice",
        out_ext=".pptx"))

    tools.append(ToolSpec(
        id="pdf2excel", name="PDF to Excel",
        blurb="Extract tables from PDFs into XLSX spreadsheets",
        category="from_pdf", icon="to_excel", filetypes=PDF_TYPES,
        runner=run_pdf_to_office("xlsx"), needs_external="libreoffice",
        out_ext=".xlsx"))

    tools.append(ToolSpec(
        id="pdf2jpg", name="PDF to JPG",
        blurb="Render every page as a JPG or PNG image",
        category="from_pdf", icon="pdf_to_jpg", filetypes=PDF_TYPES,
        options=[
            Option("format", "Image format", "choice", ["JPG", "PNG"], default="JPG"),
            Option("dpi", "Resolution (DPI)", "choice",
                   ["72", "150", "300", "600"], default="150"),
            Option("pages", "Pages", "text", default="", hint="blank = all pages"),
        ],
        runner=run_pdf_to_images, out_ext=""))

    tools.append(ToolSpec(
        id="pdfa", name="PDF to PDF/A",
        blurb="Archive-grade conversion for long-term preservation",
        category="from_pdf", icon="pdfa", filetypes=PDF_TYPES,
        options=[
            Option("version", "Standard", "choice",
                   ["PDF/A-1b", "PDF/A-2b", "PDF/A-3b"], default="PDF/A-2b"),
        ],
        runner=run_pdfa, needs_external="libreoffice", out_ext=""))

    # ---- Secure & Sign -----------------------------------------------------
    tools.append(ToolSpec(
        id="protect", name="Protect PDF",
        blurb="Encrypt with a password and set permissions",
        category="secure", icon="protect", filetypes=PDF_TYPES,
        options=[
            Option("password", "Password", "password", default=""),
            Option("owner", "Owner password (optional)", "password", default=""),
            Option("perm_print", "Allow printing", "check", default=True),
            Option("perm_copy", "Allow copying text", "check", default=True),
            Option("perm_modify", "Allow modification", "check", default=False),
            Option("perm_annotate", "Allow annotations", "check", default=False),
        ],
        runner=run_protect))

    tools.append(ToolSpec(
        id="unlock", name="Unlock PDF",
        blurb="Remove password protection from a PDF you own",
        category="secure", icon="unlock", filetypes=PDF_TYPES,
        options=[
            Option("password", "Password (if required)", "password", default=""),
        ],
        runner=run_unlock))

    tools.append(ToolSpec(
        id="sign", name="Sign PDF",
        blurb="Draw, type or import a signature and stamp it on pages",
        category="secure", icon="sign", filetypes=PDF_TYPES,
        custom_view="sign"))

    # ---- Edit --------------------------------------------------------------
    tools.append(ToolSpec(
        id="edit", name="Edit PDF",
        blurb="Add text and images to any page",
        category="edit", icon="edit", filetypes=PDF_TYPES,
        custom_view="edit"))

    return tools


CATEGORY_TITLES = [
    ("compose",  "Compose & Arrange"),
    ("optimize", "Optimize & Restore"),
    ("to_pdf",   "Convert to PDF"),
    ("from_pdf", "Convert from PDF"),
    ("secure",   "Secure & Sign"),
    ("edit",     "Edit & Annotate"),
]
