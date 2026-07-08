import { cn } from '../lib/utils'

function tier(score) {
  if (score >= 85) return { label: 'Safe', cls: 'bg-safe-50 text-safe-600 border-safe-100' }
  if (score >= 60) return { label: 'Moderate', cls: 'bg-caution-50 text-caution-600 border-caution-100' }
  return { label: 'Risky', cls: 'bg-risk-50 text-risk-600 border-risk-500/20' }
}

export default function ReliabilityBadge({ score, className }) {
  const t = tier(score)
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold',
        t.cls,
        className
      )}
      title="Estimated reliability — blends measured on-time record with modelled seat-confirmation and connection safety"
    >
      <span className="tabular-nums">{score}%</span>
      <span className="opacity-80">{t.label}</span>
      <span className="font-normal opacity-50">est.</span>
    </span>
  )
}
