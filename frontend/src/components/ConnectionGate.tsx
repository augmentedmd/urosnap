import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { AlertTriangle, Download, ExternalLink, Play, RefreshCw } from 'lucide-react'
import { api } from '@/lib/api'
import { WINDOWS_PACKAGE_LABEL, getWindowsPackageDownloadUrl } from '@/lib/download'
import { launchOpenSnapProtocol } from '@/lib/protocol'
import {
  getServiceBaseUrl,
  isRemoteUiShell,
  isSameOriginService,
  setStoredServiceUrl,
} from '@/lib/runtime'
import { Button, Card, Field, Input } from '@/components/ui'

type Props = {
  children: React.ReactNode
}

/**
 * Cloudflare UI shell cannot record by itself. Primary path: download the
 * Windows package, run OpenSnap.exe, work locally. Advanced: point this remote
 * UI at a running local service. Optional: opensnap:// if already registered.
 */
export function ConnectionGate({ children }: Props) {
  const location = useLocation()
  const remote = typeof window !== 'undefined' && isRemoteUiShell() && !isSameOriginService()
  const allowThrough = location.pathname.startsWith('/settings')
  const [serviceUrlInput, setServiceUrlInput] = useState(() => getServiceBaseUrl() || 'http://127.0.0.1:8000')
  const [checking, setChecking] = useState(remote)
  const [ok, setOk] = useState(!remote)
  const [message, setMessage] = useState<string | null>(null)
  const [launching, setLaunching] = useState(false)
  const probeTimers = useRef<number[]>([])
  const downloadUrl = getWindowsPackageDownloadUrl()

  useEffect(() => {
    return () => {
      for (const id of probeTimers.current) window.clearTimeout(id)
    }
  }, [])

  const probe = async (base: string) => {
    const normalized = (base || 'http://127.0.0.1:8000').replace(/\/+$/, '')
    setChecking(true)
    setMessage('Testing local recording service…')
    try {
      const res = await fetch(`${normalized}/api/health`, {
        headers: { 'X-Desktop-Token': 'local-desktop-dev-token' },
        cache: 'no-store',
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const body = (await res.json()) as { service?: string; status?: string }
      setStoredServiceUrl(normalized)
      setOk(true)
      setMessage(`Connected to ${body.service ?? 'OpenSnap'} (${body.status ?? 'ok'})`)
      // Warm caches used by the rest of the app.
      void api.health().catch(() => undefined)
    } catch (err) {
      setOk(false)
      setMessage(
        `Could not reach ${normalized}. ${(err as Error).message}. Allow local/private network access if the browser prompts, then try again.`,
      )
    } finally {
      setChecking(false)
    }
  }

  useEffect(() => {
    if (!remote) return
    void probe(serviceUrlInput)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- probe once on mount for remote UI
  }, [remote])

  const tryOptionalProtocol = () => {
    setLaunching(true)
    setMessage(
      'Optional: asking Windows via opensnap://start… Prefer Download + OpenSnap.exe if nothing happens.',
    )
    launchOpenSnapProtocol()
    for (const id of probeTimers.current) window.clearTimeout(id)
    probeTimers.current = [1500, 3500, 7000].map((ms) =>
      window.setTimeout(() => {
        void probe(serviceUrlInput).finally(() => {
          if (ms >= 7000) setLaunching(false)
        })
      }, ms),
    )
  }

  if (!remote || ok || allowThrough) {
    return <>{children}</>
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-2xl flex-col justify-center gap-5">
      <Card className="space-y-4 border-amber-200 bg-amber-50/70 p-6">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-6 w-6 text-amber-700" />
          <div>
            <h1 className="font-[family-name:var(--font-display)] text-2xl font-semibold text-amber-950">
              Download OpenSnap for Windows
            </h1>
            <p className="mt-2 text-sm text-amber-950/90">
              This Cloudflare page is only a UI shell. Download{' '}
              <strong>{WINDOWS_PACKAGE_LABEL}</strong>, extract it, and double-click{' '}
              <strong>OpenSnap.exe</strong> on the capture PC — no Git, Python, or protocol setup
              required. Patient data and video stay on that PC.
            </p>
          </div>
        </div>

        <ol className="list-decimal space-y-2 pl-5 text-sm text-amber-950">
          <li>
            Click <strong>Download Windows package</strong> (bookmarkable:{' '}
            <code className="text-xs">/download/windows</code>).
          </li>
          <li>
            Extract the full <strong>OpenSnap</strong> folder and double-click{' '}
            <strong>OpenSnap.exe</strong>. Prefer the local window at http://127.0.0.1:8000.
          </li>
          <li>
            Optional: keep this Cloudflare bookmark and point the connection URL below at a running
            EXE if you want the remote UI shell.
          </li>
        </ol>

        <Field label="Local recording service URL (advanced)">
          <Input
            value={serviceUrlInput}
            placeholder="http://127.0.0.1:8000"
            onChange={(e) => setServiceUrlInput(e.target.value)}
          />
        </Field>

        {message ? (
          <div className="rounded-md bg-white/80 px-3 py-2 text-sm text-amber-950">{message}</div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <a href={downloadUrl} rel="noreferrer">
            <Button type="button">
              <Download className="h-4 w-4" />
              Download Windows package
            </Button>
          </a>
          <Button type="button" disabled={checking} onClick={() => void probe(serviceUrlInput)}>
            <RefreshCw className={`h-4 w-4 ${checking ? 'animate-spin' : ''}`} />
            {checking ? 'Testing…' : 'Test connection'}
          </Button>
          <a href="http://127.0.0.1:8000" target="_blank" rel="noreferrer">
            <Button type="button" variant="secondary">
              <ExternalLink className="h-4 w-4" />
              Open local OpenSnap
            </Button>
          </a>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setStoredServiceUrl(serviceUrlInput)
              window.location.assign('/settings')
            }}
          >
            Connection settings
          </Button>
        </div>

        <div className="border-t border-amber-200/80 pt-3">
          <p className="mb-2 text-xs text-amber-900/80">
            Optional: if <code>opensnap://</code> was registered by a prior EXE install, you can try
            starting the service from this page. Download remains the primary path.
          </p>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={launching || checking}
            onClick={tryOptionalProtocol}
          >
            <Play className={`h-4 w-4 ${launching ? 'animate-pulse' : ''}`} />
            {launching ? 'Trying opensnap://…' : 'Try opensnap:// start (optional)'}
          </Button>
        </div>
      </Card>
    </div>
  )
}
