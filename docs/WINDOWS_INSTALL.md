# Windows Installation — OpenSnap

## Overview

OpenSnap runs as a local recording service on the Windows computer attached to the HDMI-to-USB capture device. The desktop UI is a browser app served by that service. The iPhone remote reaches the same service over the clinic LAN using HTTPS.

## Prerequisites

- Windows 10/11 x64
- Python 3.12+
- Node.js 20+ (build machine only; optional on clinic PC if you deploy a prebuilt `frontend/dist`)
- FFmpeg on `PATH`
- USB Video Class (UVC) HDMI capture adapter (optional for simulation mode)

## Install (clinic PC)

1. Copy the application folder to a local path, e.g. `C:\OpenSnap`.
2. Open PowerShell as the clinic workstation account that will run procedures.
3. Create and activate a virtual environment:

```powershell
cd C:\OpenSnap\backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

4. Initialize storage and database:

```powershell
mkdir ..\data -Force
alembic upgrade head
```

5. Build frontend assets (or copy a prebuilt `frontend\dist`):

```powershell
cd ..\frontend
npm ci
npm run build
```

6. Start the service:

```powershell
cd ..\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

7. Open Edge/Chrome to `http://localhost:8000`.

## Automatic startup

Prototype options:

1. **Task Scheduler** — create a task at user logon that runs:

```
C:\OpenSnap\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Working directory: `C:\OpenSnap\backend`.

2. **NSSM** (recommended for service-like behavior) — install as a Windows service that restarts on failure.

3. Optional: open the default browser to `http://localhost:8000` after service start.

Production deployment should use an institution-approved service account, restricted ACLs on `data\`, and BitLocker or approved disk encryption.

## Capture device

1. Connect endoscopy HDMI → (optional wireless HDMI) → HDMI-to-USB adapter → Windows PC.
2. Confirm the adapter appears as a camera in Windows Settings.
3. In OpenSnap → New Session / Settings, select the device by name (do not assume index 0).
4. Validate resolution and frame-rate options. Unsupported rates show warnings.

Simulation mode (synthetic pattern / sample video / webcam) can be used without the endoscopy tower.

## iPhone remote networking

The phone cannot reach `localhost` on the Windows PC. Use the PC’s LAN IP, e.g. `https://192.168.x.x:8000/remote/<token>`.

### HTTPS (required for clinical prototype hardening)

1. Obtain an institution-approved certificate for the workstation name or use an IT-approved local CA.
2. Terminate TLS with a reverse proxy (IIS / Caddy / nginx) or uvicorn SSL options.
3. Open Windows Firewall for the service port **only** on the approved clinic network profile.
4. Do not expose the service to the public internet.

### Certificate / firewall checklist

- [ ] TLS certificate installed and trusted on clinic iPhones
- [ ] Firewall allows inbound 443/8000 from clinic WLAN/VLAN only
- [ ] mDNS/hostname documented for physicians
- [ ] Pairing TTL reviewed with security team
- [ ] Workstation confirmation / additional auth policy decided for production

## Storage

Default: `C:\OpenSnap\data\opensnap_sessions\`

Restrict NTFS permissions to the recording service account and authorized clinical staff. Patient identifiers live in SQLite and must not appear in directory names.

## Uninstall

1. Stop the service / scheduled task.
2. Archive or securely wipe `data\` per institutional retention policy.
3. Remove the application folder.
