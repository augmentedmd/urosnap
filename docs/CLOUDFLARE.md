# OpenSnap on Cloudflare (optional UI shell only)

> **Not the normal product path.** Physicians should run **OpenSnap.exe** — see [WINDOWS_EXE.md](WINDOWS_EXE.md) and the root README.  
> Cloudflare is an optional demo/hosting extra for the static UI. It cannot replace the Windows recorder.

OpenSnap can publish its **browser UI** to Cloudflare Workers Static Assets while keeping **all clinical processing local** on the Windows recording computer.

## Hard boundary

| Runs on Cloudflare | Stays on the local Windows service |
| --- | --- |
| Static React SPA (HTML/JS/CSS/fonts) | Video acquisition & recording |
| Optional remote-control page shell | Automatic / manual snapshots |
| `/opensnap.json` capability metadata | Patient demographics & Notes |
| Explicit rejection of `/api/*` | SQLite, session files, PDFs |

**Cloudflare must never receive PHI, photos, video, or PDFs.** Do not put the recording service behind Cloudflare Tunnel for clinical traffic. Do not add D1/R2/KV bindings for patient data.

```
┌──────────────────────────┐
│ Cloudflare Worker        │  serves UI assets only
│ opensnap-ui              │
└────────────┬─────────────┘
             │ loads SPA
             ▼
┌──────────────────────────┐     REST / MJPEG / WS      ┌──────────────────────────┐
│ Desktop / iPhone browser │ ─────────────────────────► │ Local OpenSnap service   │
│ (UI from Cloudflare)     │   http://127.0.0.1:8000    │ (Windows workstation)    │
│                          │   or http://LAN-IP:8000    │ all processing + storage │
└──────────────────────────┘                            └──────────────────────────┘
```

## Deploy the UI shell

Workers Builds for this repo expects the Worker name **`urosnap`** and a root-level Wrangler config.

Preview branches run `npx wrangler preview`, so `wrangler.jsonc` includes an empty `previews` block. Root `npm ci`/`npm install` runs `prepare`, which builds `frontend/dist` before preview/deploy (Workers Builds currently leaves the dashboard Build command empty).

```bash
# From repo root (matches Cloudflare Workers Builds defaults)
npm install
npm run deploy          # production
npm run preview         # Worker Preview
```

Manual / local packaging:

```bash
cd frontend && npm install && npm run build
cd .. && npx wrangler preview
```

Optional dashboard settings (Workers → Settings → Builds):

- **Build command:** `npm run build` (redundant with `prepare`, but clearer)
- **Deploy command (production):** `npx wrangler deploy`
- **Preview command:** `npx wrangler preview`

The `cloudflare/` folder holds the Worker script; root `wrangler.jsonc` + `package.json` are the CI entrypoints.

After deploy, open the Worker URL. The dashboard should report the local recording service. If the service is not running, Settings → **Local processing connection** explains how to point at `http://127.0.0.1:8000`.

## Configure the browser

1. Start the local service on the Windows PC (`uvicorn` on port 8000):

```powershell
cd C:\OpenSnap\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

2. Confirm the service answers: open `http://127.0.0.1:8000/api/health` on that PC.
3. Open the Cloudflare UI URL on that same PC (or a clinic browser that can reach the PC).
4. When Chrome/Edge prompts to allow **local network / private network** access for the Cloudflare site, choose Allow. Without this, the UI shows “Local recording service unreachable.”
5. In **Settings**, set:
   - **Local recording service URL** → `http://127.0.0.1:8000` (desktop on the same PC) or `http://<workstation-lan-ip>:8000`
   - **Public UI base URL** → your Cloudflare Worker URL (used inside iPhone QR links)
6. Click **Test connection**, then **Save connection**.

### If the Cloudflare UI cannot reach localhost

Browsers treat Cloudflare (`https://…workers.dev`) as a public site and `http://127.0.0.1:8000` as a private/local target. OpenSnap’s local service advertises Private Network Access CORS headers, but you must still:

- Keep the recorder running on the workstation
- Allow the browser’s local-network permission prompt
- Or skip Cloudflare for clinical use and open `http://127.0.0.1:8000` (local UI + local API, fully offline)

The remote UI shell blocks clinical screens until `/api/health` succeeds against the local service. Live preview uses authenticated JPEG polling (`/api/sessions/{id}/preview.jpg`) instead of a cross-origin MJPEG `<img>`, which browsers often block from HTTPS pages.

## iPhone remote with Cloudflare UI

QR links look like:

```
https://<cloudflare-ui>/remote/<token>?service=http://<workstation-lan-ip>:8000
```

- The phone loads the remote **page shell** from Cloudflare.
- Start / Stop / Snapshot commands go **directly** to the workstation LAN URL in `?service=`.
- Pairing tokens are validated only by the local service.

The phone and workstation must share an approved clinic LAN. Cloudflare is not a tunnel for recording commands.

## Fully offline mode (no Cloudflare required)

Build the frontend and let the local service serve it:

```bash
cd frontend && npm run build
cd ../backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`. Same processing path; UI is also local.

## Security notes

- Treat the Cloudflare UI origin as untrusted for clinical data — it only delivers code/assets.
- Prefer locking the Worker with Cloudflare Access if the UI URL should not be public.
- Keep Windows firewall rules scoped so only the clinic LAN can reach the recording service.
- See [SECURITY_CHECKLIST.md](SECURITY_CHECKLIST.md).
