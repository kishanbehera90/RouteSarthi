import { Check } from 'lucide-react'
import { useJourneyStore } from '../store/useJourneyStore'
import { DEPARTURE_WINDOWS } from '../lib/utils'

const items = [
  { key: 'fewerTransfers', label: 'Fewer transfers' },
  { key: 'acOnly', label: 'AC only' },
  { key: 'avoidLateNight', label: 'Avoid late-night arrivals' },
]

function DeparturePicker({ vertical }) {
  const departureWindows = useJourneyStore((s) => s.filters.departureWindows)
  const toggleDepartureWindow = useJourneyStore((s) => s.toggleDepartureWindow)

  if (vertical) {
    return (
      <div className="flex flex-col gap-1">
        {DEPARTURE_WINDOWS.map((w) => {
          const active = departureWindows.includes(w.key)
          return (
            <button
              key={w.key}
              type="button"
              onClick={() => toggleDepartureWindow(w.key)}
              className={`flex items-center justify-between rounded-lg px-3 py-2 text-left text-sm font-medium transition ${
                active ? 'bg-mist-50 text-mist-600' : 'text-muted hover:bg-sunken'
              }`}
            >
              <span>
                {w.label} <span className="text-xs text-faint">· {w.hint}</span>
              </span>
              {active && <Check className="h-3.5 w-3.5" />}
            </button>
          )
        })}
      </div>
    )
  }

  return (
    <div className="flex flex-wrap gap-2">
      {DEPARTURE_WINDOWS.map((w) => {
        const active = departureWindows.includes(w.key)
        return (
          <button
            key={w.key}
            type="button"
            onClick={() => toggleDepartureWindow(w.key)}
            title={w.hint}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
              active ? 'border-brand-600 bg-primary text-white' : 'border-line bg-surface text-muted hover:border-brand-200'
            }`}
          >
            {w.label}
          </button>
        )
      })}
    </div>
  )
}

const CLASSES = [
  { code: '', label: 'Any class' },
  { code: 'SL', label: 'Sleeper' },
  { code: '3A', label: 'AC 3-tier' },
  { code: '2A', label: 'AC 2-tier' },
  { code: '1A', label: 'AC First' },
  { code: 'CC', label: 'Chair Car' },
  { code: '2S', label: 'Second sitting' },
]

function ClassPicker({ vertical }) {
  const travelClass = useJourneyStore((s) => s.filters.travelClass)
  const setTravelClass = useJourneyStore((s) => s.setTravelClass)
  return (
    <select
      value={travelClass}
      onChange={(e) => setTravelClass(e.target.value)}
      className={`rounded-full border border-line bg-surface px-3 py-1.5 text-xs font-medium text-muted outline-none transition hover:border-brand-200 ${
        vertical ? 'w-full' : ''
      }`}
      aria-label="Travel class"
    >
      {CLASSES.map((c) => (
        <option key={c.code} value={c.code}>
          {c.label}
        </option>
      ))}
    </select>
  )
}

export default function FiltersPanel({ vertical = false }) {
  const filters = useJourneyStore((s) => s.filters)
  const toggleFilter = useJourneyStore((s) => s.toggleFilter)

  if (vertical) {
    return (
      <div className="flex flex-col gap-1">
        {items.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => toggleFilter(item.key)}
            className={`flex items-center justify-between rounded-lg px-3 py-2 text-left text-sm font-medium transition ${
              filters[item.key] ? 'bg-mist-50 text-mist-600' : 'text-muted hover:bg-sunken'
            }`}
          >
            {item.label}
            {filters[item.key] && <Check className="h-3.5 w-3.5" />}
          </button>
        ))}
        <div className="mt-2 px-1">
          <ClassPicker vertical />
        </div>
        <div className="mt-3 border-t border-line-soft px-1 pt-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-faint">Departure time</p>
          <DeparturePicker vertical />
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          onClick={() => toggleFilter(item.key)}
          className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
            filters[item.key]
              ? 'border-brand-600 bg-primary text-white'
              : 'border-line bg-surface text-muted hover:border-brand-200'
          }`}
        >
          {item.label}
        </button>
      ))}
      <ClassPicker />
      <span className="hidden h-4 w-px bg-line sm:inline-block" />
      <DeparturePicker />
    </div>
  )
}
