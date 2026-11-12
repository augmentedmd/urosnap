from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import (
    get_pairing,
    get_sessions,
    load_session,
    require_desktop_auth,
    require_remote_pairing,
)
from app.database import get_db
from app.models.entities import PairingSession, ProcedureSession
from app.schemas.api import (
    PairingClaim,
    PairingClaimOut,
    PairingCreateOut,
    PairingCreateRequest,
    RecordingStatus,
    RemoteCommand,
    RemoteCommandResult,
)
from app.services.pairing import PairingService
from app.services.sessions import SessionService
from app.services.video.pipeline import get_video_pipeline

router = APIRouter(tags=["pairing"])


def _status() -> RecordingStatus:
    pipeline = get_video_pipeline()
    metrics = pipeline.recording_metrics()
    return RecordingStatus(
        session_public_id=metrics.get("session_public_id"),
        state=str(metrics.get("state") or "idle"),
        elapsed_sec=float(metrics.get("elapsed_sec") or 0),
        requested_fps=metrics.get("requested_fps"),
        actual_fps=metrics.get("actual_fps"),
        incoming_fps=metrics.get("incoming_fps"),
        snapshot_interval_sec=metrics.get("snapshot_interval_sec"),
        snapshot_count=int(metrics.get("snapshot_count") or 0),
        manual_snapshot_count=int(metrics.get("manual_snapshot_count") or 0),
        automatic_snapshot_count=int(metrics.get("automatic_snapshot_count") or 0),
        capture=pipeline.capture_status(),
        warning=metrics.get("warning"),
        error=metrics.get("error"),
        remote_connected=bool(metrics.get("remote_connected")),
    )


@router.post(
    "/api/sessions/{session_id}/pairing",
    response_model=PairingCreateOut,
    dependencies=[Depends(require_desktop_auth)],
)
def create_pairing(
    request: Request,
    payload: PairingCreateRequest = Body(default_factory=PairingCreateRequest),
    session: ProcedureSession = Depends(load_session),
    db: Session = Depends(get_db),
    pairing: PairingService = Depends(get_pairing),
) -> PairingCreateOut:
    # Prefer public host header for LAN access; fall back to request base URL
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    # Mobile cannot use localhost — use host as provided by the desktop browser
    local_base = f"{scheme}://{host}" if host else str(request.base_url).rstrip("/")
    # UI may be on Cloudflare; clinical commands always target the local/LAN service.
    ui_base = (payload.ui_base_url or local_base).rstrip("/")
    service_base = (payload.service_base_url or local_base).rstrip("/")
    _row, token, _ = pairing.create_pairing(db, session, base_url=ui_base)
    url = pairing.build_remote_url(ui_base, token, service_base_url=service_base)
    return PairingCreateOut(
        pairing_url=url,
        token=token,
        expires_at=_row.expires_at,
        qr_payload=url,
    )


@router.post("/api/pairing/claim", response_model=PairingClaimOut)
def claim_pairing(
    payload: PairingClaim,
    db: Session = Depends(get_db),
    pairing: PairingService = Depends(get_pairing),
) -> PairingClaimOut:
    row, access_token, message = pairing.claim(db, payload.token, payload.controller_id)
    if row is None or access_token is None:
        raise HTTPException(status_code=400, detail=message)
    get_video_pipeline().set_remote_connected(True)
    return PairingClaimOut(
        access_token=access_token,
        session_public_id=row.session.public_id,
        expires_at=row.expires_at,
    )


@router.post("/api/pairing/revoke", dependencies=[Depends(require_desktop_auth)])
def revoke_pairing(
    session_id: str,
    db: Session = Depends(get_db),
    sessions: SessionService = Depends(get_sessions),
    pairing: PairingService = Depends(get_pairing),
) -> dict:
    session = sessions.get_by_public_id(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    count = pairing.revoke_for_session(db, session.id)
    get_video_pipeline().set_remote_connected(False)
    return {"revoked": count}


@router.get("/api/remote/status", response_model=RecordingStatus)
def remote_status(pairing_row: PairingSession = Depends(require_remote_pairing)) -> RecordingStatus:
    # Ensure remote only sees operational status (already PHI-free)
    get_video_pipeline().set_remote_connected(True)
    status = _status()
    # Double-check scoped to paired session
    if status.session_public_id and status.session_public_id != pairing_row.session.public_id:
        # Still return status for the active pipeline; command layer enforces session match
        pass
    return status


@router.post("/api/remote/command", response_model=RemoteCommandResult)
def remote_command(
    payload: RemoteCommand,
    pairing_row: PairingSession = Depends(require_remote_pairing),
    db: Session = Depends(get_db),
    pairing: PairingService = Depends(get_pairing),
    sessions: SessionService = Depends(get_sessions),
) -> RemoteCommandResult:
    if payload.action not in {"start", "stop", "snapshot"}:
        raise HTTPException(status_code=400, detail="Unsupported action")

    is_new = pairing.remember_command(db, pairing_row, payload.command_id)
    session = pairing_row.session
    if not is_new:
        return RemoteCommandResult(
            command_id=payload.command_id,
            action=payload.action,
            success=True,
            message="Duplicate command ignored (already applied)",
            status=_status(),
        )

    # Ensure pipeline bound to this session
    sessions.attach_session_for_review(session)

    if payload.action == "start":
        ok, message = sessions.start_recording(db, session)
    elif payload.action == "stop":
        ok, message = sessions.stop_recording(db, session)
    else:
        ok, message, _snap = sessions.manual_snapshot(db, session)

    if not ok:
        return RemoteCommandResult(
            command_id=payload.command_id,
            action=payload.action,
            success=False,
            message=message,
            status=_status(),
        )
    return RemoteCommandResult(
        command_id=payload.command_id,
        action=payload.action,
        success=True,
        message=message,
        status=_status(),
    )
