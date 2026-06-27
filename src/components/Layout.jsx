import { NavLink, Outlet } from 'react-router-dom'
import { Compass, Bookmark, LifeBuoy } from 'lucide-react'
import { cn } from '../lib/utils'

const navItems = [
  { to: '/search', label: 'Plan', icon: Compass },
  { to: '/saved', label: 'Saved', icon: Bookmark },
  { to: '/live', label: 'Lifeline', icon: LifeBuoy },
]

export default function Layout() {
  return (
    <div className="mx-auto flex min-h-svh max-w-2xl flex-col bg-[#f7f8fc]">
      <header className="sticky top-0 z-10 border-b border-brand-100 bg-white/90 px-4 py-3 backdrop-blur">
        <NavLink to="/" className="flex items-baseline gap-2">
          <span className="font-display text-lg font-bold text-brand-700">RouteSarthi</span>
          <span className="hidden text-xs text-gray-400 sm:inline">Pohochao, har haal mein.</span>
        </NavLink>
      </header>

      <main className="flex-1 px-4 py-5">
        <Outlet />
      </main>

      <nav className="sticky bottom-0 z-10 border-t border-brand-100 bg-white px-4 py-2">
        <div className="flex justify-around">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  'flex flex-col items-center gap-0.5 rounded-lg px-4 py-1.5 text-xs font-medium',
                  isActive ? 'text-brand-600' : 'text-gray-400'
                )
              }
            >
              <Icon className="h-5 w-5" />
              {label}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  )
}
