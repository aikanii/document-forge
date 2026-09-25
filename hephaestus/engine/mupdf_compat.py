"""Compatibility shim: PyMuPDF renamed its import from `fitz` to `pymupdf`.

Supports both so Hephaestus works with old and new PyMuPDF installs.
"""

try:
    import pymupdf as fitz  # PyMuPDF >= 1.24
except ImportError:  # pragma: no cover - fallback for older installs
    import fitz  # type: ignore

__all__ = ["fitz"]
