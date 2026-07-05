import { formatFare } from '../lib/utils'

// Per-class fares (Sleeper / AC 3-tier / AC 2-tier / …), cheapest first.
// `compact` shows codes (SL) for tight spots; full shows labels.
export default function ClassFares({ fares, compact = false, className = '' }) {
  if (!fares?.length) return null
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
