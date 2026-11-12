# OpenSnap on Cloudflare (UI shell only)

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

```bash
cd frontend && npm install && npm run build
cd ../cloudflare && npm install
npx wrangler deploy
```

Or from `cloudflare/`:

```bash
npm run deploy
```

After deploy, open the Worker URL. The dashboard should report the local recording service. If the service is not running, Settings → **Local processing connection** explains how to point at `http://127.0.0.1:8000`.

## Configure the browser

1. Start the local service on the Windows PC (`uvicorn` on port 8000).
2. Open the Cloudflare UI URL on that same PC (or a clinic browser that can reach the PC).
3. In **Settings**, set:
   - **Local recording service URL** → `http://127.0.0.1:8000` (desktop on the same PC) or `http://<workstation-lan-ip>:8000`
   - **Public UI base URL** → your Cloudflare Worker URL (used inside iPhone QR links)
4. Save connection (reloads the app).

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
