import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Button, Card, Field, PageHeader, Select, Textarea } from '@/components/ui'
import { FileText } from 'lucide-react'

export function ReportPage() {
  const { sessionId = '' } = useParams()
  const qc = useQueryClient()
  const session = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => api.session(sessionId),
    enabled: !!sessionId,
  })
  const snapshots = useQuery({
    queryKey: ['snapshots', sessionId],
    queryFn: () => api.snapshots(sessionId),
    enabled: !!sessionId,
  })
  const reports = useQuery({
    queryKey: ['reports', sessionId],
    queryFn: () => api.reports(sessionId),
    enabled: !!sessionId,
  })

  const [notes, setNotes] = useState('')
  const [imagesPerPage, setImagesPerPage] = useState(4)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

  useEffect(() => {
    if (session.data) {
      setNotes(session.data.notes || '')
      setImagesPerPage(session.data.images_per_page || 4)
    }
  }, [session.data?.notes, session.data?.images_per_page])

  const selectedCount = (snapshots.data ?? []).filter((s) => s.selected).length
  const densityWarn = imagesPerPage >= 16

  const saveNotes = useMutation({
    mutationFn: () => api.updateSession(sessionId, { notes, images_per_page: imagesPerPage }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['session', sessionId] }),
  })

  const generate = useMutation({
    mutationFn: () =>
      api.createReport(sessionId, {
        notes,
        images_per_page: imagesPerPage,
        include_captions: true,
        include_timestamps: true,
      }),
    onSuccess: (report) => {
      qc.invalidateQueries({ queryKey: ['reports', sessionId] })
      qc.invalidateQueries({ queryKey: ['session', sessionId] })
      setPreviewUrl(report.preview_url)
    },
  })

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="Report Generator"
        subtitle="Simple PDF: letterhead, demographics, procedure details, Notes, and selected photographs."
        actions={
          <Link to={`/sessions/${sessionId}/gallery`}>
            <Button variant="outline">Gallery</Button>
          </Link>
        }
      />

      <div className="space-y-5 animate-fade-up">
        <Card className="space-y-3 p-5">
          <h2 className="text-lg font-semibold">Session</h2>
          {session.data ? (
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-[var(--color-muted)]">Patient</dt>
                <dd className="font-semibold">{session.data.patient_name}</dd>
              </div>
              <div>
                <dt className="text-[var(--color-muted)]">MRN</dt>
                <dd className="font-semibold">{session.data.medical_record_number}</dd>
              </div>
              <div>
                <dt className="text-[var(--color-muted)]">Procedure</dt>
                <dd className="font-semibold">{session.data.display_procedure_name}</dd>
              </div>
              <div>
                <dt className="text-[var(--color-muted)]">Physician</dt>
                <dd className="font-semibold">{session.data.physician}</dd>
              </div>
            </dl>
          ) : null}
        </Card>

        <Card className="space-y-3 p-5">
          <Field
            label="Notes"
            hint="Single unrestricted free-text field. No Findings / Impression / Plan sections."
          >
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Enter procedure notes…"
              rows={10}
            />
          </Field>
          <div className="flex justify-end">
            <Button variant="secondary" onClick={() => saveNotes.mutate()} disabled={saveNotes.isPending}>
              Save Notes
            </Button>
          </div>
        </Card>

        <Card className="space-y-4 p-5">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <Field label="Photographs per PDF page" hint="1–20. Default 4.">
              <Select
                value={imagesPerPage}
                onChange={(e) => setImagesPerPage(Number(e.target.value))}
              >
                {Array.from({ length: 20 }, (_, i) => i + 1).map((n) => (
                  <option key={n} value={n}>
                    {n} per page
                  </option>
                ))}
              </Select>
            </Field>
            <div className="text-sm text-[var(--color-muted)]">{selectedCount} photographs selected</div>
          </div>
          {densityWarn ? (
            <div className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900">
              High density may make images unusually small.
            </div>
          ) : null}
          <div className="flex flex-wrap gap-3">
            <Button
              size="lg"
              onClick={() => generate.mutate()}
              disabled={generate.isPending}
            >
              <FileText className="h-5 w-5" />
              {generate.isPending ? 'Generating…' : 'Preview & Generate PDF'}
            </Button>
          </div>
          {generate.isError ? (
            <div className="text-sm text-red-700">{(generate.error as Error).message}</div>
          ) : null}
        </Card>

        {previewUrl ? (
          <Card className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-[var(--color-line)] px-4 py-3">
              <h2 className="font-semibold">PDF preview</h2>
              <a href={previewUrl} target="_blank" rel="noreferrer">
                <Button variant="outline" size="sm">
                  Open / Download
                </Button>
              </a>
            </div>
            <iframe title="PDF preview" src={previewUrl} className="h-[70vh] w-full bg-slate-100" />
          </Card>
        ) : null}

        <Card className="p-5">
          <h2 className="mb-3 text-lg font-semibold">Previous versions</h2>
          <ul className="space-y-2 text-sm">
            {(reports.data ?? []).map((r) => (
              <li
                key={r.id}
                className="flex items-center justify-between rounded-lg border border-[var(--color-line)] px-3 py-2"
              >
                <span>
                  Version {r.version} · {new Date(r.created_at).toLocaleString()} · {r.images_per_page}/page
                </span>
                <a href={r.download_url} target="_blank" rel="noreferrer" className="font-semibold text-[var(--color-brand)]">
                  Download
                </a>
              </li>
            ))}
            {(reports.data ?? []).length === 0 ? (
              <li className="text-[var(--color-muted)]">No reports generated yet.</li>
            ) : null}
          </ul>
        </Card>
      </div>
    </div>
  )
}
