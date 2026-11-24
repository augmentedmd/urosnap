import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  capabilityManifestResponse,
  isLocalOnlyPath,
  localOnlyResponse,
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

  it('does not treat SPA routes as local-only', () => {
    for (const path of [
      '/',
      '/settings',
      '/sessions/new',
      '/remote/tok',
      '/opensnap.json',
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
    }
    assert.equal(body.error, 'local_processing_only')
    assert.equal(body.local_service, 'http://127.0.0.1:8000')
  })
})

describe('capabilityManifestResponse', () => {
  it('advertises ui-shell with local-only processing', async () => {
    const res = capabilityManifestResponse()
    assert.equal(res.status, 200)
    const body = (await res.json()) as {
      role: string
      processing: string
      stores_phi: boolean
      stores_media: boolean
    }
    assert.equal(body.role, 'ui-shell')
    assert.equal(body.processing, 'local-only')
    assert.equal(body.stores_phi, false)
    assert.equal(body.stores_media, false)
  })
})
