import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { FolderOpen } from 'lucide-react'
import { api, type Settings as SettingsType, type StorageBrowse } from '@/lib/api'
import {
  getServiceBaseUrl,
  getUiBaseUrl,
  setStoredServiceUrl,
  setStoredUiBaseUrl,
} from '@/lib/runtime'
import { Button, Card, Field, Input, PageHeader, Select } from '@/components/ui'

const empty: SettingsType = {
  practice_name: '',
  practice_address_line1: '',
  practice_address_line2: '',
  practice_phone: '',
  default_fps: 15,
  default_snapshot_interval_sec: 3,
  default_images_per_page: 4,
  default_resolution: '1280x720',
  default_capture_source: 'synthetic',
  preferred_physician: '',
  preferred_procedure_type: '',
  preferred_capture_device_id: '',
  storage_path: '',
  pairing_token_ttl_seconds: 900,
}

export function SettingsPage() {
  const qc = useQueryClient()
  const settings = useQuery({ queryKey: ['settings'], queryFn: api.settings })
  const devices = useQuery({ queryKey: ['devices'], queryFn: api.devices })
  const procedures = useQuery({ queryKey: ['procedures'], queryFn: api.procedureTypes })
  const [form, setForm] = useState<SettingsType>(empty)
  const [serviceUrlInput, setServiceUrlInput] = useState('')
  const [uiBaseInput, setUiBaseInput] = useState('')
  const [probeMessage, setProbeMessage] = useState<string | null>(null)
  const [probeOk, setProbeOk] = useState<boolean | null>(null)
  const [browserOpen, setBrowserOpen] = useState(false)
  const [browse, setBrowse] = useState<StorageBrowse | null>(null)
  const [browseError, setBrowseError] = useState<string | null>(null)
  const [browseLoading, setBrowseLoading] = useState(false)

  useEffect(() => {
    if (settings.data) setForm(settings.data)
  }, [settings.data])

  const openFolderBrowser = async (path?: string) => {
    setBrowserOpen(true)
    setBrowseLoading(true)
    setBrowseError(null)
    try {
      const result = await api.browseStorage(path)
      setBrowse(result)
    } catch (err) {
      setBrowseError((err as Error).message)
    } finally {
      setBrowseLoading(false)
    }
  }

  useEffect(() => {
    setServiceUrlInput(getServiceBaseUrl())
    setUiBaseInput(getUiBaseUrl())
  }, [])

  const save = useMutation({
    mutationFn: () => api.updateSettings(form),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
  })

  const probeConnection = async () => {
    const base = (serviceUrlInput || 'http://127.0.0.1:8000').replace(/\/+$/, '')
    setProbeMessage('Testing…')
    setProbeOk(null)
    try {
      const res = await fetch(`${base}/api/health`, {
        headers: { 'X-Desktop-Token': 'local-desktop-dev-token' },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const body = (await res.json()) as { service?: string; status?: string }
      setProbeOk(true)
      setProbeMessage(`Connected to ${body.service ?? 'OpenSnap'} (${body.status ?? 'ok'}) at ${base}`)
    } catch (err) {
      setProbeOk(false)
      setProbeMessage(
        `Could not reach ${base}. Start uvicorn on the Windows PC, allow local network access if the browser prompts, and confirm the URL. ${(err as Error).message}`,
      )
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Settings" subtitle="Physician preferences, practice letterhead, and local storage." />
      <div className="space-y-5 animate-fade-up">
        <Card className="space-y-4 p-5">
          <h2 className="text-lg font-semibold">Local processing connection</h2>
          <p className="text-xs text-[var(--color-muted)]">
            Cloudflare may host only the OpenSnap UI shell. Video, snapshots, patient data, and PDFs
            always stay on the local Windows recording service. Do not point these URLs at Cloudflare.
          </p>
          <Field
            label="Local recording service URL"
            hint="Used by this browser for all API and media calls. Example: http://127.0.0.1:8000 or http://192.168.1.20:8000"
          >
            <Input
              value={serviceUrlInput}
              placeholder="http://127.0.0.1:8000"
              onChange={(e) => setServiceUrlInput(e.target.value)}
            />
          </Field>
          <Field
            label="Public UI base URL (optional)"
            hint="Cloudflare Worker/Pages origin used inside iPhone QR links. Remote commands still go to the local service."
          >
            <Input
              value={uiBaseInput}
              placeholder="https://opensnap.example.workers.dev"
              onChange={(e) => setUiBaseInput(e.target.value)}
            />
          </Field>
          {probeMessage ? (
            <div
              className={
                probeOk
                  ? 'rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-900'
                  : probeOk === false
                    ? 'rounded-md bg-red-50 px-3 py-2 text-sm text-red-900'
                    : 'rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700'
              }
            >
              {probeMessage}
            </div>
          ) : null}
          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => void probeConnection()}>
              Test connection
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setStoredServiceUrl(serviceUrlInput)
                setStoredUiBaseUrl(uiBaseInput)
                qc.invalidateQueries()
                window.location.reload()
              }}
            >
              Save connection
            </Button>
          </div>
        </Card>

        <Card className="space-y-4 p-5">
          <h2 className="text-lg font-semibold">Practice information</h2>
          <p className="text-xs text-[var(--color-muted)]">
            Verify against official practice information before clinical deployment. Do not use an institutional logo unless authorized.
          </p>
          <Field label="Practice name">
            <Input value={form.practice_name} onChange={(e) => setForm({ ...form, practice_name: e.target.value })} />
          </Field>
          <Field label="Address line 1">
            <Input
              value={form.practice_address_line1}
              onChange={(e) => setForm({ ...form, practice_address_line1: e.target.value })}
            />
          </Field>
          <Field label="Address line 2">
            <Input
              value={form.practice_address_line2}
              onChange={(e) => setForm({ ...form, practice_address_line2: e.target.value })}
            />
          </Field>
          <Field label="Telephone">
            <Input value={form.practice_phone} onChange={(e) => setForm({ ...form, practice_phone: e.target.value })} />
          </Field>
          <ReportLogoField />
        </Card>

        <Card className="space-y-4 p-5">
          <h2 className="text-lg font-semibold">Physician preferences</h2>
          <Field label="Default performing physician">
            <Input
              value={form.preferred_physician}
              onChange={(e) => setForm({ ...form, preferred_physician: e.target.value })}
            />
          </Field>
          <Field label="Default procedure type">
            <Select
              value={form.preferred_procedure_type}
              onChange={(e) => setForm({ ...form, preferred_procedure_type: e.target.value })}
            >
              <option value="">—</option>
              {(procedures.data ?? []).map((p) => (
                <option key={p.id} value={p.name}>
                  {p.name}
                </option>
              ))}
            </Select>
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Default FPS">
              <Select
                value={form.default_fps}
                onChange={(e) => setForm({ ...form, default_fps: Number(e.target.value) })}
              >
                {[5, 10, 15, 24, 30, 60].map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Default snapshot interval (sec)">
              <Select
                value={form.default_snapshot_interval_sec}
                onChange={(e) =>
                  setForm({ ...form, default_snapshot_interval_sec: Number(e.target.value) })
                }
              >
                {[1, 2, 3, 5, 10, 15, 30, 60].map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Default images per PDF page">
              <Select
                value={form.default_images_per_page}
                onChange={(e) => setForm({ ...form, default_images_per_page: Number(e.target.value) })}
              >
                {Array.from({ length: 20 }, (_, i) => i + 1).map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Preferred capture device">
              <Select
                value={form.preferred_capture_device_id || form.default_capture_source}
                onChange={(e) => {
                  const device = devices.data?.find((d) => d.id === e.target.value)
                  setForm({
                    ...form,
                    preferred_capture_device_id: e.target.value,
                    default_capture_source: device?.source_type || form.default_capture_source,
                  })
                }}
              >
                {(devices.data ?? []).map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        </Card>

        <Card className="space-y-4 p-5">
          <h2 className="text-lg font-semibold">Local storage & mobile</h2>
          <Field
            label="Save sessions to folder"
            hint="Browse folders on the Windows recording PC. Session video, snapshots, and PDFs are stored here."
          >
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                value={form.storage_path}
                onChange={(e) => setForm({ ...form, storage_path: e.target.value })}
                placeholder="C:\\OpenSnap\\data\\opensnap_sessions"
              />
              <Button type="button" variant="outline" onClick={() => void openFolderBrowser(form.storage_path || undefined)}>
                <FolderOpen className="h-4 w-4" />
                Browse
              </Button>
            </div>
          </Field>
          {browserOpen ? (
            <div className="rounded-lg border border-[var(--color-line)] bg-slate-50 p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-semibold">Choose a folder</div>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={!browse?.parent || browseLoading}
                    onClick={() => void openFolderBrowser(browse?.parent || undefined)}
                  >
                    Up
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    disabled={!browse?.current || browseLoading}
                    onClick={() => {
                      if (browse?.current) {
                        setForm({ ...form, storage_path: browse.current })
                        setBrowserOpen(false)
                      }
                    }}
                  >
                    Use this folder
                  </Button>
                  <Button type="button" variant="outline" size="sm" onClick={() => setBrowserOpen(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
              <div className="mb-2 break-all text-xs text-[var(--color-muted)]">
                {browseLoading ? 'Loading…' : browse?.current || '—'}
                {browse && !browse.writable ? ' (not writable)' : ''}
              </div>
              {browseError ? <div className="mb-2 text-sm text-red-700">{browseError}</div> : null}
              {browse?.drives?.length ? (
                <div className="mb-2 flex flex-wrap gap-2">
                  {browse.drives.map((drive) => (
                    <Button
                      key={drive}
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => void openFolderBrowser(drive)}
                    >
                      {drive}
                    </Button>
                  ))}
                </div>
              ) : null}
              <ul className="max-h-56 overflow-auto rounded-md border border-[var(--color-line)] bg-white">
                {(browse?.directories ?? []).map((dir) => {
                  const name = dir.replace(/\\/g, '/').split('/').filter(Boolean).pop() || dir
                  return (
                    <li key={dir}>
                      <button
                        type="button"
                        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-slate-50"
                        onClick={() => void openFolderBrowser(dir)}
                      >
                        <FolderOpen className="h-4 w-4 text-[var(--color-muted)]" />
                        {name}
                      </button>
                    </li>
                  )
                })}
                {!browseLoading && (browse?.directories?.length ?? 0) === 0 ? (
                  <li className="px-3 py-4 text-sm text-[var(--color-muted)]">No subfolders here</li>
                ) : null}
              </ul>
            </div>
          ) : null}
          <Field label="QR pairing token TTL (seconds)">
            <Input
              type="number"
              value={form.pairing_token_ttl_seconds}
              onChange={(e) =>
                setForm({ ...form, pairing_token_ttl_seconds: Number(e.target.value) })
              }
            />
          </Field>
        </Card>

        <div className="flex justify-end gap-3">
          {save.isSuccess ? <span className="self-center text-sm text-emerald-700">Saved</span> : null}
          <Button size="lg" onClick={() => save.mutate()} disabled={save.isPending}>
            Save Settings
          </Button>
        </div>
      </div>
    </div>
  )
}

function ReportLogoField() {
  const qc = useQueryClient()
  const info = useQuery({ queryKey: ['report-logo'], queryFn: api.reportLogoInfo })
  const [version, setVersion] = useState(0)
  const refresh = () => {
    setVersion((v) => v + 1)
    qc.invalidateQueries({ queryKey: ['report-logo'] })
  }
  const upload = useMutation({ mutationFn: (file: File) => api.uploadReportLogo(file), onSuccess: refresh })
  const reset = useMutation({ mutationFn: api.resetReportLogo, onSuccess: refresh })
  const error = (upload.error || reset.error) as Error | null

  return (
    <Field
      label="Report logo"
      hint="Printed at the top left of every PDF report. PNG with a transparent background works best."
    >
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex h-24 w-24 items-center justify-center rounded-lg border border-[var(--color-line)] bg-white p-2">
          <img key={version} src={api.reportLogoUrl()} alt="Report logo" className="max-h-full max-w-full" />
        </div>
        <div className="space-y-2">
          <label className="inline-flex h-9 cursor-pointer items-center rounded-lg border border-[var(--color-line)] bg-white px-3 text-sm font-semibold hover:bg-slate-50">
            {upload.isPending ? 'Uploading…' : 'Upload logo'}
            <input
              type="file"
              accept="image/png,image/jpeg"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) upload.mutate(file)
                e.target.value = ''
              }}
            />
          </label>
          {info.data?.custom ? (
            <div>
              <Button size="sm" variant="ghost" onClick={() => reset.mutate()} disabled={reset.isPending}>
                Use default Mount Sinai Doctors logo
              </Button>
            </div>
          ) : (
            <div className="text-xs text-[var(--color-muted)]">Using the default Mount Sinai Doctors logo.</div>
          )}
          {error ? <div className="text-xs text-red-700">{error.message}</div> : null}
        </div>
      </div>
    </Field>
  )
}
