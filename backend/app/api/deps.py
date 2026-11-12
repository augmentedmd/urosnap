from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.entities import PairingSession, ProcedureSession
from app.services.pairing import PairingService
from app.services.sessions import SessionService, get_session_service


def require_desktop_auth(
    x_desktop_token: Optional[str] = Header(default=None, alias="X-Desktop-Token"),
) -> None:
    settings = get_settings()
    # Prototype: accept missing token on localhost-style deployments but prefer header.
    if x_desktop_token is None:
        return
    if x_desktop_token != settings.desktop_api_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid desktop token")


def get_sessions() -> SessionService:
    return get_session_service()


def get_pairing() -> PairingService:
    return PairingService()


def load_session(
    session_id: str,
    db: Session = Depends(get_db),
    sessions: SessionService = Depends(get_sessions),
) -> ProcedureSession:
    session = sessions.get_by_public_id(db, session_id)
    if session is None:
        # Also allow numeric PK for convenience
        if session_id.isdigit():
            from app.models.entities import ProcedureSession as PS

            session = db.query(PS).filter(PS.id == int(session_id)).one_or_none()
            if session is not None:
                session = sessions.get_by_public_id(db, session.public_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def require_remote_pairing(
    authorization: Optional[str] = Header(default=None),
    x_pairing_token: Optional[str] = Header(default=None, alias="X-Pairing-Token"),
    db: Session = Depends(get_db),
    pairing: PairingService = Depends(get_pairing),
) -> PairingSession:
    token = x_pairing_token
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing pairing token")
    row = pairing.resolve_access_token(db, token)
    if row is None:
        raise HTTPException(status_code=401, detail="Invalid or expired pairing")
    return row
