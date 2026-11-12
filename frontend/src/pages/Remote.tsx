import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, type RecordingStatus } from '@/lib/api'
import { formatDuration, uid } from '@/lib/utils'
import { Camera, Circle, Square, Wifi, WifiOff } from 'lucide-react'

/**
 * iPhone remote control — intentionally PHI-free.
 * Shows only recording operational status and large control buttons.
 */
export function Remote() {
  const { token = '' } = useParams()
  const [accessToken, setAccessToken] = useState<string | null>(null)
  const [status, setStatus] = useState<RecordingStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [controllerId] = useState(() => {
    try {
      return localStorage.getItem('es_controller_id') || uid('ctl')
    } catch {
      return uid('ctl')
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem('es_controller_id', controllerId)
    } catch {
      // Storage can be unavailable (e.g. locked-down Safari); the id is only a hint.
    }
  }, [controllerId])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const claimed = await api.claimPairing(token, controllerId)
        if (cancelled) return
        setAccessToken(claimed.access_token)
        setError(null)
      } catch (e) {
        if (!cancelled) setError((e as Error).message)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token, controllerId])

  useEffect(() => {
    if (!accessToken) return
    let alive = true
    const tick = async () => {
      try {
        const s = await api.remoteStatus(accessToken)
        if (alive) {
          setStatus(s)
          setError(null)
        }
      } catch (e) {
        if (alive) setError((e as Error).message)
      }
    }
    tick()
    const id = window.setInterval(tick, 1000)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [accessToken])

  const run = async (action: 'start' | 'stop' | 'snapshot') => {
    if (!accessToken || busy) return
    setBusy(true)
    setMessage(null)
    try {
      const result = await api.remoteCommand(accessToken, action, uid('cmd'))
      setStatus(result.status)
      setMessage(result.success ? result.message : `Failed: ${result.message}`)
      if (!result.success) setError(result.message)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const recording = status?.state === 'recording'
  const connected = !!accessToken && !error

  return (
    <div className="min-h-screen bg-[#0b3a5c] px-4 py-8 text-white">
      <div className="mx-auto flex min-h-[90vh] max-w-md flex-col">
        <header className="mb-8 text-center">
          <div className="text-sm uppercase tracking-[0.2em] text-white/60">OpenSnap</div>
          <h1 className="mt-2 text-3xl font-semibold">Remote Control</h1>
          <p className="mt-2 text-sm text-white/70">Recording controls only — no patient data</p>
        </header>

        <div className="mb-6 rounded-2xl bg-white/10 p-4 backdrop-blur">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm">
              {connected ? <Wifi className="h-4 w-4 text-emerald-300" /> : <WifiOff className="h-4 w-4 text-amber-300" />}
              {connected ? 'Connected' : 'Disconnected'}
            </div>
            <div className="text-sm capitalize text-white/80">{status?.state ?? '…'}</div>
          </div>
          <div className="mt-4 text-center">
            <div className="text-5xl font-semibold tabular-nums tracking-tight">
              {formatDuration(status?.elapsed_sec ?? 0)}
            </div>
            <div className="mt-2 text-sm text-white/70">
              {recording ? (
                <span className="inline-flex items-center gap-2">
                  <span className="rec-dot h-2.5 w-2.5 rounded-full bg-red-400" />
                  Recording
                </span>
              ) : (
                'Ready'
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-1 flex-col justify-center gap-4">
          <button
            type="button"
            disabled={busy || recording || !accessToken}
            onClick={() => run('start')}
            className="flex h-24 items-center justify-center gap-3 rounded-2xl bg-emerald-500 text-xl font-bold text-white disabled:opacity-40"
          >
            <Circle className="h-7 w-7 fill-current" />
            Start Recording
          </button>
          <button
            type="button"
            disabled={busy || !recording || !accessToken}
            onClick={() => run('stop')}
            className="flex h-24 items-center justify-center gap-3 rounded-2xl bg-red-600 text-xl font-bold text-white disabled:opacity-40"
          >
            <Square className="h-7 w-7 fill-current" />
            Stop Recording
          </button>
          <button
            type="button"
            disabled={busy || !accessToken}
            onClick={() => run('snapshot')}
            className="flex h-24 items-center justify-center gap-3 rounded-2xl bg-sky-500 text-xl font-bold text-white disabled:opacity-40"
          >
            <Camera className="h-7 w-7" />
            Take Snapshot
          </button>
        </div>

        <div className="mt-6 min-h-12 text-center text-sm">
          {message ? <div className="text-emerald-200">{message}</div> : null}
          {error ? <div className="text-amber-200">{error}</div> : null}
        </div>
      </div>
    </div>
  )
}
