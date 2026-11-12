import { getServiceBaseUrl, getUiBaseUrl, serviceUrl } from '@/lib/runtime'

export type Patient = {
  id?: number
  first_name: string
  last_name: string
  date_of_birth?: string | null
  medical_record_number: string
}

export type StorageBrowse = {
  current: string
  parent?: string | null
  directories: string[]
  drives: string[]
  writable: boolean
  exists: boolean
}

export type SessionSummary = {
  id: number
  public_id: string
  procedure_type: string
  custom_procedure_name?: string | null
  display_procedure_name: string
  physician: string
  location: string
  procedure_date: string
  procedure_time?: string | null
  status: string
  created_at: string
  recording_start_time?: string | null
  recording_stop_time?: string | null
  patient_name: string
  medical_record_number: string
  snapshot_count: number
}

export type SessionDetail = SessionSummary & {
  notes: string
  capture_source: string
  capture_device_id?: string | null
  resolution: string
  requested_fps: number
  snapshot_interval_sec: number
  images_per_page: number
  storage_path: string
  patient: Patient
}

export type CaptureDevice = {
  id: string
  name: string
  index?: number | null
  source_type: string
  resolutions: string[]
  frame_rates: number[]
  available: boolean
}

export type CaptureStatus = {
  connected: boolean
  device_id?: string | null
  device_name?: string | null
  source_type?: string | null
  incoming_fps?: number | null
  error?: string | null
}

export type RecordingStatus = {
  session_public_id?: string | null
  state: string
  elapsed_sec: number
  requested_fps?: number | null
  actual_fps?: number | null
  incoming_fps?: number | null
  snapshot_interval_sec?: number | null
  snapshot_count: number
  manual_snapshot_count: number
  automatic_snapshot_count: number
  capture: CaptureStatus
  warning?: string | null
  error?: string | null
  remote_connected: boolean
}

export type Snapshot = {
  id: number
  session_id: number
  capture_timestamp: string
  capture_type: string
  selected: boolean
  caption: string
  display_order?: number | null
  sequence_number: number
  thumbnail_url: string
  image_url: string
}

export type Report = {
  id: number
  session_id: number
  notes: string
  images_per_page: number
  version: number
  created_at: string
  download_url: string
  preview_url: string
}

export type Health = {
  status: string
  service: string
  version: string
  disk_free_bytes: number
  disk_total_bytes: number
  low_disk: boolean
  active_session_id?: string | null
  recording_state: string
  capture: CaptureStatus
  warnings: string[]
}

export type Settings = {
  practice_name: string
  practice_address_line1: string
  practice_address_line2: string
  practice_phone: string
  default_fps: number
  default_snapshot_interval_sec: number
  default_images_per_page: number
  default_resolution: string
  default_capture_source: string
  preferred_physician: string
  preferred_procedure_type: string
  preferred_capture_device_id: string
  storage_path: string
  pairing_token_ttl_seconds: number
}

export type PairingCreate = {
  pairing_url: string
  token: string
  expires_at: string
  qr_payload: string
}

function absolutizeMedia(path: string): string {
  if (!path) return path
  if (path.startsWith('http://') || path.startsWith('https://')) return path
  return serviceUrl(path)
}

function mapSnapshot(snap: Snapshot): Snapshot {
  return {
    ...snap,
    thumbnail_url: absolutizeMedia(snap.thumbnail_url),
    image_url: absolutizeMedia(snap.image_url),
  }
}

function mapReport(report: Report): Report {
  return {
    ...report,
    download_url: absolutizeMedia(report.download_url),
    preview_url: absolutizeMedia(report.preview_url),
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (!headers.has('Content-Type') && init?.body) {
    headers.set('Content-Type', 'application/json')
  }
  headers.set('X-Desktop-Token', 'local-desktop-dev-token')
  const res = await fetch(serviceUrl(path), { ...init, headers })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || JSON.stringify(body)
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<Health>('/api/health'),
  devices: () => request<CaptureDevice[]>('/api/capture/devices'),
  settings: () => request<Settings>('/api/settings'),
  updateSettings: (body: Partial<Settings>) =>
    request<Settings>('/api/settings', { method: 'PATCH', body: JSON.stringify(body) }),
  browseStorage: (path?: string) => {
    const qs = path ? `?${new URLSearchParams({ path })}` : ''
    return request<StorageBrowse>(`/api/settings/storage/browse${qs}`)
  },
  procedureTypes: () =>
    request<{ id: number; name: string; is_custom: boolean; use_count: number }[]>(
      '/api/procedure-types',
    ),
  sessions: (params?: Record<string, string>) => {
    const qs = params ? `?${new URLSearchParams(params)}` : ''
    return request<SessionSummary[]>(`/api/sessions${qs}`)
  },
  session: (id: string) => request<SessionDetail>(`/api/sessions/${id}`),
  createSession: (body: unknown) =>
    request<SessionDetail>('/api/sessions', { method: 'POST', body: JSON.stringify(body) }),
  updateSession: (id: string, body: unknown) =>
    request<SessionDetail>(`/api/sessions/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  startRecording: (id: string) =>
    request<RecordingStatus>(`/api/sessions/${id}/recording/start`, { method: 'POST' }),
  stopRecording: (id: string) =>
    request<RecordingStatus>(`/api/sessions/${id}/recording/stop`, { method: 'POST' }),
  recordingStatus: (id: string) =>
    request<RecordingStatus>(`/api/sessions/${id}/recording/status`),
  takeSnapshot: (id: string) =>
    request<Snapshot>(`/api/sessions/${id}/snapshots`, { method: 'POST' }).then(mapSnapshot),
  snapshots: (id: string) =>
    request<Snapshot[]>(`/api/sessions/${id}/snapshots`).then((rows) => rows.map(mapSnapshot)),
  updateSnapshot: (id: number, body: unknown) =>
    request<Snapshot>(`/api/snapshots/${id}`, { method: 'PATCH', body: JSON.stringify(body) }).then(
      mapSnapshot,
    ),
  bulkSelection: (sessionId: string, body: unknown) =>
    request<Snapshot[]>(`/api/sessions/${sessionId}/snapshots/selection`, {
      method: 'POST',
      body: JSON.stringify(body),
    }).then((rows) => rows.map(mapSnapshot)),
  createReport: (id: string, body: unknown) =>
    request<Report>(`/api/sessions/${id}/reports`, { method: 'POST', body: JSON.stringify(body) }).then(
      mapReport,
    ),
  reports: (id: string) =>
    request<Report[]>(`/api/sessions/${id}/reports`).then((rows) => rows.map(mapReport)),
  createPairing: (id: string) =>
    request<PairingCreate>(`/api/sessions/${id}/pairing`, {
      method: 'POST',
      body: JSON.stringify({
        // UI may be on Cloudflare; service stays on the workstation / LAN.
        ui_base_url: getUiBaseUrl(),
        service_base_url: getServiceBaseUrl() || undefined,
      }),
    }),
  revokePairing: (id: string) =>
    request<{ revoked: number }>(`/api/pairing/revoke?session_id=${encodeURIComponent(id)}`, {
      method: 'POST',
    }),
  claimPairing: (token: string, controller_id?: string) =>
    request<{ access_token: string; session_public_id: string; expires_at: string }>(
      '/api/pairing/claim',
      { method: 'POST', body: JSON.stringify({ token, controller_id }) },
    ),
  remoteStatus: (accessToken: string) =>
    request<RecordingStatus>('/api/remote/status', {
      headers: { Authorization: `Bearer ${accessToken}` },
    }),
  remoteCommand: (accessToken: string, action: string, command_id: string) =>
    request<{
      command_id: string
      action: string
      success: boolean
      message: string
      status: RecordingStatus
    }>('/api/remote/command', {
      method: 'POST',
      headers: { Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify({ action, command_id }),
    }),
}
