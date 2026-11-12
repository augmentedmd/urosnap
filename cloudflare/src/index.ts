/**
 * OpenSnap Cloudflare Worker — UI shell only.
 *
 * This Worker serves the static React SPA. It must never proxy clinical APIs,
 * media, recordings, or PHI. The browser talks directly to the local Windows
 * recording service for all processing.
 */

export interface Env {
  ASSETS: Fetcher
}

const LOCAL_ONLY_PREFIXES = ['/api/', '/ws/', '/docs', '/openapi.json', '/redoc']

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url)

    if (LOCAL_ONLY_PREFIXES.some((p) => url.pathname === p || url.pathname.startsWith(p))) {
      return Response.json(
        {
          error: 'local_processing_only',
          message:
            'OpenSnap clinical APIs are not available on Cloudflare. Start the local recording service and point the UI at it (default http://127.0.0.1:8000).',
          local_service: 'http://127.0.0.1:8000',
        },
        {
          status: 404,
          headers: {
            'cache-control': 'no-store',
            'x-opensnap-boundary': 'ui-shell-only',
          },
        },
      )
    }

    if (url.pathname === '/opensnap.json') {
      return Response.json(
        {
          product: 'OpenSnap',
          role: 'ui-shell',
          processing: 'local-only',
          local_service_default: 'http://127.0.0.1:8000',
          stores_phi: false,
          stores_media: false,
        },
        { headers: { 'cache-control': 'no-store' } },
      )
    }

    return env.ASSETS.fetch(request)
  },
} satisfies ExportedHandler<Env>
