from __future__ import annotations

import logging
import sys
import time
from typing import Optional

import cv2

from app.config import get_settings
from app.schemas.api import CaptureDevice

logger = logging.getLogger(__name__)

COMMON_RESOLUTIONS = ["640x480", "1280x720", "1920x1080"]
COMMON_FPS = [5, 10, 15, 24, 30, 60]

_device_cache: list[CaptureDevice] | None = None
_device_cache_at = 0.0
_DEVICE_CACHE_TTL_SEC = 15.0


def _windows_backends() -> list[tuple[int, str]]:
    """Preferred OpenCV backends on Windows for UVC / HDMI capture sticks."""
    backends: list[tuple[int, str]] = []
    # DirectShow is the most reliable for USB capture devices on Windows.
    if hasattr(cv2, "CAP_DSHOW"):
        backends.append((cv2.CAP_DSHOW, "DirectShow"))
    if hasattr(cv2, "CAP_MSMF"):
        backends.append((cv2.CAP_MSMF, "MediaFoundation"))
    backends.append((cv2.CAP_ANY, "Auto"))
    return backends


def _default_backends() -> list[tuple[int, str]]:
    if sys.platform.startswith("win"):
        return _windows_backends()
    return [(cv2.CAP_ANY, "Auto")]


def _probe_camera(index: int, backend: int, backend_name: str) -> Optional[CaptureDevice]:
    cap = cv2.VideoCapture(index, backend)
    try:
        if not cap.isOpened():
            return None
        # Require at least one readable frame — isOpened() alone is often a false positive.
        ok, frame = cap.read()
        if not ok or frame is None:
            return None
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or frame.shape[1] or 640)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or frame.shape[0] or 480)
        fps_raw = float(cap.get(cv2.CAP_PROP_FPS) or 0)
        fps = int(fps_raw) if fps_raw >= 1 else 30
        return CaptureDevice(
            id=f"camera:{index}",
            name=f"Capture device {index} ({backend_name})",
            index=index,
            source_type="camera",
            resolutions=sorted(
                set(COMMON_RESOLUTIONS + [f"{width}x{height}"]),
                key=lambda s: int(s.split("x")[0]) * int(s.split("x")[1]),
            ),
            frame_rates=sorted(set(COMMON_FPS + ([fps] if fps in COMMON_FPS else [fps]))),
            available=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Camera probe failed index=%s backend=%s: %s", index, backend_name, exc)
        return None
    finally:
        cap.release()


def list_capture_devices(max_index: int = 10, *, force: bool = False) -> list[CaptureDevice]:
    """Enumerate synthetic/file sources and real OpenCV capture devices."""
    global _device_cache, _device_cache_at
    now = time.monotonic()
    if (
        not force
        and _device_cache is not None
        and now - _device_cache_at < _DEVICE_CACHE_TTL_SEC
    ):
        return list(_device_cache)

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

    seen_indexes: set[int] = set()
    for index in range(max_index):
        for backend, backend_name in _default_backends():
            if index in seen_indexes:
                break
            probed = _probe_camera(index, backend, backend_name)
            if probed is None:
                continue
            devices.append(probed)
            seen_indexes.add(index)
            logger.info("Detected capture device index=%s via %s", index, backend_name)
            break

    if not seen_indexes and sys.platform.startswith("win"):
        logger.warning(
            "No cameras detected. Check Windows Settings → Privacy → Camera "
            "(allow desktop apps), Device Manager, and that no other app has exclusive access."
        )

    _device_cache = list(devices)
    _device_cache_at = now
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

    last_error = "unknown"
    for backend, backend_name in _default_backends():
        cap = cv2.VideoCapture(index, backend)
        if not cap.isOpened():
            cap.release()
            last_error = f"{backend_name} could not open index {index}"
            continue
        ok, _frame = cap.read()
        if not ok:
            cap.release()
            last_error = f"{backend_name} opened index {index} but produced no frames"
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        logger.info("Opened camera:%s with %s", index, backend_name)
        return cap

    raise RuntimeError(
        f"Unable to open camera index {index} ({last_error}). "
        "On Windows: Settings → Privacy & security → Camera → allow desktop apps, "
        "confirm the USB capture device in Device Manager, and close other apps using it."
    )
