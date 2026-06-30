import { TrendingUp } from 'lucide-react'

// Tiny "WL 38 → ~18% likely to clear" predictor with a confidence bar.
export default function ConfirmationProbability({ waitlistPosition, probability, className = '' }) {
  if (probability == null) return null
  const tone =
    probability >= 70
      ? { text: 'text-safe-600', bar: 'var(--color-safe-500)' }
      : probability >= 40
        ? { text: 'text-caution-600', bar: 'var(--color-caution-500)' }
        : { text: 'text-risk-600', bar: 'var(--color-risk-500)' }

  return (
    <div className={className}>
      <div className="flex items-center justify-between text-xs">
        <span className="flex items-center gap-1 text-muted">
          <TrendingUp className="h-3.5 w-3.5" />
          {waitlistPosition ? `WL ${waitlistPosition} → ` : ''}clearance odds
        </span>
        <span className={`font-semibold ${tone.text}`}>~{probability}% likely</span>
      </div>
      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-line">
        <div className="h-full rounded-full" style={{ width: `${probability}%`, backgroundColor: tone.bar }} />
      </div>
    </div>
  )
}
