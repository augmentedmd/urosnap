from app.services.video.pipeline import PipelineConfig, get_video_pipeline


def test_configure_same_session_does_not_restart_thread():
    pipeline = get_video_pipeline()
    cfg = PipelineConfig(
        source_type="synthetic",
        device_id="synthetic",
        resolution="640x480",
        session_public_id="preview-thrash",
    )
    pipeline.configure(cfg)
    first = pipeline._thread
    assert first is not None and first.is_alive()
    pipeline.configure(cfg)
    assert pipeline._thread is first
    pipeline.configure(
        PipelineConfig(
            source_type="synthetic",
            device_id="synthetic",
            resolution="640x480",
            session_public_id="preview-thrash",
            snapshot_interval_sec=5.0,
        )
    )
    assert pipeline._thread is first
    assert pipeline._config.snapshot_interval_sec == 5.0
