import { useNavigate } from 'react-router-dom'
import { ArrowRightLeft, Search as SearchIcon } from 'lucide-react'
import { useJourneyStore } from '../store/useJourneyStore'
import PreferenceControl from '../components/PreferenceControl'
import { corridors } from '../data/routes'

const cityNames = Array.from(
  new Set(corridors.flatMap((c) => [c.from.name, c.to.name]))
)

export default function SearchPage() {
  const navigate = useNavigate()
  const search = useJourneyStore((s) => s.search)
  const setSearch = useJourneyStore((s) => s.setSearch)

  const handleSubmit = (e) => {
    e.preventDefault()
    navigate(
      `/results?from=${encodeURIComponent(search.from)}&to=${encodeURIComponent(search.to)}&pref=${search.pref}`
    )
  }

  const swap = () => setSearch({ from: search.to, to: search.from })

  return (
    <div>
      <h1 className="font-display text-2xl font-bold text-brand-900">Where are you headed?</h1>
      <p className="mt-1 text-sm text-gray-500">
        Tell us where you're starting and where you need to be — we'll figure out the smartest way, even via another city.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-3">
        <div className="relative rounded-2xl border border-brand-100 bg-white p-1">
          <label className="block px-3 pt-2.5 text-xs font-medium uppercase tracking-wide text-gray-400">
            From
          </label>
          <input
            list="cities"
            required
            value={search.from}
            onChange={(e) => setSearch({ from: e.target.value })}
            className="w-full bg-transparent px-3 pb-2.5 text-base font-medium text-brand-900 outline-none"
            placeholder="e.g. Rourkela"
          />
          <div className="border-t border-brand-50" />
          <label className="block px-3 pt-2.5 text-xs font-medium uppercase tracking-wide text-gray-400">
            To
          </label>
          <input
            list="cities"
            required
            value={search.to}
            onChange={(e) => setSearch({ to: e.target.value })}
            className="w-full bg-transparent px-3 pb-2.5 text-base font-medium text-brand-900 outline-none"
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
            className="absolute right-3 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full border border-brand-100 bg-white shadow-sm"
          >
            <ArrowRightLeft className="h-4 w-4 text-brand-500" />
          </button>
        </div>

        <input
          type="date"
          value={search.date}
          onChange={(e) => setSearch({ date: e.target.value })}
          className="w-full rounded-2xl border border-brand-100 bg-white px-4 py-3 text-sm text-brand-900 outline-none"
        />

        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">
            What matters most?
          </p>
          <PreferenceControl value={search.pref} onChange={(pref) => setSearch({ pref })} />
        </div>

        <button
          type="submit"
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-3.5 font-semibold text-white transition hover:bg-brand-700"
        >
          <SearchIcon className="h-4 w-4" />
          Find my route
        </button>
      </form>

      <p className="mt-4 text-center text-xs text-gray-400">
        Try Rourkela → Nashik, Bhuj → Shimla, or Imphal → Bengaluru to see cross-origin routing in action.
      </p>
    </div>
  )
}
