/**
 * Durable Windows package download URLs.
 *
 * On the Cloudflare UI shell, prefer same-origin `/download/windows` (Worker
 * redirect). That keeps a bookmarkable clinic URL and lets the Worker point at
 * the current GitHub Release asset without embedding PHI or clinical APIs.
 */

import { isRemoteUiShell } from '@/lib/runtime'

/** Canonical public asset published by build-windows-exe on main / tags. */
export const WINDOWS_PACKAGE_RELEASE_URL =
  'https://github.com/augmentedmd/urosnap/releases/latest/download/OpenSnap-windows.zip'

/** Worker path that redirects to the latest Windows zip (binary only; no PHI). */
export const WINDOWS_PACKAGE_WORKER_PATH = '/download/windows'

/** Human-readable package name for UI copy. */
export const WINDOWS_PACKAGE_LABEL = 'OpenSnap-windows.zip'

/**
 * URL clinics should use to download the latest Windows package.
 * Remote UI shell → same-origin Worker redirect; otherwise GitHub latest asset.
 */
export function getWindowsPackageDownloadUrl(): string {
  if (typeof window !== 'undefined' && isRemoteUiShell()) {
    return `${window.location.origin}${WINDOWS_PACKAGE_WORKER_PATH}`
  }
  return WINDOWS_PACKAGE_RELEASE_URL
}
