import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { LogOut, User } from 'lucide-react'
import { useAuthStore } from '../store/useAuthStore'

export default function AuthMenu({ tone = 'light' }) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const { isAuthenticated, user, logout } = useAuthStore()

  const linkTone =
    tone === 'dark' ? 'text-white/80 hover:text-white' : 'text-brand-700 hover:text-content'

  if (!isAuthenticated) {
    return (
      <Link to="/login" className={`text-sm font-semibold ${linkTone}`}>
        Log in
      </Link>
    )
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-full border border-line bg-surface px-2 py-1.5 text-sm font-semibold text-content shadow-soft"
      >
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs font-bold text-white">
          {user?.name?.[0]?.toUpperCase() ?? <User className="h-3.5 w-3.5" />}
        </span>
        <span className="hidden sm:inline">{user?.name?.split(' ')[0] ?? 'Account'}</span>
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 w-44 rounded-xl border border-line bg-surface p-1.5 shadow-pop">
          <button
            type="button"
            onClick={() => {
              setOpen(false)
              logout()
              navigate('/')
            }}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-risk-600 hover:bg-risk-50"
          >
            <LogOut className="h-4 w-4" />
            Log out
          </button>
        </div>
      )}
    </div>
  )
}
