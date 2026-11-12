from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.entities import PairingSession, ProcedureSession


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class PairingService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def create_pairing(
        self,
        db: Session,
        session: ProcedureSession,
        base_url: str,
    ) -> tuple[PairingSession, str, str]:
        # Revoke unused open pairings for this session
        for existing in session.pairings:
            if not existing.revoked and existing.claimed_at is None:
                existing.revoked = True

        token = secrets.token_urlsafe(32)
        now = datetime.utcnow()
        pairing = PairingSession(
            procedure_session_id=session.id,
            token_hash=_hash_token(token),
            created_at=now,
            expires_at=now + timedelta(seconds=self.settings.pairing_token_ttl_seconds),
            revoked=False,
        )
        db.add(pairing)
        db.commit()
        db.refresh(pairing)
        pairing_url = f"{base_url.rstrip('/')}/remote/{token}"
        return pairing, token, pairing_url

    def claim(
        self,
        db: Session,
        token: str,
        controller_id: Optional[str] = None,
    ) -> tuple[Optional[PairingSession], Optional[str], str]:
        token_hash = _hash_token(token)
        pairing = db.query(PairingSession).filter(PairingSession.token_hash == token_hash).one_or_none()
        if pairing is None:
            return None, None, "Invalid pairing token"
        if pairing.revoked:
            return None, None, "Pairing revoked"
        if pairing.expires_at < datetime.utcnow() and pairing.claimed_at is None:
            return None, None, "Pairing expired"
        if pairing.controller_id and controller_id and pairing.controller_id != controller_id:
            return None, None, "Another controller is already paired"
        if pairing.controller_id and not controller_id:
            # Reconnect with same claim token later uses access token
            pass

        # One active controller: revoke other claimed pairings for session
        siblings = (
            db.query(PairingSession)
            .filter(
                PairingSession.procedure_session_id == pairing.procedure_session_id,
                PairingSession.id != pairing.id,
                PairingSession.revoked.is_(False),
            )
            .all()
        )
        for sibling in siblings:
            sibling.revoked = True

        if pairing.claimed_at is None:
            pairing.claimed_at = datetime.utcnow()
            pairing.expires_at = datetime.utcnow() + timedelta(
                seconds=self.settings.pairing_session_ttl_seconds
            )
        pairing.controller_id = controller_id or pairing.controller_id or secrets.token_hex(8)
        # Issue access token = original token for prototype (hashed at rest)
        access_token = token
        db.commit()
        db.refresh(pairing)
        return pairing, access_token, "Claimed"

    def resolve_access_token(self, db: Session, access_token: str) -> Optional[PairingSession]:
        pairing = (
            db.query(PairingSession)
            .filter(PairingSession.token_hash == _hash_token(access_token))
            .one_or_none()
        )
        if pairing is None or pairing.revoked:
            return None
        if pairing.claimed_at is None:
            return None
        if pairing.expires_at < datetime.utcnow():
            return None
        return pairing

    def revoke_for_session(self, db: Session, session_id: int) -> int:
        count = 0
        rows = db.query(PairingSession).filter(PairingSession.procedure_session_id == session_id).all()
        for row in rows:
            if not row.revoked:
                row.revoked = True
                count += 1
        db.commit()
        return count

    def remember_command(self, db: Session, pairing: PairingSession, command_id: str) -> bool:
        """Return True if command is new; False if duplicate replay."""
        if pairing.last_command_id == command_id:
            return False
        pairing.last_command_id = command_id
        db.commit()
        return True
