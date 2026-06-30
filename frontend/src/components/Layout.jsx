import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'motion/react'
import { Compass, Bookmark, LifeBuoy } from 'lucide-react'
import AuthMenu from './AuthMenu'
import Logo from './Logo'
import ThemeToggle from './ThemeToggle'
import { cn } from '../lib/utils'

const navItems = [
  { to: '/search', label: 'Plan', icon: Compass },
  { to: '/saved', label: 'Saved', icon: Bookmark },
  { to: '/live', label: 'Lifeline', icon: LifeBuoy },
]

export default function Layout() {
  const location = useLocation()

  return (
    <div className="rs-app-bg min-h-svh">
      <header className="sticky top-0 z-20 border-b border-line-soft bg-surface/70 backdrop-blur-xl supports-[backdrop-filter]:bg-surface/60">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3.5 sm:px-6 lg:px-8">
          <NavLink to="/" className="flex items-center gap-2.5">
            <Logo size={26} />
            <span className="hidden text-xs text-faint lg:inline">Peace of mind, every time.</span>
          </NavLink>

          <nav className="hidden items-center gap-6 sm:flex">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-1.5 text-sm font-medium transition-colors',
                    isActive ? 'text-brand-600' : 'text-muted hover:text-brand-600'
                  )
                }
              >
                <Icon className="h-4 w-4" />
                {label}
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-1.5">
            <ThemeToggle />
            <AuthMenu />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-4 pb-24 pt-6 sm:px-6 sm:pb-10 lg:px-8">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>

      <nav className="fixed inset-x-0 bottom-0 z-20 border-t border-line-soft bg-surface/80 px-4 py-2 backdrop-blur-xl sm:hidden">
        <div className="flex justify-around">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  'flex flex-col items-center gap-0.5 rounded-lg px-4 py-1.5 text-xs font-medium transition-colors',
                  isActive ? 'text-brand-600' : 'text-faint hover:text-brand-400'
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
