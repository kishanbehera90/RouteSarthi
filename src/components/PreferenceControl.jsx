import { cn } from '../lib/utils'

const options = [
  { value: 'cheapest', label: 'Cheapest' },
  { value: 'fastest', label: 'Fastest' },
  { value: 'confirmed', label: 'Most confirmed' },
]

export default function PreferenceControl({ value, onChange, vertical = false }) {
  if (vertical) {
    return (
      <div className="flex flex-col gap-1">
        {options.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={cn(
              'rounded-lg px-3 py-2 text-left text-sm font-medium transition',
              value === opt.value
                ? 'bg-brand-600 text-white shadow-sm'
                : 'text-brand-700 hover:bg-brand-50'
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>
    )
  }

  return (
    <div className="inline-flex rounded-full border border-brand-100 bg-white p-1">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={cn(
            'rounded-full px-3.5 py-1.5 text-sm font-medium transition',
            value === opt.value
              ? 'bg-brand-600 text-white shadow-sm'
              : 'text-brand-700 hover:bg-brand-50'
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
