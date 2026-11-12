from app.middleware_lan import lan_path_allowed
from app.services import network


def test_lan_devices_limited_to_remote_paths():
    assert lan_path_allowed("/remote/abc")
    assert lan_path_allowed("/assets/index.js")
    assert lan_path_allowed("/api/pairing/claim")
    assert lan_path_allowed("/api/remote/status")
    assert lan_path_allowed("/api/remote/command")
    assert not lan_path_allowed("/api/sessions")
    assert not lan_path_allowed("/api/sessions/abc/preview.jpg")
    assert not lan_path_allowed("/api/settings")
    assert not lan_path_allowed("/api/pairing/revoke")
    assert not lan_path_allowed("/docs")
    assert not lan_path_allowed("/openapi.json")


def test_loopback_base_rewritten_to_lan_ip(monkeypatch):
    monkeypatch.setattr(network, "lan_ip", lambda: "192.168.1.50")
    assert network.to_lan_base("http://127.0.0.1:8000", 8000) == "http://192.168.1.50:8000"
    assert network.to_lan_base("http://localhost:8000/", 8000) == "http://192.168.1.50:8000"
    assert network.to_lan_base("https://ui.example.com", 8000) == "https://ui.example.com"


def test_pairing_url_uses_lan_ip(client, monkeypatch):
    monkeypatch.setattr(network, "lan_ip", lambda: "192.168.1.50")
    session = client.post("/api/sessions", json={"capture_source": "synthetic"}).json()
    res = client.post(
        f"/api/sessions/{session['public_id']}/pairing",
        json={"ui_base_url": "http://127.0.0.1:8000", "service_base_url": "http://127.0.0.1:8000"},
    )
    assert res.status_code == 200, res.text
    url = res.json()["qr_payload"]
    assert url.startswith("http://192.168.1.50:8000/remote/")
    assert "127.0.0.1" not in url
