/**
 * Optional Windows `opensnap://` deep-link helpers.
 *
 * Download + double-click OpenSnap.exe is the primary clinic path. After the
 * EXE (or an IT register script) has registered the protocol, the Cloudflare
 * UI may optionally ask Windows to start the recorder via these URLs.
 */

export const OPENSNAP_PROTOCOL_START = 'opensnap://start'
export const OPENSNAP_PROTOCOL_OPEN = 'opensnap://open'

/**
 * Ask Windows to launch the registered OpenSnap handler (best-effort).
 * Browsers keep the current page for custom protocols (may show an allow prompt).
 */
export function launchOpenSnapProtocol(url: string = OPENSNAP_PROTOCOL_START): void {
  if (typeof window === 'undefined') return
  try {
    const iframe = document.createElement('iframe')
    iframe.style.display = 'none'
    iframe.src = url
    document.body.appendChild(iframe)
    window.setTimeout(() => {
      iframe.remove()
    }, 2500)
  } catch {
    window.location.assign(url)
  }
}
