# OpenSnap on Cloudflare (UI shell only)

OpenSnap can publish its **browser UI** to Cloudflare Workers Static Assets while keeping **all clinical processing local** on the Windows recording computer.

**Both paths coexist.** The Windows `OpenSnap.exe` packaging path is unchanged and remains the recommended clinical workflow. Cloudflare is an optional bookmarkable UI shell for demos / shared SPA origin — never a place for PHI, video, photos, or PDFs.

## Hard boundary

| Runs on Cloudflare | Stays on the local Windows service |
| --- | --- |
| Static React SPA (HTML/JS/CSS/fonts) | Video acquisition & recording |
| Optional remote-control page shell | Automatic / manual snapshots |
| `/opensnap.json` capability metadata | Patient demographics & Notes |
| `/download/windows` → latest `OpenSnap-windows.zip` (binary only) | SQLite, session files, PDFs |
| Explicit rejection of `/api/*` (HTTP 501) | |

**Cloudflare must never receive PHI, photos, video, or PDFs.** Do not put the recording service behind Cloudflare Tunnel for clinical traffic. Do not add D1/R2/KV bindings for patient data.

```
┌──────────────────────────┐
│ Cloudflare Worker        │  serves UI assets only
│ urosnap                  │  bookmarkable https://…workers.dev
└────────────┬─────────────┘
             │ loads SPA
             ▼
┌──────────────────────────┐     REST / JPEG / WS       ┌──────────────────────────┐
│ Desktop / iPhone browser │ ─────────────────────────► │ Local OpenSnap service   │
│ (UI from Cloudflare)     │   http://127.0.0.1:8000    │ OpenSnap.exe or uvicorn  │
│                          │   or http://LAN-IP:8000    │ all processing + storage │
└──────────────────────────┘                            └──────────────────────────┘
```

Production Worker (Workers Builds on `main`): **https://urosnap.michaelagorin.workers.dev**  
Confirm with `GET /opensnap.json` (`role: ui-shell`, `stores_phi: false`). `GET /api/*` must return `local_processing_only` (not clinical data).

## Two clinic options (both keep data local)

### A. Primary — OpenSnap.exe (recommended)

1. Download **OpenSnap-windows.zip** from the Cloudflare UI (**Download Windows package** / `/download/windows`) or from the GitHub Release.
2. Extract (flat layout: `OpenSnap.exe` + `_internal` at the top level) and double-click `OpenSnap.exe` → browser opens `http://127.0.0.1:8000` with UI + API same-origin.
3. No Cloudflare required for day-to-day recording. See [WINDOWS_EXE.md](WINDOWS_EXE.md).

### B. Optional — bookmarkable Cloudflare UI + local service

Use when you want a stable HTTPS bookmark for the SPA (and the Windows download) while the recorder still runs on the clinic PC.

1. Open the Cloudflare Worker URL (main Dashboard). Click **Download Windows package** if the PC does not have the EXE yet.
2. **Keep the local service running** on the Windows workstation (`OpenSnap.exe`, or `uvicorn` for IT/dev).
3. Confirm `http://127.0.0.1:8000/api/health` on that PC.
4. When the browser prompts for **local network / private network** access for the Cloudflare site, choose **Allow**.
5. In **Settings → Local processing connection**:
   - **Local recording service URL** → `http://127.0.0.1:8000` (same PC) or `http://<workstation-lan-ip>:8000`
   - **Public UI base URL** → the Cloudflare Worker URL (used inside iPhone QR links)
6. Click **Test connection**, then **Save connection**.

`opensnap://` deep-link controls on the UI are **optional** after EXE install; download + double-click remains the primary clinic path.

There is no separate connection gate — the Dashboard loads immediately with a download link when the local service is offline. Patient data, media, and PDFs never leave the workstation. Binary package download is not PHI.

### CORS / Private Network Access

Browsers treat Cloudflare (`https://…workers.dev`) as a public site and `http://127.0.0.1:8000` as a private/local target. The local service advertises `Access-Control-Allow-Private-Network` (see backend PNA middleware) and open CORS for the UI shell. You must still:

- Keep the recorder running on the workstation
- Allow the browser’s local-network permission prompt
- Or skip Cloudflare and use `http://127.0.0.1:8000` (EXE / local UI + local API)

Do **not** open the recording port to the public internet. Prefer Cloudflare Access on the Worker if the UI URL should not be world-readable.

## Deploy the UI shell

Workers Builds for this repo expects the Worker name **`urosnap`** and a root-level Wrangler config.

Preview branches run `npx wrangler preview`, so `wrangler.jsonc` includes an empty `previews` block. Root `npm ci`/`npm install` runs `prepare`, which builds `frontend/dist` before preview/deploy (Workers Builds currently leaves the dashboard Build command empty).

```bash
# From repo root (matches Cloudflare Workers Builds defaults)
npm install
npm run deploy          # production (requires Cloudflare auth / Workers Builds)
npm run preview         # Worker Preview
npm run test:worker     # boundary unit tests (no deploy)
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

The `cloudflare/` folder holds the Worker script; root `wrangler.jsonc` + `package.json` are the CI entrypoints. GitHub Actions `cloudflare-ui-shell.yml` runs Worker boundary tests without touching the Windows EXE workflow.

### Deploy auth note

`wrangler deploy` from a laptop or agent needs Cloudflare login / API token. Day-to-day production deploys for this repo go through **Workers Builds** on push to `main` (no local token required once the GitHub ↔ Cloudflare connection is set).

## iPhone remote with Cloudflare UI

QR links look like:

```
https://<cloudflare-ui>/remote/<token>?service=http://<workstation-lan-ip>:8000
```

- The phone loads the remote **page shell** from Cloudflare.
- Start / Stop / Snapshot commands go **directly** to the workstation LAN URL in `?service=`.
- Pairing tokens are validated only by the local service.

The phone and workstation must share an approved clinic LAN. Cloudflare is not a tunnel for recording commands. For EXE LAN binding, see [WINDOWS_EXE.md](WINDOWS_EXE.md) (`OpenSnap.exe --lan`).

## Fully offline mode (no Cloudflare required)

Build the frontend and let the local service serve it (or use the EXE):

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
