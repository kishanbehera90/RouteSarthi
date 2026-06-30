import { Link } from 'react-router-dom'
import Logo from './Logo'

export default function Footer() {
  const year = new Date().getFullYear()
  return (
    <footer className="border-t border-line bg-surface">
      <div className="mx-auto max-w-7xl px-6 py-12 lg:px-16">
        <div className="flex flex-col gap-8 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-xs">
            <Logo size={26} />
            <p className="mt-3 text-sm text-muted">
              Every journey deserves peace of mind — smarter routes, confirmed seats, and a
              lifeline when plans break.
            </p>
          </div>

          <nav className="flex flex-col gap-2.5">
            <p className="text-xs font-semibold uppercase tracking-wide text-faint">Explore</p>
            <Link to="/search" className="text-sm text-muted transition hover:text-content">
              Plan a journey
            </Link>
            <a href="#how-it-works" className="text-sm text-muted transition hover:text-content">
              How it works
            </a>
            <Link to="/saved" className="text-sm text-muted transition hover:text-content">
              Saved trips
            </Link>
            <Link to="/login" className="text-sm text-muted transition hover:text-content">
              Log in
            </Link>
          </nav>
        </div>

        <div className="mt-10 flex flex-col gap-1.5 border-t border-line-soft pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-faint">© {year} RouteSarthi · Peace of mind, every time.</p>
          <p className="text-xs text-faint">Made for India</p>
        </div>
      </div>
    </footer>
  )
}
