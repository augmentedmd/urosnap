"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-11-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tables are also created via SQLAlchemy metadata on startup.
    # This migration mirrors the initial schema for Alembic tracking.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("patients"):
        return

    op.create_table(
        "patients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("medical_record_number", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "procedure_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("is_custom", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("use_count", sa.Integer(), nullable=False),
    )
    op.create_table(
        "procedure_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False, unique=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("procedure_type", sa.String(200), nullable=False),
        sa.Column("custom_procedure_name", sa.String(200), nullable=True),
        sa.Column("physician", sa.String(200), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("procedure_date", sa.Date(), nullable=False),
        sa.Column("procedure_time", sa.Time(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("capture_source", sa.String(32), nullable=False),
        sa.Column("capture_device_id", sa.String(100), nullable=True),
        sa.Column("resolution", sa.String(32), nullable=False),
        sa.Column("requested_fps", sa.Integer(), nullable=False),
        sa.Column("snapshot_interval_sec", sa.Float(), nullable=False),
        sa.Column("images_per_page", sa.Integer(), nullable=False),
        sa.Column("recording_start_time", sa.DateTime(), nullable=True),
        sa.Column("recording_stop_time", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "recordings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("procedure_sessions.id"), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("resolution", sa.String(32), nullable=False),
        sa.Column("requested_frame_rate", sa.Integer(), nullable=False),
        sa.Column("actual_frame_rate", sa.Float(), nullable=True),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("integrity_status", sa.String(50), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("procedure_sessions.id"), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("thumbnail_path", sa.String(500), nullable=True),
        sa.Column("capture_timestamp", sa.DateTime(), nullable=False),
        sa.Column("capture_type", sa.String(32), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("caption", sa.String(500), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.UniqueConstraint("session_id", "sequence_number", name="uq_snapshot_seq"),
    )
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("procedure_sessions.id"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("images_per_page", sa.Integer(), nullable=False),
        sa.Column("pdf_path", sa.String(500), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("session_id", "version", name="uq_report_version"),
    )
    op.create_table(
        "pairing_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "procedure_session_id",
            sa.Integer(),
            sa.ForeignKey("procedure_sessions.id"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("controller_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("last_command_id", sa.String(64), nullable=True),
    )
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("session_public_id", sa.String(32), nullable=True),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    for table in [
        "audit_logs",
        "app_settings",
        "pairing_sessions",
        "reports",
        "snapshots",
        "recordings",
        "procedure_sessions",
        "procedure_types",
        "patients",
    ]:
        op.drop_table(table)
