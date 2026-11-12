# OpenSnap Windows EXE

Physicians should not need Git, Python, or Cloudflare. The desktop package is a double-click app:

1. Download **OpenSnap-windows.zip** from the GitHub Release (or CI artifact)
2. Extract the folder
3. Double-click **`OpenSnap.exe`**
4. The default browser opens to `http://127.0.0.1:8000` with the full UI + local recorder

All video, snapshots, patient data, and PDFs stay on that Windows PC under:

`%LOCALAPPDATA%\OpenSnap\data\`

## What the EXE does

- Starts the local FastAPI recording service
- Serves the built React UI from the same origin (no separate Vite / Cloudflare needed)
- Opens the browser automatically
- Uses synthetic video by default; webcam / capture devices appear when available

## iPhone remote

By default the EXE binds **127.0.0.1** only. To allow a phone on the clinic LAN:

```text
OpenSnap.exe --lan
```

Then set the phone / QR service URL to `http://<PC-LAN-IP>:8000`.

## FFmpeg (recommended)

For MP4 finalization, place `ffmpeg.exe` next to `OpenSnap.exe` (or on PATH). Without it, OpenSnap keeps an AVI fallback from OpenCV.

## Build from source (maintainers)

On a Windows machine with Python 3.12+ and Node 20+:

```powershell
git clone https://github.com/augmentedmd/urosnap.git
cd urosnap
.\packaging\build-windows.ps1
```

Output: `dist\OpenSnap-windows.zip`

CI: `.github/workflows/build-windows-exe.yml` builds the same zip on `main` and attaches it to version tags (`v*`).
