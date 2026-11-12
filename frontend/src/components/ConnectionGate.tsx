import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { AlertTriangle, ExternalLink, RefreshCw } from 'lucide-react'
import { api } from '@/lib/api'
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
 * When the SPA is served from Cloudflare (or any remote origin), the browser
 * must reach the Windows recorder directly. Block the clinical UI until that
 * local link works — otherwise every screen looks broken (no feed, empty data).
 */
export function ConnectionGate({ children }: Props) {
  const location = useLocation()
  const remote = typeof window !== 'undefined' && isRemoteUiShell() && !isSameOriginService()
  const allowThrough = location.pathname.startsWith('/settings')
  const [serviceUrlInput, setServiceUrlInput] = useState(() => getServiceBaseUrl() || 'http://127.0.0.1:8000')
  const [checking, setChecking] = useState(remote)
  const [ok, setOk] = useState(!remote)
  const [message, setMessage] = useState<string | null>(null)

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
              Connect the local recording service
            </h1>
            <p className="mt-2 text-sm text-amber-950/90">
              This page is only the OpenSnap UI shell (Cloudflare). Video, camera preview, patient
              data, and PDFs stay on the Windows workstation at{' '}
              <code className="rounded bg-amber-100 px-1">{serviceUrlInput || 'http://127.0.0.1:8000'}</code>.
              The camera feed cannot appear until that local service is reachable from this browser.
            </p>
          </div>
        </div>

        <ol className="list-decimal space-y-2 pl-5 text-sm text-amber-950">
          <li>
            On the Windows PC, start the recorder:
            <pre className="mt-1 overflow-x-auto rounded bg-amber-100/90 p-2 text-xs text-amber-950">
              {`cd backend
.\\.venv\\Scripts\\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000`}
            </pre>
          </li>
          <li>
            Verify{' '}
            <a
              className="font-semibold underline"
              href={`${(serviceUrlInput || 'http://127.0.0.1:8000').replace(/\/+$/, '')}/api/health`}
              target="_blank"
              rel="noreferrer"
            >
              /api/health
            </a>{' '}
            opens on that PC.
          </li>
          <li>When Chrome/Edge asks to allow local network access for this site, choose Allow.</li>
          <li>
            Prefer clinical use on the workstation itself:{' '}
            <a className="font-semibold underline" href="http://127.0.0.1:8000" target="_blank" rel="noreferrer">
              http://127.0.0.1:8000
            </a>{' '}
            (same-origin UI + API — preview always works).
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
