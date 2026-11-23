from pathlib import Path

from app.paths import (
    app_root,
    bundle_root,
    default_data_dir,
    frontend_dist_dir,
    is_frozen,
)


def test_not_frozen_in_pytest():
    assert is_frozen() is False


def test_default_paths_resolve():
    assert isinstance(default_data_dir(), Path)
    assert isinstance(frontend_dist_dir(), Path)
    assert isinstance(bundle_root(), Path)
    assert isinstance(app_root(), Path)
    assert bundle_root().name == "urosnap" or (bundle_root() / "backend").exists()


def test_frontend_dist_prefers_index_html(tmp_path, monkeypatch):
    missing = tmp_path / "missing" / "frontend" / "dist"
    present = tmp_path / "present" / "frontend" / "dist"
    present.mkdir(parents=True)
    (present / "index.html").write_text("<html></html>", encoding="utf-8")

    monkeypatch.setattr(
        "app.paths._frontend_dist_candidates",
        lambda: [missing, present],
    )
    assert frontend_dist_dir() == present


def test_frontend_dist_candidates_include_exe_fallbacks(monkeypatch, tmp_path):
    meipass = tmp_path / "_internal"
    exe = tmp_path / "OpenSnap.exe"
    meipass.mkdir()
    exe.write_bytes(b"")
    monkeypatch.setattr("app.paths.is_frozen", lambda: True)
    monkeypatch.setattr("app.paths.sys", type("S", (), {"_MEIPASS": str(meipass), "executable": str(exe), "frozen": True})())
    # Re-import helpers via direct call after patching module attrs used inside
    import app.paths as paths

    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(exe))

    candidates = paths._frontend_dist_candidates()
    assert meipass / "frontend" / "dist" in candidates
    assert tmp_path / "frontend" / "dist" in candidates
    assert tmp_path / "_internal" / "frontend" / "dist" in candidates


def test_desktop_cli_help():
    from app.desktop import main

    # argparse --help exits with SystemExit(0)
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
