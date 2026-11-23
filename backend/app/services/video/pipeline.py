from __future__ import annotations

import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

from app.schemas.api import CaptureStatus
from app.services.video.devices import (
    frame_has_signal,
    frame_is_uniform_black,
    open_capture,
    open_capture_quick,
    parse_resolution,
)

# After the camera is open, keep retrying if frames stay unlocked this long (no HDMI lock).
CAMERA_BLACK_RETRY_SEC = 2.0
# Capture-card "No signal" OSDs are informative — reopen less often so we do not thrash EDID.
CAMERA_OSD_RETRY_SEC = 8.0

_NO_HDMI_WARNING = (
    "Capture card has no HDMI signal (dongle OSD / black field). "
    "Check tower power, HDMI cable/port, and that New Session selected the USB "
    "capture device — the phone-remote QR does not carry video."
)


SnapshotCallback = Callable[[np.ndarray, datetime, str], None]

# Preview/acquisition rate when not recording. Keeps CPU/USB load down so Windows
# HID (mouse/keyboard) stays responsive; recording uses requested_fps instead.
PREVIEW_FPS_CAP = 12
# Stop the capture thread when nothing is recording and no preview client has
# touched the pipeline recently (Recording page unmounted, session left idle).
PREVIEW_IDLE_TIMEOUT_SEC = 8.0


@dataclass
class PipelineConfig:
    source_type: str = "synthetic"
    device_id: Optional[str] = None
    resolution: str = "1280x720"
    requested_fps: int = 15
    snapshot_interval_sec: float = 3.0
    session_public_id: Optional[str] = None
    video_dir: Optional[Path] = None
    snapshots_dir: Optional[Path] = None
    thumbnails_dir: Optional[Path] = None
    preview_fps_cap: int = PREVIEW_FPS_CAP
    preview_idle_timeout_sec: float = PREVIEW_IDLE_TIMEOUT_SEC


@dataclass
class PipelineState:
    recording: bool = False
    started_at: Optional[float] = None
    stopped_at: Optional[float] = None
    frames_written: int = 0
    actual_fps: float = 0.0
    incoming_fps: float = 0.0
    snapshot_count: int = 0
    manual_snapshot_count: int = 0
    automatic_snapshot_count: int = 0
    snapshot_sequence: int = 0
    warning: Optional[str] = None
    error: Optional[str] = None
    connected: bool = False
    last_frame_ts: Optional[float] = None
    remote_connected: bool = False
    last_snapshots: list[dict] = field(default_factory=list)


class VideoPipeline:
    """Single shared acquisition loop distributing frames to preview, recorder, snapshots."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._config = PipelineConfig()
        self._state = PipelineState()
        self._latest_jpeg: Optional[bytes] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._preview_condition = threading.Condition(self._lock)
        self._writer: Optional[cv2.VideoWriter] = None
        self._temp_video_path: Optional[Path] = None
        self._final_video_path: Optional[Path] = None
        self._last_auto_snapshot_mono: float = 0.0
        self._snapshot_callback: Optional[SnapshotCallback] = None
        self._frame_times: deque[float] = deque(maxlen=60)
        self._record_frame_times: deque[float] = deque(maxlen=60)
        self._synthetic_t0 = time.monotonic()
        self._thread_started_at: float = 0.0
        self._last_preview_interest_mono: float = time.monotonic()

    def set_snapshot_callback(self, callback: SnapshotCallback) -> None:
        self._snapshot_callback = callback

    def touch_preview(self) -> None:
        """Mark that a preview client is still interested (keeps acquisition alive).

        Also restarts acquisition if idle-stop already exited — otherwise a poll that
        races the dying thread can leave the pipeline stopped until remount.
        """
        with self._lock:
            self._last_preview_interest_mono = time.monotonic()
            self._ensure_acquiring_unlocked()

    def _ensure_acquiring_unlocked(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._start_acquisition_unlocked()

    def configure(self, config: PipelineConfig) -> None:
        with self._lock:
            was_running = self._thread is not None and self._thread.is_alive()
            same_bind = (
                was_running
                and self._config.session_public_id == config.session_public_id
                and self._config.source_type == config.source_type
                and self._config.device_id == config.device_id
                and self._config.resolution == config.resolution
            )
            # Preview polls call configure repeatedly — never thrash the capture thread.
            if same_bind:
                self._config.snapshot_interval_sec = config.snapshot_interval_sec
                self._config.video_dir = config.video_dir or self._config.video_dir
                self._config.snapshots_dir = config.snapshots_dir or self._config.snapshots_dir
                self._config.thumbnails_dir = config.thumbnails_dir or self._config.thumbnails_dir
                self._config.preview_fps_cap = config.preview_fps_cap
                self._config.preview_idle_timeout_sec = config.preview_idle_timeout_sec
                self._last_preview_interest_mono = time.monotonic()
                return

            self._config = config
            self._last_preview_interest_mono = time.monotonic()
            if was_running:
                if not self._state.recording:
                    self._restart_acquisition_unlocked()
            else:
                self._start_acquisition_unlocked()

    def is_acquiring(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def update_snapshot_interval(self, interval_sec: float) -> None:
        with self._lock:
            self._config.snapshot_interval_sec = interval_sec

    def set_remote_connected(self, connected: bool) -> None:
        with self._lock:
            self._state.remote_connected = connected
            if connected:
                self._last_preview_interest_mono = time.monotonic()

    def start_recording(self) -> tuple[bool, str]:
        with self._lock:
            if self._state.recording:
                return False, "Already recording"
            if not self._config.video_dir:
                return False, "Session video directory not configured"
            # Preview must already be producing frames — do not block Start on camera health.
            self._last_preview_interest_mono = time.monotonic()
            if self._latest_frame is None and (not self._thread or not self._thread.is_alive()):
                self._start_acquisition_unlocked()
            width, height = parse_resolution(self._config.resolution)
            self._config.video_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            self._temp_video_path = self._config.video_dir / f"recording_{stamp}.avi"
            self._final_video_path = self._config.video_dir / f"recording_{stamp}.mp4"
            self._writer = self._open_video_writer(
                self._temp_video_path, float(self._config.requested_fps), width, height
            )
            if self._writer is None:
                self._state.error = "Failed to open video writer"
                return False, self._state.error

            self._state.recording = True
            self._state.started_at = time.monotonic()
            self._state.stopped_at = None
            self._state.frames_written = 0
            self._state.error = None
            # Keep any camera/synthetic warning — Start must not depend on a perfect capture.
            self._last_auto_snapshot_mono = time.monotonic()
            self._record_frame_times.clear()
            if not self._thread or not self._thread.is_alive():
                self._start_acquisition_unlocked()
            return True, "Recording started"

    def stop_recording(self) -> tuple[bool, str, Optional[Path]]:
        writer: Optional[cv2.VideoWriter] = None
        temp_path: Optional[Path] = None
        final_path: Optional[Path] = None
        with self._lock:
            if not self._state.recording:
                return False, "Not recording", None
            self._state.recording = False
            self._state.stopped_at = time.monotonic()
            self._last_preview_interest_mono = time.monotonic()
            writer = self._writer
            self._writer = None
            temp_path = self._temp_video_path
            final_path = self._final_video_path
        # Release / remux outside the lock so preview/status calls are not blocked.
        result = self._finalize_writer(writer, temp_path, final_path)
        return True, "Recording stopped", result

    def take_manual_snapshot(self) -> tuple[bool, str, Optional[dict]]:
        with self._lock:
            frame = None if self._latest_frame is None else self._latest_frame.copy()
            if frame is None:
                return False, "No frame available", None
        meta = self._save_snapshot(frame, "manual")
        if meta is None:
            return False, "Snapshot directories not configured", None
        return True, "Snapshot captured", meta

    def get_latest_jpeg(self) -> Optional[bytes]:
        with self._lock:
            self._last_preview_interest_mono = time.monotonic()
            return self._latest_jpeg

    def wait_for_jpeg(self, timeout: float = 1.0) -> Optional[bytes]:
        with self._preview_condition:
            self._last_preview_interest_mono = time.monotonic()
            # Restart if idle-stop already exited (preview poll after remount).
            self._ensure_acquiring_unlocked()
            if self._latest_jpeg is not None:
                return self._latest_jpeg
            self._preview_condition.wait(timeout=timeout)
            return self._latest_jpeg

    def capture_status(self) -> CaptureStatus:
        with self._lock:
            return CaptureStatus(
                connected=self._state.connected,
                device_id=self._config.device_id or self._config.source_type,
                device_name=self._config.source_type,
                source_type=self._config.source_type,
                incoming_fps=self._state.incoming_fps or None,
                error=self._state.error,
            )

    def recording_metrics(self) -> dict:
        with self._lock:
            elapsed = 0.0
            if self._state.started_at is not None:
                end = self._state.stopped_at or time.monotonic()
                elapsed = max(0.0, end - self._state.started_at)
            state = "idle"
            if self._config.session_public_id:
                state = "ready"
            if self._state.recording:
                # Keep "recording" even if a capture warning/error is present so the UI
                # can still Stop (error must not lock the session).
                state = "recording"
            elif self._state.stopped_at is not None and self._config.session_public_id:
                state = "stopped"
            elif self._state.error:
                state = "error"
            return {
                "session_public_id": self._config.session_public_id,
                "state": state,
                "elapsed_sec": elapsed,
                "requested_fps": self._config.requested_fps,
                "actual_fps": self._state.actual_fps or None,
                "incoming_fps": self._state.incoming_fps or None,
                "snapshot_interval_sec": self._config.snapshot_interval_sec,
                "snapshot_count": self._state.snapshot_count,
                "manual_snapshot_count": self._state.manual_snapshot_count,
                "automatic_snapshot_count": self._state.automatic_snapshot_count,
                "warning": self._state.warning,
                "error": self._state.error,
                "remote_connected": self._state.remote_connected,
                "last_snapshots": list(self._state.last_snapshots),
                "temp_video_path": str(self._temp_video_path) if self._temp_video_path else None,
                "final_video_path": str(self._final_video_path) if self._final_video_path else None,
                "frames_written": self._state.frames_written,
            }

    def shutdown(self) -> None:
        writer: Optional[cv2.VideoWriter] = None
        temp_path: Optional[Path] = None
        final_path: Optional[Path] = None
        with self._lock:
            if self._state.recording:
                self._state.recording = False
                writer = self._writer
                self._writer = None
                temp_path = self._temp_video_path
                final_path = self._final_video_path
            self._stop_event.set()
        if writer is not None or temp_path is not None:
            self._finalize_writer(writer, temp_path, final_path)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        with self._lock:
            self._thread = None

    def reset_session_counters(self) -> None:
        with self._lock:
            self._state.snapshot_count = 0
            self._state.manual_snapshot_count = 0
            self._state.automatic_snapshot_count = 0
            self._state.snapshot_sequence = 0
            self._state.last_snapshots.clear()
            self._state.started_at = None
            self._state.stopped_at = None
            self._state.frames_written = 0
            self._state.warning = None
            self._state.error = None
            self._state.remote_connected = False
            self._last_preview_interest_mono = time.monotonic()
            # Allow acquisition thread to be started again after shutdown/tests
            self._stop_event = threading.Event()

    # --- internals ---

    def _acquisition_interval_sec(self) -> float:
        """Frame period for the capture loop (preview-capped unless recording)."""
        requested = max(1, int(self._config.requested_fps))
        if self._state.recording:
            fps = float(requested)
        else:
            cap = max(1, int(self._config.preview_fps_cap))
            fps = float(min(requested, cap))
        return 1.0 / fps

    def _start_acquisition_unlocked(self) -> None:
        self._stop_event.clear()
        self._thread_started_at = time.monotonic()
        self._last_preview_interest_mono = time.monotonic()
        # Drop stale frames so callers wait for the new thread (not a prior session).
        self._latest_jpeg = None
        self._latest_frame = None
        self._state.connected = True
        self._thread = threading.Thread(target=self._run_loop, name="video-pipeline", daemon=True)
        self._thread.start()

    def _restart_acquisition_unlocked(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            # Release lock while joining
            self._lock.release()
            try:
                thread.join(timeout=3)
            finally:
                self._lock.acquire()
        self._start_acquisition_unlocked()

    def _open_video_writer(
        self, path: Path, fps: float, width: int, height: int
    ) -> Optional[cv2.VideoWriter]:
        for codec in ("MJPG", "XVID", "mp4v"):
            writer = cv2.VideoWriter(
                str(path),
                cv2.VideoWriter_fourcc(*codec),
                fps,
                (width, height),
            )
            if writer.isOpened():
                return writer
            writer.release()
        return None

    def _run_loop(self) -> None:
        """PR #9-style capture: open + read on the SAME thread.

        Opening DirectShow on a background thread and reading elsewhere breaks
        Windows capture (blank preview). Keep COM init + open + read together.
        """
        if sys.platform.startswith("win"):
            try:
                import ctypes

                ctypes.windll.ole32.CoInitializeEx(None, 0x0)  # COINIT_MULTITHREADED
                # Prefer HID responsiveness over capture throughput on clinic PCs.
                THREAD_PRIORITY_BELOW_NORMAL = -1
                ctypes.windll.kernel32.SetThreadPriority(
                    ctypes.windll.kernel32.GetCurrentThread(),
                    THREAD_PRIORITY_BELOW_NORMAL,
                )
            except Exception:  # noqa: BLE001
                pass

        cap: Optional[cv2.VideoCapture] = None
        # Always publish frames immediately (synthetic), then upgrade to camera on
        # THIS same thread. Never call the long open_capture() retry storm from the
        # live loop — that hung Windows DirectShow and left "Starting preview...".
        wanted_source = self._config.source_type
        source_type = "synthetic"
        device_id = self._config.device_id
        resolution = self._config.resolution
        width, height = parse_resolution(resolution)

        with self._lock:
            self._state.connected = True
            self._state.error = None
            if wanted_source == "camera":
                self._state.warning = "Opening capture device…"
            elif wanted_source == "file":
                self._state.warning = "Opening sample video…"
            else:
                self._state.warning = None

        next_frame_due = time.monotonic()
        last_record_write = 0.0
        # Publish at least one synthetic frame before the first camera open attempt
        # so a hung DirectShow open cannot leave the UI on "Starting preview...".
        next_camera_retry = time.monotonic() + 0.05
        frames_published = 0
        camera_black_since: Optional[float] = None
        idle_stopped = False

        try:
            while not self._stop_event.is_set():
                now = time.monotonic()
                with self._lock:
                    recording = self._state.recording
                    remote_connected = self._state.remote_connected
                    idle_timeout = max(1.0, float(self._config.preview_idle_timeout_sec))
                    last_interest = self._last_preview_interest_mono
                    interval = self._acquisition_interval_sec()

                if (
                    not recording
                    and not remote_connected
                    and (now - last_interest) >= idle_timeout
                ):
                    # Re-check under the lock: a preview poll may have touched interest
                    # after we sampled it. Exiting anyway would leave acquisition dead
                    # until the next remount/configure.
                    with self._lock:
                        still_idle = (
                            not self._state.recording
                            and not self._state.remote_connected
                            and (time.monotonic() - self._last_preview_interest_mono)
                            >= idle_timeout
                        )
                        if still_idle:
                            idle_stopped = True
                            break

                remaining = next_frame_due - now
                if remaining > 0:
                    time.sleep(remaining)
                    continue
                next_frame_due = now + interval

                frame = self._read_frame(cap, source_type, width, height)
                if frame is None:
                    # Immediate synthetic fallback — NEVER call open_capture() here.
                    if source_type == "camera":
                        if cap is not None:
                            try:
                                cap.release()
                            except Exception:  # noqa: BLE001
                                pass
                            cap = None
                        source_type = "synthetic"
                        camera_black_since = None
                        next_camera_retry = time.monotonic() + 1.5
                        with self._lock:
                            self._state.connected = True
                            self._state.warning = (
                                "Camera disconnected; using synthetic until it returns"
                            )
                        frame = self._read_frame(None, "synthetic", width, height)
                    else:
                        with self._lock:
                            self._state.connected = False
                            self._state.warning = "Capture device disconnected; retrying…"
                        time.sleep(0.05)
                        continue

                # Capture cards can keep delivering black or a "No signal" OSD until HDMI
                # locks. Treat both as unlocked. Show OSD chrome (diagnostic) but replace
                # pure black with synthetic; reopen after a streak.
                camera_frame_ok = False
                if source_type == "camera" and frame is not None and not frame_has_signal(frame):
                    blank = frame_is_uniform_black(frame)
                    if camera_black_since is None:
                        camera_black_since = time.monotonic()
                    retry_after = CAMERA_BLACK_RETRY_SEC if blank else CAMERA_OSD_RETRY_SEC
                    if time.monotonic() - camera_black_since >= retry_after:
                        if cap is not None:
                            try:
                                cap.release()
                            except Exception:  # noqa: BLE001
                                pass
                            cap = None
                        source_type = "synthetic"
                        camera_black_since = None
                        next_camera_retry = time.monotonic() + 0.5
                        with self._lock:
                            self._state.connected = True
                            self._state.warning = _NO_HDMI_WARNING
                        frame = self._read_frame(None, "synthetic", width, height)
                    else:
                        with self._lock:
                            self._state.warning = _NO_HDMI_WARNING
                        # Keep sparse OSD visible so the user can see the dongle status;
                        # hide empty black fields behind synthetic bars.
                        if blank:
                            frame = self._read_frame(None, "synthetic", width, height)
                elif source_type == "camera":
                    camera_black_since = None
                    camera_frame_ok = True

                if camera_frame_ok:
                    with self._lock:
                        if self._state.warning and (
                            "synthetic" in self._state.warning.lower()
                            or "waiting for camera" in self._state.warning.lower()
                            or "waiting for video signal" in self._state.warning.lower()
                            or "no hdmi signal" in self._state.warning.lower()
                            or "opening capture" in self._state.warning.lower()
                            or "not ready" in self._state.warning.lower()
                            or "disconnected" in self._state.warning.lower()
                        ):
                            self._state.warning = None

                ok, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                jpeg_bytes = jpeg.tobytes() if ok else None

                do_write = False
                do_snapshot = False
                writer: Optional[cv2.VideoWriter] = None
                requested_fps = 15
                with self._lock:
                    self._state.connected = True
                    self._latest_frame = frame
                    if jpeg_bytes is not None:
                        self._latest_jpeg = jpeg_bytes
                        self._preview_condition.notify_all()
                    self._frame_times.append(time.monotonic())
                    self._state.incoming_fps = self._calc_fps(self._frame_times)
                    self._state.last_frame_ts = time.monotonic()
                    frames_published += 1
                    requested_fps = max(1, int(self._config.requested_fps))

                    if self._state.recording and self._writer is not None:
                        record_interval = 1.0 / requested_fps
                        if time.monotonic() - last_record_write >= record_interval * 0.98:
                            do_write = True
                            writer = self._writer

                    if self._state.recording:
                        snap_interval = max(0.5, self._config.snapshot_interval_sec)
                        if time.monotonic() - self._last_auto_snapshot_mono >= snap_interval:
                            do_snapshot = True
                            self._last_auto_snapshot_mono = time.monotonic()

                if do_write and writer is not None:
                    resized = frame
                    if frame.shape[1] != width or frame.shape[0] != height:
                        resized = cv2.resize(frame, (width, height))
                    try:
                        writer.write(resized)
                    except Exception:  # noqa: BLE001
                        pass
                    else:
                        with self._lock:
                            if self._writer is writer:
                                self._state.frames_written += 1
                                self._record_frame_times.append(time.monotonic())
                                self._state.actual_fps = self._calc_fps(self._record_frame_times)
                                last_record_write = time.monotonic()
                                if (
                                    self._state.frames_written > requested_fps * 2
                                    and self._state.actual_fps
                                    and self._state.actual_fps < requested_fps * 0.7
                                ):
                                    self._state.warning = (
                                        f"Achieved ~{self._state.actual_fps:.1f} FPS; "
                                        f"requested {requested_fps} FPS"
                                    )

                if do_snapshot:
                    self._save_snapshot(frame, "automatic")

                # After preview is alive, try a single quick same-thread camera open.
                if (
                    frames_published >= 1
                    and wanted_source == "camera"
                    and source_type == "synthetic"
                    and time.monotonic() >= next_camera_retry
                ):
                    next_camera_retry = time.monotonic() + 4.0
                    try:
                        candidate = open_capture_quick(device_id, resolution)
                        probe = self._read_frame(candidate, "camera", width, height)
                        if probe is not None and frame_has_signal(probe):
                            if cap is not None:
                                try:
                                    cap.release()
                                except Exception:  # noqa: BLE001
                                    pass
                            cap = candidate
                            source_type = "camera"
                            camera_black_since = None
                            ok2, jpeg2 = cv2.imencode(
                                ".jpg", probe, [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                            )
                            with self._lock:
                                self._state.connected = True
                                self._state.error = None
                                self._state.warning = None
                                self._latest_frame = probe
                                if ok2:
                                    self._latest_jpeg = jpeg2.tobytes()
                                    self._preview_condition.notify_all()
                        elif probe is not None:
                            # Opened but still unlocked (black / capture OSD) — release and retry.
                            try:
                                candidate.release()
                            except Exception:  # noqa: BLE001
                                pass
                            next_camera_retry = time.monotonic() + 0.75
                            with self._lock:
                                self._state.warning = _NO_HDMI_WARNING
                        else:
                            try:
                                candidate.release()
                            except Exception:  # noqa: BLE001
                                pass
                            with self._lock:
                                self._state.warning = (
                                    "Camera not ready yet; showing synthetic until it opens"
                                )
                    except Exception as exc:  # noqa: BLE001
                        with self._lock:
                            self._state.warning = f"Waiting for camera ({exc})"
                elif (
                    frames_published >= 1
                    and wanted_source == "file"
                    and source_type == "synthetic"
                    and time.monotonic() >= next_camera_retry
                ):
                    next_camera_retry = time.monotonic() + 2.0
                    try:
                        candidate = open_capture("file", device_id, resolution)
                        cap = candidate
                        source_type = "file"
                        with self._lock:
                            self._state.warning = None
                    except Exception as exc:  # noqa: BLE001
                        with self._lock:
                            self._state.warning = f"Waiting for sample video ({exc})"

        finally:
            with self._lock:
                # Only the active acquisition thread may clear connected — a replaced
                # thread (join timeout / restart) must not clobber the new loop.
                if threading.current_thread() is self._thread:
                    self._state.connected = False
                    if idle_stopped:
                        # Drop stale frames so the next preview poll waits for a fresh
                        # start instead of flashing an old black/synthetic JPEG.
                        self._latest_jpeg = None
                        self._latest_frame = None
            if cap is not None:
                try:
                    cap.release()
                except Exception:  # noqa: BLE001
                    pass

    def _read_frame(
        self,
        cap: Optional[cv2.VideoCapture],
        source_type: str,
        width: int,
        height: int,
    ) -> Optional[np.ndarray]:
        if source_type == "synthetic":
            return self._synthetic_frame(width, height)
        if cap is None:
            return None
        ok, frame = cap.read()
        if not ok or frame is None:
            if source_type == "file":
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = cap.read()
                if not ok:
                    return None
            else:
                return None
        if frame.shape[1] != width or frame.shape[0] != height:
            frame = cv2.resize(frame, (width, height))
        return frame

    def _synthetic_frame(self, width: int, height: int) -> np.ndarray:
        t = time.monotonic() - self._synthetic_t0
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # Color bars
        colors = [
            (255, 255, 255),
            (255, 255, 0),
            (0, 255, 255),
            (0, 255, 0),
            (255, 0, 255),
            (255, 0, 0),
            (0, 0, 255),
        ]
        bar_w = width // len(colors)
        for i, color in enumerate(colors):
            frame[:, i * bar_w : (i + 1) * bar_w] = color
        # Moving reticle / endoscope-like circle
        cx = int((width / 2) + (width / 4) * np.sin(t * 1.3))
        cy = int((height / 2) + (height / 4) * np.cos(t * 0.9))
        radius = min(width, height) // 5
        overlay = frame.copy()
        cv2.circle(overlay, (cx, cy), radius, (40, 40, 40), -1)
        cv2.circle(overlay, (cx, cy), radius, (0, 220, 180), 3)
        cv2.line(overlay, (cx - radius, cy), (cx + radius, cy), (0, 220, 180), 1)
        cv2.line(overlay, (cx, cy - radius), (cx, cy + radius), (0, 220, 180), 1)
        frame = cv2.addWeighted(overlay, 0.85, frame, 0.15, 0)
        label = f"OPENSNAP SIM  {datetime.utcnow().strftime('%H:%M:%S')}"
        cv2.putText(frame, label, (24, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 3, cv2.LINE_AA)
        cv2.putText(frame, label, (24, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (240, 240, 240), 1, cv2.LINE_AA)
        return frame

    def _save_snapshot(self, frame: np.ndarray, capture_type: str) -> Optional[dict]:
        """Write snapshot JPEGs without holding the pipeline lock across disk I/O."""
        with self._lock:
            if not self._config.snapshots_dir or not self._config.thumbnails_dir:
                return None
            snapshots_dir = self._config.snapshots_dir
            thumbnails_dir = self._config.thumbnails_dir
            self._state.snapshot_sequence += 1
            seq = self._state.snapshot_sequence
            callback = self._snapshot_callback
        ts = datetime.utcnow()
        filename = f"snapshot_{seq:06d}.jpg"
        path = snapshots_dir / filename
        thumb_path = thumbnails_dir / filename
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        thumbnails_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        h, w = frame.shape[:2]
        scale = 320 / max(w, 1)
        thumb = cv2.resize(frame, (int(w * scale), int(h * scale)))
        cv2.imwrite(str(thumb_path), thumb, [int(cv2.IMWRITE_JPEG_QUALITY), 80])

        meta = {
            "sequence_number": seq,
            "file_path": str(path),
            "thumbnail_path": str(thumb_path),
            "capture_timestamp": ts,
            "capture_type": capture_type,
        }
        with self._lock:
            self._state.snapshot_count += 1
            if capture_type == "manual":
                self._state.manual_snapshot_count += 1
            else:
                self._state.automatic_snapshot_count += 1
            self._state.last_snapshots.append(meta)
            if len(self._state.last_snapshots) > 50:
                self._state.last_snapshots = self._state.last_snapshots[-50:]
        if callback:
            try:
                callback(frame, ts, capture_type)
            except Exception:  # noqa: BLE001
                pass
        return meta

    def _finalize_writer(
        self,
        writer: Optional[cv2.VideoWriter],
        temp_path: Optional[Path],
        final_path: Optional[Path],
    ) -> Optional[Path]:
        if writer is not None:
            try:
                writer.release()
            except Exception:  # noqa: BLE001
                pass
        if not temp_path or not temp_path.exists():
            return None
        # Prefer MP4 via ffmpeg remux/transcode; fall back to keeping AVI
        final = final_path or temp_path.with_suffix(".mp4")
        converted = self._transcode_to_mp4(temp_path, final)
        if converted:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            return final
        # Keep recoverable intermediate
        return temp_path

    @staticmethod
    def _transcode_to_mp4(src: Path, dst: Path) -> bool:
        import shutil
        import subprocess

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return False
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(dst),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=300, check=False)
            return result.returncode == 0 and dst.exists() and dst.stat().st_size > 0
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _calc_fps(times: deque[float]) -> float:
        if len(times) < 2:
            return 0.0
        span = times[-1] - times[0]
        if span <= 0:
            return 0.0
        return (len(times) - 1) / span


_pipeline: Optional[VideoPipeline] = None
_pipeline_lock = threading.Lock()


def get_video_pipeline() -> VideoPipeline:
    global _pipeline
    with _pipeline_lock:
        if _pipeline is None:
            _pipeline = VideoPipeline()
        return _pipeline
