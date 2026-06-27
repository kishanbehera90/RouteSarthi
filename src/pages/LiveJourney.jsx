import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { LifeBuoy, CheckCircle2, AlertTriangle, RefreshCcw } from 'lucide-react'
import ModeIcon from '../components/ModeIcon'
import { formatDuration } from '../lib/utils'

export default function LiveJourney() {
  const { routeId } = useParams()
  const [route, setRoute] = useState(null)
  const [delayed, setDelayed] = useState(false)
  const [rerouted, setRerouted] = useState(false)

  useEffect(() => {
    if (!routeId) return
    fetch(`/api/routes/${routeId}`)
      .then((res) => (res.ok ? res.json() : null))
      .then(setRoute)
  }, [routeId])

  if (!routeId) {
    return (
      <div className="text-center">
        <LifeBuoy className="mx-auto h-10 w-10 text-brand-300" />
        <h1 className="mt-3 font-display text-lg font-bold text-brand-900">No active journey</h1>
        <p className="mt-1 text-sm text-gray-500">
          Start a journey from any route's plan page — we'll monitor every leg here and step in if something breaks.
        </p>
        <Link to="/search" className="mt-4 inline-block text-sm font-semibold text-brand-600">
          Plan a journey →
        </Link>
      </div>
    )
  }

  if (!route) return <p className="text-sm text-gray-400">Loading journey…</p>

  const movingLegs = route.legs.filter((l) => l.mode !== 'connection')
  const fallback = movingLegs[movingLegs.length - 1]

  return (
    <div>
      <h1 className="font-display text-xl font-bold text-brand-900">Journey in progress</h1>
      <p className="mt-1 text-sm text-gray-500">
        {route.type === 'cross-origin' ? `Via ${route.hub?.name}` : 'Direct'} · live monitoring active
      </p>

      <div className="mt-5 space-y-2">
        {movingLegs.map((leg, i) => {
          const isCurrent = i === 0
          const status = isCurrent && delayed ? 'delayed' : 'on-time'
          return (
            <div
              key={leg.id}
              className="flex items-center gap-3 rounded-xl border border-brand-100 bg-white p-3"
            >
              <ModeIcon mode={leg.mode} className="h-4 w-4 text-brand-500" />
              <div className="flex-1">
                <p className="text-sm font-medium text-brand-900">{leg.name}</p>
                <p className="text-xs text-gray-400">
                  {leg.from} → {leg.to}
                </p>
              </div>
              {status === 'on-time' ? (
                <span className="flex items-center gap-1 text-xs font-semibold text-safe-600">
                  <CheckCircle2 className="h-3.5 w-3.5" /> On time
                </span>
              ) : (
                <span className="flex items-center gap-1 text-xs font-semibold text-risk-600">
                  <AlertTriangle className="h-3.5 w-3.5" /> Delayed
                </span>
              )}
            </div>
          )
        })}
      </div>

      {!rerouted ? (
        <div className="mt-6 rounded-2xl border border-dashed border-brand-200 bg-white p-4 text-center">
          <p className="text-sm text-gray-500">
            Worried about a delay or a missed connection? Tap below and we'll re-plan the rest of your journey from your current location.
          </p>
          <button
            type="button"
            onClick={() => {
              setDelayed(true)
              setTimeout(() => setRerouted(true), 600)
            }}
            className="mt-3 inline-flex items-center gap-2 rounded-xl bg-risk-500 px-5 py-3 text-sm font-semibold text-white"
          >
            <LifeBuoy className="h-4 w-4" />
            Save me!
          </button>
        </div>
      ) : (
        <div className="mt-6 rounded-2xl border border-safe-100 bg-safe-50 p-4">
          <div className="flex items-center gap-2 text-safe-600">
            <RefreshCcw className="h-4 w-4" />
            <p className="text-sm font-semibold">Re-routed from your current location</p>
          </div>
          <p className="mt-2 text-sm text-gray-600">{route.planB}</p>
          <p className="mt-2 text-xs text-gray-400">
            New estimated arrival shifts by the buffer above — still well within a safe connection window for {fallback?.name}.
          </p>
        </div>
      )}

      <p className="mt-4 text-center text-xs text-gray-400">
        Total planned time: {route.totalTimeMins ? formatDuration(route.totalTimeMins) : '—'}
      </p>
    </div>
  )
}
