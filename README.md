# OpenSnap

Local Windows app for urology video capture, snapshots, and procedure PDFs.

**Prototype for evaluation.** Not a HIPAA compliance claim. Clinical use needs institutional IT / security review.

---

## How to use (this is the only path physicians need)

1. Download **`OpenSnap-windows.zip`** from the latest [GitHub Actions build](https://github.com/augmentedmd/urosnap/actions/workflows/build-windows-exe.yml) (open a green run on `main` → Artifacts → **OpenSnap-windows**), or from a [Release](https://github.com/augmentedmd/urosnap/releases) when tagged.
2. Extract the zip on the Windows procedure PC.
3. Double-click **`OpenSnap.exe`**.
4. Your browser opens to the app. Create a session and record.

No Git. No Python. No Cloudflare. No `uvicorn`.

Data stays on that PC at `%LOCALAPPDATA%\OpenSnap\data\`.

More detail: [docs/WINDOWS_EXE.md](docs/WINDOWS_EXE.md)

### Typical procedure day

1. **Before:** New Session → (optional) patient info → Create  
2. **During:** Start Recording → snapshots as needed → Stop (iPhone remote optional)  
3. **After:** Gallery → select photos → Notes → Generate PDF  

---

## What OpenSnap is

| Piece | Role |
| --- | --- |
| **OpenSnap.exe** | One double-click app: local recorder + UI in the browser |
| **Browser window** | Session setup, live preview, gallery, reports, settings |
| **iPhone (optional)** | Start / stop / snapshot only — no patient data on the phone |

Capture defaults to a **synthetic** test pattern so you can try the app without endoscopy hardware. Webcams and USB HDMI capture devices show up in New Session / Settings when Windows sees them.

---

## Docs map

| Doc | Audience |
| --- | --- |
| [docs/WINDOWS_EXE.md](docs/WINDOWS_EXE.md) | **Start here** — download, run, iPhone LAN flag |
| [docs/WINDOWS_INSTALL.md](docs/WINDOWS_INSTALL.md) | Clinic install notes (EXE-first) |
| [docs/SECURITY_CHECKLIST.md](docs/SECURITY_CHECKLIST.md) | Security review checklist |
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the system is structured |
| [docs/CLOUDFLARE.md](docs/CLOUDFLARE.md) | **Optional / advanced** — UI shell only; not required |

---

## For developers only

Skip this section unless you are changing the code.

### Run from source (same behavior as the EXE)

```bash
cd frontend && npm install && npm run build
cd ../backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.desktop
```

### Hot-reload UI

```bash
# terminal 1
cd backend && source .venv/bin/activate && python -m app.desktop --no-browser

# terminal 2
cd frontend && npm run dev
```

### Tests & Windows package build

```bash
cd backend && pytest -q
# on Windows:
.\packaging\build-windows.ps1
```

### Cloudflare

Cloudflare can host a **static UI shell** for demos. It cannot record video or store patient data. Day-to-day clinical use is **OpenSnap.exe**, not the Workers URL. See [docs/CLOUDFLARE.md](docs/CLOUDFLARE.md).
