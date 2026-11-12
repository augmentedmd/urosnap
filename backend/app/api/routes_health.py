from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import __version__
from app.config import get_settings
from app.database import get_db
from app.schemas.api import HealthOut
from app.services.storage import StorageManager
from app.services.video.devices import list_capture_devices
from app.services.video.pipeline import get_video_pipeline

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    settings = get_settings()
    free, total = StorageManager().disk_usage(settings.data_dir)
    pipeline = get_video_pipeline()
    metrics = pipeline.recording_metrics()
    cameras = [d for d in list_capture_devices() if d.source_type == "camera" and d.available]
    capture = pipeline.capture_status()
    active_session = metrics.get("session_public_id")

    warnings: list[str] = []
    if free < settings.low_disk_warning_bytes:
        warnings.append("Low disk space")
    # Only warn about live capture when a session actually needs the device.
    if active_session and not capture.connected:
        warnings.append("Capture device not connected for the active session")
    if not cameras and not pipeline.is_acquiring():
        warnings.append(
            "No USB/webcam capture device detected. New sessions will use synthetic video until "
            "a camera is available. On Windows: Settings → Privacy → Camera → allow desktop apps; "
            "check Device Manager; close Zoom/Teams/other apps that may lock the device; then refresh."
        )
    if metrics.get("warning"):
        warnings.append(str(metrics["warning"]))
    if metrics.get("error"):
        warnings.append(str(metrics["error"]))

    return HealthOut(
        status="ok",
        service=settings.app_name,
        version=__version__,
        disk_free_bytes=free,
        disk_total_bytes=total,
        low_disk=free < settings.low_disk_warning_bytes,
        active_session_id=active_session,
        recording_state=str(metrics.get("state") or "idle"),
        capture=capture,
        cameras_detected=len(cameras),
        camera_names=[d.name for d in cameras],
        warnings=warnings,
    )
