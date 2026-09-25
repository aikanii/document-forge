#!/usr/bin/env bash
# ============================================================
#  Hephaestus — Linux executable build script
#  Requires: python3, tkinter (python3-tk), python3-pip
# ============================================================
set -e
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"

echo "[1/3] Installing Python dependencies ..."
"$PYTHON" -m pip install --user -r requirements.txt pyinstaller || \
  "$PYTHON" -m pip install -r requirements.txt pyinstaller

echo "[2/3] Verifying tkinter is present ..."
"$PYTHON" -c "import tkinter" || {
  echo "tkinter missing — install it first, e.g.: sudo apt install python3-tk"
  exit 1
}

echo "[3/3] Building the Hephaestus executable ..."
"$PYTHON" -m PyInstaller packaging/Hephaestus.spec --noconfirm

echo
echo " ============================================================"
echo "  BUILD COMPLETE"
echo "  Run it with:  dist/Hephaestus/Hephaestus"
echo " ============================================================"
