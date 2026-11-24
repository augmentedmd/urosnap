/**
 * Deep-link helpers for the Windows `opensnap://` custom URL protocol.
 *
 * A public Cloudflare page cannot spawn OpenSnap.exe by itself. After the EXE
 * (or register-opensnap-protocol.ps1) registers the protocol once, the browser
 * can hand off to the local recorder via these URLs.
 */

export const OPENSNAP_PROTOCOL_START = 'opensnap://start'
export const OPENSNAP_PROTOCOL_OPEN = 'opensnap://open'

/**
 * Ask Windows to launch the registered OpenSnap handler.
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
