import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api, type Settings as SettingsType } from '@/lib/api'
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

  useEffect(() => {
    if (settings.data) setForm(settings.data)
  }, [settings.data])

  const save = useMutation({
    mutationFn: () => api.updateSettings(form),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
  })

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Settings" subtitle="Physician preferences, practice letterhead, and local storage." />
      <div className="space-y-5 animate-fade-up">
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
          <Field label="Storage directory">
            <Input value={form.storage_path} readOnly />
          </Field>
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
