from __future__ import annotations

import time
from datetime import date


def test_recording_continues_after_pairing_revoke(client):
    payload = {
        "patient": {
            "first_name": "Pat",
            "last_name": "Remote",
            "date_of_birth": "1988-03-03",
            "medical_record_number": "TEST-DISC-1",
        },
        "procedure_type": "Prostate biopsy",
        "physician": "Dr. Test",
        "location": "OR-2",
        "procedure_date": date.today().isoformat(),
        "capture_source": "synthetic",
        "capture_device_id": "synthetic",
        "resolution": "640x480",
        "requested_fps": 10,
        "snapshot_interval_sec": 1.0,
        "images_per_page": 4,
    }
    sid = client.post("/api/sessions", json=payload).json()["public_id"]
    token = client.post(f"/api/sessions/{sid}/pairing").json()["token"]
    access = client.post("/api/pairing/claim", json={"token": token, "controller_id": "phone"}).json()[
        "access_token"
    ]
    start = client.post(
        "/api/remote/command",
        headers={"Authorization": f"Bearer {access}"},
        json={"command_id": "cmd_disc_start", "action": "start"},
    )
    assert start.json()["success"] is True

    # Phone disconnect / revoke must not stop recording
    revoke = client.post(f"/api/pairing/revoke?session_id={sid}")
    assert revoke.status_code == 200
    time.sleep(1.2)
    status = client.get(f"/api/sessions/{sid}/recording/status").json()
    assert status["state"] == "recording"

    stop = client.post(f"/api/sessions/{sid}/recording/stop")
    assert stop.status_code == 200
    assert stop.json()["state"] == "stopped"
