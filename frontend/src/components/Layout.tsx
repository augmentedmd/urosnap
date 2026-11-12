import { NavLink, Outlet } from 'react-router-dom'
import { cn } from '@/lib/utils'
import {
  Camera,
  FileText,
  History,
  LayoutDashboard,
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
        <div className="hidden px-5 pb-6 text-xs text-white/60 lg:block">
          <div className="flex items-center gap-2">
            <FileText className="h-3.5 w-3.5" />
            Prototype — local-first clinical workflow
          </div>
        </div>
      </aside>
      <main className="px-4 py-6 sm:px-8 lg:px-10">
        <Outlet />
      </main>
    </div>
  )
}
