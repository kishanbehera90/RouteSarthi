import { Check } from 'lucide-react'
import { useJourneyStore } from '../store/useJourneyStore'

const items = [
  { key: 'fewerTransfers', label: 'Fewer transfers' },
  { key: 'acOnly', label: 'AC only' },
  { key: 'avoidLateNight', label: 'Avoid late-night arrivals' },
]

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
      </div>
    )
  }

  return (
    <div className="flex flex-wrap gap-2">
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
    </div>
  )
}
