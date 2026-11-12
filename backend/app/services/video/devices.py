from __future__ import annotations

from typing import Optional

import cv2

from app.config import get_settings
from app.schemas.api import CaptureDevice


COMMON_RESOLUTIONS = ["640x480", "1280x720", "1920x1080"]
COMMON_FPS = [5, 10, 15, 24, 30, 60]


def list_capture_devices(max_index: int = 6) -> list[CaptureDevice]:
    """Enumerate synthetic/file sources and OpenCV camera indexes."""
    settings = get_settings()
    devices: list[CaptureDevice] = [
        CaptureDevice(
            id="synthetic",
            name="Synthetic pattern (simulator)",
            source_type="synthetic",
            resolutions=COMMON_RESOLUTIONS,
            frame_rates=COMMON_FPS,
            available=True,
        )
    ]

    sample = settings.sample_video_path
    devices.append(
        CaptureDevice(
            id="file",
            name="Prerecorded test video",
            source_type="file",
            resolutions=COMMON_RESOLUTIONS,
            frame_rates=COMMON_FPS,
            available=sample.exists(),
        )
    )

    for index in range(max_index):
        cap = cv2.VideoCapture(index)
        try:
            if not cap.isOpened():
                continue
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
            fps = int(cap.get(cv2.CAP_PROP_FPS) or 30) or 30
            name = f"Camera {index}"
            backend = cap.getBackendName() if hasattr(cap, "getBackendName") else "OpenCV"
            devices.append(
                CaptureDevice(
                    id=f"camera:{index}",
                    name=f"{name} ({backend})",
                    index=index,
                    source_type="camera",
                    resolutions=sorted(
                        set(COMMON_RESOLUTIONS + [f"{width}x{height}"]),
                        key=lambda s: int(s.split("x")[0]) * int(s.split("x")[1]),
                    ),
                    frame_rates=sorted(set(COMMON_FPS + ([fps] if fps in COMMON_FPS else []))),
                    available=True,
                )
            )
        finally:
            cap.release()

    return devices


def parse_resolution(resolution: str) -> tuple[int, int]:
    w, h = resolution.lower().split("x")
    return int(w), int(h)


def open_capture(
    source_type: str,
    device_id: Optional[str],
    resolution: str,
) -> cv2.VideoCapture:
    settings = get_settings()
    width, height = parse_resolution(resolution)

    if source_type == "synthetic":
        # Synthetic frames are generated in the pipeline; return a dummy closed capture.
        return cv2.VideoCapture()

    if source_type == "file":
        path = str(settings.sample_video_path)
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise RuntimeError(f"Unable to open sample video at {path}")
        return cap

    # camera
    index = 0
    if device_id and device_id.startswith("camera:"):
        index = int(device_id.split(":", 1)[1])
    elif device_id and device_id.isdigit():
        index = int(device_id)

    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open camera index {index}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return cap
