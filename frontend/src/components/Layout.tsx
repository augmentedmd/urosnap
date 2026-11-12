import { NavLink, Outlet } from 'react-router-dom'
import { useState } from 'react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import {
  Camera,
  History,
  LayoutDashboard,
  Power,
  Settings,
  Video,
} from 'lucide-react'

const links = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/sessions/new', label: 'New Session', icon: Video },
  { to: '/sessions', label: 'Previous Sessions', icon: History },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function Layout() {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[240px_1fr]">
      <aside className="border-b border-[var(--color-line)] bg-[#0b3a5c] text-white lg:border-b-0 lg:border-r lg:min-h-screen">
        <div className="px-5 py-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/15">
              <Camera className="h-5 w-5" />
            </div>
            <div>
              <div className="font-[family-name:var(--font-display)] text-lg font-semibold tracking-tight">
                OpenSnap
              </div>
              <div className="text-xs text-white/70">Local recording service</div>
            </div>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-4 lg:flex-col">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === '/'}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium text-white/80 transition hover:bg-white/10 hover:text-white',
                  isActive && 'bg-white/15 text-white',
                )
              }
            >
              <link.icon className="h-4 w-4" />
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-3 pb-4">
          <QuitButton />
        </div>
      </aside>
      <main className="px-4 py-6 sm:px-8 lg:px-10">
        <Outlet />
      </main>
    </div>
  )
}

function QuitButton() {
  const [state, setState] = useState<'idle' | 'confirm' | 'quitting' | 'closed'>('idle')
  const [error, setError] = useState<string | null>(null)

  const quit = async () => {
    setState('quitting')
    setError(null)
    try {
      await api.shutdown()
      setState('closed')
    } catch (e) {
      setError((e as Error).message)
      setState('idle')
    }
  }

  if (state === 'closed') {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0b3a5c] p-6 text-center text-white">
        <div>
          <Power className="mx-auto mb-4 h-10 w-10 text-white/70" />
          <h1 className="text-2xl font-semibold">OpenSnap has been closed</h1>
          <p className="mt-2 text-white/70">You can close this browser tab. Open OpenSnap again from its desktop shortcut.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {state === 'confirm' ? (
        <div className="space-y-2 rounded-lg bg-white/10 p-3 text-sm">
          <div>Quit OpenSnap? The camera and phone remote will stop.</div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={quit}
              className="rounded-md bg-red-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-700"
            >
              Quit
            </button>
            <button
              type="button"
              onClick={() => setState('idle')}
              className="rounded-md bg-white/15 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/25"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setState('confirm')}
          disabled={state === 'quitting'}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium text-white/80 transition hover:bg-white/10 hover:text-white"
        >
          <Power className="h-4 w-4" />
          {state === 'quitting' ? 'Quitting…' : 'Quit OpenSnap'}
        </button>
      )}
      {error ? <div className="px-3 text-xs text-amber-200">{error}</div> : null}
    </div>
  )
}
