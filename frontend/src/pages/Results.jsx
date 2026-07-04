import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Columns2, SlidersHorizontal, ArrowRight, Compass } from 'lucide-react'
import RouteCard from '../components/RouteCard'
import DecisionReasoning from '../components/DecisionReasoning'
import { ResultsSkeleton } from '../components/Skeleton'
import PreferenceControl from '../components/PreferenceControl'
import FiltersPanel from '../components/FiltersPanel'
import EyebrowLabel from '../components/EyebrowLabel'
import ArrowButton from '../components/ArrowButton'
import BackLink from '../components/BackLink'
import { corridors } from '../data/routes'
import { useJourneyStore } from '../store/useJourneyStore'
import { isLateNightTime } from '../lib/utils'

export default function Results() {
  const [params, setParams] = useSearchParams()
  const from = params.get('from') ?? ''
  const to = params.get('to') ?? ''
  const pref = params.get('pref') ?? 'confirmed'
  const date = params.get('date') ?? ''

  const filters = useJourneyStore((s) => s.filters)

  const [state, setState] = useState({ loading: true, corridor: null, routes: [] })
  const [showAll, setShowAll] = useState(false)

  useEffect(() => {
    let cancelled = false
    setState((s) => ({ ...s, loading: true }))
    fetch(
      `/api/routes?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&pref=${pref}` +
        (date ? `&date=${date}` : '')
    )
      .then((res) => res.json())
      .then((data) => {
        if (!cancelled) setState({ loading: false, corridor: data.corridor, routes: data.routes })
      })
    return () => {
      cancelled = true
    }
  }, [from, to, pref, date])

  const visibleRoutes = useMemo(() => {
    return state.routes.filter((r) => {
      if (filters.acOnly) {
        // Engine routes carry real class data; mock routes fall back to fare proxy.
        if (r.acAvailable === false) return false
        if (r.acAvailable === undefined && r.totalFareInr < 600) return false
      }
      if (filters.fewerTransfers && (r.transfers ?? r.legs.filter((l) => l.mode === 'train').length - 1) > 0) return false
      if (filters.avoidLateNight) {
        // Last leg with a real arrival time (road legs carry none).
        const arriving = r.legs.filter((l) => l.mode !== 'connection' && l.arrive)
        const lastLeg = arriving[arriving.length - 1]
        if (lastLeg && isLateNightTime(lastLeg.arrive)) return false
      }
      return true
    })
  }, [state.routes, filters])

  const shownRoutes = showAll ? visibleRoutes : visibleRoutes.slice(0, 6)

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
        <EyebrowLabel>Still expanding</EyebrowLabel>
        <div className="mt-3 flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-mist-50 text-mist-600">
            <Compass className="h-5 w-5" />
          </span>
          <div>
            <h1 className="font-display text-xl font-bold text-content">
              {from ? `${from}${to ? ` → ${to}` : ''} isn't mapped yet` : "That route isn't mapped yet"}
            </h1>
            <p className="mt-1 text-sm text-muted">
              RouteSarthi is rolling out corridor by corridor. Here are the routes we've mapped so far — each shows the full cross-origin plan.
            </p>
          </div>
        </div>

        <div className="mt-5 space-y-2.5">
          {corridors.map((c) => (
            <Link
              key={c.id}
              to={`/results?from=${encodeURIComponent(c.from.name)}&to=${encodeURIComponent(c.to.name)}`}
              className="group flex items-center justify-between rounded-2xl border border-line bg-surface px-4 py-3.5 shadow-soft transition hover:border-mist-300 hover:shadow-card"
            >
              <div>
                <p className="text-sm font-semibold text-content">
                  {c.from.name} → {c.to.name}
                </p>
                <p className="mt-0.5 text-xs text-faint">{c.tagline}</p>
              </div>
              <ArrowRight className="h-4 w-4 shrink-0 text-faint transition group-hover:translate-x-0.5 group-hover:text-mist-500" />
            </Link>
          ))}
        </div>

        <ArrowButton as={Link} to="/search" variant="ghost" className="mt-5">
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
          <h1 className="mt-3 font-display text-xl font-bold text-content">
            {state.corridor.from.name} → {state.corridor.to.name}
          </h1>
          <p className="mt-1 text-sm text-muted">{state.corridor.tagline}</p>
        </div>
        <Link
          to={`/compare?from=${from}&to=${to}`}
          className="flex shrink-0 items-center gap-1 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs font-semibold text-brand-700"
        >
          <Columns2 className="h-3.5 w-3.5" />
          Compare
        </Link>
      </div>

      {state.corridor.reasoning && (
        <div className="mt-4">
          <DecisionReasoning
            reasoning={state.corridor.reasoning}
            from={state.corridor.from.name}
            to={state.corridor.to.name}
          />
        </div>
      )}

      {/* Mobile/tablet: horizontal pill controls. Desktop: sidebar (below) takes over. */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 lg:hidden">
        <PreferenceControl value={pref} onChange={(p) => setParams(date ? { from, to, pref: p, date } : { from, to, pref: p })} />
        <FiltersPanel />
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-[220px_1fr]">
        <aside className="hidden lg:block">
          <div className="sticky top-20 space-y-5 rounded-2xl border border-line bg-surface p-4 shadow-card">
            <div>
              <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-faint">
                <SlidersHorizontal className="h-3.5 w-3.5" />
                Sort by
              </p>
              <PreferenceControl vertical value={pref} onChange={(p) => setParams(date ? { from, to, pref: p, date } : { from, to, pref: p })} />
            </div>
            <div className="border-t border-line-soft pt-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-faint">Filters</p>
              <FiltersPanel vertical />
            </div>
          </div>
        </aside>

        <div>
          <div className="grid gap-3 sm:grid-cols-2">
            {visibleRoutes.length === 0 && (
              <p className="text-sm text-faint sm:col-span-2">No routes match your filters — try relaxing one.</p>
            )}
            {shownRoutes.map((route, i) => (
              <RouteCard key={route.id} route={route} index={i} />
            ))}
          </div>

          {!showAll && visibleRoutes.length > 6 && (
            <div className="mt-4 flex justify-center">
              <button
                type="button"
                onClick={() => setShowAll(true)}
                className="rounded-full border border-line bg-surface px-5 py-2.5 text-sm font-semibold text-brand-700 shadow-soft transition hover:shadow-card"
              >
                Show {visibleRoutes.length - 6} more trains
              </button>
            </div>
          )}

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
