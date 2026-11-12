import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { Camera, Images, Square, Circle } from 'lucide-react'
import { api } from '@/lib/api'
import { formatDuration } from '@/lib/utils'
import { LivePreview } from '@/components/LivePreview'
import { Badge, Button, Card, PageHeader, Select, StatusDot } from '@/components/ui'

const INTERVALS = [1, 2, 3, 5, 10, 15, 30, 60]

export function Recording() {
  const { sessionId = '' } = useParams()
  const qc = useQueryClient()
  const session = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => api.session(sessionId),
    enabled: !!sessionId,
  })
  const status = useQuery({
    queryKey: ['recording', sessionId],
    queryFn: () => api.recordingStatus(sessionId),
    enabled: !!sessionId,
    refetchInterval: 500,
  })
  const pairing = useQuery({
    queryKey: ['pairing', sessionId],
    queryFn: () => api.createPairing(sessionId),
    enabled: !!sessionId,
    staleTime: 60_000,
  })

  const [interval, setIntervalSec] = useState(3)
  useEffect(() => {
    if (session.data) setIntervalSec(session.data.snapshot_interval_sec)
  }, [session.data?.snapshot_interval_sec])

  const start = useMutation({
    mutationFn: () => api.startRecording(sessionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recording', sessionId] })
      qc.invalidateQueries({ queryKey: ['session', sessionId] })
    },
  })
  const stop = useMutation({
    mutationFn: () => api.stopRecording(sessionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recording', sessionId] })
      qc.invalidateQueries({ queryKey: ['session', sessionId] })
    },
  })
  const snap = useMutation({
    mutationFn: () => api.takeSnapshot(sessionId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['recording', sessionId] }),
  })
  const updateInterval = useMutation({
    mutationFn: (value: number) =>
      api.updateSession(sessionId, { snapshot_interval_sec: value }),
  })
  const revoke = useMutation({
    mutationFn: () => api.revokePairing(sessionId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pairing', sessionId] }),
  })

  const s = status.data
  const recording = s?.state === 'recording'
  // Always allow Stop while a take is in progress — never trap the user if status flaps to "error".
  const canStop =
    recording || ((s?.elapsed_sec ?? 0) > 0 && s?.state !== 'stopped' && s?.state !== 'ready')

  return (
    <div>
      <PageHeader
        title="Active Recording"
        subtitle={
          session.data
            ? `${session.data.display_procedure_name} · ${session.data.patient_name}`
            : 'Loading session…'
        }
        actions={
          <div className="flex gap-2">
            <Link to={`/sessions/${sessionId}/gallery`}>
              <Button variant="outline">
                <Images className="h-4 w-4" />
                Gallery
              </Button>
            </Link>
            <Link to={`/sessions/${sessionId}/report`}>
              <Button variant="secondary">Report</Button>
            </Link>
          </div>
        }
      />

      <div className="grid gap-5 xl:grid-cols-[1.4fr_0.8fr]">
        <Card className="overflow-hidden animate-fade-up">
          <div className="relative aspect-video bg-slate-900">
            <LivePreview sessionId={sessionId} />
            {recording ? (
              <div className="absolute left-4 top-4 flex items-center gap-2 rounded-md bg-red-600 px-3 py-1.5 text-sm font-semibold text-white">
                <span className="rec-dot h-2.5 w-2.5 rounded-full bg-white" />
                REC {formatDuration(s?.elapsed_sec ?? 0)}
              </div>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-3 border-t border-[var(--color-line)] p-4">
            <Button
              size="lg"
              disabled={recording || start.isPending}
              onClick={() => start.mutate()}
            >
              <Circle className="h-5 w-5 fill-current" />
              Start Recording
            </Button>
            <Button
              size="lg"
              variant="danger"
              disabled={!canStop || stop.isPending}
              onClick={() => stop.mutate()}
            >
              <Square className="h-5 w-5 fill-current" />
              Stop Recording
            </Button>
            <Button
              size="lg"
              variant="secondary"
              disabled={snap.isPending}
              onClick={() => snap.mutate()}
            >
              <Camera className="h-5 w-5" />
              Take Snapshot
            </Button>
          </div>
        </Card>

        <div className="space-y-4 animate-fade-up">
          <Card className="space-y-3 p-5">
            <h2 className="text-lg font-semibold">Status</h2>
            <div className="flex flex-wrap gap-2">
              <Badge tone={recording ? 'danger' : 'brand'}>{s?.state ?? '…'}</Badge>
              <Badge tone={s?.capture.connected ? 'ok' : 'warn'}>
                Capture {s?.capture.connected ? 'OK' : 'Down'}
              </Badge>
              <Badge tone={s?.remote_connected ? 'ok' : 'neutral'}>
                Remote {s?.remote_connected ? 'connected' : 'waiting'}
              </Badge>
            </div>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-[var(--color-muted)]">Requested FPS</dt>
                <dd className="font-semibold">{s?.requested_fps ?? session.data?.requested_fps ?? '—'}</dd>
              </div>
              <div>
                <dt className="text-[var(--color-muted)]">Actual FPS</dt>
                <dd className="font-semibold">
                  {s?.actual_fps ? s.actual_fps.toFixed(1) : recording ? '…' : '—'}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--color-muted)]">Incoming FPS</dt>
                <dd className="font-semibold">
                  {s?.incoming_fps ? s.incoming_fps.toFixed(1) : '—'}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--color-muted)]">Elapsed</dt>
                <dd className="font-semibold">{formatDuration(s?.elapsed_sec ?? 0)}</dd>
              </div>
              <div>
                <dt className="text-[var(--color-muted)]">Snapshots</dt>
                <dd className="font-semibold">
                  {s?.snapshot_count ?? 0} total · {s?.manual_snapshot_count ?? 0} manual
                </dd>
              </div>
            </dl>
            {s?.warning ? (
              <div className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900">{s.warning}</div>
            ) : null}
            {s?.error ? (
              <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">{s.error}</div>
            ) : null}
            <div>
              <label className="mb-1 block text-sm font-semibold">Snapshot interval</label>
              <Select
                value={interval}
                onChange={(e) => {
                  const value = Number(e.target.value)
                  setIntervalSec(value)
                  updateInterval.mutate(value)
                }}
              >
                {INTERVALS.map((i) => (
                  <option key={i} value={i}>
                    Every {i}s
                  </option>
                ))}
              </Select>
              <p className="mt-1 text-xs text-[var(--color-muted)]">
                Can be changed during recording without interrupting video.
              </p>
            </div>
          </Card>

          <Card className="p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold">iPhone remote</h2>
              <Button variant="outline" size="sm" onClick={() => revoke.mutate()}>
                Revoke
              </Button>
            </div>
            <StatusDot active={!!s?.remote_connected} label="Remote controller" />
            <div className="mt-4 flex justify-center rounded-xl bg-white p-4">
              {pairing.data ? (
                <QRCodeSVG value={pairing.data.qr_payload} size={180} />
              ) : (
                <div className="flex h-[180px] w-[180px] items-center justify-center text-sm text-[var(--color-muted)]">
                  Generating QR…
                </div>
              )}
            </div>
            <p className="mt-3 break-all text-xs text-[var(--color-muted)]">
              {pairing.data?.pairing_url}
            </p>
            <p className="mt-2 text-xs text-[var(--color-muted)]">
              QR contains a temporary pairing token only — no patient identifiers.
              Scan from a phone on the same approved local network.
            </p>
          </Card>
        </div>
      </div>
    </div>
  )
}
