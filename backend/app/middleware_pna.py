from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class PrivateNetworkAccessMiddleware(BaseHTTPMiddleware):
    """Allow Cloudflare-hosted UI (public HTTPS) to call the local OpenSnap service.

    Chrome/Edge send Access-Control-Request-Private-Network on preflight when a
    public site talks to localhost/LAN. Without Access-Control-Allow-Private-Network
    the browser reports the local recording service as unreachable.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if request.headers.get("access-control-request-private-network", "").lower() == "true":
            response.headers["Access-Control-Allow-Private-Network"] = "true"
        # Also advertise on normal responses for clients that check after PNA permission.
        response.headers.setdefault("Access-Control-Allow-Private-Network", "true")
        return response
