from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

from app.config import get_settings
from app.schemas.api import CaptureStatus
from app.services.video.devices import open_capture, parse_resolution


SnapshotCallback = Callable[[np.ndarray, datetime, str], None]


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

    def set_snapshot_callback(self, callback: SnapshotCallback) -> None:
        self._snapshot_callback = callback

    def configure(self, config: PipelineConfig) -> None:
        with self._lock:
            was_running = self._thread is not None and self._thread.is_alive()
            self._config = config
            if was_running:
                # Restart acquisition with new source if not recording
                if not self._state.recording:
                    self._restart_acquisition_unlocked()
            else:
                self._start_acquisition_unlocked()

    def update_snapshot_interval(self, interval_sec: float) -> None:
        with self._lock:
            self._config.snapshot_interval_sec = interval_sec

    def set_remote_connected(self, connected: bool) -> None:
        with self._lock:
            self._state.remote_connected = connected

    def start_recording(self) -> tuple[bool, str]:
        with self._lock:
            if self._state.recording:
                return False, "Already recording"
            if not self._config.video_dir:
                return False, "Session video directory not configured"
            width, height = parse_resolution(self._config.resolution)
            self._config.video_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            self._temp_video_path = self._config.video_dir / f"recording_{stamp}.avi"
            self._final_video_path = self._config.video_dir / f"recording_{stamp}.mp4"
            fourcc = cv2.VideoWriter_fourcc(*"MJPG")
            self._writer = cv2.VideoWriter(
                str(self._temp_video_path),
                fourcc,
                float(self._config.requested_fps),
                (width, height),
            )
            if not self._writer.isOpened():
                self._writer = None
                self._state.error = "Failed to open video writer"
                return False, self._state.error

            self._state.recording = True
            self._state.started_at = time.monotonic()
            self._state.stopped_at = None
            self._state.frames_written = 0
            self._state.error = None
            self._state.warning = None
            self._last_auto_snapshot_mono = time.monotonic()
            self._record_frame_times.clear()
            if not self._thread or not self._thread.is_alive():
                self._start_acquisition_unlocked()
            return True, "Recording started"

    def stop_recording(self) -> tuple[bool, str, Optional[Path]]:
        with self._lock:
            if not self._state.recording:
                return False, "Not recording", None
            self._state.recording = False
            self._state.stopped_at = time.monotonic()
            final_path = self._finalize_writer_unlocked()
            return True, "Recording stopped", final_path

    def take_manual_snapshot(self) -> tuple[bool, str, Optional[dict]]:
        with self._lock:
            frame = self._latest_frame
            if frame is None:
                return False, "No frame available", None
            meta = self._save_snapshot_unlocked(frame, "manual")
            return True, "Snapshot captured", meta

    def get_latest_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._latest_jpeg

    def wait_for_jpeg(self, timeout: float = 1.0) -> Optional[bytes]:
        with self._preview_condition:
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
                state = "recording"
            elif self._state.stopped_at is not None and self._config.session_public_id:
                state = "stopped"
            if self._state.error:
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
        with self._lock:
            if self._state.recording:
                self._state.recording = False
                self._finalize_writer_unlocked()
            self._stop_event.set()
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
            # Allow acquisition thread to be started again after shutdown/tests
            self._stop_event = threading.Event()

    # --- internals ---

    def _start_acquisition_unlocked(self) -> None:
        self._stop_event.clear()
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

    def _run_loop(self) -> None:
        settings = get_settings()
        cap: Optional[cv2.VideoCapture] = None
        source_type = self._config.source_type
        try:
            if source_type != "synthetic":
                try:
                    cap = open_capture(source_type, self._config.device_id, self._config.resolution)
                    with self._lock:
                        self._state.connected = True
                        self._state.error = None
                except Exception as exc:  # noqa: BLE001
                    with self._lock:
                        self._state.connected = False
                        self._state.error = str(exc)
                        self._state.warning = "Falling back to synthetic video"
                    source_type = "synthetic"
                    cap = None
            else:
                with self._lock:
                    self._state.connected = True

            width, height = parse_resolution(self._config.resolution)
            next_frame_due = time.monotonic()
            last_record_write = 0.0

            while not self._stop_event.is_set():
                now = time.monotonic()
                # Target ~30 FPS acquisition for preview; recording gated separately
                if now < next_frame_due:
                    time.sleep(min(0.005, next_frame_due - now))
                    continue
                next_frame_due = now + (1.0 / 30.0)

                frame = self._read_frame(cap, source_type, width, height)
                if frame is None:
                    with self._lock:
                        self._state.connected = False
                        self._state.error = "Capture device disconnected"
                    time.sleep(0.2)
                    # Attempt reconnect for cameras
                    if source_type == "camera" and cap is not None:
                        cap.release()
                        try:
                            cap = open_capture(source_type, self._config.device_id, self._config.resolution)
                            with self._lock:
                                self._state.connected = True
                                self._state.error = None
                        except Exception:  # noqa: BLE001
                            pass
                    continue

                ok, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                with self._lock:
                    self._state.connected = True
                    self._latest_frame = frame
                    if ok:
                        self._latest_jpeg = jpeg.tobytes()
                        self._preview_condition.notify_all()
                    self._frame_times.append(time.monotonic())
                    self._state.incoming_fps = self._calc_fps(self._frame_times)
                    self._state.last_frame_ts = time.monotonic()

                    # Recording write with FPS gating
                    if self._state.recording and self._writer is not None:
                        interval = 1.0 / max(1, self._config.requested_fps)
                        if time.monotonic() - last_record_write >= interval * 0.98:
                            resized = frame
                            if frame.shape[1] != width or frame.shape[0] != height:
                                resized = cv2.resize(frame, (width, height))
                            self._writer.write(resized)
                            self._state.frames_written += 1
                            self._record_frame_times.append(time.monotonic())
                            self._state.actual_fps = self._calc_fps(self._record_frame_times)
                            last_record_write = time.monotonic()
                            # Warn if actual FPS substantially below requested
                            if (
                                self._state.frames_written > self._config.requested_fps * 2
                                and self._state.actual_fps
                                and self._state.actual_fps < self._config.requested_fps * 0.7
                            ):
                                self._state.warning = (
                                    f"Achieved ~{self._state.actual_fps:.1f} FPS; "
                                    f"requested {self._config.requested_fps} FPS"
                                )

                    # Automatic snapshots while recording
                    if self._state.recording:
                        interval = max(0.5, self._config.snapshot_interval_sec)
                        if time.monotonic() - self._last_auto_snapshot_mono >= interval:
                            self._save_snapshot_unlocked(frame, "automatic")
                            self._last_auto_snapshot_mono = time.monotonic()

        finally:
            if cap is not None:
                cap.release()

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

    def _save_snapshot_unlocked(self, frame: np.ndarray, capture_type: str) -> dict:
        assert self._config.snapshots_dir and self._config.thumbnails_dir
        self._config.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self._config.thumbnails_dir.mkdir(parents=True, exist_ok=True)
        self._state.snapshot_sequence += 1
        seq = self._state.snapshot_sequence
        ts = datetime.utcnow()
        filename = f"snapshot_{seq:06d}.jpg"
        path = self._config.snapshots_dir / filename
        thumb_path = self._config.thumbnails_dir / filename
        cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        # Thumbnail
        h, w = frame.shape[:2]
        scale = 320 / max(w, 1)
        thumb = cv2.resize(frame, (int(w * scale), int(h * scale)))
        cv2.imwrite(str(thumb_path), thumb, [int(cv2.IMWRITE_JPEG_QUALITY), 80])

        self._state.snapshot_count += 1
        if capture_type == "manual":
            self._state.manual_snapshot_count += 1
        else:
            self._state.automatic_snapshot_count += 1

        meta = {
            "sequence_number": seq,
            "file_path": str(path),
            "thumbnail_path": str(thumb_path),
            "capture_timestamp": ts,
            "capture_type": capture_type,
        }
        self._state.last_snapshots.append(meta)
        if len(self._state.last_snapshots) > 50:
            self._state.last_snapshots = self._state.last_snapshots[-50:]
        if self._snapshot_callback:
            try:
                self._snapshot_callback(frame, ts, capture_type)
            except Exception:  # noqa: BLE001
                pass
        return meta

    def _finalize_writer_unlocked(self) -> Optional[Path]:
        if self._writer is not None:
            self._writer.release()
            self._writer = None
        if not self._temp_video_path or not self._temp_video_path.exists():
            return None
        # Prefer MP4 via ffmpeg remux/transcode; fall back to keeping AVI
        final = self._final_video_path or self._temp_video_path.with_suffix(".mp4")
        converted = self._transcode_to_mp4(self._temp_video_path, final)
        if converted:
            try:
                self._temp_video_path.unlink(missing_ok=True)
            except OSError:
                pass
            return final
        # Keep recoverable intermediate
        return self._temp_video_path

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
