/**
 * OpenSnap Cloudflare Worker — UI shell only.
 *
 * This Worker serves the static React SPA. It must never proxy clinical APIs,
 * media, recordings, or PHI. The browser talks directly to the local Windows
 * recording service (OpenSnap.exe or uvicorn) for all processing.
 *
 * Binary downloads (OpenSnap-windows.zip) are fine to advertise / redirect —
 * that is not clinical data.
 */

export interface Env {
  ASSETS: Fetcher
}

/** Durable GitHub Release asset for the Windows package (updated by CI on main). */
export const WINDOWS_PACKAGE_RELEASE_URL =
  'https://github.com/augmentedmd/urosnap/releases/latest/download/OpenSnap-windows.zip'

/** Paths that belong only to the local recording service — never Cloudflare. */
export function isLocalOnlyPath(pathname: string): boolean {
  if (pathname === '/api' || pathname.startsWith('/api/')) return true
  if (pathname === '/ws' || pathname.startsWith('/ws/')) return true
  if (pathname === '/docs' || pathname.startsWith('/docs/')) return true
  if (pathname === '/openapi.json' || pathname === '/redoc') return true
  return false
}

const LOCAL_ONLY_HEADERS = {
  'cache-control': 'no-store',
  'x-opensnap-boundary': 'ui-shell-only',
} as const

export function localOnlyResponse(): Response {
  return Response.json(
    {
      error: 'local_processing_only',
      message:
        'OpenSnap clinical APIs are not available on Cloudflare. Start OpenSnap.exe (or uvicorn) on the clinic PC and point the UI at it (default http://127.0.0.1:8000).',
      local_service: 'http://127.0.0.1:8000',
      windows_download: '/download/windows',
    },
    {
      // 501: this origin deliberately does not implement clinical processing.
      status: 501,
      headers: { ...LOCAL_ONLY_HEADERS },
    },
  )
}

export function capabilityManifestResponse(): Response {
  return Response.json(
    {
      product: 'OpenSnap',
      role: 'ui-shell',
      processing: 'local-only',
      local_service_default: 'http://127.0.0.1:8000',
      stores_phi: false,
      stores_media: false,
      windows_package: {
        filename: 'OpenSnap-windows.zip',
        download_path: '/download/windows',
        release_url: WINDOWS_PACKAGE_RELEASE_URL,
        note: 'Binary installer only — not PHI. Extract and run OpenSnap.exe on the capture PC.',
      },
      coexistence: {
        windows_exe: 'OpenSnap.exe packaging remains the primary clinical path',
        cloudflare:
          'Static UI shell + Windows package download redirect; never proxies /api/* or media',
        protocol: 'opensnap:// deep-link is optional after EXE install; download is primary UX',
      },
    },
    { headers: { 'cache-control': 'no-store' } },
  )
}

/** Redirect clinic staff to the durable GitHub Release zip (no PHI). */
export function windowsPackageDownloadResponse(): Response {
  return Response.redirect(WINDOWS_PACKAGE_RELEASE_URL, 302)
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url)

    if (isLocalOnlyPath(url.pathname)) {
      return localOnlyResponse()
    }

    if (url.pathname === '/opensnap.json') {
      return capabilityManifestResponse()
    }

    if (url.pathname === '/download/windows' || url.pathname === '/download/windows/') {
      return windowsPackageDownloadResponse()
    }

    return env.ASSETS.fetch(request)
  },
} satisfies ExportedHandler<Env>
