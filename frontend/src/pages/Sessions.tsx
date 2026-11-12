import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useState } from 'react'
import { api } from '@/lib/api'
import { Badge, Button, Card, Input, PageHeader, Select } from '@/components/ui'

export function Sessions() {
  const [q, setQ] = useState('')
  const [procedure, setProcedure] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const procedures = useQuery({ queryKey: ['procedures'], queryFn: api.procedureTypes })
  const sessions = useQuery({
    queryKey: ['sessions', q, procedure, dateFrom, dateTo],
    queryFn: () => {
      const params: Record<string, string> = {}
      if (q) params.q = q
      if (procedure) params.procedure_type = procedure
      if (dateFrom) params.date_from = dateFrom
      if (dateTo) params.date_to = dateTo
      return api.sessions(params)
    },
  })

  return (
    <div>
      <PageHeader
        title="Previous Sessions"
        subtitle="Search, reopen, review media, edit Notes, and regenerate versioned PDFs."
      />

      <Card className="mb-5 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <Input placeholder="Search patient, MRN, physician…" value={q} onChange={(e) => setQ(e.target.value)} />
        <Select value={procedure} onChange={(e) => setProcedure(e.target.value)}>
          <option value="">All procedures</option>
          {(procedures.data ?? []).map((p) => (
            <option key={p.id} value={p.name}>
              {p.name}
            </option>
          ))}
        </Select>
        <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
      </Card>

      <Card className="overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-[var(--color-muted)]">
            <tr>
              <th className="px-4 py-3 font-semibold">Patient</th>
              <th className="px-4 py-3 font-semibold">Procedure</th>
              <th className="px-4 py-3 font-semibold">Physician</th>
              <th className="px-4 py-3 font-semibold">Date</th>
              <th className="px-4 py-3 font-semibold">Status</th>
              <th className="px-4 py-3 font-semibold">Photos</th>
              <th className="px-4 py-3 font-semibold" />
            </tr>
          </thead>
          <tbody>
            {(sessions.data ?? []).map((s) => (
              <tr key={s.public_id} className="border-t border-[var(--color-line)]">
                <td className="px-4 py-3">
                  <div className="font-medium">{s.patient_name}</div>
                  <div className="text-xs text-[var(--color-muted)]">{s.medical_record_number}</div>
                </td>
                <td className="px-4 py-3">{s.display_procedure_name}</td>
                <td className="px-4 py-3">{s.physician}</td>
                <td className="px-4 py-3">{s.procedure_date}</td>
                <td className="px-4 py-3">
                  <Badge>{s.status}</Badge>
                </td>
                <td className="px-4 py-3">{s.snapshot_count}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <Link to={`/sessions/${s.public_id}/record`}>
                      <Button size="sm" variant="outline">
                        Open
                      </Button>
                    </Link>
                    <Link to={`/sessions/${s.public_id}/gallery`}>
                      <Button size="sm" variant="secondary">
                        Gallery
                      </Button>
                    </Link>
                    <Link to={`/sessions/${s.public_id}/report`}>
                      <Button size="sm">Report</Button>
                    </Link>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
