"""OpenSnap desktop entrypoint — used by the Windows EXE and local `python -m app.desktop`.

Starts the local recording service and opens the UI in the default browser.
No Cloudflare, no git clone, no manual uvicorn for end users.
"""

from __future__ import annotations

import argparse
import logging
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from app.config import get_settings
from app.main import app
from app.paths import is_frozen

logger = logging.getLogger("opensnap.desktop")


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


def run(host: str | None = None, port: int | None = None, open_browser: bool = True) -> None:
    settings = get_settings()
    host = host or settings.host or "127.0.0.1"
    # Desktop EXE binds loopback by default so the machine isn't exposed on the LAN
    # unless the physician explicitly chooses 0.0.0.0 for iPhone remote.
    if is_frozen() and host == "0.0.0.0":
        host = "127.0.0.1"
    port = int(port or settings.port or 8000)
    url = f"http://127.0.0.1:{port}"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("Starting OpenSnap on %s (data: %s)", url, settings.data_dir)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.sessions_dir.mkdir(parents=True, exist_ok=True)

    if open_browser:
        threading.Thread(
            target=_wait_then_open,
            args=(url, "127.0.0.1", port),
            daemon=True,
        ).start()

    # Prefer 127.0.0.1 in the browser even if uvicorn listens on all interfaces.
    uvicorn.run(app, host=host, port=port, log_level="info", factory=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenSnap desktop recording service")
    parser.add_argument("--host", default=None, help="Bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="Port (default 8000)")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the default browser automatically",
    )
    parser.add_argument(
        "--lan",
        action="store_true",
        help="Bind 0.0.0.0 so an iPhone on the LAN can reach the service",
    )
    args = parser.parse_args(argv)
    host = "0.0.0.0" if args.lan else args.host
    try:
        run(host=host, port=args.port, open_browser=not args.no_browser)
    except KeyboardInterrupt:
        return 0
    except OSError as exc:
        logger.error("Failed to start OpenSnap: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
