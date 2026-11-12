from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.entities import AppSetting
from app.schemas.api import SettingsOut, SettingsUpdate


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
]


def _serialize(value: Any) -> str:
    return json.dumps(value)


def _deserialize(raw: str) -> Any:
    return json.loads(raw)


def get_all_settings(db: Session) -> SettingsOut:
    settings = get_settings()
    stored = {row.key: _deserialize(row.value) for row in db.query(AppSetting).all()}
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
        storage_path=str(settings.sessions_dir),
        pairing_token_ttl_seconds=int(
            stored.get("pairing_token_ttl_seconds", settings.pairing_token_ttl_seconds)
        ),
        data=stored,
    )


def update_settings(db: Session, payload: SettingsUpdate) -> SettingsOut:
    data = payload.model_dump(exclude_none=True)
    for key, value in data.items():
        row = db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
        if row is None:
            db.add(AppSetting(key=key, value=_serialize(value)))
        else:
            row.value = _serialize(value)
    db.commit()
    return get_all_settings(db)
