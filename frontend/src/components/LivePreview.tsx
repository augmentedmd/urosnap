import { useEffect, useRef, useState } from 'react'
import { serviceUrl } from '@/lib/runtime'

type Props = {
  sessionId: string
  className?: string
  alt?: string
}

/**
 * Cross-origin-safe live preview.
 *
 * Cloudflare HTTPS UI cannot reliably use <img src="http://127.0.0.1/...mjpg">
 * (mixed content / private-network). Poll a single JPEG via fetch with the
 * desktop token instead, and render a blob URL.
 */
export function LivePreview({ sessionId, className, alt = 'Live endoscopy preview' }: Props) {
  const [src, setSrc] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const blobRef = useRef<string | null>(null)

  useEffect(() => {
    let cancelled = false
    let timer: number | undefined

    const revoke = () => {
      if (blobRef.current) {
        URL.revokeObjectURL(blobRef.current)
        blobRef.current = null
      }
    }

    const tick = async () => {
      try {
        const res = await fetch(serviceUrl(`/api/sessions/${sessionId}/preview.jpg`), {
          headers: { 'X-Desktop-Token': 'local-desktop-dev-token' },
          cache: 'no-store',
        })
        if (!res.ok) {
          // 503 while warming up is expected — keep polling quietly.
          if (!cancelled) setError(res.status === 503 ? null : `HTTP ${res.status}`)
        } else {
          const blob = await res.blob()
          if (!cancelled) {
            const next = URL.createObjectURL(blob)
            revoke()
            blobRef.current = next
            setSrc(next)
            setError(null)
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError((err as Error).message || 'Preview unavailable')
        }
      } finally {
        if (!cancelled) {
          timer = window.setTimeout(() => void tick(), 250)
        }
      }
    }

    void tick()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
      revoke()
    }
  }, [sessionId])

  return (
    <div className={`relative h-full w-full bg-slate-900 ${className ?? ''}`}>
      {src ? (
        <img src={src} alt={alt} className="h-full w-full object-contain" />
      ) : (
        <div className="flex h-full items-center justify-center px-6 text-center text-sm text-white/70">
          {error ? `Waiting for local preview… (${error})` : 'Connecting to local preview…'}
        </div>
      )}
    </div>
  )
}
