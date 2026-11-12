# OpenSnap — Architecture

Local-first, browser-based urology video capture and procedure reporting system.

## Components

```
┌──────────────────────┐
│ Cloudflare Worker    │  optional: static UI shell only (no PHI/media)
│ opensnap-ui          │
└──────────┬───────────┘
           │ loads SPA assets
           ▼
┌─────────────────────┐   browser → local service   ┌──────────────────────────────┐
│  Desktop Browser    │◄───────────────────────────►│  Local Recording Service     │
│  (React SPA)        │   REST / MJPEG / WebSocket  │  (Python / FastAPI)          │
│                     │   never via Cloudflare      │                              │
│  Dashboard          │                             │  • Video acquisition         │
│  New Session        │                             │  • Recording engine          │
│  Active Recording   │                             │  • Snapshot scheduler        │
│  Image Gallery      │                             │  • PDF generation            │
│  Report Generator   │                             │  • SQLite + local storage    │
│  Previous Sessions  │                             │  • Pairing / auth            │
│  Settings           │                             └──────────────┬───────────────┘
└─────────────────────┘                                            │
                                                                   │ LAN (control only)
┌─────────────────────┐                                            │
│  iPhone Safari      │◄───────────────────────────────────────────┘
│  Remote Control     │  QR may open Cloudflare UI shell with
│  Start / Stop / Snap│  ?service=http://workstation-lan:8000
│  Status only        │  Commands hit the local service directly
└─────────────────────┘
```

See [docs/CLOUDFLARE.md](docs/CLOUDFLARE.md) for the Cloudflare UI-shell deployment model.

## Data flow

1. Physician creates a session on the desktop UI → FastAPI persists patient/session metadata to SQLite and creates a session directory under the configured storage root.
2. A single video acquisition pipeline opens the selected capture device (or simulated source) and distributes frames to:
   - Live preview (MJPEG / WebSocket frame stream)
   - Recording writer (timestamp-aware, H.264 MP4 finalization)
   - Snapshot scheduler (monotonic interval + manual capture)
3. Recording state lives in the Python service, independent of browser connections.
4. QR pairing issues a short-lived cryptographically secure token scoped to recording-control APIs only.
5. The iPhone remote sends start/stop/snapshot commands and receives non-identifying status.
6. After recording, the gallery loads snapshot metadata + thumbnails from local storage.
7. ReportLab generates a versioned PDF (letterhead, demographics, procedure details, Notes, selected photos).

## Storage layout

```
{storage_root}/
  opensnap_sessions/
    session_{YYYYMMDD}_{short_id}/
      video/
      snapshots/
      thumbnails/
      reports/
      metadata/
  opensnap.db
```

Session directory names never include patient names or MRNs.

## Security boundaries

| Boundary | Rule |
|---|---|
| Desktop API | Localhost-oriented; session auth for clinical data |
| Mobile API | Pairing-token scoped to recording start/stop/snapshot/status only |
| Mobile payload | No PHI, no media, no notes, no reports |
| Storage | Local filesystem only; no cloud |
| Network | No public internet exposure; mobile over approved LAN HTTPS |
| Logs | No patient identifiers in application logs |

**Prototype note:** Pairing uses secure tokens and scoped permissions. Clinical deployment requires institutional authentication, certificate management, Windows ACL hardening, and compliance review. This prototype does **not** claim HIPAA compliance or production readiness.

## Video pipeline

```
Capture Device / Simulator
        │
        ▼
  Frame Acquisition Loop (single OpenCV / FFmpeg source)
        │
        ├──► Preview ring buffer → HTTP MJPEG / WS
        ├──► Recording writer (requested FPS gating)
        └──► Snapshot scheduler (interval + manual)
```

Only one process opens the camera. Browser close does not stop recording.

## Report model

Every procedure uses the same PDF structure:

1. Practice letterhead
2. Patient demographics
3. Procedure details
4. One free-text **Notes** field
5. Selected photographs (1–20 per page)

There are **no** Findings, Impression, Plan, Technique, Indication, Anesthesia, or Complications fields.

## Prototype vs production

| Area | Prototype | Production (institutional) |
|---|---|---|
| Auth | Local workstation assumption + pairing tokens | Institutional SSO / workstation lock |
| TLS | Optional self-signed for LAN | Institution-approved certs |
| Storage encryption | Documented; OS-level recommended | BitLocker / approved encryption |
| Hardware | Simulated + UVC webcam | Validated HDMI capture path |
| Compliance | Technical safeguards only | Full security/compliance review |
