from __future__ import annotations

import time
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from app.services.pdf_report import format_report_date


def _create(client, **overrides) -> dict:
    payload = {
        "patient": {
            "first_name": "Alex",
            "last_name": "Synthetic",
            "date_of_birth": "1980-01-05",
            "medical_record_number": "TEST-MRN-9",
        },
        "procedure_type": "Diagnostic cystoscopy",
        "physician": "Dr. Hidden Urologist",
        "location": "Suite 2",
        "procedure_date": "2026-11-03",
        "procedure_time": "14:37:00",
        "capture_source": "synthetic",
        "capture_device_id": "synthetic",
        "resolution": "640x480",
        "requested_fps": 10,
        "snapshot_interval_sec": 60,
    }
    payload.update(overrides)
    res = client.post("/api/sessions", json=payload)
    assert res.status_code == 200, res.text
    return res.json()


def _record_with_snapshots(client, sid: str, count: int) -> None:
    assert client.post(f"/api/sessions/{sid}/recording/start").status_code == 200
    for _ in range(count):
        assert client.post(f"/api/sessions/{sid}/snapshots").status_code == 200
        time.sleep(0.15)
    assert client.post(f"/api/sessions/{sid}/recording/stop").status_code == 200
    ids = [s["id"] for s in client.get(f"/api/sessions/{sid}/snapshots").json()]
    client.post(f"/api/sessions/{sid}/snapshots/selection", json={"selected_ids": ids, "ordered_ids": ids})


def test_format_report_date():
    assert format_report_date(date(2026, 11, 3)) == "Nov 3, 2026"
    assert format_report_date(datetime(2026, 1, 12, 23, 5)) == "Jan 12, 2026"
    assert format_report_date(None) == "—"


def test_report_layout(client):
    sid = _create(client)["public_id"]
    _record_with_snapshots(client, sid, 2)
    res = client.post(f"/api/sessions/{sid}/reports", json={"notes": "Short note.", "images_per_page": 4})
    assert res.status_code == 200, res.text
    pdf = PdfReader(BytesIO(client.get(res.json()["download_url"]).content))
    first = pdf.pages[0].extract_text()
    full = "\n".join(p.extract_text() for p in pdf.pages)

    assert "Nov 3, 2026" in first
    assert "Jan 5, 1980" in first
    assert "2026-11-03" not in full
    assert "Procedure Time" not in full and "14:37" not in full
    assert "Performing Urologist" not in full and "Hidden Urologist" not in full
    assert "Photographs" in first
    # Logo plus both photographs on page 1.
    assert len(pdf.pages) == 1
    assert len(pdf.pages[0].images) == 3


def test_delete_session_and_files(client):
    body = _create(client)
    sid = body["public_id"]
    _record_with_snapshots(client, sid, 1)
    folder = Path(body["storage_path"])
    assert folder.is_dir()

    res = client.delete(f"/api/sessions/{sid}?delete_files=true")
    assert res.status_code == 200, res.text
    assert client.get(f"/api/sessions/{sid}").status_code == 404
    assert sid not in [s["public_id"] for s in client.get("/api/sessions").json()]
    assert not folder.exists()


def test_delete_keeps_files_by_default(client):
    body = _create(client)
    sid = body["public_id"]
    folder = Path(body["storage_path"])
    assert client.delete(f"/api/sessions/{sid}").status_code == 200
    assert client.get(f"/api/sessions/{sid}").status_code == 404
    assert folder.is_dir()


def test_cannot_delete_while_recording(client):
    sid = _create(client)["public_id"]
    assert client.post(f"/api/sessions/{sid}/recording/start").status_code == 200
    try:
        res = client.delete(f"/api/sessions/{sid}")
        assert res.status_code == 409
        assert client.get(f"/api/sessions/{sid}").status_code == 200
    finally:
        client.post(f"/api/sessions/{sid}/recording/stop")
