<div align="center">

<img src="assets/icon_128.png" alt="Hephaestus wax-seal logo" width="96"/>

# ⚒ Hephaestus
### *The Document Forge* — a private, offline PDF workshop

**Merge · Split · Compress · Convert · Sign · Protect · OCR · Edit — all on your own machine.**

[![Python](https://img.shields.io/badge/python-3.10%2B-7A1F1F?style=flat-square&logo=python&logoColor=white)]()
[![Platforms](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-A87F2C?style=flat-square)]()
[![License](https://img.shields.io/badge/license-MIT-3F6B35?style=flat-square)]()

*A full-featured desktop answer to ilovepdf.com — 22 tools, no uploads, no accounts, no limits.*

</div>

---

## What it does

| Workshop | Tools |
|---|---|
| **Compose & Arrange** | Merge PDF · Split PDF (ranges / per-page / chunks / extract) · Organize pages (drag-reorder, rotate, duplicate, delete thumbnails) · Rotate PDF · Page Numbers · Watermark (text or image, tiled or diagonal) |
| **Optimize & Restore** | Compress PDF (3 levels) · Repair PDF (salvage damaged files) · OCR PDF (scanned → searchable, 40+ languages) |
| **Convert to PDF** | Word → PDF · PowerPoint → PDF · Excel → PDF · JPG/PNG → PDF (page-size aware) · HTML → PDF |
| **Convert from PDF** | PDF → Word · PDF → PowerPoint · PDF → Excel · PDF → JPG/PNG (72–600 DPI) · PDF → PDF/A (1b/2b/3b archival) |
| **Secure & Sign** | Protect PDF (AES-256 + permission flags) · Unlock PDF · Sign PDF (draw, type or import a signature, stamp anywhere) |
| **Edit & Annotate** | Edit PDF — add styled text and images to any page with live preview |

**22 tools.** Everything runs locally; your documents never touch the internet.

---

## Running it from source

```bash
# 1. install Python deps
pip install -r requirements.txt

# 2. launch
python -m hephaestus          # or:  python run_hephaestus.py
```

Requirements: Python 3.10+, `tkinter` (ships with Python on Windows/macOS;
on Debian/Ubuntu: `sudo apt install python3-tk`).

### Optional engines (for the full ilovepdf feature parity)

| Engine | Needed for | Install |
|---|---|---|
| **LibreOffice** (headless) | Word/PPT/Excel ⇄ PDF, HTML → PDF, PDF/A | [libreoffice.org](https://www.libreoffice.org/download/download/) · `sudo apt install libreoffice` · `brew install --cask libreoffice` |
| **Tesseract** | OCR tool | [UB-Mannheim installer](https://github.com/UB-Mannheim/tesseract/wiki) (Win) · `brew install tesseract` · `sudo apt install tesseract-ocr` |
| **tkinterdnd2** | native drag & drop of files onto the window | `pip install tkinterdnd2` |

Hephaestus auto-detects these at startup (see **About & Diagnostics…**) and
shows friendly install guidance inside any tool that needs a missing engine.
All other tools work without them.

---

## Building an executable

One-click scripts are provided in `packaging/`:

| OS | Command | Result |
|---|---|---|
| **Windows** | double-click `packaging\build_windows.bat` | `dist\Hephaestus\Hephaestus.exe` |
| **macOS** | `./packaging/build_macos.sh` | `dist/Hephaestus.app` |
| **Linux** | `./packaging/build_linux.sh` | `dist/Hephaestus/Hephaestus` |

Each script installs dependencies + PyInstaller and compiles
`packaging/Hephaestus.spec` (windowed app, wax-seal icon, assets bundled).
The resulting folder is self-contained — zip it and share it.

> Tip: install LibreOffice and Tesseract on the target machine as well if you
> want the conversion/OCR tools there; everything else is fully bundled.

---

## The workshop tour

- **Home — “The Forge Floor”**: 22 parchment cards in six workshop aisles,
  with live search (`Seek a tool`). Escape always walks you back home.
- **Tool panels**: drop zone (click, drag from your OS with tkinterdnd2, or
  **Ctrl+V** a path), option forms with context-aware fields, output-folder
  choice, threaded progress with live status.
- **Organize PDF**: film-strip of page thumbnails rendered at high fidelity —
  drag to reorder, multi-select (Ctrl/Shift), rotate, duplicate, delete,
  reverse the whole deck.
- **Sign PDF**: draw with the mouse, type in serif/script style, or import a
  PNG; pick ink color and stamp size, click the page to place, save a
  signature-flattened PDF. Multiple placements per page allowed.
- **Edit PDF**: add text (6 font styles, 6 inks + custom color) and images
  (5–100 % page width) anywhere, with numbered overlays and an item ledger.
- **About & Diagnostics**: shows which optional engines are installed.

Typography is **Times New Roman** throughout (with metric-compatible serif
fallbacks — Liberation Serif / Nimbus Roman / Tinos — on systems without it),
on a parchment-and-oxblood archival palette with a hand-drawn wax-seal mark.

---

## Project layout

```
Hephaestus/
├── run_hephaestus.py          # launcher
├── hephaestus/
│   ├── app.py                 # main window, home grid, navigation, about
│   ├── theme.py               # parchment palette + Times New Roman fonts
│   ├── icons.py               # hand-drawn canvas icons + wax seal
│   ├── widgets.py             # scroll frames, cards, drop zone, file list…
│   ├── tools.py               # declarative registry of all 22 tools
│   ├── engine/
│   │   ├── pdf_ops.py         # merge/split/compress/rotate/watermark/…
│   │   ├── image_ops.py       # PDF ⇄ images
│   │   ├── ocr.py             # Tesseract bridge
│   │   └── office.py          # LibreOffice headless bridge (+ PDF/A)
│   └── views/
│       ├── tool_panel.py      # generic panel generated from ToolSpec
│       ├── organize_view.py   # thumbnail page manager
│       ├── sign_view.py       # signature pad + stamper
│       └── edit_view.py       # text/image annotator
├── packaging/                 # PyInstaller spec + 3 build scripts + icon gen
├── assets/                    # wax-seal icons (png/ico/iconset)
└── tests/                     # engine smoke tests
```

## Tests

```bash
python -m pytest tests -q        # or:  python tests/test_engine.py
```

## Notes & honesty corner

- *PDF → Word/PowerPoint/Excel* uses LibreOffice’s best-effort conversion
  (same class of engine every offline converter uses); layout fidelity depends
  on the source PDF.
- *Protect* writes AES-256 with owner permissions; *Unlock* only removes
  encryption when you supply the correct password — Hephaestus will never help
  crack someone else’s file.
- OCR quality follows Tesseract and the scan DPI you choose (300 recommended).

## License

MIT — forge away. ⚒
