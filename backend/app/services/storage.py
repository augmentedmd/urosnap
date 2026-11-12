from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings


def generate_session_public_id() -> str:
    return secrets.token_hex(4)


def session_dir_name(public_id: str, when: datetime | None = None) -> str:
    when = when or datetime.utcnow()
    return f"session_{when.strftime('%Y%m%d')}_{public_id}"


class StorageManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = self.settings.sessions_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def create_session_tree(self, public_id: str) -> Path:
        path = self.root / session_dir_name(public_id)
        for sub in ("video", "snapshots", "thumbnails", "reports", "metadata"):
            (path / sub).mkdir(parents=True, exist_ok=True)
        return path

    def write_metadata(self, session_path: Path, data: dict[str, Any]) -> Path:
        meta_path = session_path / "metadata" / "session.json"
        tmp = meta_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        tmp.replace(meta_path)
        return meta_path

    @staticmethod
    def sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def disk_usage(path: Path) -> tuple[int, int]:
        import shutil

        usage = shutil.disk_usage(path)
        return usage.free, usage.total
