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


def _frontend_dist_candidates() -> list[Path]:
    """Possible UI locations: PyInstaller _MEIPASS, beside EXE, and repo checkout."""
    candidates: list[Path] = []
    if is_frozen():
        meipass = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend(
            [
                meipass / "frontend" / "dist",
                exe_dir / "frontend" / "dist",
                exe_dir / "_internal" / "frontend" / "dist",
            ]
        )
    else:
        candidates.append(Path(__file__).resolve().parents[2] / "frontend" / "dist")
    # De-dupe while preserving order
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        resolved = path.resolve() if path.exists() else path
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def frontend_dist_dir() -> Path:
    """Directory with Vite `index.html` + `assets/`. Prefers a candidate that has index.html."""
    candidates = _frontend_dist_candidates()
    for path in candidates:
        if (path / "index.html").is_file():
            return path
    return candidates[0] if candidates else Path("frontend") / "dist"


def backend_assets_dir() -> Path:
    if is_frozen():
        return bundle_root() / "backend" / "assets"
    return Path(__file__).resolve().parents[1] / "assets"
