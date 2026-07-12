import { useState } from 'react'
import { Eye, EyeOff, Lock } from 'lucide-react'
import { cn } from '../lib/utils'

// Shared everywhere a password is typed (login, signup, reset) so the
// show/hide eye toggle is consistent app-wide, not something each page
// reimplements (and risks forgetting).
export default function PasswordField({ value, onChange, error, placeholder, autoComplete }) {
  const [show, setShow] = useState(false)
  return (
    <div>
      <div
        className={cn(
          'flex items-center gap-2 rounded-xl border bg-surface px-3 py-3',
          error ? 'border-risk-500/50' : 'border-line'
        )}
      >
        <Lock className="h-4 w-4 shrink-0 text-faint" />
        <input
          type={show ? 'text' : 'password'}
          required
          maxLength={72}
          autoComplete={autoComplete}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          className="w-full bg-transparent text-base font-medium text-content outline-none"
        />
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          aria-label={show ? 'Hide password' : 'Show password'}
          className="shrink-0 text-faint hover:text-muted"
        >
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
      {error && <p className="mt-1 text-xs font-medium text-risk-600">{error}</p>}
    </div>
  )
}
