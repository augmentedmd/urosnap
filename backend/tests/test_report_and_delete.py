from __future__ import annotations

import time
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from app.services.pdf_report import format_report_date, title_case


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


def _start(client, sid: str) -> None:
    # The synthetic source needs a moment to publish its first frame after the session opens.
    deadline = time.time() + 5
    while True:
        res = client.post(f"/api/sessions/{sid}/recording/start")
        if res.status_code == 200 or time.time() > deadline:
            break
        time.sleep(0.1)
    assert res.status_code == 200, res.text


def _record_with_snapshots(client, sid: str, count: int) -> None:
    _start(client, sid)
    for _ in range(count):
        assert client.post(f"/api/sessions/{sid}/snapshots").status_code == 200
        time.sleep(0.15)
    assert client.post(f"/api/sessions/{sid}/recording/stop").status_code == 200
    ids = [s["id"] for s in client.get(f"/api/sessions/{sid}/snapshots").json()]
    client.post(f"/api/sessions/{sid}/snapshots/selection", json={"selected_ids": ids, "ordered_ids": ids})


def test_format_report_date():
    assert format_report_date(date(2026, 11, 3)) == "November 3, 2026"
    assert format_report_date(datetime(2026, 1, 12, 23, 5)) == "January 12, 2026"
    assert format_report_date(None) == "—"


def test_title_case():
    assert title_case("Diagnostic cystoscopy") == "Diagnostic Cystoscopy"
    assert title_case("SpaceOAR and fiducial marker placement") == "SpaceOAR and Fiducial Marker Placement"
    assert title_case("Other / Custom Procedure") == "Other / Custom Procedure"


def _pdf_text(client, sid: str, notes: str) -> tuple[PdfReader, str]:
    res = client.post(f"/api/sessions/{sid}/reports", json={"notes": notes, "images_per_page": 4})
    assert res.status_code == 200, res.text
    pdf = PdfReader(BytesIO(client.get(res.json()["download_url"]).content))
    return pdf, "\n".join(p.extract_text() for p in pdf.pages)


def test_report_layout(client):
    sid = _create(client)["public_id"]
    _record_with_snapshots(client, sid, 2)
    pdf, full = _pdf_text(client, sid, "Short note about the bladder.")
    first = pdf.pages[0].extract_text()

    assert "Diagnostic Cystoscopy" in first
    assert "Mount Sinai Doctors" in first and "Long Island" not in full
    assert "November 3, 2026" in first
    assert "January 5, 1980" in first
    assert "Urologist:" in first and "Dr. Hidden Urologist" in first
    assert "Generated" not in full
    # Practice name appears once, in the letterhead, not repeated in the footer.
    assert first.count("Mount Sinai Doctors") == 1
    assert "2026-11-03" not in full
    assert "Procedure Time" not in full and "14:37" not in full
    assert "Performing Urologist" not in full
    assert "Location" not in full and "Suite 2" not in full
    # Procedure name is the page title only, not repeated as a table row.
    assert full.count("Diagnostic Cystoscopy") == 1 and "Diagnostic cystoscopy" not in full
    assert "Photographs" not in full
    assert "Captured Images:" in first
    assert full.index("Captured Images:") < full.index("Notes:") < full.index("Short note about the bladder.")
    # Logo plus both photographs on page 1.
    assert len(pdf.pages) == 1
    assert len(pdf.pages[0].images) == 3


def test_report_omits_empty_notes(client):
    sid = _create(client)["public_id"]
    _pdf, full = _pdf_text(client, sid, "   \n  ")
    assert "Notes" not in full


def test_long_notes_break_across_pages(client):
    sid = _create(client)["public_id"]
    notes = "\n".join(f"Line {i} of a long procedure note." for i in range(150))
    pdf, full = _pdf_text(client, sid, notes)
    assert len(pdf.pages) >= 2
    assert "Line 149 of a long procedure note." in full


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
    _start(client, sid)
    try:
        res = client.delete(f"/api/sessions/{sid}")
        assert res.status_code == 409
        assert client.get(f"/api/sessions/{sid}").status_code == 200
    finally:
        client.post(f"/api/sessions/{sid}/recording/stop")
