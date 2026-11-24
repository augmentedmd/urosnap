from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app import protocol
from app.desktop import main


def test_extract_protocol_argv_splits_url():
    remaining, url = protocol.extract_protocol_argv(
        ["--no-browser", "opensnap://start", "--port", "8000"]
    )
    assert remaining == ["--no-browser", "--port", "8000"]
    assert url == "opensnap://start"


def test_parse_protocol_start_defaults_no_browser():
    launch = protocol.parse_protocol_url("opensnap://start")
    assert launch.action == "start"
    assert launch.open_browser is False


def test_parse_protocol_open_enables_browser():
    launch = protocol.parse_protocol_url("opensnap://open")
    assert launch.action == "start"
    assert launch.open_browser is True


def test_parse_protocol_browser_query():
    assert protocol.parse_protocol_url("opensnap://start?browser=1").open_browser is True
    assert protocol.parse_protocol_url("opensnap://start?browser=0").open_browser is False


def test_parse_protocol_path_forms():
    assert protocol.parse_protocol_url("opensnap:///start").action == "start"
    assert protocol.parse_protocol_url("opensnap:start").action == "start"


def test_protocol_command_quotes_path():
    cmd = protocol.protocol_command(r"C:\Program Files\OpenSnap\OpenSnap.exe")
    assert cmd == r'"C:\Program Files\OpenSnap\OpenSnap.exe" "%1"'


def test_register_protocol_rejected_off_windows(monkeypatch):
    monkeypatch.setattr(protocol.sys, "platform", "linux")
    with pytest.raises(OSError, match="Windows"):
        protocol.register_protocol(Path("/tmp/OpenSnap.exe"))


def test_register_protocol_writes_hkcu(monkeypatch, tmp_path):
    exe = tmp_path / "OpenSnap.exe"
    exe.write_bytes(b"MZ")

    class FakeKey:
        def __init__(self, path: str):
            self.path = path
            self.values: dict[str | None, tuple] = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    keys: dict[str, FakeKey] = {}
    hive = object()

    def create_key(parent, path):
        if parent is hive:
            full = path
        else:
            full = f"{parent.path}\\{path}"
        key = FakeKey(full)
        keys[full] = key
        return key

    def set_value(key, name, _reserved, typ, value):
        key.values[name] = (typ, value)

    fake_winreg = type(
        "W",
        (),
        {
            "HKEY_CURRENT_USER": hive,
            "REG_SZ": 1,
            "CreateKeyEx": staticmethod(create_key),
            "SetValueEx": staticmethod(set_value),
        },
    )()

    monkeypatch.setattr(protocol.sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "winreg", fake_winreg)

    registered = protocol.register_protocol(exe)
    assert registered == exe
    root = keys[r"Software\Classes\opensnap"]
    assert root.values[None][1] == protocol.PROTOCOL_NAME
    assert root.values["URL Protocol"][1] == ""
    cmd = keys[r"Software\Classes\opensnap\shell\open\command"]
    assert cmd.values[None][1] == f'"{exe}" "%1"'


def test_desktop_register_protocol_flag(monkeypatch, tmp_path):
    exe = tmp_path / "OpenSnap.exe"
    exe.write_bytes(b"MZ")
    called: list[Path] = []

    monkeypatch.setattr("app.desktop.register_protocol", lambda: called.append(exe) or exe)
    code = main(["--register-protocol"])
    assert code == 0
    assert called == [exe]


def test_desktop_protocol_start_skips_browser(monkeypatch):
    seen: dict[str, object] = {}

    def fake_run(*, host=None, port=None, open_browser=True):
        seen["open_browser"] = open_browser
        seen["host"] = host

    monkeypatch.setattr("app.desktop.register_protocol", lambda: Path("OpenSnap.exe"))
    monkeypatch.setattr("app.desktop._maybe_register_protocol", lambda: None)
    monkeypatch.setattr("app.desktop.run", fake_run)
    code = main(["opensnap://start"])
    assert code == 0
    assert seen["open_browser"] is False


def test_desktop_protocol_open_enables_browser(monkeypatch):
    seen: dict[str, object] = {}

    def fake_run(*, host=None, port=None, open_browser=True):
        seen["open_browser"] = open_browser

    monkeypatch.setattr("app.desktop.register_protocol", lambda: Path("OpenSnap.exe"))
    monkeypatch.setattr("app.desktop._maybe_register_protocol", lambda: None)
    monkeypatch.setattr("app.desktop.run", fake_run)
    code = main(["opensnap://open"])
    assert code == 0
    assert seen["open_browser"] is True
