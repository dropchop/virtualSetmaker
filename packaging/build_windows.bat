@echo off
rem ============================================================
rem  virtualSetmaker - one-click Windows build
rem  Produces a standalone dist\vsm-gui.exe (no Python needed to run it).
rem  Requires: Python 3.9+ installed from python.org (with tcl/tk).
rem  Run this from anywhere; it works out of the repo root.
rem ============================================================
setlocal
cd /d "%~dp0.."

echo.
echo [1/3] Checking Python...
py -3 --version || (
    echo ERROR: Python 3 not found. Install it from https://www.python.org/downloads/
    echo        and make sure "py" launcher + tcl/tk are included.
    pause & exit /b 1
)

echo.
echo [2/3] Installing PyInstaller...
py -3 -m pip install --upgrade pyinstaller || (pause & exit /b 1)

echo.
echo [3/3] Building vsm-gui.exe ...
py -3 -m PyInstaller --noconfirm --clean packaging\vsm-gui.spec || (pause & exit /b 1)

echo.
echo ============================================================
echo  Done! Your app is at:  %cd%\dist\vsm-gui.exe
echo  Double-click it to open the exporter.
echo ============================================================
pause
