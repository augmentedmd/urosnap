import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useMemo, useState } from 'react'
import { api, type Snapshot } from '@/lib/api'
import { cn, formatDate } from '@/lib/utils'
import { Badge, Button, Card, Input, PageHeader } from '@/components/ui'
import { ArrowDown, ArrowUp, Check, FileText } from 'lucide-react'

export function Gallery() {
  const { sessionId = '' } = useParams()
  const qc = useQueryClient()
  const [viewer, setViewer] = useState<Snapshot | null>(null)

  const snapshots = useQuery({
    queryKey: ['snapshots', sessionId],
    queryFn: () => api.snapshots(sessionId),
    enabled: !!sessionId,
    refetchInterval: 2000,
  })

  const selected = useMemo(
    () =>
      (snapshots.data ?? [])
        .filter((s) => s.selected)
        .sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0)),
    [snapshots.data],
  )

  const toggle = useMutation({
    mutationFn: ({ id, selected }: { id: number; selected: boolean }) =>
      api.updateSnapshot(id, { selected }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['snapshots', sessionId] }),
  })

  const bulk = useMutation({
    mutationFn: (body: { selected_ids: number[]; ordered_ids?: number[] }) =>
      api.bulkSelection(sessionId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['snapshots', sessionId] }),
  })

  const caption = useMutation({
    mutationFn: ({ id, caption }: { id: number; caption: string }) =>
      api.updateSnapshot(id, { caption }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['snapshots', sessionId] }),
  })

  const moveSelected = (id: number, dir: -1 | 1) => {
    const ids = selected.map((s) => s.id)
    const idx = ids.indexOf(id)
    const swap = idx + dir
    if (idx < 0 || swap < 0 || swap >= ids.length) return
    ;[ids[idx], ids[swap]] = [ids[swap], ids[idx]]
    bulk.mutate({ selected_ids: ids, ordered_ids: ids })
  }

  return (
    <div>
      <PageHeader
        title="Image Gallery"
        subtitle="Select and reorder photographs for the PDF report. Originals are never deleted."
        actions={
          <div className="flex gap-2">
            <Link to={`/sessions/${sessionId}/record`}>
              <Button variant="outline">Back to Recording</Button>
            </Link>
            <Link to={`/sessions/${sessionId}/report`}>
              <Button>
                <FileText className="h-4 w-4" />
                Report ({selected.length})
              </Button>
            </Link>
          </div>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() =>
            bulk.mutate({
              selected_ids: (snapshots.data ?? []).map((s) => s.id),
              ordered_ids: (snapshots.data ?? []).map((s) => s.id),
            })
          }
        >
          Select All
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => bulk.mutate({ selected_ids: [], ordered_ids: [] })}
        >
          Deselect All
        </Button>
        <Badge tone="brand">{selected.length} selected</Badge>
        <Badge tone="neutral">{snapshots.data?.length ?? 0} total</Badge>
      </div>

      {selected.length > 0 ? (
        <Card className="mb-5 p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--color-muted)]">
            Selected order
          </h2>
          <div className="flex flex-wrap gap-3">
            {selected.map((s, i) => (
              <div key={s.id} className="flex items-center gap-2 rounded-lg border border-[var(--color-line)] p-2">
                <img src={s.thumbnail_url} alt="" className="h-12 w-16 rounded object-cover" />
                <span className="text-sm font-semibold">#{i + 1}</span>
                <button
                  type="button"
                  className="rounded p-1 hover:bg-slate-100"
                  onClick={() => moveSelected(s.id, -1)}
                  aria-label="Move up"
                >
                  <ArrowUp className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  className="rounded p-1 hover:bg-slate-100"
                  onClick={() => moveSelected(s.id, 1)}
                  aria-label="Move down"
                >
                  <ArrowDown className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6">
        {(snapshots.data ?? []).map((snap) => (
          <button
            key={snap.id}
            type="button"
            onClick={() => toggle.mutate({ id: snap.id, selected: !snap.selected })}
            onDoubleClick={() => setViewer(snap)}
            className={cn(
              'group relative overflow-hidden rounded-xl border-2 bg-white text-left transition',
              snap.selected ? 'border-[var(--color-brand)]' : 'border-transparent hover:border-slate-300',
            )}
          >
            <img src={snap.thumbnail_url} alt="" className="aspect-video w-full object-cover" loading="lazy" />
            <div className="space-y-1 p-2">
              <div className="flex items-center justify-between gap-2">
                <Badge tone={snap.capture_type === 'manual' ? 'brand' : 'neutral'}>
                  {snap.capture_type}
                </Badge>
                {snap.selected ? (
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--color-brand)] text-white">
                    <Check className="h-3 w-3" />
                  </span>
                ) : null}
              </div>
              <div className="text-[11px] text-[var(--color-muted)]">
                {formatDate(snap.capture_timestamp)} · {new Date(snap.capture_timestamp).toLocaleTimeString()}
              </div>
            </div>
          </button>
        ))}
      </div>

      {(snapshots.data ?? []).length === 0 ? (
        <Card className="p-10 text-center text-[var(--color-muted)]">
          No photographs yet. Start recording to capture automatic and manual snapshots.
        </Card>
      ) : null}

      {viewer ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          onClick={() => setViewer(null)}
        >
          <div
            className="max-h-[90vh] w-full max-w-4xl overflow-auto rounded-2xl bg-white p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <img src={viewer.image_url} alt="" className="max-h-[70vh] w-full object-contain" />
            <div className="mt-3 flex flex-wrap items-end gap-3">
              <div className="flex-1">
                <label className="mb-1 block text-sm font-semibold">Caption</label>
                <Input
                  defaultValue={viewer.caption}
                  onBlur={(e) => caption.mutate({ id: viewer.id, caption: e.target.value })}
                />
              </div>
              <Button variant="outline" onClick={() => setViewer(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
