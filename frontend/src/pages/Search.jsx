import { useNavigate } from 'react-router-dom'
import { ArrowRightLeft, ArrowRight, MapPinned } from 'lucide-react'
import { useJourneyStore } from '../store/useJourneyStore'
import PreferenceControl from '../components/PreferenceControl'
import EyebrowLabel from '../components/EyebrowLabel'
import ArrowButton from '../components/ArrowButton'
import JourneyDatePicker from '../components/JourneyDatePicker'
import { corridors } from '../data/routes'
import heroRail from '../assets/hero-rail.webp'

const cityNames = Array.from(
  new Set(corridors.flatMap((c) => [c.from.name, c.to.name]))
)

export default function SearchPage() {
  const navigate = useNavigate()
  const search = useJourneyStore((s) => s.search)
  const setSearch = useJourneyStore((s) => s.setSearch)

  const goToResults = (from, to, pref) =>
    navigate(`/results?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&pref=${pref}`)

  const handleSubmit = (e) => {
    e.preventDefault()
    goToResults(search.from, search.to, search.pref)
  }

  const swap = () => setSearch({ from: search.to, to: search.from })

  const pickCorridor = (corridor) => {
    setSearch({ from: corridor.from.name, to: corridor.to.name })
    goToResults(corridor.from.name, corridor.to.name, search.pref)
  }

  const routeLabel = search.from && search.to ? `${search.from} → ${search.to}` : null

  return (
    <div>
      <div className="relative mb-8 overflow-hidden rounded-3xl">
        <img
          src={heroRail}
          alt=""
          className="absolute inset-0 h-full w-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-brand-900/95 via-brand-900/80 to-brand-900/45" />
        <div className="relative px-6 py-12 sm:px-10 sm:py-14">
          <EyebrowLabel tone="dark">Plan a journey</EyebrowLabel>
          <h1 className="mt-3 max-w-lg font-display text-3xl font-bold text-white sm:text-4xl">
            Where are you headed?
          </h1>
          <p className="mt-2 max-w-md text-sm text-white/80 sm:text-base">
            Tell us where you're starting and where you need to be — we'll figure out the smartest way, even via another city.
          </p>
        </div>
      </div>

      <div className="lg:grid lg:grid-cols-[1fr_360px] lg:items-start lg:gap-12">
        <div className="mx-auto w-full max-w-xl lg:mx-0">
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="relative rounded-2xl border border-line bg-surface p-1 shadow-card">
              <label className="block px-3 pt-2.5 text-xs font-medium uppercase tracking-wide text-faint">
                From
              </label>
              <input
                list="cities"
                required
                value={search.from}
                onChange={(e) => setSearch({ from: e.target.value })}
                className="w-full bg-transparent px-3 pb-2.5 text-base font-medium text-content outline-none"
                placeholder="e.g. Rourkela"
              />
              <div className="border-t border-brand-50" />
              <label className="block px-3 pt-2.5 text-xs font-medium uppercase tracking-wide text-faint">
                To
              </label>
              <input
                list="cities"
                required
                value={search.to}
                onChange={(e) => setSearch({ to: e.target.value })}
                className="w-full bg-transparent px-3 pb-2.5 text-base font-medium text-content outline-none"
                placeholder="e.g. Nashik"
              />
              <datalist id="cities">
                {cityNames.map((name) => (
                  <option key={name} value={name} />
                ))}
              </datalist>

              <button
                type="button"
                onClick={swap}
                aria-label="Swap source and destination"
                className="absolute right-3 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full border border-line bg-surface shadow-soft transition hover:shadow-card"
              >
                <ArrowRightLeft className="h-4 w-4 text-brand-500" />
              </button>
            </div>

            <JourneyDatePicker
              value={search.date}
              onChange={(iso) => setSearch({ date: iso })}
              routeLabel={routeLabel}
            />

            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-faint">
                What matters most?
              </p>
              <PreferenceControl value={search.pref} onChange={(pref) => setSearch({ pref })} />
            </div>

            <ArrowButton type="submit" variant="solid" className="w-full justify-center">
              Find my route
            </ArrowButton>
          </form>
        </div>

        <div className="mx-auto mt-10 w-full max-w-xl lg:mx-0 lg:mt-0">
          <p className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-faint">
            <MapPinned className="h-3.5 w-3.5" />
            Popular corridors
          </p>
          <div className="space-y-2.5">
            {corridors.map((corridor) => (
              <button
                key={corridor.id}
                type="button"
                onClick={() => pickCorridor(corridor)}
                className="group flex w-full items-center justify-between rounded-2xl border border-line bg-surface px-4 py-3.5 text-left shadow-soft transition hover:border-mist-300 hover:shadow-card"
              >
                <div>
                  <p className="text-sm font-semibold text-content">
                    {corridor.from.name} → {corridor.to.name}
                  </p>
                  <p className="mt-0.5 text-xs text-faint">{corridor.tagline}</p>
                </div>
                <ArrowRight className="h-4 w-4 shrink-0 text-faint transition group-hover:translate-x-0.5 group-hover:text-mist-500" />
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
