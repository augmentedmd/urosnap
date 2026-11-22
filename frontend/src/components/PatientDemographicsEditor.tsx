import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, type Patient, type SessionDetail } from '@/lib/api'
import { Button, Card, Field, Input } from '@/components/ui'

type FormState = {
  first_name: string
  last_name: string
  date_of_birth: string
  medical_record_number: string
}

function fromPatient(patient?: Patient | null): FormState {
  return {
    first_name: patient?.first_name || '',
    last_name: patient?.last_name || '',
    date_of_birth: patient?.date_of_birth || '',
    medical_record_number: patient?.medical_record_number || '',
  }
}

function hasAnyDemographics(form: FormState) {
  return Boolean(
    form.first_name.trim() ||
      form.last_name.trim() ||
      form.date_of_birth ||
      form.medical_record_number.trim(),
  )
}

export function PatientDemographicsEditor({
  sessionId,
  patient,
  compact = false,
}: {
  sessionId: string
  patient?: Patient | null
  compact?: boolean
}) {
  const qc = useQueryClient()
  const [form, setForm] = useState<FormState>(() => fromPatient(patient))
  const [savedFlash, setSavedFlash] = useState(false)

  useEffect(() => {
    setForm(fromPatient(patient))
  }, [
    patient?.first_name,
    patient?.last_name,
    patient?.date_of_birth,
    patient?.medical_record_number,
  ])

  const save = useMutation({
    mutationFn: () =>
      api.updateSession(sessionId, {
        patient: {
          first_name: form.first_name,
          last_name: form.last_name,
          date_of_birth: form.date_of_birth || null,
          medical_record_number: form.medical_record_number,
        },
      }),
    onSuccess: (session: SessionDetail) => {
      qc.setQueryData(['session', sessionId], session)
      qc.invalidateQueries({ queryKey: ['session', sessionId] })
      qc.invalidateQueries({ queryKey: ['sessions'] })
      qc.invalidateQueries({ queryKey: ['recent-sessions'] })
      setForm(fromPatient(session.patient))
      setSavedFlash(true)
      window.setTimeout(() => setSavedFlash(false), 2000)
    },
  })

  const empty = !hasAnyDemographics(form)
  const title = empty ? 'Add patient demographics' : 'Patient demographics'

  return (
    <Card className={`space-y-3 ${compact ? 'p-4' : 'p-5'}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="text-xs text-[var(--color-muted)]">
            Optional. Can be added or changed after the session starts — including during recording.
          </p>
        </div>
        {savedFlash ? (
          <span className="text-sm font-semibold text-emerald-700">Saved</span>
        ) : null}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="First name">
          <Input
            value={form.first_name}
            onChange={(e) => setForm({ ...form, first_name: e.target.value })}
            autoComplete="off"
          />
        </Field>
        <Field label="Last name">
          <Input
            value={form.last_name}
            onChange={(e) => setForm({ ...form, last_name: e.target.value })}
            autoComplete="off"
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
            autoComplete="off"
          />
        </Field>
      </div>
      {save.isError ? (
        <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">
          {(save.error as Error).message}
        </div>
      ) : null}
      <div className="flex justify-end">
        <Button
          type="button"
          variant="secondary"
          size={compact ? 'sm' : 'md'}
          disabled={save.isPending}
          onClick={() => save.mutate()}
        >
          {save.isPending ? 'Saving…' : empty ? 'Save demographics' : 'Update demographics'}
        </Button>
      </div>
    </Card>
  )
}
