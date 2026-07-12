import { useEffect, useRef, useState } from 'react'
import { motion } from 'motion/react'
import { ChevronDown } from 'lucide-react'
import { cn } from '../lib/utils'

function tier(score) {
  if (score >= 85) return { label: 'Safe', color: 'var(--color-safe-500)' }
  if (score >= 60) return { label: 'Moderate', color: 'var(--color-caution-500)' }
  return { label: 'Risky', color: 'var(--color-risk-500)' }
}

function BreakdownBars({ items }) {
  return (
    <div className="mt-4 w-full space-y-2.5 border-t border-line pt-4">
      {items.map((it) => {
        const c = tier(it.value).color
        return (
          <div key={it.label}>
            <div className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-1.5 text-muted">
                {it.label}
                {typeof it.weight === 'number' && (
                  <span className="text-faint" title="How much this factor counts toward the overall score">
                    · {it.weight}% of score
                  </span>
                )}
                {it.source === 'measured' && (
                  <span
                    className="rounded-full bg-safe-50 px-1.5 py-px text-[10px] font-semibold text-safe-600"
                    title="Based on a full year of real arrival records"
                  >
                    measured
                  </span>
                )}
              </span>
              <span className="font-semibold tabular-nums" style={{ color: c }}>
                {it.value}%
              </span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-line">
              <motion.div
                className="h-full rounded-full"
                style={{ backgroundColor: c }}
                initial={{ width: 0 }}
                animate={{ width: `${it.value}%` }}
                transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
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

export default function ReliabilityGauge({ score, size = 128, stroke = 11, showLabel = true, breakdown = null }) {
  const t = tier(score)
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const display = useCountUp(score)
  const [open, setOpen] = useState(false)

  const ring = (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="var(--color-line)"
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
          <span className="font-display text-2xl font-bold tabular-nums text-content">{display}%</span>
          <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: t.color }}>
            {t.label}
          </span>
        </div>
      </div>
  )

  if (breakdown && breakdown.length) {
    return (
      <div className="flex w-full flex-col items-center">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="group flex flex-col items-center gap-1.5"
        >
          {ring}
          <span className="flex items-center gap-1 text-[11px] font-medium text-muted transition group-hover:text-content">
            {open ? 'Hide breakdown' : 'See score breakdown'}
            <ChevronDown className={cn('h-3.5 w-3.5 transition-transform', open && 'rotate-180')} />
          </span>
        </button>
        {open && <BreakdownBars items={breakdown} />}
      </div>
    )
  }

  if (!showLabel) return ring

  return (
    <div className="flex items-center gap-4">
      {ring}
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-wide text-faint">Reliability score</p>
        <p className="mt-1 text-sm text-muted">
          A single number blending confirmation odds, historical delays, and connection safety across every leg.
        </p>
      </div>
    </div>
  )
}
