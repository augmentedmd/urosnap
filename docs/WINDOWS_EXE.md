# OpenSnap Windows EXE

Physicians should not need Git, Python, or Cloudflare. The desktop package is a double-click app:

1. Download **OpenSnap-windows.zip** from the Cloudflare UI (**Download Windows package**, path `/download/windows`) or from the GitHub Release latest asset
2. Extract the zip — **`OpenSnap.exe`** and **`_internal`** appear at the top level (do not run the EXE from inside the zip)
3. Double-click **`OpenSnap.exe`**
4. The default browser opens to `http://127.0.0.1:8000` with the full UI + local recorder

If the browser shows JSON saying **Frontend not built yet**, port 8000 is usually already taken by an old `uvicorn`/source install without the UI. Quit that process in Task Manager, then start `OpenSnap.exe` again.

All video, snapshots, patient data, and PDFs stay on that Windows PC under:

`%LOCALAPPDATA%\OpenSnap\data\`

## What the EXE does

- Starts the local FastAPI recording service
- Serves the built React UI from the same origin (no separate Vite / Cloudflare needed)
- Opens the browser automatically
- Prefers a real USB/webcam capture device when Windows exposes one; otherwise uses synthetic video

Optional: you may also bookmark the Cloudflare-hosted **UI shell** while still running this EXE as the local recorder. That site hosts the Windows download redirect and never receives PHI or media; see [CLOUDFLARE.md](CLOUDFLARE.md). The EXE packaging path is independent and remains fully supported.

### Optional `opensnap://` deep-link

Download + double-click is primary. If the packaged EXE registers `opensnap://` (or IT runs a register script), the Cloudflare UI can optionally offer **Try opensnap:// start**. Ignore that control if the browser has no handler — re-download and run the EXE instead.

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

CI: `.github/workflows/build-windows-exe.yml` builds the same zip on `main` and publishes it to the GitHub Release used by `/download/windows` (`releases/latest/download/OpenSnap-windows.zip`). Version tags (`v*`) also attach the zip.
