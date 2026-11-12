import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { AlertTriangle, HardDrive, Plus, Video } from 'lucide-react'
import { api } from '@/lib/api'
import { formatBytes } from '@/lib/utils'
import { Badge, Button, Card, PageHeader, StatusDot } from '@/components/ui'

export function Dashboard() {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 3000 })
  const sessions = useQuery({ queryKey: ['sessions'], queryFn: () => api.sessions() })

  const h = health.data
  const warnings = h?.warnings ?? []

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle="Recording service status and recent sessions"
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
        </Card>
        <Card className="p-5">
          <div className="text-sm text-[var(--color-muted)]">Capture device</div>
          <div className="mt-2 text-xl font-semibold">
            {h?.capture.connected ? 'Connected' : 'Not connected'}
          </div>
          <div className="mt-3 text-sm text-[var(--color-muted)]">
            {h?.capture.source_type ?? '—'}
            {h?.capture.incoming_fps ? ` · ${h.capture.incoming_fps.toFixed(1)} in FPS` : ''}
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
                  <td className="px-4 py-3">{s.procedure_date}</td>
                  <td className="px-4 py-3">
                    <Badge tone={s.status === 'recording' ? 'danger' : s.status === 'stopped' ? 'ok' : 'brand'}>
                      {s.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link to={`/sessions/${s.public_id}/record`}>
                      <Button variant="outline" size="sm">
                        <Video className="h-4 w-4" />
                        Open
                      </Button>
                    </Link>
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
