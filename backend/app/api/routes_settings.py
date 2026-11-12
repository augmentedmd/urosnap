from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_desktop_auth
from app.database import get_db
from app.schemas.api import SettingsOut, SettingsUpdate, StorageBrowseOut
from app.services.settings_store import browse_storage, get_all_settings, update_settings

router = APIRouter(
    prefix="/api/settings",
    tags=["settings"],
    dependencies=[Depends(require_desktop_auth)],
)


@router.get("", response_model=SettingsOut)
def read_settings(db: Session = Depends(get_db)) -> SettingsOut:
    return get_all_settings(db)


@router.patch("", response_model=SettingsOut)
def patch_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsOut:
    try:
        return update_settings(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/storage/browse", response_model=StorageBrowseOut)
def storage_browse(path: Optional[str] = Query(default=None)) -> StorageBrowseOut:
    """Browse local folders on the Windows recorder for the save-to directory."""
    return browse_storage(path)
