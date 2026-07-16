# PyInstaller spec for the standalone Windows GUI.
# Build ON Windows with:  packaging\build_windows.bat
# (or:  py -m PyInstaller packaging\vsm-gui.spec)
# Output: dist\vsm-gui.exe  (one file, no console window)

import os

block_cipher = None

here = os.path.dirname(os.path.abspath(SPECPATH if "SPECPATH" in dir() else __file__))
repo = os.path.dirname(here)
src = os.path.join(repo, "src")

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
