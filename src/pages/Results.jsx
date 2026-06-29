import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Columns2, SlidersHorizontal } from 'lucide-react'
import RouteCard from '../components/RouteCard'
import { ResultsSkeleton } from '../components/Skeleton'
import PreferenceControl from '../components/PreferenceControl'
import FiltersPanel from '../components/FiltersPanel'
import EyebrowLabel from '../components/EyebrowLabel'
import ArrowButton from '../components/ArrowButton'
import BackLink from '../components/BackLink'
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
    return (
      <div className="mx-auto max-w-6xl">
        <ResultsSkeleton />
      </div>
    )
  }

  if (!state.corridor) {
    return (
      <div className="mx-auto max-w-2xl">
        <BackLink to="/search">Back to search</BackLink>
        <EyebrowLabel>Your routes</EyebrowLabel>
        <p className="mt-3 text-sm text-gray-500">
          We don't have mock data for "{from} → {to}" yet. Try Rourkela → Nashik, Bhuj → Shimla, or Imphal → Bengaluru.
        </p>
        <ArrowButton as={Link} to="/search" variant="solid" className="mt-4">
          Back to search
        </ArrowButton>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl">
      <BackLink to="/search">Back to search</BackLink>

      <div className="flex items-start justify-between gap-3">
        <div>
          <EyebrowLabel>Your routes</EyebrowLabel>
          <h1 className="mt-3 font-display text-xl font-bold text-brand-900">
            {state.corridor.from.name} → {state.corridor.to.name}
          </h1>
          <p className="mt-1 text-sm text-gray-500">{state.corridor.tagline}</p>
        </div>
        <Link
          to={`/compare?from=${from}&to=${to}`}
          className="flex shrink-0 items-center gap-1 rounded-lg border border-brand-900/10 bg-white px-2.5 py-1.5 text-xs font-semibold text-brand-700"
        >
          <Columns2 className="h-3.5 w-3.5" />
          Compare
        </Link>
      </div>

      {/* Mobile/tablet: horizontal pill controls. Desktop: sidebar (below) takes over. */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 lg:hidden">
        <PreferenceControl value={pref} onChange={(p) => setParams({ from, to, pref: p })} />
        <FiltersPanel />
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-[220px_1fr]">
        <aside className="hidden lg:block">
          <div className="sticky top-20 space-y-5 rounded-2xl border border-brand-900/10 bg-white p-4">
            <div>
              <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                <SlidersHorizontal className="h-3.5 w-3.5" />
                Sort by
              </p>
              <PreferenceControl vertical value={pref} onChange={(p) => setParams({ from, to, pref: p })} />
            </div>
            <div className="border-t border-brand-900/5 pt-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">Filters</p>
              <FiltersPanel vertical />
            </div>
          </div>
        </aside>

        <div>
          <div className="grid gap-3 sm:grid-cols-2">
            {visibleRoutes.length === 0 && (
              <p className="text-sm text-gray-400 sm:col-span-2">No routes match your filters — try relaxing one.</p>
            )}
            {visibleRoutes.map((route, i) => (
              <RouteCard key={route.id} route={route} index={i} />
            ))}
          </div>

          {state.routes.some((r) => r.type === 'cross-origin') && (
            <div className="mt-4 flex justify-center">
              <ArrowButton as={Link} to={`/hub-picker?from=${from}&to=${to}`} variant="ghost">
                Compare origin hubs
              </ArrowButton>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
