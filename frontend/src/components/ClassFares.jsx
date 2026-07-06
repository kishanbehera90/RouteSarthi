import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { formatFare } from '../lib/utils'

// Per-class fares (Sleeper / AC 3-tier / …), cheapest first.
// `compact` shows codes (SL) for tight spots; full shows labels.
// `collapsible` shows only the cheapest with an expander for the rest —
// keeps result cards from feeling congested.
export default function ClassFares({ fares, compact = false, collapsible = false, className = '' }) {
  const [open, setOpen] = useState(false)
  if (!fares?.length) return null

  if (!collapsible) {
    return (
      <div className={`flex flex-wrap gap-x-3 gap-y-1 ${className}`}>
        {fares.map((f) => (
          <span key={f.code} className="flex items-baseline gap-1 text-xs">
            <span className="text-faint">{compact ? f.code : f.label}</span>
            <span className="font-semibold text-content">{formatFare(f.fareInr)}</span>
          </span>
        ))}
      </div>
    )
  }

  const [cheapest, ...rest] = fares
  return (
    <div className={className}>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          if (rest.length) setOpen((o) => !o)
        }}
        aria-expanded={open}
        className="flex w-full items-center justify-between rounded-xl border border-line bg-sunken px-3 py-2 text-left transition-colors hover:border-brand-900/15"
      >
        <span className="text-xs text-content">
          <span className="text-faint">Cheapest · </span>
          {cheapest.label} <span className="font-semibold">{formatFare(cheapest.fareInr)}</span>
        </span>
        {rest.length > 0 && (
          <span className="flex shrink-0 items-center gap-1 text-xs font-semibold text-mist-600">
            {open ? 'Show less' : `${rest.length} more class${rest.length > 1 ? 'es' : ''}`}
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? 'rotate-180' : ''}`} />
          </span>
        )}
      </button>
      {open && (
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1.5 px-1">
          {rest.map((f) => (
            <span key={f.code} className="flex items-baseline gap-1 text-xs">
              <span className="text-faint">{f.label}</span>
              <span className="font-semibold text-content">{formatFare(f.fareInr)}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
