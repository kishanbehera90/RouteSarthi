import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { MapPinned, ArrowRight } from 'lucide-react'
import ModeIcon from '../components/ModeIcon'
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

  if (!routes) return <p className="text-sm text-gray-400">Loading hubs…</p>

  const crossOrigin = routes.filter((r) => r.type === 'cross-origin')
  const byHub = new Map()
  for (const r of crossOrigin) {
    const key = r.hub?.code
    if (!key) continue
    if (!byHub.has(key)) byHub.set(key, { hub: r.hub, routes: [] })
    byHub.get(key).routes.push(r)
  }

  return (
    <div>
      <h1 className="font-display text-xl font-bold text-brand-900">Pick your origin hub</h1>
      <p className="mt-1 text-sm text-gray-500">
        When a nearby city is much better connected, we route you there first. Here's the first-mile cost for each.
      </p>

      <div className="mt-5 space-y-3">
        {[...byHub.values()].map(({ hub, routes: hubRoutes }) => {
          const best = hubRoutes[0]
          const firstMile = best.legs[0]
          return (
            <div key={hub.code} className="rounded-2xl border border-brand-100 bg-white p-4">
              <div className="flex items-center gap-2">
                <MapPinned className="h-4 w-4 text-brand-600" />
                <p className="font-semibold text-brand-900">{hub.name}</p>
              </div>
              <div className="mt-2 flex items-center gap-2 text-sm text-gray-500">
                <ModeIcon mode={firstMile.mode} className="h-4 w-4 text-brand-400" />
                <span>
                  {formatDuration(firstMile.durationMins)} · {formatFare(firstMile.fareInr)} first-mile
                </span>
              </div>
              <p className="mt-2 text-xs text-gray-400">
                {hubRoutes.length} confirmed route{hubRoutes.length > 1 ? 's' : ''} onward from here
              </p>
              <Link
                to={`/routes/${best.id}`}
                className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-brand-600"
              >
                Plan via {hub.name} <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          )
        })}
        {byHub.size === 0 && (
          <p className="text-sm text-gray-400">No cross-origin hub needed for this route.</p>
        )}
      </div>
    </div>
  )
}
