from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_sessions, load_session, require_desktop_auth
from app.database import get_db
from app.models.entities import ProcedureSession, ProcedureType, Snapshot
from app.schemas.api import (
    PatientOut,
    RecordingStatus,
    ReportCreate,
    ReportOut,
    SessionCreate,
    SessionDetail,
    SessionSummary,
    SessionUpdate,
    SnapshotBulkUpdate,
    SnapshotOut,
    SnapshotUpdate,
)
from app.services.sessions import SessionService
from app.services.video.pipeline import get_video_pipeline

router = APIRouter(prefix="/api", tags=["sessions"], dependencies=[Depends(require_desktop_auth)])


def _summary(session: ProcedureSession) -> SessionSummary:
    return SessionSummary(
        id=session.id,
        public_id=session.public_id,
        procedure_type=session.procedure_type,
        custom_procedure_name=session.custom_procedure_name,
        display_procedure_name=session.display_procedure_name,
        physician=session.physician,
        location=session.location,
        procedure_date=session.procedure_date,
        procedure_time=session.procedure_time,
        status=session.status.value if hasattr(session.status, "value") else str(session.status),
        created_at=session.created_at,
        recording_start_time=session.recording_start_time,
        recording_stop_time=session.recording_stop_time,
        patient_name=(
            f"{session.patient.last_name}, {session.patient.first_name}".strip(", ").strip()
            or "Unnamed patient"
        ),
        medical_record_number=session.patient.medical_record_number or "—",
        snapshot_count=len(session.snapshots) if session.snapshots is not None else 0,
    )


def _patient_out(patient) -> PatientOut:
    dob = patient.date_of_birth
    return PatientOut(
        id=patient.id,
        first_name=patient.first_name or "",
        last_name=patient.last_name or "",
        date_of_birth=None if dob is None or getattr(dob, "year", 1901) <= 1900 else dob,
        medical_record_number=patient.medical_record_number or "",
    )


def _detail(session: ProcedureSession) -> SessionDetail:
    base = _summary(session)
    return SessionDetail(
        **base.model_dump(),
        notes=session.notes,
        capture_source=session.capture_source.value,
        capture_device_id=session.capture_device_id,
        resolution=session.resolution,
        requested_fps=session.requested_fps,
        snapshot_interval_sec=session.snapshot_interval_sec,
        images_per_page=session.images_per_page,
        storage_path=session.storage_path,
        patient=_patient_out(session.patient),
    )


def _snapshot_out(snap: Snapshot, public_id: str) -> SnapshotOut:
    return SnapshotOut(
        id=snap.id,
        session_id=snap.session_id,
        capture_timestamp=snap.capture_timestamp,
        capture_type=snap.capture_type.value,
        selected=snap.selected,
        caption=snap.caption,
        display_order=snap.display_order,
        sequence_number=snap.sequence_number,
        thumbnail_url=f"/api/sessions/{public_id}/snapshots/{snap.id}/thumbnail",
        image_url=f"/api/sessions/{public_id}/snapshots/{snap.id}/image",
    )


def _recording_status(session: Optional[ProcedureSession] = None) -> RecordingStatus:
    pipeline = get_video_pipeline()
    metrics = pipeline.recording_metrics()
    capture = pipeline.capture_status()
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
        capture=capture,
        warning=metrics.get("warning"),
        error=metrics.get("error"),
        remote_connected=bool(metrics.get("remote_connected")),
    )


@router.post("/sessions", response_model=SessionDetail)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
    sessions: SessionService = Depends(get_sessions),
) -> SessionDetail:
    try:
        session = sessions.create_session(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session = sessions.get_by_public_id(db, session.public_id)
    assert session is not None
    return _detail(session)


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions(
    q: Optional[str] = None,
    procedure_type: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    sessions: SessionService = Depends(get_sessions),
) -> list[SessionSummary]:
    rows = sessions.list_sessions(
        db, q=q, procedure_type=procedure_type, date_from=date_from, date_to=date_to, limit=limit
    )
    return [_summary(s) for s in rows]


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(session: ProcedureSession = Depends(load_session)) -> SessionDetail:
    return _detail(session)


@router.patch("/sessions/{session_id}", response_model=SessionDetail)
def patch_session(
    payload: SessionUpdate,
    session: ProcedureSession = Depends(load_session),
    db: Session = Depends(get_db),
    sessions: SessionService = Depends(get_sessions),
) -> SessionDetail:
    session = sessions.update_session(db, session, payload)
    session = sessions.get_by_public_id(db, session.public_id)
    assert session is not None
    return _detail(session)


@router.post("/sessions/{session_id}/recording/start", response_model=RecordingStatus)
def start_recording(
    session: ProcedureSession = Depends(load_session),
    db: Session = Depends(get_db),
    sessions: SessionService = Depends(get_sessions),
) -> RecordingStatus:
    ok, message = sessions.start_recording(db, session)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return _recording_status(session)


@router.post("/sessions/{session_id}/recording/stop", response_model=RecordingStatus)
def stop_recording(
    session: ProcedureSession = Depends(load_session),
    db: Session = Depends(get_db),
    sessions: SessionService = Depends(get_sessions),
) -> RecordingStatus:
    ok, message = sessions.stop_recording(db, session)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return _recording_status(session)


@router.get("/sessions/{session_id}/recording/status", response_model=RecordingStatus)
def recording_status(
    session: ProcedureSession = Depends(load_session),
    db: Session = Depends(get_db),
    sessions: SessionService = Depends(get_sessions),
) -> RecordingStatus:
    sessions.sync_pipeline_snapshots(db, session)
    return _recording_status(session)


@router.get("/recording/status", response_model=RecordingStatus)
def global_recording_status() -> RecordingStatus:
    return _recording_status()


@router.post("/sessions/{session_id}/snapshots", response_model=SnapshotOut)
def take_snapshot(
    session: ProcedureSession = Depends(load_session),
    db: Session = Depends(get_db),
    sessions: SessionService = Depends(get_sessions),
) -> SnapshotOut:
    ok, message, snap = sessions.manual_snapshot(db, session)
    if not ok or snap is None:
        raise HTTPException(status_code=400, detail=message)
    return _snapshot_out(snap, session.public_id)


@router.get("/sessions/{session_id}/snapshots", response_model=list[SnapshotOut])
def list_snapshots(
    session: ProcedureSession = Depends(load_session),
    db: Session = Depends(get_db),
    sessions: SessionService = Depends(get_sessions),
) -> list[SnapshotOut]:
    sessions.sync_pipeline_snapshots(db, session)
    session = sessions.get_by_public_id(db, session.public_id)
    assert session is not None
    snaps = sorted(session.snapshots, key=lambda s: s.sequence_number)
    return [_snapshot_out(s, session.public_id) for s in snaps]


@router.patch("/snapshots/{snapshot_id}", response_model=SnapshotOut)
def update_snapshot(
    snapshot_id: int,
    payload: SnapshotUpdate,
    db: Session = Depends(get_db),
) -> SnapshotOut:
    snap = db.query(Snapshot).filter(Snapshot.id == snapshot_id).one_or_none()
    if snap is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    if payload.selected is not None:
        snap.selected = payload.selected
        if payload.selected and snap.display_order is None:
            max_order = max(
                (s.display_order or 0 for s in snap.session.snapshots if s.selected),
                default=0,
            )
            snap.display_order = max_order + 1
        if not payload.selected:
            snap.display_order = None
    if payload.caption is not None:
        snap.caption = payload.caption
    if payload.display_order is not None:
        snap.display_order = payload.display_order
    db.commit()
    db.refresh(snap)
    return _snapshot_out(snap, snap.session.public_id)


@router.post("/sessions/{session_id}/snapshots/selection", response_model=list[SnapshotOut])
def bulk_selection(
    payload: SnapshotBulkUpdate,
    session: ProcedureSession = Depends(load_session),
    db: Session = Depends(get_db),
) -> list[SnapshotOut]:
    selected_set = set(payload.selected_ids)
    for snap in session.snapshots:
        snap.selected = snap.id in selected_set
        if not snap.selected:
            snap.display_order = None
    if payload.ordered_ids:
        for idx, sid in enumerate(payload.ordered_ids, start=1):
            for snap in session.snapshots:
                if snap.id == sid:
                    snap.selected = True
                    snap.display_order = idx
    db.commit()
    snaps = sorted(session.snapshots, key=lambda s: s.sequence_number)
    return [_snapshot_out(s, session.public_id) for s in snaps]


@router.get("/sessions/{session_id}/snapshots/{snapshot_id}/image")
def snapshot_image(
    snapshot_id: int,
    session: ProcedureSession = Depends(load_session),
) -> FileResponse:
    snap = next((s for s in session.snapshots if s.id == snapshot_id), None)
    if snap is None or not Path(snap.file_path).exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(snap.file_path, media_type="image/jpeg")


@router.get("/sessions/{session_id}/snapshots/{snapshot_id}/thumbnail")
def snapshot_thumbnail(
    snapshot_id: int,
    session: ProcedureSession = Depends(load_session),
) -> FileResponse:
    snap = next((s for s in session.snapshots if s.id == snapshot_id), None)
    if snap is None:
        raise HTTPException(status_code=404, detail="Image not found")
    path = Path(snap.thumbnail_path or snap.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(path, media_type="image/jpeg")


def _placeholder_jpeg(message: str = "Starting preview...") -> bytes:
    import cv2
    import numpy as np

    img = np.zeros((360, 640, 3), dtype=np.uint8)
    img[:] = (28, 28, 28)
    cv2.putText(
        img,
        message,
        (36, 190),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (220, 220, 220),
        2,
        cv2.LINE_AA,
    )
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    return buf.tobytes() if ok else b""


@router.get("/sessions/{session_id}/preview.jpg")
def preview_jpeg(session: ProcedureSession = Depends(load_session)) -> Response:
    """Single JPEG frame for the recording UI (polled; must not restart capture each time)."""
    pipeline = get_video_pipeline()
    from app.services.sessions import get_session_service

    # Idempotent bind — configure() no longer restarts when already attached.
    get_session_service().attach_session_for_review(session)
    # Never block the API worker waiting for frames — that starved Start/Stop.
    frame = pipeline.get_latest_jpeg()
    if frame is None:
        frame = _placeholder_jpeg()
    return Response(
        content=frame,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get("/sessions/{session_id}/preview.mjpg")
def preview_stream(session: ProcedureSession = Depends(load_session)) -> StreamingResponse:
    pipeline = get_video_pipeline()
    from app.services.sessions import get_session_service

    get_session_service().attach_session_for_review(session)

    def gen():
        while True:
            frame = pipeline.wait_for_jpeg(timeout=1.0)
            if frame is None:
                continue
            yield (
                b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                + str(len(frame)).encode()
                + b"\r\n\r\n"
                + frame
                + b"\r\n"
            )

    return StreamingResponse(
        gen(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.post("/sessions/{session_id}/reports", response_model=ReportOut)
def create_report(
    payload: ReportCreate,
    session: ProcedureSession = Depends(load_session),
    db: Session = Depends(get_db),
    sessions: SessionService = Depends(get_sessions),
) -> ReportOut:
    from app.services.settings_store import get_all_settings

    settings = get_all_settings(db)
    report, _warning = sessions.generate_report(
        db,
        session,
        notes=payload.notes,
        images_per_page=payload.images_per_page,
        include_captions=payload.include_captions,
        include_timestamps=payload.include_timestamps,
        practice_overrides={
            "name": settings.practice_name,
            "line1": settings.practice_address_line1,
            "line2": settings.practice_address_line2,
            "phone": settings.practice_phone,
        },
    )
    return ReportOut(
        id=report.id,
        session_id=report.session_id,
        notes=report.notes,
        images_per_page=report.images_per_page,
        version=report.version,
        created_at=report.created_at,
        download_url=f"/api/reports/{report.id}/download",
        preview_url=f"/api/reports/{report.id}/preview",
    )


@router.get("/sessions/{session_id}/reports", response_model=list[ReportOut])
def list_reports(session: ProcedureSession = Depends(load_session)) -> list[ReportOut]:
    return [
        ReportOut(
            id=r.id,
            session_id=r.session_id,
            notes=r.notes,
            images_per_page=r.images_per_page,
            version=r.version,
            created_at=r.created_at,
            download_url=f"/api/reports/{r.id}/download",
            preview_url=f"/api/reports/{r.id}/preview",
        )
        for r in sorted(session.reports, key=lambda x: x.version)
    ]


@router.get("/reports/{report_id}/download")
@router.get("/reports/{report_id}/preview")
def download_report(report_id: int, db: Session = Depends(get_db)) -> FileResponse:
    from app.models.entities import Report

    report = db.query(Report).filter(Report.id == report_id).one_or_none()
    if report is None or not Path(report.pdf_path).exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(
        report.pdf_path,
        media_type="application/pdf",
        filename=Path(report.pdf_path).name,
    )


@router.get("/procedure-types")
def procedure_types(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(ProcedureType).order_by(ProcedureType.is_custom.asc(), ProcedureType.name.asc()).all()
    return [
        {"id": r.id, "name": r.name, "is_custom": r.is_custom, "use_count": r.use_count}
        for r in rows
    ]


@router.get("/sessions/{session_id}/video")
def get_video(session: ProcedureSession = Depends(load_session)) -> Response:
    if not session.recordings:
        raise HTTPException(status_code=404, detail="No recording")
    rec = sorted(session.recordings, key=lambda r: r.created_at)[-1]
    path = Path(rec.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Recording file missing")
    media = "video/mp4" if path.suffix.lower() == ".mp4" else "video/x-msvideo"
    return FileResponse(path, media_type=media, filename=path.name)
