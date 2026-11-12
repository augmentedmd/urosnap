import asyncio

import httpx

from app.main import app
from app.middleware_lan import lan_path_allowed
from app.services import network


def _get_as(client_ip: str, path: str) -> int:
    async def go() -> int:
        transport = httpx.ASGITransport(app=app, client=(client_ip, 50123))
        async with httpx.AsyncClient(transport=transport, base_url="http://192.168.1.50:8000") as c:
            return (await c.get(path)).status_code

    return asyncio.run(go())


def test_phone_blocked_from_desktop_api_but_reaches_remote(client):
    assert _get_as("192.168.1.77", "/api/sessions") == 403
    assert _get_as("192.168.1.77", "/api/settings") == 403
    assert _get_as("192.168.1.77", "/api/remote/status") == 401


def test_pc_using_its_own_lan_ip_is_local(client):
    assert _get_as("192.168.1.50", "/api/sessions") == 200
    assert _get_as("127.0.0.1", "/api/sessions") == 200


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
