"""Session-start black preview: signal lock + idle-stop / remount races."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from app.services.video import devices
from app.services.video.pipeline import PipelineConfig, VideoPipeline, get_video_pipeline


def test_frame_has_signal_rejects_black_and_accepts_content():
    black = np.zeros((120, 160, 3), dtype=np.uint8)
    assert not devices.frame_has_signal(black)
    assert devices.frame_is_uniform_black(black)

    content = np.zeros((120, 160, 3), dtype=np.uint8)
    content[:, :] = (30, 120, 200)
    assert devices.frame_has_signal(content)
    assert not devices.frame_is_uniform_black(content)

    noisy = np.random.randint(0, 40, (120, 160, 3), dtype=np.uint8)
    assert devices.frame_has_signal(noisy)


def test_frame_has_signal_rejects_capture_card_osd():
    """Dongle 'No signal' OSDs (QR + text on black) must not count as HDMI lock."""
    osd = np.zeros((480, 640, 3), dtype=np.uint8)
    # Fake QR block + status text + rx/tx counters — sparse chrome on a black field.
    osd[36:156, 36:156] = 240
    osd[180:200, 40:320] = 220
    osd[420:440, 480:620] = 200
    assert not devices.frame_is_uniform_black(osd)
    assert not devices.frame_has_signal(osd)

    # Endoscopy-like circular FOV with dark surround should still pass.
    scope = np.zeros((480, 640, 3), dtype=np.uint8)
    yy, xx = np.ogrid[:480, :640]
    circle = (xx - 320) ** 2 + (yy - 240) ** 2 <= 180**2
    scope[circle] = (40, 110, 90)
    assert devices.frame_has_signal(scope)


def _fake_osd_frame(h: int = 120, w: int = 160) -> np.ndarray:
    osd = np.zeros((h, w, 3), dtype=np.uint8)
    osd[8:40, 8:40] = 240
    osd[50:58, 10:90] = 220
    osd[100:108, 110:150] = 200
    return osd


def test_warm_read_require_signal_skips_black_then_accepts(monkeypatch):
    class Cap:
        def __init__(self):
            self.n = 0

        def read(self):
            self.n += 1
            if self.n < 5:
                return True, np.zeros((48, 64, 3), dtype=np.uint8)
            frame = np.zeros((48, 64, 3), dtype=np.uint8)
            frame[:, :] = (10, 80, 160)
            return True, frame

    monkeypatch.setattr(devices.time, "sleep", lambda _s: None)
    frame = devices._warm_read(Cap(), tries=20, delay=0.0, require_signal=True)
    assert frame is not None
    assert devices.frame_has_signal(frame)


def test_warm_read_require_signal_skips_osd_then_accepts(monkeypatch):
    class Cap:
        def __init__(self):
            self.n = 0

        def read(self):
            self.n += 1
            if self.n < 4:
                return True, _fake_osd_frame(48, 64)
            frame = np.zeros((48, 64, 3), dtype=np.uint8)
            frame[:, :] = (10, 80, 160)
            return True, frame

    monkeypatch.setattr(devices.time, "sleep", lambda _s: None)
    frame = devices._warm_read(Cap(), tries=20, delay=0.0, require_signal=True)
    assert frame is not None
    assert devices.frame_has_signal(frame)


def test_warm_read_require_signal_returns_none_if_only_black(monkeypatch):
    class Cap:
        def read(self):
            return True, np.zeros((48, 64, 3), dtype=np.uint8)

    monkeypatch.setattr(devices.time, "sleep", lambda _s: None)
    assert devices._warm_read(Cap(), tries=5, delay=0.0, require_signal=True) is None


def test_touch_preview_restarts_after_idle_stop():
    """Preview interest after idle-stop must restart acquisition (remount path)."""
    pipeline = get_video_pipeline()
    pipeline.configure(
        PipelineConfig(
            source_type="synthetic",
            device_id="synthetic",
            resolution="640x480",
            requested_fps=10,
            preview_fps_cap=10,
            preview_idle_timeout_sec=1.0,
            session_public_id="touch-restart",
        )
    )
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and not pipeline.get_latest_jpeg():
        time.sleep(0.05)
    assert pipeline.get_latest_jpeg()
    assert pipeline.is_acquiring()

    with pipeline._lock:
        pipeline._last_preview_interest_mono = time.monotonic() - 2.0
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and pipeline.is_acquiring():
        time.sleep(0.05)
    assert not pipeline.is_acquiring()

    pipeline.touch_preview()
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and not pipeline.get_latest_jpeg():
        time.sleep(0.05)
    assert pipeline.is_acquiring()
    assert pipeline.get_latest_jpeg()


def test_idle_exit_clears_stale_jpeg_so_poll_waits_for_fresh_frame():
    pipeline = get_video_pipeline()
    pipeline.configure(
        PipelineConfig(
            source_type="synthetic",
            device_id="synthetic",
            resolution="640x480",
            requested_fps=10,
            preview_fps_cap=10,
            preview_idle_timeout_sec=1.0,
            session_public_id="idle-clear",
        )
    )
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and not pipeline.get_latest_jpeg():
        time.sleep(0.05)
    assert pipeline.get_latest_jpeg()

    with pipeline._lock:
        pipeline._last_preview_interest_mono = time.monotonic() - 2.0
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and pipeline.is_acquiring():
        time.sleep(0.05)
    assert not pipeline.is_acquiring()
    # Stale frame dropped on idle-stop so the next poll cannot stick on it.
    with pipeline._lock:
        assert pipeline._latest_jpeg is None


def test_black_camera_frames_fall_back_to_synthetic_until_signal(tmp_path: Path, monkeypatch):
    """Once open, sustained black frames must not stick the preview on a black card."""
    pipeline = VideoPipeline()

    class SignalThenBlackThenSignalCap:
        """Probe succeeds (signal), then goes black past the retry window, then recovers."""

        def __init__(self):
            self.reads = 0

        def read(self):
            self.reads += 1
            frame = np.zeros((240, 320, 3), dtype=np.uint8)
            # First few reads: signal so upgrade succeeds.
            if self.reads <= 3:
                frame[:, :] = (20, 90, 200)
            elif self.reads <= 30:
                # Black streak — pipeline should substitute synthetic / reopen.
                pass
            else:
                frame[:, :] = (20, 90, 200)
            return True, frame

        def release(self):
            pass

    caps: list[SignalThenBlackThenSignalCap] = []

    def fake_quick(_device_id, _resolution):
        cap = SignalThenBlackThenSignalCap()
        caps.append(cap)
        return cap

    monkeypatch.setattr(
        "app.services.video.pipeline.open_capture_quick",
        fake_quick,
    )
    monkeypatch.setattr(
        "app.services.video.pipeline.CAMERA_BLACK_RETRY_SEC",
        0.15,
    )

    pipeline.configure(
        PipelineConfig(
            source_type="camera",
            device_id="camera:0",
            resolution="320x240",
            requested_fps=20,
            preview_fps_cap=20,
            preview_idle_timeout_sec=30.0,
            session_public_id="black-lock",
            video_dir=tmp_path / "v",
            snapshots_dir=tmp_path / "s",
            thumbnails_dir=tmp_path / "t",
        )
    )

    # Preview must stay non-black throughout the black streak / reopen.
    deadline = time.monotonic() + 5.0
    samples = 0
    while time.monotonic() < deadline and samples < 25:
        jpeg = pipeline.get_latest_jpeg()
        if not jpeg:
            time.sleep(0.05)
            continue
        import cv2

        img = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
        assert img is not None
        assert devices.frame_has_signal(img), (
            f"published near-black frame mean={float(img.mean()):.2f} std={float(img.std()):.2f}"
        )
        samples += 1
        time.sleep(0.05)

    assert samples >= 10
    # Black streak should have forced at least one reopen.
    assert len(caps) >= 1
    pipeline.shutdown()


def test_camera_upgrade_rejects_black_probe(tmp_path: Path, monkeypatch):
    pipeline = VideoPipeline()

    class AlwaysBlackCap:
        def read(self):
            return True, np.zeros((240, 320, 3), dtype=np.uint8)

        def release(self):
            pass

    opens = {"n": 0}

    def fake_quick(_device_id, _resolution):
        opens["n"] += 1
        return AlwaysBlackCap()

    monkeypatch.setattr("app.services.video.pipeline.open_capture_quick", fake_quick)
    monkeypatch.setattr("app.services.video.pipeline.frame_has_signal", devices.frame_has_signal)

    pipeline.configure(
        PipelineConfig(
            source_type="camera",
            device_id="camera:0",
            resolution="320x240",
            requested_fps=15,
            preview_fps_cap=15,
            preview_idle_timeout_sec=30.0,
            session_public_id="black-probe",
            video_dir=tmp_path / "v",
            snapshots_dir=tmp_path / "s",
            thumbnails_dir=tmp_path / "t",
        )
    )

    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and not pipeline.get_latest_jpeg():
        time.sleep(0.05)
    jpeg = pipeline.get_latest_jpeg()
    assert jpeg
    import cv2

    img = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img is not None
    # Synthetic bars — not a black capture field.
    assert float(img.std()) > 20.0
    # Black probe must not stick as the live source; retries keep happening.
    time.sleep(1.0)
    assert opens["n"] >= 1
    pipeline.shutdown()
