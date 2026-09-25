@echo off
REM ============================================================
REM  Hephaestus — Windows executable build script
REM  Requires: Python 3.10+ with pip, and (optionally) LibreOffice
REM  and Tesseract installed for the full feature set.
REM ============================================================
setlocal
cd /d "%~dp0\.."

echo [1/3] Installing Python dependencies...
py -3 -m pip install --upgrade pip
py -3 -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo [2/3] Installing PyInstaller...
py -3 -m pip install pyinstaller
if errorlevel 1 goto :fail

echo [3/3] Building Hephaestus.exe ...
py -3 -m PyInstaller packaging\Hephaestus.spec --noconfirm
if errorlevel 1 goto :fail

echo.
echo  ============================================================
echo   BUILD COMPLETE
echo   Your app is in:  dist\Hephaestus\Hephaestus.exe
echo   Copy the whole dist\Hephaestus folder anywhere you like.
echo  ============================================================
pause
exit /b 0

:fail
echo.
echo  BUILD FAILED — see the messages above.
pause
exit /b 1
