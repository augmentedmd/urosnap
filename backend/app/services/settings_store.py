from __future__ import annotations

import json
import os
import string
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.entities import AppSetting
from app.schemas.api import SettingsOut, SettingsUpdate, StorageBrowseOut


SETTING_KEYS = [
    "practice_name",
    "practice_address_line1",
    "practice_address_line2",
    "practice_phone",
    "default_fps",
    "default_snapshot_interval_sec",
    "default_images_per_page",
    "default_resolution",
    "default_capture_source",
    "preferred_physician",
    "preferred_procedure_type",
    "preferred_capture_device_id",
    "pairing_token_ttl_seconds",
    "storage_path",
]


def _serialize(value: Any) -> str:
    return json.dumps(value)


def _deserialize(raw: str) -> Any:
    return json.loads(raw)


def _stored_map(db: Session) -> dict[str, Any]:
    return {row.key: _deserialize(row.value) for row in db.query(AppSetting).all()}


def get_sessions_dir(db: Session | None = None) -> Path:
    """Resolve the session media root (folder picker override or default)."""
    settings = get_settings()
    if db is None:
        from app.database import SessionLocal

        local = SessionLocal()
        try:
            return get_sessions_dir(local)
        finally:
            local.close()
    stored = _stored_map(db)
    override = stored.get("storage_path")
    if override:
        path = Path(str(override)).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path
    settings.sessions_dir.mkdir(parents=True, exist_ok=True)
    return settings.sessions_dir


def get_all_settings(db: Session) -> SettingsOut:
    settings = get_settings()
    stored = _stored_map(db)
    return SettingsOut(
        practice_name=stored.get("practice_name", settings.practice_name),
        practice_address_line1=stored.get("practice_address_line1", settings.practice_address_line1),
        practice_address_line2=stored.get("practice_address_line2", settings.practice_address_line2),
        practice_phone=stored.get("practice_phone", settings.practice_phone),
        default_fps=int(stored.get("default_fps", settings.default_fps)),
        default_snapshot_interval_sec=float(
            stored.get("default_snapshot_interval_sec", settings.default_snapshot_interval_sec)
        ),
        default_images_per_page=int(
            stored.get("default_images_per_page", settings.default_images_per_page)
        ),
        default_resolution=stored.get("default_resolution", settings.default_resolution),
        default_capture_source=stored.get("default_capture_source", settings.default_capture_source),
        preferred_physician=str(stored.get("preferred_physician", "")),
        preferred_procedure_type=str(stored.get("preferred_procedure_type", "")),
        preferred_capture_device_id=str(stored.get("preferred_capture_device_id", "")),
        storage_path=str(get_sessions_dir(db)),
        pairing_token_ttl_seconds=int(
            stored.get("pairing_token_ttl_seconds", settings.pairing_token_ttl_seconds)
        ),
        data=stored,
    )


def update_settings(db: Session, payload: SettingsUpdate) -> SettingsOut:
    data = payload.model_dump(exclude_none=True)
    if "storage_path" in data:
        path = Path(str(data["storage_path"])).expanduser().resolve()
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError(f"Cannot use storage folder: {exc}") from exc
        if not os.access(path, os.W_OK):
            raise ValueError(f"Storage folder is not writable: {path}")
        data["storage_path"] = str(path)
    for key, value in data.items():
        row = db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
        if row is None:
            db.add(AppSetting(key=key, value=_serialize(value)))
        else:
            row.value = _serialize(value)
    db.commit()
    return get_all_settings(db)


def _list_windows_drives() -> list[str]:
    drives: list[str] = []
    for letter in string.ascii_uppercase:
        root = Path(f"{letter}:/")
        if root.exists():
            drives.append(str(root.resolve()))
    return drives


def browse_storage(path: Optional[str] = None) -> StorageBrowseOut:
    """List directories on the local workstation for the Settings folder picker."""
    settings = get_settings()
    if path:
        current = Path(path).expanduser()
    else:
        current = settings.sessions_dir.parent if settings.sessions_dir.parent.exists() else Path.cwd()

    if not current.exists():
        parent = str(current.parent) if current.parent != current else None
        return StorageBrowseOut(
            current=str(current),
            parent=parent,
            directories=[],
            drives=_list_windows_drives() if os.name == "nt" else [],
            writable=False,
            exists=False,
        )

    current = current.resolve()
    if not current.is_dir():
        current = current.parent

    directories: list[str] = []
    try:
        for entry in sorted(current.iterdir(), key=lambda p: p.name.lower()):
            if entry.is_dir() and not entry.name.startswith("."):
                directories.append(str(entry))
    except OSError:
        directories = []

    parent = str(current.parent) if current.parent != current else None
    writable = os.access(current, os.W_OK)
    return StorageBrowseOut(
        current=str(current),
        parent=parent,
        directories=directories,
        drives=_list_windows_drives() if os.name == "nt" else [],
        writable=writable,
        exists=True,
    )
