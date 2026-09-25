"""Office conversions via a headless LibreOffice install.

Handles: PDF -> Word/PowerPoint/Excel, Word/PowerPoint/Excel -> PDF,
HTML -> PDF, and PDF -> PDF/A.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Callable, List, Optional, Sequence

Progress = Callable[[float, str], None]


def _nop(_f: float, _m: str = "") -> None:
    pass


class ToolMissingError(RuntimeError):
    """Raised when LibreOffice is not installed."""


LIBREOFFICE_HELP = (
    "LibreOffice was not found on this system.\n\n"
    "Hephaestus uses it (invisibly, in the background) for Word/PowerPoint/\n"
    "Excel and HTML conversions. Install the free LibreOffice suite:\n\n"
    "      https://www.libreoffice.org/download/download/\n\n"
    "  • Windows / macOS: run the installer, then restart Hephaestus.\n"
    "  • Linux: sudo apt install libreoffice  (or dnf/pacman equivalent).\n"
)


def find_soffice() -> Optional[str]:
    for name in ("soffice", "libreoffice"):
        exe = shutil.which(name)
        if exe:
            return exe
    candidates = []
    if sys.platform == "win32":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
            candidates.append(os.path.join(base, "LibreOffice", "program", "soffice.exe"))
    elif sys.platform == "darwin":
        candidates.append("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    else:
        candidates += ["/usr/bin/soffice", "/usr/lib/libreoffice/program/soffice",
                       "/opt/libreoffice/program/soffice",
                       "/var/lib/flatpak/exports/bin/org.libreoffice.LibreOffice"]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def _lock_profile_dir() -> str:
    """A dedicated user profile lets soffice run even if one is already open."""
    d = os.path.join(tempfile.gettempdir(), "hephaestus_lo_profile")
    os.makedirs(d, exist_ok=True)
    return d


def convert(files: Sequence[str], target: str, out_dir: str,
            extra_args: Optional[Sequence[str]] = None,
            timeout_per_file: int = 240,
            progress: Progress = _nop) -> List[str]:
    """Convert *files* to *target* format ('docx', 'pdf', 'pdf:writer_pdf_Export:{...}' ...).

    Returns the produced files. Raises ToolMissingError if LibreOffice is absent.
    """
    exe = find_soffice()
    if exe is None:
        raise ToolMissingError(LIBREOFFICE_HELP)
    if not files:
        raise ValueError("No input files given.")

    os.makedirs(out_dir, exist_ok=True)
    profile = _lock_profile_dir()
    produced: List[str] = []
    total = len(files)
    # One soffice invocation per file: predictable and resilient to single failures.
    errors: List[str] = []
    for i, src in enumerate(files):
        progress(i / total, f"Converting {os.path.basename(src)} ...")
        with tempfile.TemporaryDirectory(prefix="hephaestus_lo_") as tmp_out:
            cmd = [exe, "--headless", "--norestore", "--nolockcheck",
                   f"-env:UserInstallation=file://{profile}",
                   "--convert-to", target, "--outdir", tmp_out, src]
            if extra_args:
                cmd[1:1] = list(extra_args)
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True,
                                      timeout=timeout_per_file,
                                      startupinfo=startupinfo)
            except subprocess.TimeoutExpired:
                errors.append(f"{os.path.basename(src)}: conversion timed out")
                continue
            made = [os.path.join(tmp_out, f) for f in os.listdir(tmp_out)]
            made = [f for f in made if os.path.isfile(f)]
            if not made:
                detail = (proc.stderr or proc.stdout or "").strip().splitlines()
                detail = detail[-1] if detail else "unknown error"
                errors.append(f"{os.path.basename(src)}: {detail}")
                continue
            for f in made:
                base = os.path.splitext(os.path.basename(src))[0]
                dest = os.path.join(out_dir, base + os.path.splitext(f)[1])
                k = 2
                while os.path.exists(dest):
                    dest = os.path.join(out_dir, f"{base} ({k}){os.path.splitext(f)[1]}")
                    k += 1
                shutil.move(f, dest)
                produced.append(dest)
            # give soffice a beat to release its profile lock
            time.sleep(0.15)
    if not produced:
        raise RuntimeError("Conversion failed for every input file.\n\n" +
                           "\n".join(errors))
    progress(1.0, "Done")
    return produced


OFFICE_TO_PDF_EXTS = (".doc", ".docx", ".odt", ".rtf", ".txt",
                      ".ppt", ".pptx", ".odp",
                      ".xls", ".xlsx", ".ods", ".csv")


def office_to_pdf(files: Sequence[str], out_dir: str,
                  progress: Progress = _nop) -> List[str]:
    return convert(files, "pdf", out_dir, progress=progress)


def html_to_pdf(files: Sequence[str], out_dir: str,
                progress: Progress = _nop) -> List[str]:
    return convert(files, "pdf", out_dir, progress=progress)


# LibreOffice PDF export filter options for PDF/A versions.
_PDFA_FILTERS = {
    "PDF/A-1b": 'pdf:writer_pdf_Export:{"SelectPdfVersion":{"type":"long","value":"1"}}',
    "PDF/A-2b": 'pdf:writer_pdf_Export:{"SelectPdfVersion":{"type":"long","value":"2"}}',
    "PDF/A-3b": 'pdf:writer_pdf_Export:{"SelectPdfVersion":{"type":"long","value":"3"}}',
}


def pdf_to_pdfa(files: Sequence[str], out_dir: str, version: str = "PDF/A-2b",
                progress: Progress = _nop) -> List[str]:
    target = _PDFA_FILTERS.get(version, _PDFA_FILTERS["PDF/A-2b"])
    return convert(files, target, out_dir, progress=progress)


PDF_TO_OFFICE_TARGETS = {
    "docx": "docx:MS Word 2007 XML",
    "pptx": "pptx:Impress MS PowerPoint 2007 XML",
    "xlsx": "xlsx:Calc MS Excel 2007 XML",
}


def pdf_to_office(path: str, target: str, out_dir: str,
                  progress: Progress = _nop) -> List[str]:
    fmt = PDF_TO_OFFICE_TARGETS.get(target.lower())
    if fmt is None:
        raise ValueError(f"Unsupported target: {target}")
    return convert([path], fmt, out_dir, progress=progress)
