import { useEffect, useRef, useState } from 'react'
import { motion } from 'motion/react'

function tier(score) {
  if (score >= 85) return { label: 'Safe', color: 'var(--color-safe-500)' }
  if (score >= 60) return { label: 'Moderate', color: 'var(--color-caution-500)' }
  return { label: 'Risky', color: 'var(--color-risk-500)' }
}

// rAF count-up; falls back to the final value when reduced motion is requested.
function useCountUp(target, duration = 900) {
  const [val, setVal] = useState(() =>
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? target : 0
  )
  const ref = useRef()
  useEffect(() => {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      setVal(target)
      return
    }
    let start
    const step = (t) => {
      if (!start) start = t
      const p = Math.min((t - start) / duration, 1)
      const eased = 1 - Math.pow(1 - p, 3)
      setVal(Math.round(target * eased))
      if (p < 1) ref.current = requestAnimationFrame(step)
    }
    ref.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(ref.current)
  }, [target, duration])
  return val
}

export default function ReliabilityGauge({ score, size = 128, stroke = 11, showLabel = true }) {
  const t = tier(score)
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const display = useCountUp(score)

  const ring = (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="rgba(22,28,69,0.08)"
            strokeWidth={stroke}
          />
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={t.color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={c}
            initial={{ strokeDashoffset: c }}
            animate={{ strokeDashoffset: c * (1 - score / 100) }}
            transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display text-2xl font-bold tabular-nums text-brand-900">{display}%</span>
          <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: t.color }}>
            {t.label}
          </span>
        </div>
      </div>
  )

  if (!showLabel) return ring

  return (
    <div className="flex items-center gap-4">
      {ring}
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Reliability score</p>
        <p className="mt-1 text-sm text-gray-500">
          A single number blending confirmation odds, historical delays, and connection safety across every leg.
        </p>
      </div>
    </div>
  )
}
