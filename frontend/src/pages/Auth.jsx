import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, Mail, User as UserIcon } from 'lucide-react'
import EyebrowLabel from '../components/EyebrowLabel'
import ArrowButton from '../components/ArrowButton'
import Logo from '../components/Logo'
import PasswordField from '../components/PasswordField'
import ThemeToggle from '../components/ThemeToggle'
import { cn } from '../lib/utils'
import { useAuthStore } from '../store/useAuthStore'

function Field({ icon: Icon, error, ...props }) {
  return (
    <div>
      <div
        className={cn(
          'flex items-center gap-2 rounded-xl border bg-surface px-3 py-3',
          error ? 'border-risk-500/50' : 'border-line'
        )}
      >
        <Icon className="h-4 w-4 shrink-0 text-faint" />
        <input
          {...props}
          className="w-full bg-transparent text-base font-medium text-content outline-none"
        />
      </div>
      {error && <p className="mt-1 text-xs font-medium text-risk-600">{error}</p>}
    </div>
  )
}

function TabSwitch({ mode, setMode }) {
  return (
    <div className="inline-flex rounded-full border border-brand-100 bg-surface p-1">
      {[
        { key: 'login', label: 'Log in' },
        { key: 'signup', label: 'Sign up' },
      ].map((t) => (
        <button
          key={t.key}
          type="button"
          onClick={() => setMode(t.key)}
          className={cn(
            'rounded-full px-4 py-1.5 text-sm font-medium transition',
            mode === t.key ? 'bg-primary text-white shadow-sm' : 'text-brand-700 hover:bg-brand-50'
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}

export default function Auth() {
  const navigate = useNavigate()
  const location = useLocation()
  const { login, signup, forgotPassword, error, clearError } = useAuthStore()

  const [mode, setMode] = useState('login') // 'login' | 'signup' | 'forgot'
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [name, setName] = useState('')
  const [fieldError, setFieldError] = useState('')

  const switchMode = (m) => {
    setMode(m)
    setSent(false)
    setFieldError('')
    clearError()
  }

  const redirectAfterAuth = () => navigate(location.state?.from?.pathname ?? '/search', { replace: true })

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoading(true)
    const ok = await login({ email, password })
    setLoading(false)
    if (ok) redirectAfterAuth()
  }

  const handleSignup = async (e) => {
    e.preventDefault()
    setFieldError('')
    if (password.length < 8) return setFieldError('Password must be at least 8 characters.')
    if (password !== confirmPassword) return setFieldError('Passwords do not match.')
    setLoading(true)
    const ok = await signup({ email, password, name })
    setLoading(false)
    if (ok) redirectAfterAuth()
  }

  const handleForgot = async (e) => {
    e.preventDefault()
    setLoading(true)
    await forgotPassword(email)
    setLoading(false)
    setSent(true) // always show success — never confirm/deny an account exists
  }

  return (
    <div className="flex min-h-svh flex-col bg-surface">
      <header className="flex items-center justify-between px-6 py-6 lg:px-16">
        <Link to="/">
          <Logo size={26} />
        </Link>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <Link to="/" className="flex items-center gap-1.5 text-sm text-faint hover:text-brand-600">
            <ArrowLeft className="h-3.5 w-3.5" />
            Back home
          </Link>
        </div>
      </header>

      <div className="flex flex-1 items-center justify-center px-6 pb-16">
        <div className="w-full max-w-sm">
          {mode === 'forgot' ? (
            <>
              <EyebrowLabel>Reset password</EyebrowLabel>
              <h1 className="mt-3 font-display text-2xl font-bold text-content">Forgot your password?</h1>
              <p className="mt-1 text-sm text-muted">
                Enter your account email — if it matches an account, we'll send a reset link.
              </p>

              {sent ? (
                <div className="mt-6 rounded-xl bg-safe-50 px-4 py-3 text-sm font-medium text-safe-600">
                  If that email is registered, a reset link is on its way. Check your inbox.
                </div>
              ) : (
                <form onSubmit={handleForgot} className="mt-6 space-y-4">
                  <Field
                    icon={Mail}
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    autoComplete="email"
                  />
                  <ArrowButton
                    type="submit"
                    variant="solid"
                    disabled={loading}
                    className="w-full justify-center disabled:opacity-50"
                  >
                    {loading ? 'Sending…' : 'Send reset link'}
                  </ArrowButton>
                </form>
              )}

              <button
                type="button"
                onClick={() => switchMode('login')}
                className="mt-4 block w-full text-center text-sm text-faint hover:text-brand-600"
              >
                Back to log in
              </button>
            </>
          ) : (
            <>
              <EyebrowLabel>{mode === 'signup' ? 'Get started' : 'Welcome back'}</EyebrowLabel>
              <h1 className="mt-3 font-display text-2xl font-bold text-content">
                {mode === 'signup' ? 'Create your account' : 'Log in to RouteSarthi'}
              </h1>
              <p className="mt-1 text-sm text-muted">
                {mode === 'signup'
                  ? 'Save trips, track recent searches, and pick up right where you left off.'
                  : 'Your saved trips and recent searches are waiting.'}
              </p>

              <div className="mt-5">
                <TabSwitch mode={mode} setMode={switchMode} />
              </div>

              <form onSubmit={mode === 'signup' ? handleSignup : handleLogin} className="mt-5 space-y-4">
                {mode === 'signup' && (
                  <Field
                    icon={UserIcon}
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Your name"
                    autoComplete="name"
                  />
                )}
                <Field
                  icon={Mail}
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  autoComplete="email"
                />
                <PasswordField
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={mode === 'signup' ? 'At least 8 characters' : 'Password'}
                  autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                />
                {mode === 'signup' && (
                  <PasswordField
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Confirm password"
                    autoComplete="new-password"
                    error={fieldError}
                  />
                )}

                {mode === 'login' && (
                  <button
                    type="button"
                    onClick={() => switchMode('forgot')}
                    className="block text-sm font-medium text-brand-600 hover:text-brand-700"
                  >
                    Forgot password?
                  </button>
                )}

                {error && (
                  <p className="rounded-lg bg-risk-50 px-3 py-2 text-sm font-medium text-risk-600">{error}</p>
                )}

                <ArrowButton
                  type="submit"
                  variant="solid"
                  disabled={loading}
                  className="w-full justify-center disabled:opacity-50"
                >
                  {loading ? 'Please wait…' : mode === 'signup' ? 'Create account' : 'Log in'}
                </ArrowButton>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
