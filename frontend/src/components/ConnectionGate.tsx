import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { AlertTriangle, ExternalLink, Play, RefreshCw } from 'lucide-react'
import { api } from '@/lib/api'
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
 * Cloudflare UI shell cannot record by itself. Prefer OpenSnap.exe on the PC.
 * Advanced users may still point this remote UI at a running local service.
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

  const startLocalService = () => {
    setLaunching(true)
    setMessage(
      'Asking Windows to start OpenSnap… Allow the browser prompt if shown. First-time setup: run OpenSnap.exe once so opensnap:// is registered.',
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
              Start the local recording service
            </h1>
            <p className="mt-2 text-sm text-amber-950/90">
              This Cloudflare page is only a UI shell — patient data and video stay on the Windows
              PC. After a one-time OpenSnap.exe install, use <strong>Start local service</strong> so
              you do not need to hunt for the EXE each procedure day.
            </p>
          </div>
        </div>

        <ol className="list-decimal space-y-2 pl-5 text-sm text-amber-950">
          <li>
            <strong>One-time:</strong> extract <strong>OpenSnap-windows.zip</strong> and double-click{' '}
            <strong>OpenSnap.exe</strong> once (registers the <code>opensnap://</code> helper).
          </li>
          <li>
            Bookmark this Cloudflare page. On clinic days, open the bookmark and click{' '}
            <strong>Start local service</strong> — Windows launches the recorder via deep-link.
          </li>
          <li>
            Allow local/private network access when the browser prompts. PHI never goes through
            Cloudflare.
          </li>
        </ol>

        <Field label="Local recording service URL">
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
          <Button type="button" disabled={launching || checking} onClick={startLocalService}>
            <Play className={`h-4 w-4 ${launching ? 'animate-pulse' : ''}`} />
            {launching ? 'Starting…' : 'Start local service'}
          </Button>
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
      </Card>
    </div>
  )
}
