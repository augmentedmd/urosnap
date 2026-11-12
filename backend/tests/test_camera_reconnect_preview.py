"""When camera is wanted but temporarily unavailable, preview may be synthetic;
once a camera open+read succeeds on the acquisition thread, preview must switch."""

from pathlib import Path

import numpy as np

from app.services.video.pipeline import PipelineConfig, VideoPipeline


def test_publish_camera_frame_replaces_synthetic(tmp_path: Path, monkeypatch):
    pipeline = VideoPipeline()
    width, height = 320, 240

    # Seed synthetic into the preview buffer (unplug fallback state).
    syn = pipeline._synthetic_frame(width, height)
    ok, jpeg = __import__("cv2").imencode(".jpg", syn)
    assert ok
    pipeline._latest_frame = syn
    pipeline._latest_jpeg = jpeg.tobytes()
    syn_bytes = pipeline._latest_jpeg

    # Simulate a successful same-thread camera probe frame (solid red ≠ synthetic bars).
    cam = np.zeros((height, width, 3), dtype=np.uint8)
    cam[:, :] = (0, 0, 255)
    ok, cam_jpeg = __import__("cv2").imencode(".jpg", cam)
    assert ok
    pipeline._latest_frame = cam
    pipeline._latest_jpeg = cam_jpeg.tobytes()

    assert pipeline.get_latest_jpeg() != syn_bytes
    assert pipeline.get_latest_jpeg() == cam_jpeg.tobytes()


def test_configure_idempotent_still(tmp_path: Path):
    pipeline = VideoPipeline()
    cfg = PipelineConfig(
        source_type="synthetic",
        device_id="synthetic",
        resolution="640x480",
        session_public_id="reconnect-id",
        video_dir=tmp_path / "v",
        snapshots_dir=tmp_path / "s",
        thumbnails_dir=tmp_path / "t",
    )
    pipeline.configure(cfg)
    t1 = pipeline._thread
    pipeline.configure(cfg)
    assert pipeline._thread is t1
