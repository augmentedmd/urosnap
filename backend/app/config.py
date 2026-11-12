from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPENSNAP_", env_file=".env", extra="ignore")

    app_name: str = "OpenSnap"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Storage
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    storage_subdir: str = "opensnap_sessions"
    database_name: str = "opensnap.db"

    # Practice letterhead defaults (verify before clinical use)
    practice_name: str = "Mount Sinai Doctors – Long Island"
    practice_address_line1: str = "5 Cuba Hill Road"
    practice_address_line2: str = "Greenlawn, NY 11740"
    practice_phone: str = "(631) 628-5000"

    # Recording defaults
    default_fps: int = 15
    default_snapshot_interval_sec: float = 3.0
    default_images_per_page: int = 4
    default_resolution: str = "1280x720"
    default_capture_source: str = "synthetic"  # synthetic | file | camera
    sample_video_path: Path = Path(__file__).resolve().parents[1] / "assets" / "sample_video.mp4"

    # Pairing
    pairing_token_ttl_seconds: int = 900  # unused link expiry
    pairing_session_ttl_seconds: int = 14400  # active remote window
    desktop_api_token: str = "local-desktop-dev-token"

    # Disk warnings (bytes free)
    low_disk_warning_bytes: int = 5 * 1024 * 1024 * 1024  # 5 GiB

    @property
    def sessions_dir(self) -> Path:
        return self.data_dir / self.storage_subdir

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / self.database_name}"

    @property
    def database_path(self) -> Path:
        return self.data_dir / self.database_name


@lru_cache
def get_settings() -> Settings:
    return Settings()
