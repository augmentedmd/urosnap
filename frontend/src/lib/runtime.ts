/**
 * OpenSnap runtime wiring for Cloudflare-hosted UI + local processing.
 *
 * The Cloudflare Worker/Pages origin may serve only static UI assets.
 * All clinical API, media, recording, and PDF traffic goes to the local
 * recording service and never through Cloudflare.
 */

const STORAGE_SERVICE = 'opensnap_service_url'
const STORAGE_UI = 'opensnap_ui_base_url'

function normalizeBase(url: string): string {
  return url.trim().replace(/\/+$/, '')
}

function isLoopbackHost(hostname: string): boolean {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]'
}

/** True when the SPA is being served from the same origin as the local API. */
export function isSameOriginService(): boolean {
  if (typeof window === 'undefined') return true
  const configured = getStoredServiceUrl()
  if (!configured) {
    return isLoopbackHost(window.location.hostname)
  }
  try {
    const service = new URL(configured)
    return service.origin === window.location.origin
  } catch {
    return false
  }
}

/** True when UI is hosted away from the Windows recorder (e.g. Cloudflare). */
export function isRemoteUiShell(): boolean {
  if (typeof window === 'undefined') return false
  return !isLoopbackHost(window.location.hostname)
}

export function getStoredServiceUrl(): string {
  if (typeof window === 'undefined') return ''
  const fromQuery = new URLSearchParams(window.location.search).get('service')
  if (fromQuery) {
    const normalized = normalizeBase(fromQuery)
    window.localStorage.setItem(STORAGE_SERVICE, normalized)
    return normalized
  }
  return window.localStorage.getItem(STORAGE_SERVICE) || ''
}

export function setStoredServiceUrl(url: string): void {
  const normalized = normalizeBase(url)
  if (!normalized) {
    window.localStorage.removeItem(STORAGE_SERVICE)
    return
  }
  window.localStorage.setItem(STORAGE_SERVICE, normalized)
}

export function getStoredUiBaseUrl(): string {
  if (typeof window === 'undefined') return ''
  return window.localStorage.getItem(STORAGE_UI) || ''
}

export function setStoredUiBaseUrl(url: string): void {
  const normalized = normalizeBase(url)
  if (!normalized) {
    window.localStorage.removeItem(STORAGE_UI)
    return
  }
  window.localStorage.setItem(STORAGE_UI, normalized)
}

/**
 * Base URL for the local recording service.
 * Empty string means same-origin (local FastAPI serving the SPA).
 */
export function getServiceBaseUrl(): string {
  const stored = getStoredServiceUrl()
  if (stored) return stored

  const env = import.meta.env.VITE_LOCAL_SERVICE_URL as string | undefined
  if (env) return normalizeBase(env)

  if (typeof window !== 'undefined' && !isLoopbackHost(window.location.hostname)) {
    // Cloudflare (or any remote) hosted UI defaults to local workstation service.
    return 'http://127.0.0.1:8000'
  }
  return ''
}

/** Resolve an API/media path against the local recording service. */
export function serviceUrl(path: string): string {
  const base = getServiceBaseUrl()
  if (!path.startsWith('/')) {
    return base ? `${base}/${path}` : `/${path}`
  }
  return `${base}${path}`
}

/** Optional Cloudflare (or other) public UI origin used when building QR links. */
export function getUiBaseUrl(): string {
  const stored = getStoredUiBaseUrl()
  if (stored) return stored
  const env = import.meta.env.VITE_PUBLIC_UI_BASE_URL as string | undefined
  if (env) return normalizeBase(env)
  if (typeof window !== 'undefined') return window.location.origin
  return ''
}

export function buildRemotePairingUrl(token: string, serviceBase: string, uiBase?: string): string {
  const ui = normalizeBase(uiBase || getUiBaseUrl())
  const service = normalizeBase(serviceBase || getServiceBaseUrl() || 'http://127.0.0.1:8000')
  const url = new URL(`${ui}/remote/${token}`)
  // Phone must call the LAN/local service directly — never Cloudflare — for commands.
  url.searchParams.set('service', service)
  return url.toString()
}
