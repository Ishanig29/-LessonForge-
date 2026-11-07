import { BookOpenCheck, FilePlus2, LayoutDashboard, Library, Menu, Settings, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { Badge, cx } from '../components/ui'
import { api } from '../services/api'
import type { PublicConfig } from '../types/api'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/create', label: 'Create Lesson', icon: FilePlus2 },
  { to: '/lessons', label: 'My Lessons', icon: BookOpenCheck },
  { to: '/library', label: 'Research Library', icon: Library },
  { to: '/settings', label: 'Settings', icon: Settings },
]

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-2">
      <img src="/favicon.svg" alt="" className="size-7" />
      <div>
        <p className="font-serif text-[17px] leading-none text-ink">LessonForge</p>
        <p className="mt-1 text-[10.5px] tracking-wide text-muted">Research · Generate · Verify · Teach</p>
      </div>
    </div>
  )
}

export function AppLayout() {
  const [open, setOpen] = useState(false)
  const [config, setConfig] = useState<PublicConfig | null>(null)
  const location = useLocation()
  useEffect(() => setOpen(false), [location.pathname])
  useEffect(() => {
    api.settings().then(setConfig).catch(() => setConfig(null))
  }, [])

  const nav = (
    <nav aria-label="Main" className="mt-8 flex flex-col gap-0.5">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            cx(
              'flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors',
              isActive ? 'bg-card font-medium text-ink shadow-soft ring-1 ring-line' : 'text-ink-2 hover:bg-paper-2',
            )
          }
        >
          <Icon className="size-4" aria-hidden />
          {label}
        </NavLink>
      ))}
    </nav>
  )

  const footer = config && (
    <div className="mt-auto space-y-2 px-2 text-xs text-muted">
      {config.demo_mode && <Badge tone="warn">Offline demo mode</Badge>}
      <p>
        Model: <span className="font-mono text-ink-2">{config.demo_mode ? 'demo stand-in' : config.ai_model}</span>
      </p>
    </div>
  )

  return (
    <div className="flex min-h-full">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-card focus:px-3 focus:py-2">
        Skip to content
      </a>
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-line bg-paper px-3 py-5 lg:flex">
        <Brand />
        {nav}
        {footer}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-line bg-paper px-4 py-3 lg:hidden">
          <Brand />
          <button onClick={() => setOpen(true)} className="rounded-lg p-2 hover:bg-paper-2" aria-label="Open navigation">
            <Menu className="size-5" />
          </button>
        </div>
        {open && (
          <div className="fixed inset-0 z-40 bg-ink/30 lg:hidden" onClick={() => setOpen(false)}>
            <aside className="flex h-full w-64 flex-col bg-paper px-3 py-5" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between">
                <Brand />
                <button onClick={() => setOpen(false)} className="rounded p-1.5 hover:bg-paper-2" aria-label="Close navigation">
                  <X className="size-4" />
                </button>
              </div>
              {nav}
              {footer}
            </aside>
          </div>
        )}
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
