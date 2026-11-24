/**
 * OpenSnap Cloudflare Worker — UI shell only.
 *
 * This Worker serves the static React SPA. It must never proxy clinical APIs,
 * media, recordings, or PHI. The browser talks directly to the local Windows
 * recording service (OpenSnap.exe or uvicorn) for all processing.
 */

export interface Env {
  ASSETS: Fetcher
}

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
      coexistence: {
        windows_exe: 'OpenSnap.exe packaging remains the primary clinical path',
        cloudflare: 'Static UI shell only; never proxies /api/* or media',
      },
    },
    { headers: { 'cache-control': 'no-store' } },
  )
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

    return env.ASSETS.fetch(request)
  },
} satisfies ExportedHandler<Env>
