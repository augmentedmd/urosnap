from pathlib import Path

from app.paths import app_root, bundle_root, default_data_dir, frontend_dist_dir, is_frozen


def test_not_frozen_in_pytest():
    assert is_frozen() is False


def test_default_paths_resolve():
    assert isinstance(default_data_dir(), Path)
    assert isinstance(frontend_dist_dir(), Path)
    assert isinstance(bundle_root(), Path)
    assert isinstance(app_root(), Path)
    assert bundle_root().name == "urosnap" or (bundle_root() / "backend").exists()


def test_desktop_cli_help():
    from app.desktop import main

    # argparse --help exits with SystemExit(0)
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
