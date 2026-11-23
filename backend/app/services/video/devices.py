from __future__ import annotations

import logging
import os
import sys
import time
from typing import Iterator, Optional

import cv2
import numpy as np

from app.config import get_settings
from app.schemas.api import CaptureDevice

logger = logging.getLogger(__name__)

# Quiet OpenCV's noisy "index out of range" spam while probing empty slots.
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
try:
    cv2.setLogLevel(0)
except Exception:  # noqa: BLE001
    pass

COMMON_RESOLUTIONS = ["640x480", "1280x720", "1920x1080"]
COMMON_FPS = [5, 10, 15, 24, 30, 60]

_device_cache: list[CaptureDevice] | None = None
_device_cache_at = 0.0
_DEVICE_CACHE_TTL_SEC = 30.0
# Last known camera rows — kept even when we skip probing during acquisition.
_last_cameras: list[CaptureDevice] = []
# Remember which backend successfully opened each camera index.
_index_backends: dict[int, int] = {}


def _windows_backends() -> list[tuple[int, str]]:
    """Preferred OpenCV backends on Windows for UVC / HDMI capture sticks.

    DirectShow first — matching the PR #9 build that successfully showed camera
    preview on the user's workstation.
    """
    backends: list[tuple[int, str]] = []
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


def _open_attempts(index: int, backend: int) -> Iterator[cv2.VideoCapture]:
    """Try both OpenCV open styles used on Windows, one handle at a time.

    Must be lazy: opening both forms at once leaves a second handle holding the
    device, after which DirectShow opens succeed but never deliver frames.
    """
    yield cv2.VideoCapture(index, backend)
    # Legacy combined form: VideoCapture(index + CAP_DSHOW)
    if backend not in (0, getattr(cv2, "CAP_ANY", 0)):
        yield cv2.VideoCapture(index + backend)


def frame_is_uniform_black(
    frame, *, max_mean: float = 6.0, max_std: float = 3.0
) -> bool:
    """True for a near-empty field with no capture-card OSD chrome."""
    if frame is None:
        return True
    try:
        sample = frame[::8, ::8]
        mean = float(np.mean(sample))
        std = float(np.std(sample))
    except Exception:  # noqa: BLE001
        return True
    return mean < max_mean and std < max_std


def frame_has_signal(
    frame,
    *,
    min_mean: float = 6.0,
    min_std: float = 3.0,
    max_dark_fraction: float = 0.90,
    dark_luma: float = 18.0,
) -> bool:
    """True when a frame is unlikely to be an unlocked / no-signal field.

    HDMI-to-USB capture sticks often deliver valid-looking black frames for a while
    after open until the input locks. Many sticks then switch to an on-screen display
    (QR code, "No signal, Waiting…", rx/tx counters) that bumps mean/std enough to
    look like "content" while remaining mostly black. Treating either as success
    leaves LivePreview stuck until the device is reopened or HDMI actually locks.
    """
    if frame is None:
        return False
    try:
        sample = frame[::8, ::8]
        mean = float(np.mean(sample))
        std = float(np.std(sample))
        # Per-pixel luma proxy (max channel) — OSD chrome is sparse on a black field.
        luma = sample.max(axis=-1) if sample.ndim == 3 else sample
        dark_fraction = float(np.mean(luma < dark_luma))
    except Exception:  # noqa: BLE001
        return False
    if dark_fraction >= max_dark_fraction:
        return False
    return mean >= min_mean or std >= min_std


def _warm_read(
    cap: cv2.VideoCapture,
    tries: int = 20,
    delay: float = 0.05,
    *,
    require_signal: bool = False,
):
    """DirectShow capture cards often return no frame for the first reads after open.

    When require_signal=True, keep reading past empty/black frames so we do not
    "lock" onto a no-signal black field (common on session start).
    """
    last = None
    for _ in range(tries):
        ok, frame = cap.read()
        if ok and frame is not None:
            last = frame
            if not require_signal or frame_has_signal(frame):
                return frame
        time.sleep(delay)
    if require_signal:
        return None
    return last


def _probe_camera(index: int, backend: int, backend_name: str) -> Optional[CaptureDevice]:
    for cap in _open_attempts(index, backend):
        try:
            if not cap.isOpened():
                cap.release()
                continue
            frame = _warm_read(cap, tries=10)
            if frame is None:
                cap.release()
                continue
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or frame.shape[1] or 640)
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or frame.shape[0] or 480)
            fps_raw = float(cap.get(cv2.CAP_PROP_FPS) or 0)
            fps = int(fps_raw) if fps_raw >= 1 else 30
            cap.release()
            _index_backends[index] = backend
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
            try:
                cap.release()
            except Exception:  # noqa: BLE001
                pass
    return None


def list_capture_devices(max_index: int = 8, *, force: bool = False) -> list[CaptureDevice]:
    """Enumerate synthetic/file sources and real OpenCV capture devices."""
    global _device_cache, _device_cache_at, _last_cameras
    now = time.monotonic()
    if (
        not force
        and _device_cache is not None
        and now - _device_cache_at < _DEVICE_CACHE_TTL_SEC
    ):
        return list(_device_cache)

    settings = get_settings()

    def _base_devices() -> list[CaptureDevice]:
        rows = [
            CaptureDevice(
                id="synthetic",
                name="Synthetic pattern (simulator)",
                source_type="synthetic",
                resolutions=COMMON_RESOLUTIONS,
                frame_rates=COMMON_FPS,
                available=True,
            ),
            CaptureDevice(
                id="file",
                name="Prerecorded test video",
                source_type="file",
                resolutions=COMMON_RESOLUTIONS,
                frame_rates=COMMON_FPS,
                available=settings.sample_video_path.exists(),
            ),
        ]
        return rows

    # Never steal the camera while acquisition owns it. Return cached / last-known
    # cameras so the UI does not falsely say "camera not detected".
    if not force:
        try:
            from app.services.video.pipeline import get_video_pipeline

            if get_video_pipeline().is_acquiring():
                if _device_cache is not None:
                    return list(_device_cache)
                return _base_devices() + list(_last_cameras)
        except Exception:  # noqa: BLE001
            pass

    devices: list[CaptureDevice] = _base_devices()

    seen_indexes: set[int] = set()
    consecutive_misses = 0
    for index in range(max_index):
        found = False
        for backend, backend_name in _default_backends():
            probed = _probe_camera(index, backend, backend_name)
            if probed is None:
                continue
            devices.append(probed)
            seen_indexes.add(index)
            found = True
            logger.info("Detected capture device index=%s via %s", index, backend_name)
            break
        if found:
            consecutive_misses = 0
        else:
            consecutive_misses += 1
            # Stop after two empty indexes — avoids DSHOW spam on unused slots.
            if consecutive_misses >= 2:
                break

    if seen_indexes:
        _last_cameras = [d for d in devices if d.source_type == "camera"]
    elif _last_cameras:
        # Probe failed (often because another handle still holds the device) —
        # keep showing the last known cameras as available for session setup.
        devices.extend(_last_cameras)
    elif sys.platform.startswith("win"):
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

    if source_type == "synthetic":
        return cv2.VideoCapture()

    if source_type == "file":
        path = str(settings.sample_video_path)
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise RuntimeError(f"Unable to open sample video at {path}")
        return cap

    index = 0
    if device_id and device_id.startswith("camera:"):
        index = int(device_id.split(":", 1)[1])
    elif device_id and device_id.isdigit():
        index = int(device_id)

    backends = list(_default_backends())
    preferred = _index_backends.get(index)
    if preferred is not None:
        preferred_name = next((n for b, n in backends if b == preferred), "Preferred")
        backends = [(preferred, preferred_name)] + [(b, n) for b, n in backends if b != preferred]

    last_error = "unknown"
    for attempt in range(2):
        for backend, backend_name in backends:
            for cap in _open_attempts(index, backend):
                if not cap.isOpened():
                    cap.release()
                    last_error = f"{backend_name} could not open index {index}"
                    continue
                # Prefer a non-black frame so we don't accept an unlocked HDMI input.
                if _warm_read(cap, tries=40, delay=0.05, require_signal=True) is None:
                    cap.release()
                    last_error = (
                        f"{backend_name} opened index {index} but produced no video signal"
                    )
                    continue
                _index_backends[index] = backend
                logger.info(
                    "Opened camera:%s with %s (attempt %s)", index, backend_name, attempt + 1
                )
                return cap
        time.sleep(0.35 * (attempt + 1))

    raise RuntimeError(
        f"Unable to open camera index {index} ({last_error}). "
        "On Windows: Settings → Privacy & security → Camera → allow desktop apps, "
        "confirm the USB capture device in Device Manager, and close other apps using it."
    )


def open_capture_quick(
    device_id: Optional[str],
    resolution: str,
) -> cv2.VideoCapture:
    """One-shot camera open for the live loop (no nested retry storms).

    Used for reconnect / upgrade so a hung MSMF/DirectShow read cannot stall
    the preview thread for seconds. Caller must invoke this on the acquisition thread.
    """
    index = 0
    if device_id and device_id.startswith("camera:"):
        index = int(device_id.split(":", 1)[1])
    elif device_id and device_id.isdigit():
        index = int(device_id)

    backends = list(_default_backends())
    preferred = _index_backends.get(index)
    if preferred is not None:
        preferred_name = next((n for b, n in backends if b == preferred), "Preferred")
        backends = [(preferred, preferred_name)] + [(b, n) for b, n in backends if b != preferred]
    # Real camera backends only; CAP_ANY just re-picks one of these.
    backends = [(b, n) for b, n in backends if n != "Auto"] or backends

    last_error = "unknown"
    for backend, backend_name in backends:
        for cap in _open_attempts(index, backend):
            if not cap.isOpened():
                cap.release()
                last_error = f"{backend_name} could not open index {index}"
                continue
            # Do not force a resolution: renegotiating format right after open can make
            # DirectShow stop delivering frames. The pipeline resizes frames instead.
            # Require non-black frames (~1.5s): capture cards often return black until
            # HDMI/SDI locks; accepting black makes session-start preview stay dark
            # until a later reopen (e.g. leave page → idle-stop → return).
            if _warm_read(cap, tries=30, delay=0.05, require_signal=True) is None:
                cap.release()
                last_error = (
                    f"{backend_name} opened index {index} but produced no video signal"
                )
                continue
            _index_backends[index] = backend
            logger.info("Quick-opened camera:%s with %s", index, backend_name)
            return cap
    raise RuntimeError(last_error)
