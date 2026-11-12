from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.api.deps import require_desktop_auth
from app.database import get_db
from app.schemas.api import SettingsOut, SettingsUpdate, StorageBrowseOut
from app.services.pdf_report import custom_logo_path, report_logo_path
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


@router.get("/report-logo")
def read_report_logo() -> FileResponse:
    path = report_logo_path()
    if path is None:
        raise HTTPException(status_code=404, detail="No report logo")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.get("/report-logo/info")
def report_logo_info() -> dict:
    return {"custom": custom_logo_path().exists()}


@router.post("/report-logo")
async def upload_report_logo(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Logo must be under 10 MB")
    try:
        with PILImage.open(io.BytesIO(data)) as im:
            im.load()
            logo = im.convert("RGBA")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Logo must be a PNG or JPEG image") from exc
    # Normalize to PNG so ReportLab can embed it regardless of the uploaded format.
    target = custom_logo_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    logo.save(target, format="PNG")
    return {"custom": True}


@router.delete("/report-logo")
def reset_report_logo() -> dict:
    custom_logo_path().unlink(missing_ok=True)
    return {"custom": False}


@router.get("/storage/browse", response_model=StorageBrowseOut)
def storage_browse(path: Optional[str] = Query(default=None)) -> StorageBrowseOut:
    """Browse local folders on the Windows recorder for the save-to directory."""
    return browse_storage(path)
