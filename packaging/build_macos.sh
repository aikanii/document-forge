#!/usr/bin/env bash
# ============================================================
#  Hephaestus — macOS app bundle build script
#  Requires: Xcode command line tools, Python 3.10+,
#  and (optionally) LibreOffice + Tesseract for full features.
# ============================================================
set -e
cd "$(dirname "$0")/.."

echo "[1/4] Checking python3 ..."
PYTHON="${PYTHON:-python3}"

echo "[2/4] Installing Python dependencies ..."
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r requirements.txt pyinstaller

echo "[3/4] Building the .icns icon (if missing) ..."
if [ ! -f assets/icon.icns ]; then
  iconutil -c icns assets/icon.iconset -o assets/icon.icns || \
    echo "  (iconutil unavailable — building without a custom .icns)"
fi

echo "[4/4] Building Hephaestus.app ..."
"$PYTHON" -m PyInstaller packaging/Hephaestus.spec --noconfirm

echo
echo " ============================================================"
echo "  BUILD COMPLETE"
echo "  Your app is at:  dist/Hephaestus.app"
echo "  (drag it into /Applications)"
echo " ============================================================"
