from app.services.pairing import PairingService


def test_build_remote_url_includes_local_service_query():
    url = PairingService.build_remote_url(
        "https://opensnap-ui.example.workers.dev",
        "tok123",
        service_base_url="http://192.168.1.20:8000",
    )
    assert url.startswith("https://opensnap-ui.example.workers.dev/remote/tok123?")
    assert "service=http%3A%2F%2F192.168.1.20%3A8000" in url


def test_create_pairing_accepts_cloudflare_ui_base(client):
    from datetime import date

    payload = {
        "patient": {
            "first_name": "A",
            "last_name": "B",
            "date_of_birth": "1990-01-01",
            "medical_record_number": "CF-1",
        },
        "procedure_type": "Diagnostic cystoscopy",
        "physician": "Dr. Test",
        "location": "OR",
        "procedure_date": date.today().isoformat(),
        "capture_source": "synthetic",
        "capture_device_id": "synthetic",
        "resolution": "640x480",
        "requested_fps": 10,
        "snapshot_interval_sec": 3,
        "images_per_page": 4,
    }
    sid = client.post("/api/sessions", json=payload).json()["public_id"]
    res = client.post(
        f"/api/sessions/{sid}/pairing",
        json={
            "ui_base_url": "https://opensnap-ui.example.workers.dev",
            "service_base_url": "http://10.0.0.5:8000",
        },
    )
    assert res.status_code == 200
    url = res.json()["pairing_url"]
    assert url.startswith("https://opensnap-ui.example.workers.dev/remote/")
    assert "service=http%3A%2F%2F10.0.0.5%3A8000" in url
    assert "CF-1" not in url
