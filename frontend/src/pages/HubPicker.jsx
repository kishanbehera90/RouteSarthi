import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { MapPinned } from 'lucide-react'
import ModeIcon from '../components/ModeIcon'
import EyebrowLabel from '../components/EyebrowLabel'
import ArrowButton from '../components/ArrowButton'
import BackLink from '../components/BackLink'
import { HubPickerSkeleton } from '../components/Skeleton'
import { formatDuration, formatFare } from '../lib/utils'

export default function HubPicker() {
  const [params] = useSearchParams()
  const from = params.get('from') ?? ''
  const to = params.get('to') ?? ''
  const [routes, setRoutes] = useState(null)

  useEffect(() => {
    fetch(`/api/routes?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&pref=confirmed`)
      .then((res) => res.json())
      .then((data) => setRoutes(data.routes))
  }, [from, to])

  if (!routes) return <HubPickerSkeleton />

  const crossOrigin = routes.filter((r) => r.type === 'cross-origin')
  const byHub = new Map()
  for (const r of crossOrigin) {
    const key = r.hub?.code
    if (!key) continue
    if (!byHub.has(key)) byHub.set(key, { hub: r.hub, routes: [] })
    byHub.get(key).routes.push(r)
  }

  return (
    <div className="mx-auto max-w-2xl">
      <BackLink>Back to results</BackLink>
      <EyebrowLabel>Choose a hub</EyebrowLabel>
      <h1 className="mt-3 font-display text-xl font-bold text-content">Pick your origin hub</h1>
      <p className="mt-1 text-sm text-muted">
        When a nearby city is much better connected, we route you there first. Here's the first-mile cost for each.
      </p>

      <div className="mt-5 space-y-3">
        {[...byHub.values()].map(({ hub, routes: hubRoutes }) => {
          const best = hubRoutes[0]
          const firstMile = best.legs[0]
          return (
            <div key={hub.code} className="rounded-2xl border border-line bg-surface p-4 shadow-card transition-shadow hover:shadow-lift">
              <div className="flex items-center gap-2">
                <MapPinned className="h-4 w-4 text-mist-500" />
                <p className="font-semibold text-content">{hub.name}</p>
              </div>
              <div className="mt-2 flex items-center gap-2 text-sm text-muted">
                <ModeIcon mode={firstMile.mode} className="h-4 w-4 text-brand-400" />
                <span>
                  {formatDuration(firstMile.durationMins)} · {formatFare(firstMile.fareInr)} first-mile
                </span>
              </div>
              <p className="mt-2 text-xs text-faint">
                {hubRoutes.length} confirmed route{hubRoutes.length > 1 ? 's' : ''} onward from here
              </p>
              <ArrowButton as={Link} to={`/routes/${best.id}`} variant="ghost" className="mt-3 text-sm">
                Plan via {hub.name}
              </ArrowButton>
            </div>
          )
        })}
        {byHub.size === 0 && (
          <p className="text-sm text-faint">No cross-origin hub needed for this route.</p>
        )}
      </div>
    </div>
  )
}
