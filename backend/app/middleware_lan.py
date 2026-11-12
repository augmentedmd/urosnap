from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.services.network import is_loopback_host

# Devices other than this PC (the paired phone) may only use the PHI-free remote API.
REMOTE_API_PREFIXES = ("/api/pairing/claim", "/api/remote/")
BLOCKED_PREFIXES = ("/api/", "/ws", "/docs", "/redoc", "/openapi.json")


def lan_path_allowed(path: str) -> bool:
    if path.startswith(REMOTE_API_PREFIXES):
        return True
    # Remaining paths are the static SPA shell, which carries no patient data.
    return not path.startswith(BLOCKED_PREFIXES)


class LanRemoteOnlyMiddleware(BaseHTTPMiddleware):
    """Desktop endpoints accept requests without a token, so they must stay loopback-only."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client = request.client.host if request.client else None
        # "testclient" is Starlette's in-process TestClient, not a network peer.
        local = client == "testclient" or is_loopback_host(client)
        if not local and not lan_path_allowed(request.url.path):
            return JSONResponse(
                {"detail": "Only the phone remote is available from other devices"},
                status_code=403,
            )
        return await call_next(request)
