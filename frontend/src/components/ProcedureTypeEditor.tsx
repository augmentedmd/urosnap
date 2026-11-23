import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type SessionDetail } from '@/lib/api'
import { Button, Card, Field, Input, Select } from '@/components/ui'

const CUSTOM = 'Other / Custom Procedure'

type FormState = {
  procedure_type: string
  custom_procedure_name: string
  save_custom_procedure: boolean
}

function fromSession(session?: Pick<SessionDetail, 'procedure_type' | 'custom_procedure_name'> | null): FormState {
  return {
    procedure_type: session?.procedure_type || 'Diagnostic cystoscopy',
    custom_procedure_name: session?.custom_procedure_name || '',
    save_custom_procedure: false,
  }
}

export function ProcedureTypeEditor({
  sessionId,
  procedureType,
  customProcedureName,
  compact = false,
}: {
  sessionId: string
  procedureType?: string | null
  customProcedureName?: string | null
  compact?: boolean
}) {
  const qc = useQueryClient()
  const procedures = useQuery({ queryKey: ['procedures'], queryFn: api.procedureTypes })
  const [form, setForm] = useState<FormState>(() =>
    fromSession({
      procedure_type: procedureType || 'Diagnostic cystoscopy',
      custom_procedure_name: customProcedureName || null,
    }),
  )
  const [savedFlash, setSavedFlash] = useState(false)

  useEffect(() => {
    setForm(
      fromSession({
        procedure_type: procedureType || 'Diagnostic cystoscopy',
        custom_procedure_name: customProcedureName || null,
      }),
    )
  }, [procedureType, customProcedureName])

  const isCustom = form.procedure_type === CUSTOM

  const save = useMutation({
    mutationFn: () =>
      api.updateSession(sessionId, {
        procedure_type: form.procedure_type || 'Diagnostic cystoscopy',
        custom_procedure_name: isCustom ? form.custom_procedure_name || null : null,
        save_custom_procedure: isCustom && form.save_custom_procedure,
      }),
    onSuccess: (session: SessionDetail) => {
      qc.setQueryData(['session', sessionId], session)
      qc.invalidateQueries({ queryKey: ['session', sessionId] })
      qc.invalidateQueries({ queryKey: ['sessions'] })
      qc.invalidateQueries({ queryKey: ['recent-sessions'] })
      qc.invalidateQueries({ queryKey: ['procedures'] })
      setForm(fromSession(session))
      setSavedFlash(true)
      window.setTimeout(() => setSavedFlash(false), 2000)
    },
  })

  // Ensure the current type appears even if the catalog is still loading.
  const catalog = procedures.data ?? []
  const options =
    form.procedure_type && !catalog.some((p) => p.name === form.procedure_type)
      ? [
          ...catalog,
          {
            id: -1,
            name: form.procedure_type,
            is_custom: false,
            use_count: 0,
          },
        ]
      : catalog

  return (
    <Card className={`space-y-3 ${compact ? 'p-4' : 'p-5'}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">Procedure type</h2>
          <p className="text-xs text-[var(--color-muted)]">
            Can be changed after the session starts — including during recording.
          </p>
        </div>
        {savedFlash ? (
          <span className="text-sm font-semibold text-emerald-700">Saved</span>
        ) : null}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Procedure type">
          <Select
            value={form.procedure_type}
            onChange={(e) => setForm({ ...form, procedure_type: e.target.value })}
          >
            {options.map((p) => (
              <option key={p.id} value={p.name}>
                {p.name}
                {p.is_custom ? ' (saved custom)' : ''}
              </option>
            ))}
          </Select>
        </Field>
        {isCustom ? (
          <Field label="Custom procedure name">
            <Input
              value={form.custom_procedure_name}
              onChange={(e) => setForm({ ...form, custom_procedure_name: e.target.value })}
              autoComplete="off"
            />
          </Field>
        ) : null}
      </div>
      {isCustom ? (
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.save_custom_procedure}
            onChange={(e) => setForm({ ...form, save_custom_procedure: e.target.checked })}
          />
          Save custom name for future selection
        </label>
      ) : null}
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
          {save.isPending ? 'Saving…' : 'Update procedure type'}
        </Button>
      </div>
    </Card>
  )
}
