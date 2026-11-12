import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { AlertTriangle, HardDrive, Plus, Video } from 'lucide-react'
import { api } from '@/lib/api'
import { getServiceBaseUrl, isSameOriginService } from '@/lib/runtime'
import { formatBytes, formatDate } from '@/lib/utils'
import { DeleteSessionButton } from '@/components/DeleteSessionButton'
import { Badge, Button, Card, PageHeader, StatusDot } from '@/components/ui'

export function Dashboard() {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 3000 })
  const sessions = useQuery({ queryKey: ['sessions'], queryFn: () => api.sessions() })

  const h = health.data
  const warnings = h?.warnings ?? []
  const serviceBase = getServiceBaseUrl() || window.location.origin

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle={
          isSameOriginService()
            ? 'Recording service status and recent sessions'
            : `UI may be remote; processing is local at ${serviceBase}`
        }
        actions={
          <Link to="/sessions/new">
            <Button size="lg">
              <Plus className="h-5 w-5" />
              New Session
            </Button>
          </Link>
        }
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4 animate-fade-up">
        <Card className="p-5">
          <div className="text-sm text-[var(--color-muted)]">Recording service</div>
          <div className="mt-2 text-xl font-semibold">{h ? 'Online' : health.isError ? 'Offline' : '…'}</div>
          <div className="mt-3">
            <StatusDot active={!!h && h.status === 'ok'} label={h?.service ?? 'Checking…'} />
          </div>
          <div className="mt-2 text-xs text-[var(--color-muted)]">Build {h?.version ?? '…'}</div>
        </Card>
        <Card className="p-5">
          <div className="text-sm text-[var(--color-muted)]">Capture device</div>
          <div className="mt-2 text-xl font-semibold">
            {(h?.cameras_detected ?? 0) > 0
              ? `${h?.cameras_detected} detected`
              : h?.capture.connected
                ? 'Connected'
                : 'None detected'}
          </div>
          <div className="mt-3 text-sm text-[var(--color-muted)]">
            {h?.camera_names?.[0] ||
              (h?.active_session_id
                ? `${h?.capture.source_type ?? '—'}${h?.capture.incoming_fps ? ` · ${h.capture.incoming_fps.toFixed(1)} in FPS` : ''}`
                : 'Idle — open New Session to use a camera')}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-sm text-[var(--color-muted)]">Recording status</div>
          <div className="mt-2 flex items-center gap-2 text-xl font-semibold capitalize">
            {h?.recording_state === 'recording' ? (
              <span className="rec-dot inline-block h-3 w-3 rounded-full bg-red-600" />
            ) : null}
            {h?.recording_state ?? '—'}
          </div>
          <div className="mt-3 text-sm text-[var(--color-muted)]">
            Active session: {h?.active_session_id ?? 'None'}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-sm text-[var(--color-muted)]">Disk space</div>
          <div className="mt-2 text-xl font-semibold">
            {h ? formatBytes(h.disk_free_bytes) : '—'}
          </div>
          <div className="mt-3 flex items-center gap-2 text-sm text-[var(--color-muted)]">
            <HardDrive className="h-4 w-4" />
            {h ? `${formatBytes(h.disk_free_bytes)} free of ${formatBytes(h.disk_total_bytes)}` : '…'}
          </div>
        </Card>
      </div>

      {health.isError ? (
        <Card className="mt-4 border-red-200 bg-red-50/80 p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 text-red-700" />
            <div className="space-y-2">
              <div className="font-semibold text-red-900">Local recording service unreachable</div>
              <p className="text-sm text-red-900">
                Run <strong>OpenSnap.exe</strong> on the Windows PC (double-click). It starts the
                recorder and opens the app at{' '}
                <a className="font-semibold underline" href="http://127.0.0.1:8000" target="_blank" rel="noreferrer">
                  http://127.0.0.1:8000
                </a>
                . This Cloudflare page cannot capture video by itself.
              </p>
              <div className="flex flex-wrap gap-3 text-sm">
                <a className="font-semibold underline text-red-950" href={`${serviceBase}/api/health`} target="_blank" rel="noreferrer">
                  Check /api/health
                </a>
                <Link to="/settings" className="font-semibold text-red-950 underline">
                  Connection settings
                </Link>
              </div>
            </div>
          </div>
        </Card>
      ) : null}

      {warnings.length > 0 ? (
        <Card className="mt-4 border-amber-200 bg-amber-50/80 p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 text-amber-700" />
            <div>
              <div className="font-semibold text-amber-900">System warnings</div>
              <ul className="mt-1 list-disc pl-5 text-sm text-amber-900">
                {warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          </div>
        </Card>
      ) : null}

      <div className="mt-8">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xl font-semibold">Recent sessions</h2>
          <Link to="/sessions" className="text-sm font-semibold text-[var(--color-brand)]">
            View all
          </Link>
        </div>
        <Card className="overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-[var(--color-muted)]">
              <tr>
                <th className="px-4 py-3 font-semibold">Patient</th>
                <th className="px-4 py-3 font-semibold">Procedure</th>
                <th className="px-4 py-3 font-semibold">Date</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold" />
              </tr>
            </thead>
            <tbody>
              {(sessions.data ?? []).slice(0, 8).map((s) => (
                <tr key={s.public_id} className="border-t border-[var(--color-line)]">
                  <td className="px-4 py-3">{s.patient_name}</td>
                  <td className="px-4 py-3">{s.display_procedure_name}</td>
                  <td className="px-4 py-3 whitespace-nowrap">{formatDate(s.procedure_date)}</td>
                  <td className="px-4 py-3">
                    <Badge
                      tone={
                        s.status === 'recording'
                          ? 'danger'
                          : s.status === 'interrupted' || s.status === 'error'
                            ? 'warn'
                            : s.status === 'stopped' || s.status === 'completed'
                              ? 'ok'
                              : 'brand'
                      }
                    >
                      {s.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-1">
                      <Link to={`/sessions/${s.public_id}/record`}>
                        <Button variant="outline" size="sm">
                          <Video className="h-4 w-4" />
                          Open
                        </Button>
                      </Link>
                      <DeleteSessionButton session={s} />
                    </div>
                  </td>
                </tr>
              ))}
              {(sessions.data ?? []).length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-[var(--color-muted)]">
                    No sessions yet. Create a new session to begin.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  )
}
