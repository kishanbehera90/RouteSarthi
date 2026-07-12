import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, CheckCircle2 } from 'lucide-react'
import EyebrowLabel from '../components/EyebrowLabel'
import ArrowButton from '../components/ArrowButton'
import Logo from '../components/Logo'
import PasswordField from '../components/PasswordField'
import ThemeToggle from '../components/ThemeToggle'
import { useAuthStore } from '../store/useAuthStore'

// Reached from the emailed reset link — a logged-out user by definition, so
// this stays a public top-level route (not nested under RequireAuth, which
// would strip the ?token= query string via a redirect before it's ever read).
export default function ResetPassword() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const token = params.get('token') ?? ''
  const { resetPassword, error, clearError } = useAuthStore()

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [fieldError, setFieldError] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    clearError()
    setFieldError('')
    if (password.length < 8) return setFieldError('Password must be at least 8 characters.')
    if (password !== confirm) return setFieldError('Passwords do not match.')
    setLoading(true)
    const ok = await resetPassword({ token, newPassword: password })
    setLoading(false)
    if (ok) setDone(true)
  }

  return (
    <div className="flex min-h-svh flex-col bg-surface">
      <header className="flex items-center justify-between px-6 py-6 lg:px-16">
        <Link to="/">
          <Logo size={26} />
        </Link>
        <ThemeToggle />
      </header>

      <div className="flex flex-1 items-center justify-center px-6 pb-16">
        <div className="w-full max-w-sm">
          {!token ? (
            <div className="rounded-xl bg-risk-50 px-4 py-3 text-sm font-medium text-risk-600">
              This link is missing its reset token — request a new one from the login page.
            </div>
          ) : done ? (
            <>
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-safe-50 text-safe-600">
                <CheckCircle2 className="h-6 w-6" />
              </div>
              <h1 className="mt-4 font-display text-2xl font-bold text-content">Password updated</h1>
              <p className="mt-1 text-sm text-muted">You can now log in with your new password.</p>
              <ArrowButton as={Link} to="/login" variant="solid" className="mt-5 w-full justify-center">
                Go to log in
              </ArrowButton>
            </>
          ) : (
            <>
              <EyebrowLabel>Reset password</EyebrowLabel>
              <h1 className="mt-3 font-display text-2xl font-bold text-content">Choose a new password</h1>

              <form onSubmit={handleSubmit} className="mt-6 space-y-4">
                <PasswordField
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  autoComplete="new-password"
                />
                <PasswordField
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Repeat password"
                  autoComplete="new-password"
                />

                {(fieldError || error) && (
                  <p className="rounded-lg bg-risk-50 px-3 py-2 text-sm font-medium text-risk-600">
                    {fieldError || error}
                  </p>
                )}

                <ArrowButton
                  type="submit"
                  variant="solid"
                  disabled={loading}
                  className="w-full justify-center disabled:opacity-50"
                >
                  {loading ? 'Updating…' : 'Update password'}
                </ArrowButton>
              </form>
            </>
          )}

          <button
            type="button"
            onClick={() => navigate('/login')}
            className="mt-4 flex w-full items-center justify-center gap-1.5 text-sm text-faint hover:text-brand-600"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to log in
          </button>
        </div>
      </div>
    </div>
  )
}
