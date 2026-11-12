from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models.entities import (
    AuditLog,
    CaptureSourceType,
    CaptureType,
    Patient,
    ProcedureSession,
    ProcedureType,
    Recording,
    Report,
    SessionStatus,
    Snapshot,
)
from app.schemas.api import SessionCreate, SessionUpdate
from app.services.pdf_report import PdfReportGenerator, density_warning
from app.services.storage import StorageManager, generate_session_public_id
from app.services.video.pipeline import PipelineConfig, get_video_pipeline


PREDEFINED_PROCEDURES = [
    "Prostate biopsy",
    "Diagnostic cystoscopy",
    "Transrectal ultrasound",
    "SpaceOAR and fiducial marker placement",
    "Other / Custom Procedure",
]


class SessionService:
    def __init__(self) -> None:
        self.storage = StorageManager()
        self.pdf = PdfReportGenerator()
        self.pipeline = get_video_pipeline()

    def seed_procedure_types(self, db: Session) -> None:
        existing = {p.name for p in db.query(ProcedureType).all()}
        for name in PREDEFINED_PROCEDURES:
            if name not in existing:
                db.add(ProcedureType(name=name, is_custom=False))
        db.commit()

    def create_session(self, db: Session, payload: SessionCreate) -> ProcedureSession:
        if payload.procedure_type == "Other / Custom Procedure" and not (
            payload.custom_procedure_name and payload.custom_procedure_name.strip()
        ):
            raise ValueError("Custom procedure name is required")

        public_id = generate_session_public_id()
        session_path = self.storage.create_session_tree(public_id)

        patient = Patient(
            first_name=payload.patient.first_name.strip(),
            last_name=payload.patient.last_name.strip(),
            date_of_birth=payload.patient.date_of_birth,
            medical_record_number=payload.patient.medical_record_number.strip(),
        )
        db.add(patient)
        db.flush()

        try:
            capture_source = CaptureSourceType(payload.capture_source)
        except ValueError as exc:
            raise ValueError("Invalid capture source") from exc

        session = ProcedureSession(
            public_id=public_id,
            patient_id=patient.id,
            procedure_type=payload.procedure_type,
            custom_procedure_name=(payload.custom_procedure_name or None),
            physician=payload.physician.strip(),
            location=payload.location.strip(),
            procedure_date=payload.procedure_date,
            procedure_time=payload.procedure_time,
            status=SessionStatus.ready,
            notes="",
            storage_path=str(session_path),
            capture_source=capture_source,
            capture_device_id=payload.capture_device_id,
            resolution=payload.resolution,
            requested_fps=payload.requested_fps,
            snapshot_interval_sec=payload.snapshot_interval_sec,
            images_per_page=payload.images_per_page,
        )
        db.add(session)

        # Procedure type bookkeeping
        proc = (
            db.query(ProcedureType)
            .filter(ProcedureType.name == payload.procedure_type)
            .one_or_none()
        )
        if proc:
            proc.use_count += 1
        if (
            payload.procedure_type == "Other / Custom Procedure"
            and payload.save_custom_procedure
            and payload.custom_procedure_name
        ):
            custom_name = payload.custom_procedure_name.strip()
            existing_custom = (
                db.query(ProcedureType).filter(ProcedureType.name == custom_name).one_or_none()
            )
            if existing_custom is None:
                db.add(ProcedureType(name=custom_name, is_custom=True, use_count=1))
            else:
                existing_custom.use_count += 1

        db.add(
            AuditLog(
                action="session_created",
                actor="desktop",
                session_public_id=public_id,
                detail="Session created",
            )
        )
        db.commit()
        db.refresh(session)

        self.storage.write_metadata(
            session_path,
            {
                "public_id": public_id,
                "procedure_type": session.display_procedure_name,
                "created_at": datetime.utcnow().isoformat(),
            },
        )

        self.pipeline.reset_session_counters()
        self.pipeline.configure(
            PipelineConfig(
                source_type=capture_source.value,
                device_id=payload.capture_device_id,
                resolution=payload.resolution,
                requested_fps=payload.requested_fps,
                snapshot_interval_sec=payload.snapshot_interval_sec,
                session_public_id=public_id,
                video_dir=session_path / "video",
                snapshots_dir=session_path / "snapshots",
                thumbnails_dir=session_path / "thumbnails",
            )
        )
        return session

    def get_by_public_id(self, db: Session, public_id: str) -> Optional[ProcedureSession]:
        return (
            db.query(ProcedureSession)
            .options(
                joinedload(ProcedureSession.patient),
                joinedload(ProcedureSession.snapshots),
                joinedload(ProcedureSession.reports),
                joinedload(ProcedureSession.recordings),
            )
            .filter(ProcedureSession.public_id == public_id)
            .one_or_none()
        )

    def list_sessions(
        self,
        db: Session,
        q: Optional[str] = None,
        procedure_type: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 50,
    ) -> list[ProcedureSession]:
        query = db.query(ProcedureSession).options(joinedload(ProcedureSession.patient))
        if procedure_type:
            query = query.filter(
                or_(
                    ProcedureSession.procedure_type == procedure_type,
                    ProcedureSession.custom_procedure_name == procedure_type,
                )
            )
        if date_from:
            query = query.filter(ProcedureSession.procedure_date >= date_from)
        if date_to:
            query = query.filter(ProcedureSession.procedure_date <= date_to)
        if q:
            like = f"%{q}%"
            query = query.join(Patient).filter(
                or_(
                    Patient.first_name.ilike(like),
                    Patient.last_name.ilike(like),
                    Patient.medical_record_number.ilike(like),
                    ProcedureSession.physician.ilike(like),
                    ProcedureSession.public_id.ilike(like),
                )
            )
        return query.order_by(ProcedureSession.created_at.desc()).limit(limit).all()

    def update_session(
        self, db: Session, session: ProcedureSession, payload: SessionUpdate
    ) -> ProcedureSession:
        if payload.notes is not None:
            session.notes = payload.notes
        if payload.snapshot_interval_sec is not None:
            session.snapshot_interval_sec = payload.snapshot_interval_sec
            metrics = self.pipeline.recording_metrics()
            if metrics.get("session_public_id") == session.public_id:
                self.pipeline.update_snapshot_interval(payload.snapshot_interval_sec)
        if payload.images_per_page is not None:
            session.images_per_page = payload.images_per_page
        if payload.physician is not None:
            session.physician = payload.physician
        if payload.location is not None:
            session.location = payload.location
        db.commit()
        db.refresh(session)
        return session

    def attach_session_for_review(self, session: ProcedureSession) -> None:
        """Re-bind pipeline directories for an existing session without starting capture if idle."""
        path = Path(session.storage_path)
        self.pipeline.configure(
            PipelineConfig(
                source_type=session.capture_source.value,
                device_id=session.capture_device_id,
                resolution=session.resolution,
                requested_fps=session.requested_fps,
                snapshot_interval_sec=session.snapshot_interval_sec,
                session_public_id=session.public_id,
                video_dir=path / "video",
                snapshots_dir=path / "snapshots",
                thumbnails_dir=path / "thumbnails",
            )
        )

    def persist_snapshot_meta(self, db: Session, session: ProcedureSession, meta: dict) -> Snapshot:
        snap = Snapshot(
            session_id=session.id,
            file_path=meta["file_path"],
            thumbnail_path=meta.get("thumbnail_path"),
            capture_timestamp=meta["capture_timestamp"],
            capture_type=CaptureType(meta["capture_type"]),
            selected=False,
            caption="",
            display_order=None,
            sequence_number=meta["sequence_number"],
        )
        db.add(snap)
        db.commit()
        db.refresh(snap)
        return snap

    def sync_pipeline_snapshots(self, db: Session, session: ProcedureSession) -> int:
        """Persist any snapshots recorded by the pipeline that are not yet in DB."""
        metrics = self.pipeline.recording_metrics()
        if metrics.get("session_public_id") != session.public_id:
            return 0
        existing = {s.sequence_number for s in session.snapshots}
        added = 0
        for meta in metrics.get("last_snapshots", []):
            if meta["sequence_number"] in existing:
                continue
            # Also skip if file already linked somehow
            self.persist_snapshot_meta(db, session, meta)
            existing.add(meta["sequence_number"])
            added += 1
        if added:
            db.refresh(session)
        return added

    def start_recording(self, db: Session, session: ProcedureSession) -> tuple[bool, str]:
        self.attach_session_for_review(session)
        ok, message = self.pipeline.start_recording()
        if ok:
            session.status = SessionStatus.recording
            session.recording_start_time = datetime.utcnow()
            db.add(
                AuditLog(
                    action="recording_started",
                    actor="system",
                    session_public_id=session.public_id,
                    detail=message,
                )
            )
            db.commit()
        return ok, message

    def stop_recording(self, db: Session, session: ProcedureSession) -> tuple[bool, str]:
        ok, message, final_path = self.pipeline.stop_recording()
        self.sync_pipeline_snapshots(db, session)
        metrics = self.pipeline.recording_metrics()
        if ok:
            session.status = SessionStatus.stopped
            session.recording_stop_time = datetime.utcnow()
            if final_path:
                file_size = final_path.stat().st_size if final_path.exists() else None
                checksum = None
                integrity = "ok"
                try:
                    if final_path.exists():
                        checksum = self.storage.sha256_file(final_path)
                except OSError:
                    integrity = "checksum_failed"
                rec = Recording(
                    session_id=session.id,
                    file_path=str(final_path),
                    resolution=session.resolution,
                    requested_frame_rate=session.requested_fps,
                    actual_frame_rate=metrics.get("actual_fps"),
                    duration_sec=metrics.get("elapsed_sec"),
                    file_size_bytes=file_size,
                    integrity_status=integrity,
                    checksum_sha256=checksum,
                )
                db.add(rec)
            db.add(
                AuditLog(
                    action="recording_stopped",
                    actor="system",
                    session_public_id=session.public_id,
                    detail=message,
                )
            )
            db.commit()
        return ok, message

    def manual_snapshot(self, db: Session, session: ProcedureSession) -> tuple[bool, str, Optional[Snapshot]]:
        ok, message, meta = self.pipeline.take_manual_snapshot()
        if not ok or meta is None:
            return ok, message, None
        snap = self.persist_snapshot_meta(db, session, meta)
        return True, message, snap

    def generate_report(
        self,
        db: Session,
        session: ProcedureSession,
        notes: Optional[str],
        images_per_page: Optional[int],
        include_captions: bool = True,
        include_timestamps: bool = True,
        practice_overrides: Optional[dict] = None,
    ) -> tuple[Report, Optional[str]]:
        if notes is not None:
            session.notes = notes
        if images_per_page is not None:
            session.images_per_page = images_per_page
        ipp = session.images_per_page
        warning = density_warning(ipp)

        version = (max((r.version for r in session.reports), default=0)) + 1
        reports_dir = Path(session.storage_path) / "reports"
        out_path = reports_dir / f"report_v{version}.pdf"
        self.pdf.generate(
            session=session,
            snapshots=list(session.snapshots),
            notes=session.notes,
            images_per_page=ipp,
            output_path=out_path,
            include_captions=include_captions,
            include_timestamps=include_timestamps,
            practice_overrides=practice_overrides,
        )
        report = Report(
            session_id=session.id,
            notes=session.notes,
            images_per_page=ipp,
            pdf_path=str(out_path),
            version=version,
        )
        db.add(report)
        db.add(
            AuditLog(
                action="report_generated",
                actor="desktop",
                session_public_id=session.public_id,
                detail=f"version={version}",
            )
        )
        db.commit()
        db.refresh(report)
        return report, warning


_session_service: Optional[SessionService] = None


def get_session_service() -> SessionService:
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service
