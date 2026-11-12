from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def bundle_root() -> Path:
    """Read-only resources shipped inside the app (UI, sample assets)."""
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # backend/app/paths.py -> repo root
    return Path(__file__).resolve().parents[2]


def app_root() -> Path:
    """Writable install / project root (next to the EXE when packaged)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def default_data_dir() -> Path:
    """Persistent clinical data (sessions, SQLite). Prefer LocalAppData on Windows EXE."""
    if is_frozen():
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "OpenSnap" / "data"
        return app_root() / "data"
    return Path(__file__).resolve().parents[2] / "data"


def frontend_dist_dir() -> Path:
    if is_frozen():
        return bundle_root() / "frontend" / "dist"
    return bundle_root() / "frontend" / "dist"


def backend_assets_dir() -> Path:
    if is_frozen():
        return bundle_root() / "backend" / "assets"
    return Path(__file__).resolve().parents[1] / "assets"
