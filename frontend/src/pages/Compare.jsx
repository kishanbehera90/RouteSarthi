import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import ReliabilityBadge from '../components/ReliabilityBadge'
import ConfirmationPill from '../components/ConfirmationPill'
import EyebrowLabel from '../components/EyebrowLabel'
import ArrowButton from '../components/ArrowButton'
import BackLink from '../components/BackLink'
import { CompareSkeleton } from '../components/Skeleton'
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

  if (!routes) return <CompareSkeleton />

  const direct = routes.find((r) => r.type === 'direct')
  const best = routes.find((r) => r.type === 'cross-origin')

  return (
    <div className="mx-auto max-w-2xl">
      <BackLink>Back to results</BackLink>
      <EyebrowLabel>Compare</EyebrowLabel>
      <h1 className="mt-3 font-display text-xl font-bold text-content">Direct vs. smarter route</h1>
      <p className="mt-1 text-sm text-muted">
        Here's the honest comparison — see why the detour usually wins.
      </p>

      <div className="mt-5 grid grid-cols-2 gap-3">
        {[
          { label: 'Direct', route: direct },
          { label: best?.hub ? `Via ${best.hub.name}` : 'Cross-origin', route: best },
        ].map(({ label, route }) => (
          <div
            key={label}
            className="rounded-2xl border border-line bg-surface p-4 shadow-card"
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-faint">{label}</p>
            {route ? (
              <>
                <div className="mt-2">
                  <ConfirmationPill status={route.confirmation} waitlistPosition={route.waitlistPosition} />
                </div>
                <p className="mt-3 text-lg font-bold text-content">
                  {formatFare(route.totalFareInr)}
                </p>
                <p className="text-sm text-muted">
                  {route.totalTimeMins ? formatDuration(route.totalTimeMins) : '—'}
                </p>
                <div className="mt-2">
                  <ReliabilityBadge score={route.reliability} />
                </div>
                <ArrowButton as={Link} to={`/routes/${route.id}`} variant="ghost" className="mt-4 text-xs">
                  View plan
                </ArrowButton>
              </>
            ) : (
              <p className="mt-2 text-sm text-faint">No option found.</p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
