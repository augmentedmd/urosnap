"""OpenSnap desktop entrypoint — used by the Windows EXE and local `python -m app.desktop`.

Starts the local recording service and opens the UI in the default browser.
No Cloudflare, no git clone, no manual uvicorn for end users.

Also registers the Windows `opensnap://` URL protocol so the Cloudflare UI
bookmark can start this EXE via a deep-link (one-time install, then website-only).
"""

from __future__ import annotations

import argparse
import json
import logging
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from app.config import get_settings
from app.main import app
from app.protocol import (
    extract_protocol_argv,
    parse_protocol_url,
    register_protocol,
)

logger = logging.getLogger("opensnap.desktop")


def _maybe_register_protocol() -> None:
    """Best-effort HKCU registration so Cloudflare `opensnap://start` works afterward."""
    if sys.platform != "win32":
        return
    try:
        exe = register_protocol()
        logger.info("Registered opensnap:// → %s", exe)
    except Exception as exc:
        # Non-fatal: clinic can still double-click the EXE or run the PowerShell helper.
        logger.warning("Could not register opensnap:// protocol: %s", exc)


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def _wait_then_open(url: str, host: str, port: int, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_open(host, port):
            webbrowser.open(url)
            return
        time.sleep(0.2)
    # Still try — user can refresh if startup is slow.
    webbrowser.open(url)


def _redirect_output_if_windowed(log_dir) -> None:
    """The EXE is built without a console, so stdout/stderr are None; uvicorn needs real streams."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = open(log_dir / "opensnap.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    if sys.stdout is None:
        sys.stdout = log_file
    if sys.stderr is None:
        sys.stderr = log_file


def _running_opensnap(port: int) -> bool:
    """True when another OpenSnap is already serving this port (e.g. the EXE was double-clicked twice)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1.5) as res:
            return json.load(res).get("service") == get_settings().app_name
    except Exception:
        return False


def _ui_is_served(port: int) -> bool:
    """True when GET / returns the React shell (not the 'Frontend not built yet' JSON)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1.5) as res:
            content_type = (res.headers.get("Content-Type") or "").lower()
            body = res.read(512)
            if "text/html" in content_type:
                return True
            if b"Frontend not built" in body:
                return False
            head = body.lstrip()[:64].lower()
            return head.startswith(b"<!doctype") or head.startswith(b"<html")
    except Exception:
        return False


def run(host: str | None = None, port: int | None = None, open_browser: bool = True) -> None:
    from app.paths import frontend_dist_dir

    settings = get_settings()
    _redirect_output_if_windowed(settings.data_dir / "logs")
    # Listen on the LAN so the iPhone remote can connect. LanRemoteOnlyMiddleware
    # limits other devices to the PHI-free remote endpoints.
    host = host or "0.0.0.0"
    port = int(port or settings.port or 8000)
    url = f"http://127.0.0.1:{port}"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if _running_opensnap(port):
        if _ui_is_served(port):
            logger.info("OpenSnap is already running on %s; opening it", url)
            if open_browser:
                webbrowser.open(url)
            return
        message = (
            f"Port {port} already has OpenSnap API without the UI "
            f"(often a leftover `uvicorn` from a source install).\n\n"
            "Quit that process in Task Manager, then start OpenSnap.exe again."
        )
        logger.error(message.replace("\n\n", " "))
        _show_error(message)
        raise OSError(message)

    ui_dir = frontend_dist_dir()
    index = ui_dir / "index.html"
    if not index.is_file():
        message = (
            f"OpenSnap UI is missing at:\n{index}\n\n"
            "Re-extract the full OpenSnap folder from OpenSnap-windows.zip "
            "(keep the _internal folder next to OpenSnap.exe)."
        )
        logger.error("UI missing: %s", index)
        _show_error(message)
        raise OSError(message)

    logger.info("Starting OpenSnap on %s (data: %s, ui: %s)", url, settings.data_dir, ui_dir)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.sessions_dir.mkdir(parents=True, exist_ok=True)

    if open_browser:
        threading.Thread(
            target=_wait_then_open,
            args=(url, "127.0.0.1", port),
            daemon=True,
        ).start()

    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="info"))
    app.state.uvicorn_server = server
    try:
        server.run()
    except SystemExit:
        # uvicorn calls sys.exit(1) when it cannot bind instead of raising.
        if not server.started:
            raise OSError(f"Port {port} is already in use by another program.") from None
        raise


def _show_error(message: str) -> None:
    """With no console window, a dialog is the only way the user sees a startup failure."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "OpenSnap", 0x10)
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    remaining, protocol_url = extract_protocol_argv(raw)

    parser = argparse.ArgumentParser(description="OpenSnap desktop recording service")
    parser.add_argument("--host", default=None, help="Bind address (default 0.0.0.0 / LAN)")
    parser.add_argument("--port", type=int, default=None, help="Port (default 8000)")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the default browser automatically",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Bind 127.0.0.1 only (disables the iPhone remote)",
    )
    parser.add_argument(
        "--register-protocol",
        action="store_true",
        help="Register opensnap:// in HKCU for this EXE and exit (no service start)",
    )
    parser.add_argument(
        "--lan",
        action="store_true",
        help="Bind 0.0.0.0 so clinic LAN devices can reach the service (default)",
    )
    args = parser.parse_args(remaining)

    open_browser = not args.no_browser
    if protocol_url:
        try:
            launch = parse_protocol_url(protocol_url)
        except ValueError as exc:
            logger.error("%s", exc)
            _show_error(str(exc))
            return 2
        if launch.action == "register" or args.register_protocol:
            try:
                exe = register_protocol()
                logger.info("Registered opensnap:// → %s", exe)
                return 0
            except OSError as exc:
                _show_error(f"Could not register opensnap://:\n\n{exc}")
                return 1
        # Deep-link from Cloudflare: start the recorder; browser open only if requested.
        open_browser = launch.open_browser and not args.no_browser
        logger.info("Protocol launch %s (open_browser=%s)", launch.raw, open_browser)

    if args.register_protocol and not protocol_url:
        try:
            exe = register_protocol()
            logger.info("Registered opensnap:// → %s", exe)
            return 0
        except OSError as exc:
            _show_error(f"Could not register opensnap://:\n\n{exc}")
            return 1

    # Keep protocol registration fresh whenever the EXE runs (path may move after re-extract).
    _maybe_register_protocol()

    host = "127.0.0.1" if args.local_only else args.host
    if args.lan and host is None:
        host = "0.0.0.0"
    try:
        run(host=host, port=args.port, open_browser=open_browser)
    except KeyboardInterrupt:
        return 0
    except OSError as exc:
        logger.error("Failed to start OpenSnap: %s", exc)
        _show_error(f"OpenSnap could not start:\n\n{exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
