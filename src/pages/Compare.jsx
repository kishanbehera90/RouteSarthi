import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import ReliabilityBadge from '../components/ReliabilityBadge'
import ConfirmationPill from '../components/ConfirmationPill'
import { formatDuration, formatFare } from '../lib/utils'

export default function Compare() {
  const [params] = useSearchParams()
  const from = params.get('from') ?? ''
  const to = params.get('to') ?? ''
  const [routes, setRoutes] = useState(null)

  useEffect(() => {
    fetch(`/api/routes?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&pref=confirmed`)
      .then((res) => res.json())
      .then((data) => setRoutes(data.routes))
  }, [from, to])

  if (!routes) return <p className="text-sm text-gray-400">Loading comparison…</p>

  const direct = routes.find((r) => r.type === 'direct')
  const best = routes.find((r) => r.type === 'cross-origin')

  return (
    <div>
      <h1 className="font-display text-xl font-bold text-brand-900">Direct vs. smarter route</h1>
      <p className="mt-1 text-sm text-gray-500">
        Here's the honest comparison — see why the detour usually wins.
      </p>

      <div className="mt-5 grid grid-cols-2 gap-3">
        {[
          { label: 'Direct', route: direct },
          { label: best?.hub ? `Via ${best.hub.name}` : 'Cross-origin', route: best },
        ].map(({ label, route }) => (
          <div
            key={label}
            className="rounded-2xl border border-brand-100 bg-white p-4"
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">{label}</p>
            {route ? (
              <>
                <div className="mt-2">
                  <ConfirmationPill status={route.confirmation} waitlistPosition={route.waitlistPosition} />
                </div>
                <p className="mt-3 text-lg font-bold text-brand-900">
                  {formatFare(route.totalFareInr)}
                </p>
                <p className="text-sm text-gray-500">
                  {route.totalTimeMins ? formatDuration(route.totalTimeMins) : '—'}
                </p>
                <div className="mt-2">
                  <ReliabilityBadge score={route.reliability} />
                </div>
                <Link
                  to={`/routes/${route.id}`}
                  className="mt-4 block text-center text-xs font-semibold text-brand-600"
                >
                  View plan →
                </Link>
              </>
            ) : (
              <p className="mt-2 text-sm text-gray-400">No option found.</p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
