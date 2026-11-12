import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { Button, Card, Field, Input, PageHeader, Select } from '@/components/ui'

const FPS = [5, 10, 15, 24, 30, 60]
const INTERVALS = [1, 2, 3, 5, 10, 15, 30, 60]

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

function nowTime() {
  return new Date().toTimeString().slice(0, 5)
}

export function NewSession() {
  const navigate = useNavigate()
  const settings = useQuery({ queryKey: ['settings'], queryFn: api.settings })
  const devices = useQuery({ queryKey: ['devices'], queryFn: api.devices })
  const procedures = useQuery({ queryKey: ['procedures'], queryFn: api.procedureTypes })

  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    date_of_birth: '',
    medical_record_number: '',
    procedure_type: 'Diagnostic cystoscopy',
    custom_procedure_name: '',
    save_custom_procedure: false,
    physician: '',
    location: '',
    procedure_date: todayISO(),
    procedure_time: nowTime(),
    capture_source: 'synthetic',
    capture_device_id: 'synthetic',
    resolution: '1280x720',
    requested_fps: 15,
    snapshot_interval_sec: 3,
    images_per_page: 4,
  })

  const selectedDevice = useMemo(
    () => devices.data?.find((d) => d.id === form.capture_device_id),
    [devices.data, form.capture_device_id],
  )

  useEffect(() => {
    if (!settings.data && !devices.data) return
    setForm((f) => {
      const preferredId = settings.data?.preferred_capture_device_id || ''
      const preferred = devices.data?.find((d) => d.id === preferredId && d.available)
      const firstCamera = devices.data?.find((d) => d.source_type === 'camera' && d.available)
      // Prefer saved preference, else first real camera, else synthetic.
      // User can always switch to a camera in the dropdown once Windows exposes it.
      const chosen =
        preferred ||
        firstCamera ||
        devices.data?.find((d) => d.id === 'synthetic') ||
        devices.data?.[0]

      return {
        ...f,
        physician: f.physician || settings.data?.preferred_physician || '',
        procedure_type: settings.data?.preferred_procedure_type || f.procedure_type,
        requested_fps: settings.data?.default_fps || f.requested_fps,
        snapshot_interval_sec: settings.data?.default_snapshot_interval_sec || f.snapshot_interval_sec,
        resolution: settings.data?.default_resolution || chosen?.resolutions?.[0] || f.resolution,
        capture_source: chosen?.source_type || f.capture_source,
        capture_device_id: chosen?.id || f.capture_device_id,
        images_per_page: settings.data?.default_images_per_page || f.images_per_page,
      }
    })
  }, [settings.data, devices.data])

  const create = useMutation({
    mutationFn: api.createSession,
    onSuccess: (session) => navigate(`/sessions/${session.public_id}/record`),
  })

  const isCustom = form.procedure_type === 'Other / Custom Procedure'

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="New Session"
        subtitle="All fields are optional. Demographics are never carried into the next session."
      />

      <form
        className="space-y-5 animate-fade-up"
        onSubmit={(e) => {
          e.preventDefault()
          const device = devices.data?.find((d) => d.id === form.capture_device_id)
          create.mutate({
            patient: {
              first_name: form.first_name,
              last_name: form.last_name,
              date_of_birth: form.date_of_birth || null,
              medical_record_number: form.medical_record_number,
            },
            procedure_type: form.procedure_type || 'Diagnostic cystoscopy',
            custom_procedure_name: isCustom ? form.custom_procedure_name || null : null,
            save_custom_procedure: isCustom && form.save_custom_procedure,
            physician: form.physician,
            location: form.location,
            procedure_date: form.procedure_date || todayISO(),
            procedure_time: form.procedure_time ? `${form.procedure_time}:00` : null,
            capture_source: device?.source_type || form.capture_source,
            capture_device_id: form.capture_device_id,
            resolution: form.resolution,
            requested_fps: Number(form.requested_fps),
            snapshot_interval_sec: Number(form.snapshot_interval_sec),
            images_per_page: Number(form.images_per_page),
          })
        }}
      >
        <Card className="space-y-4 p-5">
          <h2 className="text-lg font-semibold">Patient demographics</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="First name">
              <Input
                value={form.first_name}
                onChange={(e) => setForm({ ...form, first_name: e.target.value })}
              />
            </Field>
            <Field label="Last name">
              <Input
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              />
            </Field>
            <Field label="Date of birth">
              <Input
                type="date"
                value={form.date_of_birth}
                onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })}
              />
            </Field>
            <Field label="Medical record number">
              <Input
                value={form.medical_record_number}
                onChange={(e) => setForm({ ...form, medical_record_number: e.target.value })}
              />
            </Field>
          </div>
        </Card>

        <Card className="space-y-4 p-5">
          <h2 className="text-lg font-semibold">Procedure</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Procedure type">
              <Select
                value={form.procedure_type}
                onChange={(e) => setForm({ ...form, procedure_type: e.target.value })}
              >
                {(procedures.data ?? []).map((p) => (
                  <option key={p.id} value={p.name}>
                    {p.name}
                    {p.is_custom ? ' (saved custom)' : ''}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Performing urologist">
              <Input
                value={form.physician}
                onChange={(e) => setForm({ ...form, physician: e.target.value })}
              />
            </Field>
            <Field label="Procedure date">
              <Input
                type="date"
                value={form.procedure_date}
                onChange={(e) => setForm({ ...form, procedure_date: e.target.value })}
              />
            </Field>
            <Field label="Procedure time">
              <Input
                type="time"
                value={form.procedure_time}
                onChange={(e) => setForm({ ...form, procedure_time: e.target.value })}
              />
            </Field>
            <Field label="Location">
              <Input
                value={form.location}
                onChange={(e) => setForm({ ...form, location: e.target.value })}
              />
            </Field>
          </div>
          {isCustom ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Custom procedure name">
                <Input
                  value={form.custom_procedure_name}
                  onChange={(e) => setForm({ ...form, custom_procedure_name: e.target.value })}
                />
              </Field>
              <label className="flex items-end gap-2 pb-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.save_custom_procedure}
                  onChange={(e) => setForm({ ...form, save_custom_procedure: e.target.checked })}
                />
                Save custom name for future selection
              </label>
            </div>
          ) : null}
        </Card>

        <Card className="space-y-4 p-5">
          <h2 className="text-lg font-semibold">Recording settings</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Capture device"
              hint={
                (devices.data ?? []).some((d) => d.source_type === 'camera' && d.available)
                  ? 'Real cameras are preferred automatically when Windows exposes them.'
                  : 'No camera detected yet — synthetic simulator is active. Allow camera access for desktop apps in Windows Privacy settings, then refresh this page.'
              }
            >
              <Select
                value={form.capture_device_id}
                onChange={(e) => {
                  const device = devices.data?.find((d) => d.id === e.target.value)
                  setForm({
                    ...form,
                    capture_device_id: e.target.value,
                    capture_source: device?.source_type || 'synthetic',
                    resolution: device?.resolutions?.[0] || form.resolution,
                  })
                }}
              >
                {(devices.data ?? []).map((d) => (
                  <option key={d.id} value={d.id} disabled={!d.available}>
                    {d.name}
                    {!d.available ? ' (unavailable)' : ''}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Resolution">
              <Select
                value={form.resolution}
                onChange={(e) => setForm({ ...form, resolution: e.target.value })}
              >
                {(selectedDevice?.resolutions ?? ['1280x720']).map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Recording frame rate" hint="Actual recorded FPS (independent of snapshot interval)">
              <Select
                value={form.requested_fps}
                onChange={(e) => setForm({ ...form, requested_fps: Number(e.target.value) })}
              >
                {FPS.map((f) => (
                  <option key={f} value={f}>
                    {f} FPS
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Automatic snapshot interval">
              <Select
                value={form.snapshot_interval_sec}
                onChange={(e) => setForm({ ...form, snapshot_interval_sec: Number(e.target.value) })}
              >
                {INTERVALS.map((i) => (
                  <option key={i} value={i}>
                    Every {i} second{i === 1 ? '' : 's'}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        </Card>

        {create.isError ? (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {(create.error as Error).message}
          </div>
        ) : null}

        <div className="flex justify-end gap-3">
          <Button type="button" variant="outline" onClick={() => navigate('/')}>
            Cancel
          </Button>
          <Button type="submit" size="lg" disabled={create.isPending}>
            {create.isPending ? 'Creating…' : 'Create Session'}
          </Button>
        </div>
      </form>
    </div>
  )
}
