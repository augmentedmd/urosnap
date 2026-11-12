from app.services.video.pipeline import PipelineConfig, get_video_pipeline


def test_recording_state_not_overridden_by_error():
    pipeline = get_video_pipeline()
    pipeline.configure(
        PipelineConfig(
            source_type="synthetic",
            session_public_id="teststate",
            video_dir=None,
        )
    )
    # Stop the acquisition thread so it can't clear the injected camera error mid-test.
    pipeline.shutdown()
    with pipeline._lock:
        pipeline._state.recording = True
        pipeline._state.started_at = 1.0
        pipeline._state.error = "Unable to open camera index 0"
    metrics = pipeline.recording_metrics()
    assert metrics["state"] == "recording"
    assert metrics["error"]
    with pipeline._lock:
        pipeline._state.recording = False
        pipeline._state.error = None
