import time
from pathlib import Path

import numpy as np

from app.services.video.pipeline import PipelineConfig, get_video_pipeline


def test_ensure_preview_jpeg_never_blank_for_camera_source(tmp_path: Path):
    pipeline = get_video_pipeline()
    pipeline.configure(
        PipelineConfig(
            source_type="camera",
            device_id="camera:99",
            resolution="640x480",
            session_public_id="ensure-cam",
            video_dir=tmp_path / "video",
            snapshots_dir=tmp_path / "snap",
            thumbnails_dir=tmp_path / "th",
        )
    )
    jpeg = pipeline.ensure_preview_jpeg()
    assert jpeg and len(jpeg) > 500

    # Must look like color bars (high channel variance), not a flat gray placeholder.
    import cv2

    arr = np.frombuffer(jpeg, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    assert img is not None
    assert float(img.std()) > 20.0


def test_live_record_after_ensure(tmp_path: Path):
    pipeline = get_video_pipeline()
    pipeline.configure(
        PipelineConfig(
            source_type="synthetic",
            device_id="synthetic",
            resolution="640x480",
            requested_fps=10,
            session_public_id="ensure-rec",
            video_dir=tmp_path / "video",
            snapshots_dir=tmp_path / "snap",
            thumbnails_dir=tmp_path / "th",
        )
    )
    assert pipeline.ensure_preview_jpeg()
    ok, msg = pipeline.start_recording()
    assert ok, msg
    time.sleep(0.5)
    ok, msg, _path = pipeline.stop_recording()
    assert ok, msg
    assert pipeline.recording_metrics()["frames_written"] >= 1
