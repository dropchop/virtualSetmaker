# PyInstaller spec for the standalone Windows GUI.
# Build ON Windows with:  packaging\build_windows.bat
# (or:  py -m PyInstaller packaging\vsm-gui.spec)
# Output: dist\vsm-gui.exe  (one file, no console window)

import os

block_cipher = None

# SPECPATH (set by PyInstaller) is already the directory holding this spec.
here = os.path.abspath(SPECPATH)
repo = os.path.dirname(here)
src = os.path.join(repo, "src")

if not os.path.isfile(os.path.join(src, "virtualsetmaker", "gui.py")):
    raise SystemExit("Cannot find src/virtualsetmaker/gui.py next to packaging/ (looked in %s)" % repo)

a = Analysis(
    [os.path.join(src, "virtualsetmaker", "gui.py")],
    pathex=[src],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="vsm-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # windowed app: no console window
    icon=None,
)
