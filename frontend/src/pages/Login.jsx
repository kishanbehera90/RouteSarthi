import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Phone, ShieldCheck, User as UserIcon } from 'lucide-react'
import EyebrowLabel from '../components/EyebrowLabel'
import ArrowButton from '../components/ArrowButton'
import Logo from '../components/Logo'
import ThemeToggle from '../components/ThemeToggle'
import { useAuthStore } from '../store/useAuthStore'

export default function Login() {
  const navigate = useNavigate()
  const { knowsPhone, login } = useAuthStore()

  const [step, setStep] = useState('phone') // 'phone' | 'otp' | 'name'
  const [phone, setPhone] = useState('')
  const [otp, setOtp] = useState('')
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)

  const sendOtp = (e) => {
    e.preventDefault()
    setLoading(true)
    setTimeout(() => {
      setLoading(false)
      setStep('otp')
    }, 500)
  }

  const verifyOtp = (e) => {
    e.preventDefault()
    setLoading(true)
    setTimeout(() => {
      setLoading(false)
      if (knowsPhone(phone)) {
        login(phone)
        navigate('/search')
      } else {
        setStep('name')
      }
    }, 500)
  }

  const finishSignup = (e) => {
    e.preventDefault()
    login(phone, name.trim() || 'Traveller')
    navigate('/search')
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
          <EyebrowLabel>{step === 'name' ? 'Almost there' : 'Welcome'}</EyebrowLabel>

          {step === 'phone' && (
            <form onSubmit={sendOtp}>
              <h1 className="mt-3 font-display text-2xl font-bold text-content">
                Log in or sign up
              </h1>
              <p className="mt-1 text-sm text-muted">
                We'll text you a one-time code — no password to remember.
              </p>

              <label className="mt-6 block">
                <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-faint">
                  Mobile number
                </span>
                <div className="flex items-center gap-2 rounded-xl border border-line bg-surface px-3 py-3">
                  <Phone className="h-4 w-4 text-faint" />
                  <span className="text-sm text-faint">+91</span>
                  <input
                    type="tel"
                    inputMode="numeric"
                    required
                    pattern="[0-9]{10}"
                    maxLength={10}
                    value={phone}
                    onChange={(e) => setPhone(e.target.value.replace(/\D/g, ''))}
                    placeholder="98765 43210"
                    className="w-full bg-transparent text-base font-medium text-content outline-none"
                  />
                </div>
              </label>

              <ArrowButton
                type="submit"
                variant="solid"
                disabled={loading || phone.length !== 10}
                className="mt-5 w-full justify-center disabled:opacity-50"
              >
                {loading ? 'Sending OTP…' : 'Send OTP'}
              </ArrowButton>
            </form>
          )}

          {step === 'otp' && (
            <form onSubmit={verifyOtp}>
              <h1 className="mt-3 font-display text-2xl font-bold text-content">
                Enter the code
              </h1>
              <p className="mt-1 text-sm text-muted">
                Sent to +91 {phone}. (Demo mode — any 4–6 digit code works.)
              </p>

              <label className="mt-6 block">
                <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-faint">
                  OTP
                </span>
                <div className="flex items-center gap-2 rounded-xl border border-line bg-surface px-3 py-3">
                  <ShieldCheck className="h-4 w-4 text-faint" />
                  <input
                    type="text"
                    inputMode="numeric"
                    required
                    minLength={4}
                    maxLength={6}
                    value={otp}
                    onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                    placeholder="••••"
                    className="w-full bg-transparent text-base font-medium tracking-widest text-content outline-none"
                  />
                </div>
              </label>

              <ArrowButton
                type="submit"
                variant="solid"
                disabled={loading || otp.length < 4}
                className="mt-5 w-full justify-center disabled:opacity-50"
              >
                {loading ? 'Verifying…' : 'Verify & continue'}
              </ArrowButton>
              <button
                type="button"
                onClick={() => setStep('phone')}
                className="mt-3 block w-full text-center text-sm text-faint"
              >
                Change number
              </button>
            </form>
          )}

          {step === 'name' && (
            <form onSubmit={finishSignup}>
              <h1 className="mt-3 font-display text-2xl font-bold text-content">
                What should we call you?
              </h1>
              <p className="mt-1 text-sm text-muted">
                First time here — just your first name is fine.
              </p>

              <label className="mt-6 block">
                <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-faint">
                  Name
                </span>
                <div className="flex items-center gap-2 rounded-xl border border-line bg-surface px-3 py-3">
                  <UserIcon className="h-4 w-4 text-faint" />
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Kishan"
                    className="w-full bg-transparent text-base font-medium text-content outline-none"
                  />
                </div>
              </label>

              <ArrowButton type="submit" variant="solid" className="mt-5 w-full justify-center">
                Create account
              </ArrowButton>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
