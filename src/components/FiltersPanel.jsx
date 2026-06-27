import { useJourneyStore } from '../store/useJourneyStore'

const items = [
  { key: 'fewerTransfers', label: 'Fewer transfers' },
  { key: 'acOnly', label: 'AC only' },
  { key: 'avoidLateNight', label: 'Avoid late-night arrivals' },
]

export default function FiltersPanel() {
  const filters = useJourneyStore((s) => s.filters)
  const toggleFilter = useJourneyStore((s) => s.toggleFilter)

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          onClick={() => toggleFilter(item.key)}
          className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
            filters[item.key]
              ? 'border-brand-600 bg-brand-600 text-white'
              : 'border-gray-200 bg-white text-gray-600 hover:border-brand-200'
          }`}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}
