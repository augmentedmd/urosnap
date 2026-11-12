from __future__ import annotations

import sys

from app import desktop


def test_windowed_exe_logs_to_file(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    desktop._redirect_output_if_windowed(tmp_path / "logs")
    try:
        print("hello from windowed exe")
        sys.stdout.flush()
        assert "hello from windowed exe" in (tmp_path / "logs" / "opensnap.log").read_text()
        assert sys.stderr is sys.stdout
    finally:
        sys.stdout.close()


def test_second_launch_opens_existing_instance(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(desktop, "_running_opensnap", lambda port: True)
    monkeypatch.setattr(desktop.webbrowser, "open", opened.append)
    monkeypatch.setattr(desktop.uvicorn.Server, "run", lambda self: (_ for _ in ()).throw(AssertionError("started twice")))
    desktop.run(port=8999)
    assert opened == ["http://127.0.0.1:8999"]


def test_shutdown_endpoint(client):
    from app.main import app

    assert client.post("/api/system/shutdown").status_code == 501

    class FakeServer:
        should_exit = False

    app.state.uvicorn_server = FakeServer()
    try:
        res = client.post("/api/system/shutdown")
        assert res.status_code == 200
        assert app.state.uvicorn_server.should_exit is True
    finally:
        del app.state.uvicorn_server
