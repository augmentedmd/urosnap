# OpenSnap

Local-first, browser-based urology video capture and procedure reporting system.

**Prototype for evaluation.** Clinical production use requires institutional IT, security, compliance, and clinical engineering review. This software does not claim HIPAA compliance or production readiness.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

Three components:

1. **Local Recording Service** (Python / FastAPI) — video acquisition, recording, snapshots, storage, PDFs, pairing
2. **Desktop Browser App** (React) — session setup, live preview, gallery, reports, settings
3. **iPhone Remote** (mobile web) — start/stop recording and snapshots only (no PHI)

All clinical data stays on the Windows recording computer. No cloud services are required for normal operation.

### Optional Cloudflare UI shell

You may host the **static UI only** on Cloudflare Workers. Processing still runs entirely on the local service — Cloudflare never sees PHI, video, photos, or PDFs. Details: [docs/CLOUDFLARE.md](docs/CLOUDFLARE.md).

## Quick start (development)

### Prerequisites

- Python 3.12+
- Node.js 20+
- FFmpeg on `PATH`
- (Optional) USB webcam or HDMI-to-USB capture device

### Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend (dev)

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL (typically http://localhost:5173). The frontend proxies API calls to the local service.

### Combined (production-style local)

Build the frontend and let FastAPI serve it:

```bash
cd frontend && npm install && npm run build
cd ../backend && source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open http://localhost:8000

### Simulated video

By default the service uses a **synthetic video pattern** so you can develop without endoscopy hardware.

In Settings (or when creating a session), choose:

- **Synthetic pattern** — generated color bars / moving overlay
- **Prerecorded test video** — place a file at `backend/assets/sample_video.mp4` (optional)
- **Webcam** — OpenCV index of a UVC device
- **USB capture device** — detected cameras listed by name/index

### Tests

```bash
cd backend
source .venv/bin/activate
pytest -q
```

## Physician workflow

1. **Desktop — before procedure:** New Session → patient info → procedure → frame rate → snapshot interval → Create → QR code
2. **iPhone — during procedure:** Scan QR → Start Recording → Take Snapshot as needed → Stop Recording
3. **Desktop — after procedure:** Gallery → select/reorder photos → Notes → images per page → Preview PDF → Generate

## Where files are stored

Default storage root: `./data` (configurable in Settings)

```
data/
  opensnap.db
  opensnap_sessions/
    session_YYYYMMDD_xxxxxx/
      video/
      snapshots/
      thumbnails/
      reports/
      metadata/
```

Directories use internal session IDs — never patient names or MRNs.

## Connecting a USB capture device

1. Connect the HDMI-to-USB adapter (UVC preferred).
2. Confirm Windows recognizes it as a camera.
3. Open the OpenSnap app → New Session or Settings.
4. Select the device from the capture device list (do not assume index 0).
5. Choose resolution and recording frame rate; unsupported rates show a warning.

The endoscopy tower’s primary clinical monitor is unaffected — this system only reads the HDMI tap via the USB adapter.

## iPhone pairing

1. Create a session on the desktop.
2. Scan the QR code shown on the Active Recording screen.
3. The phone opens a control page over the local network (HTTPS in deployment).
4. The phone can start/stop recording and take snapshots.
5. Recording continues if the phone disconnects.
6. Pairing can be revoked from the desktop.

The QR token does **not** grant access to patient data, photos, video, or PDFs.

## Report structure

Every PDF contains only:

- Practice letterhead (configurable; default Mount Sinai Doctors – Long Island contact block)
- Patient demographics
- Procedure details
- One free-text **Notes** field
- Selected photographs (1–20 per page)

There are no separate Findings / Impression / Plan fields.

## Windows installation

See [docs/WINDOWS_INSTALL.md](docs/WINDOWS_INSTALL.md) and [docs/SECURITY_CHECKLIST.md](docs/SECURITY_CHECKLIST.md).

## Acceptance criteria (prototype)

- [x] Desktop web app launches
- [x] Simulated video source available
- [x] Patient sessions can be created
- [x] Procedure types + custom names
- [x] Continuous recording with configurable FPS
- [x] Automatic + manual snapshots; interval changeable during recording
- [x] QR pairing + iPhone remote (control only)
- [x] Recording continues if phone disconnects
- [x] Image gallery with select/reorder
- [x] Single Notes field; PDF with letterhead, demographics, procedure, notes, photos
- [x] 1–20 photos per page
- [x] Previous sessions reopenable; notes editable; reports versioned
- [x] All clinical data local; no external runtime services

Hardware path validation (wireless HDMI + clinical capture adapters) requires on-site testing.
