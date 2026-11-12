# -*- mode: python ; coding: utf-8 -*-
# Build on Windows from repo root after frontend build:
#   cd backend
#   ..\.venv-packaging\Scripts\pyinstaller.exe ..\packaging\opensnap.spec

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

SPECDIR = Path(SPEC).resolve().parent
ROOT = SPECDIR.parent
BACKEND = ROOT / "backend"
FRONTEND_DIST = ROOT / "frontend" / "dist"
ASSETS = BACKEND / "assets"

if not FRONTEND_DIST.exists():
    raise SystemExit(
        f"Missing UI build at {FRONTEND_DIST}. Run: npm --prefix frontend ci && npm --prefix frontend run build"
    )

datas = [
    (str(FRONTEND_DIST), "frontend/dist"),
]
if ASSETS.exists():
    datas.append((str(ASSETS), "backend/assets"))

binaries = []
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "app.main",
    "app.desktop",
    "cv2",
]

for pkg in ("uvicorn", "reportlab", "cv2"):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception:
        pass

# Pillow / numpy data if needed
try:
    datas += collect_data_files("reportlab")
except Exception:
    pass

a = Analysis(
    [str(BACKEND / "opensnap_desktop.py")],
    pathex=[str(BACKEND)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OpenSnap",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # no terminal window; logs go to %LOCALAPPDATA%\OpenSnap\data\logs
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="OpenSnap",
)
