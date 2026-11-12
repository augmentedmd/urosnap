# Endoscopy Studio — Implementation Plan

## Phases

### Phase 1 — Project Foundation ✅
- React + Vite + TypeScript + Tailwind frontend
- FastAPI + SQLAlchemy + SQLite + Alembic backend
- Application navigation
- Simulated video source
- Basic session management

### Phase 2 — Video Acquisition ✅
- Camera detection / selection
- Live preview
- Continuous recording with selectable FPS (5/10/15/24/30/60)
- Automatic + manual snapshots
- Shared acquisition pipeline

### Phase 3 — Session Management ✅
- Patient demographics + procedure selection
- Custom procedure names
- Session directories + DB persistence
- Previous-session retrieval

### Phase 4 — Image Gallery ✅
- Thumbnails, selection, reordering, captions
- Lazy loading / efficient grid

### Phase 5 — PDF Reports ✅
- Letterhead, demographics, procedure, Notes, photos
- 1–20 images per page, preview, versioning

### Phase 6 — iPhone Remote ✅
- QR pairing, scoped tokens, mobile UI
- Disconnection resilience

### Phase 7 — Reliability and Security ✅ (prototype level)
- Recording recovery hooks, disk monitoring, audit logging, automated tests
- Clinical production hardening remains institutional

### Phase 8 — Windows Deployment ✅ (documented)
- Service install, autostart, firewall/HTTPS docs

## Acceptance criteria tracking

See README § Acceptance Criteria. Features are marked complete only after automated or manual verification.

## Testing strategy

- Unit tests for validation, pairing, PDF layout math, snapshot scheduling
- Integration test: full simulated workflow (create → record → snap → gallery → notes → PDF → reopen)
- Hardware-dependent features documented when unverifiable without capture devices
