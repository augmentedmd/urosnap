# OpenSnap Windows EXE

**This is the normal way to run OpenSnap.**

Physicians should not use Git, Python, Cloudflare, or terminal commands.

## Install & run

1. Open [Build Windows EXE](https://github.com/augmentedmd/urosnap/actions/workflows/build-windows-exe.yml)
2. Click the latest green run on branch **`main`**
3. Download the **OpenSnap-windows** artifact (a zip)
4. Extract it on the Windows procedure PC
5. Double-click **`OpenSnap\OpenSnap.exe`**
6. The browser opens the app at `http://127.0.0.1:8000`

When maintainers publish a version tag (`v*`), the same zip is attached to the [GitHub Release](https://github.com/augmentedmd/urosnap/releases).

## What it does

- Starts the local recording service
- Serves the UI from the same app (no separate website required)
- Opens your default browser
- Stores sessions under `%LOCALAPPDATA%\OpenSnap\data\`

Synthetic video works immediately. Real cameras appear when Windows detects them.

## iPhone remote

Default: localhost only (safer).

For phone control on the clinic Wi‑Fi / LAN:

```text
OpenSnap.exe --lan
```

Phone must reach `http://<PC-LAN-IP>:8000`. The QR flow uses that service URL. The phone never receives patient charts or media.

## FFmpeg

Place `ffmpeg.exe` beside `OpenSnap.exe` for MP4 output. Optional; without it, AVI fallback may be used.

## Build the zip (maintainers)

On Windows with Python 3.12+ and Node 20+:

```powershell
git clone https://github.com/augmentedmd/urosnap.git
cd urosnap
.\packaging\build-windows.ps1
```

Output: `dist\OpenSnap-windows.zip`

CI workflow: `.github/workflows/build-windows-exe.yml`
