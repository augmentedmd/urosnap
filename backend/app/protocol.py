"""Windows custom URL protocol helpers for `opensnap://` deep-links.

A public webpage cannot spawn Windows processes by itself. After a one-time
registration (first OpenSnap.exe launch, `--register-protocol`, or the
packaging PowerShell script), the Cloudflare UI can open `opensnap://start`
and the OS launches the local recorder.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

PROTOCOL_SCHEME = "opensnap"
PROTOCOL_NAME = "URL:OpenSnap Protocol"


@dataclass(frozen=True)
class ProtocolLaunch:
    """Parsed `opensnap://…` deep-link."""

    action: str
    open_browser: bool
    raw: str


def is_protocol_url(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower().startswith(f"{PROTOCOL_SCHEME}:")


def extract_protocol_argv(argv: list[str]) -> tuple[list[str], str | None]:
    """Split CLI args into normal flags and an optional `opensnap://` URL."""
    remaining: list[str] = []
    protocol: str | None = None
    for arg in argv:
        if is_protocol_url(arg):
            protocol = arg
        else:
            remaining.append(arg)
    return remaining, protocol


def parse_protocol_url(url: str) -> ProtocolLaunch:
    """Interpret `opensnap://start`, `opensnap://open`, etc."""
    raw = url.strip()
    # Windows sometimes percent-encodes; normalize empty host/path forms.
    parsed = urlparse(raw)
    if parsed.scheme.lower() != PROTOCOL_SCHEME:
        raise ValueError(f"Unsupported protocol URL: {url!r}")

    # Accept opensnap://start, opensnap:start, opensnap://start/, opensnap:///start
    path_bits = [unquote(p) for p in re.split(r"[/?#]", parsed.path or "") if p]
    host = (parsed.netloc or "").strip().lower()
    action = host or (path_bits[0].lower() if path_bits else "start")
    if action in {"", "/", "local"}:
        action = "start"

    query = parse_qs(parsed.query)
    browser_vals = [v.lower() for v in query.get("browser", [])]
    # Protocol launches usually come from the Cloudflare UI — default: do not steal focus
    # with a second local browser tab. Pass ?browser=1 (or action=open) to open local UI.
    if action in {"open", "ui", "app"}:
        open_browser = True
        action = "start"
    elif "1" in browser_vals or "true" in browser_vals or "yes" in browser_vals:
        open_browser = True
    elif "0" in browser_vals or "false" in browser_vals or "no" in browser_vals:
        open_browser = False
    else:
        open_browser = False

    if action not in {"start", "register"}:
        # Unknown verbs still start the service (safe default for bookmarks).
        action = "start"

    return ProtocolLaunch(action=action, open_browser=open_browser, raw=raw)


def protocol_command(exe_path: str | Path) -> str:
    """Registry command string: quoted EXE path + `%1` for the deep-link URL."""
    exe = str(Path(exe_path))
    if " " in exe and not (exe.startswith('"') and exe.endswith('"')):
        exe = f'"{exe}"'
    elif not exe.startswith('"'):
        exe = f'"{exe}"'
    return f'{exe} "%1"'


def default_exe_path() -> Path:
    """Path Windows should launch for `opensnap://` handlers."""
    return Path(sys.executable).resolve()


def register_protocol(exe_path: str | Path | None = None) -> Path:
    """Register `opensnap://` under HKCU (no admin). Returns the registered EXE path.

    Raises OSError / PermissionError on failure. No-op on non-Windows when called
    from tests; callers should check platform first if they need a bool result.
    """
    if sys.platform != "win32":
        raise OSError("opensnap:// protocol registration is only supported on Windows")

    import winreg

    exe = Path(exe_path) if exe_path else default_exe_path()
    if not exe.exists():
        raise FileNotFoundError(f"Cannot register protocol; EXE not found: {exe}")

    command = protocol_command(exe)
    key_path = rf"Software\Classes\{PROTOCOL_SCHEME}"
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path) as root:
        winreg.SetValueEx(root, None, 0, winreg.REG_SZ, PROTOCOL_NAME)
        winreg.SetValueEx(root, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKeyEx(root, r"DefaultIcon") as icon:
            winreg.SetValueEx(icon, None, 0, winreg.REG_SZ, f"{exe},0")
        with winreg.CreateKeyEx(root, r"shell\open\command") as cmd:
            winreg.SetValueEx(cmd, None, 0, winreg.REG_SZ, command)
    return exe


def unregister_protocol() -> None:
    """Remove the HKCU `opensnap://` registration if present."""
    if sys.platform != "win32":
        return
    import winreg

    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{PROTOCOL_SCHEME}\shell\open\command")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{PROTOCOL_SCHEME}\shell\open")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{PROTOCOL_SCHEME}\shell")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{PROTOCOL_SCHEME}\DefaultIcon")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{PROTOCOL_SCHEME}")
    except FileNotFoundError:
        pass


def is_protocol_registered() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{PROTOCOL_SCHEME}\shell\open\command"):
            return True
    except FileNotFoundError:
        return False
