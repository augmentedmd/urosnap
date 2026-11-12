from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_desktop_auth
from app.schemas.api import CaptureDevice, CaptureStatus
from app.services.video.devices import list_capture_devices
from app.services.video.pipeline import get_video_pipeline

router = APIRouter(prefix="/api/capture", tags=["capture"], dependencies=[Depends(require_desktop_auth)])


@router.get("/devices", response_model=list[CaptureDevice])
def devices() -> list[CaptureDevice]:
    return list_capture_devices()


@router.get("/status", response_model=CaptureStatus)
def status() -> CaptureStatus:
    return get_video_pipeline().capture_status()
