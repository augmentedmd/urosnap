"""Acquisition loop CPU/idle mitigations for Windows input lag."""

from __future__ import annotations

import time
from pathlib import Path

from app.services.video.pipeline import (
    PREVIEW_FPS_CAP,
    PipelineConfig,
    get_video_pipeline,
)


def _wait_jpeg(pipeline, timeout: float = 3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        jpeg = pipeline.get_latest_jpeg()
        if jpeg:
            return jpeg
        time.sleep(0.05)
    return None


def test_preview_acquisition_respects_fps_cap():
    pipeline = get_video_pipeline()
    pipeline.configure(
        PipelineConfig(
            source_type="synthetic",
            device_id="synthetic",
            resolution="640x480",
            requested_fps=30,
            preview_fps_cap=10,
            preview_idle_timeout_sec=30.0,
            session_public_id="fps-cap",
        )
    )
    assert _wait_jpeg(pipeline)
    # Keep interest alive while measuring.
    time.sleep(1.2)
    pipeline.touch_preview()
    metrics = pipeline.recording_metrics()
    incoming = metrics.get("incoming_fps") or 0.0
    # Cap is 10; allow scheduler jitter but must be well below the old hard-coded 30.
    assert 3.0 <= incoming <= 14.0, incoming
    assert incoming <= PREVIEW_FPS_CAP + 3.0


def test_pipeline_idles_without_preview_interest():
    pipeline = get_video_pipeline()
    pipeline.configure(
        PipelineConfig(
            source_type="synthetic",
            device_id="synthetic",
            resolution="640x480",
            requested_fps=10,
            preview_fps_cap=10,
            preview_idle_timeout_sec=1.0,
            session_public_id="idle-stop",
        )
    )
    assert _wait_jpeg(pipeline)
    assert pipeline.is_acquiring()

    # Stop refreshing interest; acquisition should exit after the idle timeout.
    with pipeline._lock:
        pipeline._last_preview_interest_mono = time.monotonic() - 2.0
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and pipeline.is_acquiring():
        time.sleep(0.05)
    assert not pipeline.is_acquiring()


def test_configure_restarts_after_idle(tmp_path: Path):
    pipeline = get_video_pipeline()
    cfg = PipelineConfig(
        source_type="synthetic",
        device_id="synthetic",
        resolution="640x480",
        requested_fps=10,
        preview_fps_cap=10,
        preview_idle_timeout_sec=1.0,
        session_public_id="idle-restart",
        video_dir=tmp_path / "video",
        snapshots_dir=tmp_path / "snap",
        thumbnails_dir=tmp_path / "th",
    )
    pipeline.configure(cfg)
    assert _wait_jpeg(pipeline)
    with pipeline._lock:
        pipeline._last_preview_interest_mono = time.monotonic() - 2.0
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and pipeline.is_acquiring():
        time.sleep(0.05)
    assert not pipeline.is_acquiring()

    pipeline.configure(cfg)
    assert _wait_jpeg(pipeline)
    assert pipeline.is_acquiring()


def test_recording_keeps_pipeline_alive_without_preview(tmp_path: Path):
    pipeline = get_video_pipeline()
    pipeline.configure(
        PipelineConfig(
            source_type="synthetic",
            device_id="synthetic",
            resolution="640x480",
            requested_fps=10,
            preview_fps_cap=10,
            preview_idle_timeout_sec=1.0,
            session_public_id="rec-alive",
            video_dir=tmp_path / "video",
            snapshots_dir=tmp_path / "snap",
            thumbnails_dir=tmp_path / "th",
        )
    )
    assert _wait_jpeg(pipeline)
    ok, msg = pipeline.start_recording()
    assert ok, msg
    with pipeline._lock:
        pipeline._last_preview_interest_mono = time.monotonic() - 5.0
    time.sleep(1.5)
    assert pipeline.is_acquiring()
    ok, msg, _path = pipeline.stop_recording()
    assert ok, msg


def test_manual_snapshot_writes_without_requiring_lock_held(tmp_path: Path):
    pipeline = get_video_pipeline()
    pipeline.configure(
        PipelineConfig(
            source_type="synthetic",
            device_id="synthetic",
            resolution="640x480",
            requested_fps=10,
            preview_idle_timeout_sec=30.0,
            session_public_id="snap-io",
            video_dir=tmp_path / "video",
            snapshots_dir=tmp_path / "snap",
            thumbnails_dir=tmp_path / "th",
        )
    )
    assert _wait_jpeg(pipeline)
    ok, msg, meta = pipeline.take_manual_snapshot()
    assert ok, msg
    assert meta is not None
    assert Path(meta["file_path"]).is_file()
    assert Path(meta["thumbnail_path"]).is_file()
