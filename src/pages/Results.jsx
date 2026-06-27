import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Columns2 } from 'lucide-react'
import RouteCard from '../components/RouteCard'
import PreferenceControl from '../components/PreferenceControl'
import FiltersPanel from '../components/FiltersPanel'
import { useJourneyStore } from '../store/useJourneyStore'

export default function Results() {
  const [params, setParams] = useSearchParams()
  const from = params.get('from') ?? ''
  const to = params.get('to') ?? ''
  const pref = params.get('pref') ?? 'confirmed'

  const filters = useJourneyStore((s) => s.filters)

  const [state, setState] = useState({ loading: true, corridor: null, routes: [] })

  useEffect(() => {
    let cancelled = false
    setState((s) => ({ ...s, loading: true }))
    fetch(`/api/routes?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&pref=${pref}`)
      .then((res) => res.json())
      .then((data) => {
        if (!cancelled) setState({ loading: false, corridor: data.corridor, routes: data.routes })
      })
    return () => {
      cancelled = true
    }
  }, [from, to, pref])

  const visibleRoutes = useMemo(() => {
    return state.routes.filter((r) => {
      if (filters.acOnly && r.totalFareInr < 600) return false
      if (filters.fewerTransfers && r.legs.filter((l) => l.mode !== 'connection').length > 1) return false
      return true
    })
  }, [state.routes, filters])

  if (state.loading) {
    return <p className="text-sm text-gray-400">Finding the smartest way there…</p>
  }

  if (!state.corridor) {
    return (
      <div>
        <p className="text-sm text-gray-500">
          We don't have mock data for "{from} → {to}" yet. Try Rourkela → Nashik, Bhuj → Shimla, or Imphal → Bengaluru.
        </p>
        <Link to="/search" className="mt-3 inline-block text-sm font-semibold text-brand-600">
          ← Back to search
        </Link>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-bold text-brand-900">
            {state.corridor.from.name} → {state.corridor.to.name}
          </h1>
          <p className="mt-1 text-sm text-gray-500">{state.corridor.tagline}</p>
        </div>
        <Link
          to={`/compare?from=${from}&to=${to}`}
          className="flex shrink-0 items-center gap-1 rounded-lg border border-brand-100 bg-white px-2.5 py-1.5 text-xs font-semibold text-brand-700"
        >
          <Columns2 className="h-3.5 w-3.5" />
          Compare
        </Link>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <PreferenceControl
          value={pref}
          onChange={(p) => setParams({ from, to, pref: p })}
        />
        <FiltersPanel />
      </div>

      <div className="mt-4 space-y-3">
        {visibleRoutes.length === 0 && (
          <p className="text-sm text-gray-400">No routes match your filters — try relaxing one.</p>
        )}
        {visibleRoutes.map((route) => (
          <RouteCard key={route.id} route={route} />
        ))}
      </div>

      {state.routes.some((r) => r.type === 'cross-origin') && (
        <Link
          to={`/hub-picker?from=${from}&to=${to}`}
          className="mt-4 block text-center text-sm font-semibold text-brand-600"
        >
          Compare origin hubs →
        </Link>
      )}
    </div>
  )
}
