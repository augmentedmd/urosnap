from __future__ import annotations

import ipaddress
import socket
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

LOOPBACK_NAMES = {"localhost", "127.0.0.1", "::1", "[::1]"}


def is_loopback_host(host: Optional[str]) -> bool:
    if not host:
        return False
    host = host.strip("[]").lower()
    if host in LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def lan_ip() -> Optional[str]:
    """Best-guess IPv4 address of this PC on the local network."""
    try:
        # UDP connect sends no packets; it only selects the outbound interface.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            ip = sock.getsockname()[0]
            if not ipaddress.ip_address(ip).is_loopback:
                return ip
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ipaddress.ip_address(ip).is_loopback:
                return ip
    except OSError:
        pass
    return None


def to_lan_base(base_url: str, default_port: int) -> str:
    """Rewrite a loopback base URL so a phone on the same network can reach it."""
    parts = urlsplit(base_url)
    if not is_loopback_host(parts.hostname):
        return base_url.rstrip("/")
    ip = lan_ip()
    if not ip:
        return base_url.rstrip("/")
    port = parts.port or default_port
    return urlunsplit((parts.scheme or "http", f"{ip}:{port}", "", "", "")).rstrip("/")
