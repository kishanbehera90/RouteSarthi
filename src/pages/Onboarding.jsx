import { useNavigate } from 'react-router-dom'
import { MapPinned, ShieldCheck, LifeBuoy, ArrowRight } from 'lucide-react'

const points = [
  {
    icon: MapPinned,
    title: 'Routes through smarter hubs',
    body: 'If your town is poorly connected, we route you via a nearby city with far better options — and show you exactly how to get there.',
  },
  {
    icon: ShieldCheck,
    title: 'Connections you can trust',
    body: 'Every transfer is scored on real historical delay data, so we only recommend ones you can actually make.',
  },
  {
    icon: LifeBuoy,
    title: 'A lifeline if it breaks',
    body: 'If a leg runs late mid-journey, tap "Save me!" and we re-plan the rest of your trip from where you are.',
  },
]

export default function Onboarding() {
  const navigate = useNavigate()
  return (
    <div className="mx-auto flex min-h-svh max-w-2xl flex-col bg-gradient-to-b from-brand-900 to-brand-700 px-6 py-10 text-white">
      <div className="flex-1">
        <p className="text-sm font-medium text-brand-200">RouteSarthi</p>
        <h1 className="mt-2 font-display text-3xl font-bold leading-tight sm:text-4xl">
          Pohochao, har haal mein.
        </h1>
        <p className="mt-2 text-brand-100">We get you there, no matter what.</p>

        <div className="mt-10 space-y-6">
          {points.map(({ icon: Icon, title, body }) => (
            <div key={title} className="flex gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/10">
                <Icon className="h-4.5 w-4.5" />
              </div>
              <div>
                <p className="font-semibold">{title}</p>
                <p className="mt-0.5 text-sm text-brand-100">{body}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <button
        type="button"
        onClick={() => navigate('/search')}
        className="mt-10 flex items-center justify-center gap-2 rounded-xl bg-white px-5 py-3.5 font-semibold text-brand-800 transition hover:bg-brand-50"
      >
        Plan a journey
        <ArrowRight className="h-4 w-4" />
      </button>
    </div>
  )
}
