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
- Prefers a real USB/webcam capture device when Windows exposes one; otherwise uses synthetic video

### If the app says “Synthetic pattern”

1. Confirm the HDMI-to-USB device (or webcam) appears under **Device Manager → Cameras**.
2. **Windows Settings → Privacy & security → Camera** → enable camera access and **Let desktop apps access your camera**.
3. Close Zoom / Teams / OBS / other apps that may lock the device.
4. Fully quit `OpenSnap.exe`, start it again, open **New Session** — you should see `Capture device 0 (DirectShow)` (or similar) and it should be selected automatically.

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
