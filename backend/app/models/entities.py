from __future__ import annotations

import enum
from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SessionStatus(str, enum.Enum):
    created = "created"
    ready = "ready"
    recording = "recording"
    stopped = "stopped"
    interrupted = "interrupted"
    completed = "completed"
    error = "error"


class CaptureType(str, enum.Enum):
    automatic = "automatic"
    manual = "manual"


class CaptureSourceType(str, enum.Enum):
    synthetic = "synthetic"
    file = "file"
    camera = "camera"


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    medical_record_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    sessions: Mapped[list[ProcedureSession]] = relationship(back_populates="patient")


class ProcedureType(Base):
    __tablename__ = "procedure_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ProcedureSession(Base):
    __tablename__ = "procedure_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    procedure_type: Mapped[str] = mapped_column(String(200), nullable=False)
    custom_procedure_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    physician: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    procedure_date: Mapped[date] = mapped_column(Date, nullable=False)
    procedure_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, native_enum=False), default=SessionStatus.created, nullable=False
    )
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    # Capture configuration
    capture_source: Mapped[CaptureSourceType] = mapped_column(
        Enum(CaptureSourceType, native_enum=False),
        default=CaptureSourceType.synthetic,
        nullable=False,
    )
    capture_device_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resolution: Mapped[str] = mapped_column(String(32), default="1280x720", nullable=False)
    requested_fps: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    snapshot_interval_sec: Mapped[float] = mapped_column(Float, default=3.0, nullable=False)
    images_per_page: Mapped[int] = mapped_column(Integer, default=4, nullable=False)

    recording_start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    recording_stop_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    patient: Mapped[Patient] = relationship(back_populates="sessions")
    recordings: Mapped[list[Recording]] = relationship(back_populates="session", cascade="all, delete-orphan")
    snapshots: Mapped[list[Snapshot]] = relationship(back_populates="session", cascade="all, delete-orphan")
    reports: Mapped[list[Report]] = relationship(back_populates="session", cascade="all, delete-orphan")
    pairings: Mapped[list[PairingSession]] = relationship(back_populates="session", cascade="all, delete-orphan")

    @property
    def display_procedure_name(self) -> str:
        if self.procedure_type == "Other / Custom Procedure" and self.custom_procedure_name:
            return self.custom_procedure_name
        return self.procedure_type


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("procedure_sessions.id"), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    resolution: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_frame_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_frame_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    integrity_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped[ProcedureSession] = relationship(back_populates="recordings")


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("procedure_sessions.id"), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    capture_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    capture_type: Mapped[CaptureType] = mapped_column(
        Enum(CaptureType, native_enum=False), nullable=False
    )
    selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    caption: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    display_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)

    session: Mapped[ProcedureSession] = relationship(back_populates="snapshots")

    __table_args__ = (UniqueConstraint("session_id", "sequence_number", name="uq_snapshot_seq"),)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("procedure_sessions.id"), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    images_per_page: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    pdf_path: Mapped[str] = mapped_column(String(500), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped[ProcedureSession] = relationship(back_populates="reports")

    __table_args__ = (UniqueConstraint("session_id", "version", name="uq_report_version"),)


class PairingSession(Base):
    __tablename__ = "pairing_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    procedure_session_id: Mapped[int] = mapped_column(
        ForeignKey("procedure_sessions.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    controller_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_command_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    session: Mapped[ProcedureSession] = relationship(back_populates="pairings")


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), default="system", nullable=False)
    session_public_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
