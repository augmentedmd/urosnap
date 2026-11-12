from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Isolate test data before app import
TEST_ROOT = Path(__file__).resolve().parent / "_tmp_data"
TEST_ROOT.mkdir(parents=True, exist_ok=True)
os.environ["OPENSNAP_DATA_DIR"] = str(TEST_ROOT)


@pytest.fixture(autouse=True)
def _clean_db(tmp_path_factory):
    # Ensure settings cache and DB use the test data dir
    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.sessions_dir.mkdir(parents=True, exist_ok=True)
    yield


@pytest.fixture()
def client():
    from app.database import Base, SessionLocal, engine
    from app.main import app
    from app.services.sessions import get_session_service
    from app.services.video.pipeline import get_video_pipeline

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        get_session_service().seed_procedure_types(db)
    finally:
        db.close()

    pipeline = get_video_pipeline()
    pipeline.reset_session_counters()

    with TestClient(app) as c:
        yield c

    pipeline.shutdown()
