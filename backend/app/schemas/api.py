from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


ALLOWED_FPS = {5, 10, 15, 24, 30, 60}
SNAPSHOT_PRESETS = {1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 30.0, 60.0}


class PatientCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    date_of_birth: date
    medical_record_number: str = Field(min_length=1, max_length=64)


class PatientOut(PatientCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class SessionCreate(BaseModel):
    patient: PatientCreate
    procedure_type: str = Field(min_length=1, max_length=200)
    custom_procedure_name: Optional[str] = Field(default=None, max_length=200)
    save_custom_procedure: bool = False
    physician: str = Field(min_length=1, max_length=200)
    location: str = Field(min_length=1, max_length=200)
    procedure_date: date
    procedure_time: Optional[time] = None
    capture_source: str = "synthetic"
    capture_device_id: Optional[str] = None
    resolution: str = "1280x720"
    requested_fps: int = 15
    snapshot_interval_sec: float = 3.0
    images_per_page: int = 4

    @field_validator("requested_fps")
    @classmethod
    def validate_fps(cls, v: int) -> int:
        if v not in ALLOWED_FPS:
            raise ValueError(f"Frame rate must be one of {sorted(ALLOWED_FPS)}")
        return v

    @field_validator("snapshot_interval_sec")
    @classmethod
    def validate_interval(cls, v: float) -> float:
        if v < 0.5 or v > 120:
            raise ValueError("Snapshot interval must be between 0.5 and 120 seconds")
        return v

    @field_validator("images_per_page")
    @classmethod
    def validate_ipp(cls, v: int) -> int:
        if v < 1 or v > 20:
            raise ValueError("Images per page must be between 1 and 20")
        return v


class SessionUpdate(BaseModel):
    notes: Optional[str] = None
    snapshot_interval_sec: Optional[float] = None
    images_per_page: Optional[int] = None
    status: Optional[str] = None
    physician: Optional[str] = None
    location: Optional[str] = None

    @field_validator("snapshot_interval_sec")
    @classmethod
    def validate_interval(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0.5 or v > 120):
            raise ValueError("Snapshot interval must be between 0.5 and 120 seconds")
        return v

    @field_validator("images_per_page")
    @classmethod
    def validate_ipp(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 1 or v > 20):
            raise ValueError("Images per page must be between 1 and 20")
        return v


class SessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    public_id: str
    procedure_type: str
    custom_procedure_name: Optional[str]
    display_procedure_name: str
    physician: str
    location: str
    procedure_date: date
    procedure_time: Optional[time]
    status: str
    created_at: datetime
    recording_start_time: Optional[datetime]
    recording_stop_time: Optional[datetime]
    patient_name: str
    medical_record_number: str
    snapshot_count: int = 0


class SessionDetail(SessionSummary):
    notes: str
    capture_source: str
    capture_device_id: Optional[str]
    resolution: str
    requested_fps: int
    snapshot_interval_sec: float
    images_per_page: int
    storage_path: str
    patient: PatientOut


class CaptureDevice(BaseModel):
    id: str
    name: str
    index: Optional[int] = None
    source_type: str
    resolutions: list[str] = Field(default_factory=list)
    frame_rates: list[int] = Field(default_factory=list)
    available: bool = True


class CaptureStatus(BaseModel):
    connected: bool
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    source_type: Optional[str] = None
    incoming_fps: Optional[float] = None
    error: Optional[str] = None


class RecordingStatus(BaseModel):
    session_public_id: Optional[str] = None
    state: str  # idle | ready | recording | stopped | error
    elapsed_sec: float = 0.0
    requested_fps: Optional[int] = None
    actual_fps: Optional[float] = None
    incoming_fps: Optional[float] = None
    snapshot_interval_sec: Optional[float] = None
    snapshot_count: int = 0
    manual_snapshot_count: int = 0
    automatic_snapshot_count: int = 0
    capture: CaptureStatus
    warning: Optional[str] = None
    error: Optional[str] = None
    remote_connected: bool = False


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    capture_timestamp: datetime
    capture_type: str
    selected: bool
    caption: str
    display_order: Optional[int]
    sequence_number: int
    thumbnail_url: str
    image_url: str


class SnapshotUpdate(BaseModel):
    selected: Optional[bool] = None
    caption: Optional[str] = None
    display_order: Optional[int] = None


class SnapshotBulkUpdate(BaseModel):
    selected_ids: list[int]
    ordered_ids: Optional[list[int]] = None


class ReportCreate(BaseModel):
    notes: Optional[str] = None
    images_per_page: Optional[int] = None
    include_captions: bool = True
    include_timestamps: bool = True


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    notes: str
    images_per_page: int
    version: int
    created_at: datetime
    download_url: str
    preview_url: str


class PairingCreateOut(BaseModel):
    pairing_url: str
    token: str
    expires_at: datetime
    qr_payload: str


class PairingClaim(BaseModel):
    token: str
    controller_id: Optional[str] = None


class PairingClaimOut(BaseModel):
    access_token: str
    session_public_id: str
    expires_at: datetime


class RemoteCommand(BaseModel):
    command_id: str = Field(min_length=8, max_length=64)
    action: str  # start | stop | snapshot


class RemoteCommandResult(BaseModel):
    command_id: str
    action: str
    success: bool
    message: str
    status: RecordingStatus


class ProcedureTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_custom: bool
    use_count: int


class HealthOut(BaseModel):
    status: str
    service: str
    version: str
    disk_free_bytes: int
    disk_total_bytes: int
    low_disk: bool
    active_session_id: Optional[str]
    recording_state: str
    capture: CaptureStatus
    warnings: list[str] = Field(default_factory=list)


class SettingsOut(BaseModel):
    practice_name: str
    practice_address_line1: str
    practice_address_line2: str
    practice_phone: str
    default_fps: int
    default_snapshot_interval_sec: float
    default_images_per_page: int
    default_resolution: str
    default_capture_source: str
    preferred_physician: str = ""
    preferred_procedure_type: str = ""
    preferred_capture_device_id: str = ""
    storage_path: str
    pairing_token_ttl_seconds: int
    data: dict[str, Any] = Field(default_factory=dict)


class SettingsUpdate(BaseModel):
    practice_name: Optional[str] = None
    practice_address_line1: Optional[str] = None
    practice_address_line2: Optional[str] = None
    practice_phone: Optional[str] = None
    default_fps: Optional[int] = None
    default_snapshot_interval_sec: Optional[float] = None
    default_images_per_page: Optional[int] = None
    default_resolution: Optional[str] = None
    default_capture_source: Optional[str] = None
    preferred_physician: Optional[str] = None
    preferred_procedure_type: Optional[str] = None
    preferred_capture_device_id: Optional[str] = None
    pairing_token_ttl_seconds: Optional[int] = None
