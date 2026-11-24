import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  WINDOWS_PACKAGE_RELEASE_URL,
  capabilityManifestResponse,
  isLocalOnlyPath,
  localOnlyResponse,
  windowsPackageDownloadResponse,
} from './index.ts'

describe('isLocalOnlyPath', () => {
  it('rejects clinical API and websocket paths', () => {
    for (const path of [
      '/api',
      '/api/health',
      '/api/sessions/abc/preview.jpg',
      '/ws',
      '/ws/preview',
      '/docs',
      '/docs/oauth2-redirect',
      '/openapi.json',
      '/redoc',
    ]) {
      assert.equal(isLocalOnlyPath(path), true, path)
    }
  })

  it('does not treat SPA routes or download as local-only', () => {
    for (const path of [
      '/',
      '/settings',
      '/sessions/new',
      '/remote/tok',
      '/opensnap.json',
      '/download/windows',
      '/documentation',
      '/assets/index.js',
    ]) {
      assert.equal(isLocalOnlyPath(path), false, path)
    }
  })
})

describe('localOnlyResponse', () => {
  it('returns a non-2xx boundary payload without proxying', async () => {
    const res = localOnlyResponse()
    assert.equal(res.status, 501)
    assert.equal(res.headers.get('x-opensnap-boundary'), 'ui-shell-only')
    assert.equal(res.headers.get('cache-control'), 'no-store')
    const body = (await res.json()) as {
      error: string
      local_service: string
      windows_download: string
    }
    assert.equal(body.error, 'local_processing_only')
    assert.equal(body.local_service, 'http://127.0.0.1:8000')
    assert.equal(body.windows_download, '/download/windows')
  })
})

describe('capabilityManifestResponse', () => {
  it('advertises ui-shell with local-only processing and download metadata', async () => {
    const res = capabilityManifestResponse()
    assert.equal(res.status, 200)
    const body = (await res.json()) as {
      role: string
      processing: string
      stores_phi: boolean
      stores_media: boolean
      windows_package: { download_path: string; release_url: string; filename: string }
    }
    assert.equal(body.role, 'ui-shell')
    assert.equal(body.processing, 'local-only')
    assert.equal(body.stores_phi, false)
    assert.equal(body.stores_media, false)
    assert.equal(body.windows_package.filename, 'OpenSnap-windows.zip')
    assert.equal(body.windows_package.download_path, '/download/windows')
    assert.equal(body.windows_package.release_url, WINDOWS_PACKAGE_RELEASE_URL)
  })
})

describe('windowsPackageDownloadResponse', () => {
  it('redirects to the durable GitHub Release zip', () => {
    const res = windowsPackageDownloadResponse()
    assert.equal(res.status, 302)
    assert.equal(res.headers.get('location'), WINDOWS_PACKAGE_RELEASE_URL)
  })
})
