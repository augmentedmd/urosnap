# Windows installation — OpenSnap

## Recommended (clinic PC)

Use the packaged app. You do **not** need Python, Node, Git, or Cloudflare.

1. Download **OpenSnap-windows.zip** from a green [Build Windows EXE](https://github.com/augmentedmd/urosnap/actions/workflows/build-windows-exe.yml) run on `main`, or from a GitHub Release.
2. Extract to a stable folder, e.g. `C:\OpenSnap\`.
3. Double-click **`OpenSnap.exe`**.
4. Browser opens to `http://127.0.0.1:8000`.

Clinical files: `%LOCALAPPDATA%\OpenSnap\data\`

Full notes: [WINDOWS_EXE.md](WINDOWS_EXE.md)

### Optional: start at logon

Create a Task Scheduler task at user logon that runs:

```text
C:\OpenSnap\OpenSnap\OpenSnap.exe
```

(Adjust path to wherever you extracted the folder.)

### Optional: iPhone on the clinic LAN

```text
OpenSnap.exe --lan
```

Then use `http://<PC-LAN-IP>:8000` in the QR / phone service URL.

### FFmpeg (recommended)

Copy `ffmpeg.exe` next to `OpenSnap.exe` for MP4 finalization. Without it, OpenSnap can keep an AVI fallback.

### Firewall

Allow inbound TCP 8000 on the clinic LAN only if you use `--lan` for iPhone remote. Default EXE bind is localhost-only.

---

## Advanced: run from source (developers / IT)

Only if you are not using the EXE.

Prerequisites: Windows 10/11, Python 3.12+, Node 20+ (to build UI), FFmpeg optional.

```powershell
cd C:\OpenSnap\frontend
npm ci
npm run build
cd ..\backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.desktop --lan
```

Do **not** tell physicians to run `uvicorn` or clone the repo — ship them the EXE zip instead.

See also [SECURITY_CHECKLIST.md](SECURITY_CHECKLIST.md).
