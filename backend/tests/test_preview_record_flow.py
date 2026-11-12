import time
from pathlib import Path

from app.services.video.pipeline import PipelineConfig, get_video_pipeline


def test_synthetic_preview_frames_then_record_and_stop(tmp_path: Path):
    pipeline = get_video_pipeline()
    video_dir = tmp_path / "video"
    pipeline.configure(
        PipelineConfig(
            source_type="synthetic",
            device_id="synthetic",
            resolution="640x480",
            requested_fps=10,
            session_public_id="preview-record",
            video_dir=video_dir,
            snapshots_dir=tmp_path / "snapshots",
            thumbnails_dir=tmp_path / "thumbs",
        )
    )

    deadline = time.monotonic() + 3.0
    jpeg = None
    while time.monotonic() < deadline:
        jpeg = pipeline.get_latest_jpeg()
        if jpeg:
            break
        time.sleep(0.05)
    assert jpeg is not None and len(jpeg) > 100

    ok, message = pipeline.start_recording()
    assert ok, message
    time.sleep(0.6)
    metrics = pipeline.recording_metrics()
    assert metrics["state"] == "recording"
    assert (metrics.get("frames_written") or 0) >= 1

    ok, message, path = pipeline.stop_recording()
    assert ok, message
    assert metrics_after_stop_ready(pipeline)


def metrics_after_stop_ready(pipeline) -> bool:
    metrics = pipeline.recording_metrics()
    return metrics["state"] in {"stopped", "ready"}


def test_camera_source_still_publishes_frames_via_synthetic_fallback(tmp_path: Path):
    """Even if camera open fails, preview must not stay blank."""
    pipeline = get_video_pipeline()
    pipeline.configure(
        PipelineConfig(
            source_type="camera",
            device_id="camera:99",
            resolution="640x480",
            requested_fps=10,
            session_public_id="camera-fallback",
            video_dir=tmp_path / "video",
            snapshots_dir=tmp_path / "snapshots",
            thumbnails_dir=tmp_path / "thumbs",
        )
    )

    deadline = time.monotonic() + 4.0
    jpeg = None
    while time.monotonic() < deadline:
        jpeg = pipeline.get_latest_jpeg()
        if jpeg:
            break
        time.sleep(0.05)
    assert jpeg is not None and len(jpeg) > 100
    status = pipeline.capture_status()
    assert status.connected is True
