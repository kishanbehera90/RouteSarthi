import { Fragment, useEffect, useRef, useState } from 'react'
import { Sparkles, X, Radar, Check, ArrowRight, RotateCcw } from 'lucide-react'
import { cn } from '../lib/utils'

// Animated "watch the engine choose" strip: direct option fails → nearby hubs
// get scanned → the winning hub is revealed. Plays once on mount; replayable.
export default function DecisionReasoning({ reasoning, from, to }) {
  const hubs = reasoning?.hubsScanned ?? []
  const winner = hubs.find((h) => h.winner) ?? hubs[hubs.length - 1]
  // stages: direct(0), scan(1), hubs(2..1+n), conclusion(2+n)
  const total = 3 + hubs.length

  const prefersReduced =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

  const [step, setStep] = useState(prefersReduced ? total : 0)
  const timer = useRef(null)

  const play = () => {
    if (prefersReduced) {
      setStep(total)
      return
    }
    setStep(0)
    clearInterval(timer.current)
    timer.current = setInterval(() => {
      setStep((s) => {
        if (s >= total) {
          clearInterval(timer.current)
          return s
        }
        return s + 1
      })
    }, 600)
  }

  useEffect(() => {
    play()
    return () => clearInterval(timer.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reasoning])

  if (!reasoning) return null
  const vis = (i) => step > i

  const stageCls = (i) =>
    cn(
      'transition-all duration-500 ease-out',
      vis(i) ? 'opacity-100 translate-y-0' : 'translate-y-1 opacity-0'
    )

  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-card">
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-mist-600">
          <Sparkles className="h-3.5 w-3.5" />
          How we found this route
        </p>
        <button
          type="button"
          onClick={play}
          className="flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium text-muted transition hover:bg-sunken hover:text-content"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Replay
        </button>
      </div>

      <div className="mt-3 flex flex-wrap items-stretch gap-2">
        {/* Direct fails */}
        <div className={stageCls(0)}>
          <div className="flex h-full items-center gap-2 rounded-xl border border-risk-500/20 bg-risk-50 px-3 py-2">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-risk-500/15 text-risk-600">
              <X className="h-3.5 w-3.5" />
            </span>
            <div className="leading-tight">
              <p className="text-xs font-semibold text-content">Direct {from} → {to}</p>
              <p className="text-[11px] font-medium text-risk-600">
                {reasoning.direct.confirmability}% confirmable · {reasoning.direct.note}
              </p>
            </div>
          </div>
        </div>

        <Connector show={vis(1)} />

        {/* Scan */}
        <div className={stageCls(1)}>
          <div className="flex h-full items-center gap-2 rounded-xl bg-sunken px-3 py-2 text-muted">
            <Radar className="h-4 w-4 text-mist-500" />
            <p className="text-xs font-semibold">Scanned {hubs.length} nearby hubs</p>
          </div>
        </div>

        {/* Hubs */}
        {hubs.map((h, idx) => (
          <Fragment key={h.name}>
            <Connector show={vis(2 + idx)} />
            <div className={stageCls(2 + idx)}>
              <div
                className={cn(
                  'flex h-full items-center gap-2 rounded-xl border px-3 py-2',
                  h.winner
                    ? 'border-safe-100 bg-safe-50 ring-1 ring-safe-500/20'
                    : 'border-line bg-surface'
                )}
              >
                {h.winner && (
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-safe-500/15 text-safe-600">
                    <Check className="h-3.5 w-3.5" />
                  </span>
                )}
                <div className="leading-tight">
                  <p className={cn('text-xs font-semibold', h.winner ? 'text-safe-600' : 'text-content')}>
                    {h.name}
                  </p>
                  <p className={cn('text-[11px] font-medium', h.winner ? 'text-safe-600' : 'text-faint')}>
                    {h.dailyTrains}/day · {h.confirmPct}%
                  </p>
                </div>
              </div>
            </div>
          </Fragment>
        ))}
      </div>

      {/* Conclusion */}
      <div className={cn('mt-3', stageCls(2 + hubs.length))}>
        <p className="flex items-start gap-1.5 text-sm text-content">
          <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-mist-500" />
          <span>
            <span className="font-semibold">Via {winner?.name} wins</span> — {winner?.dailyTrains} confirmed
            trains a day at {winner?.confirmPct}%+, vs just {reasoning.direct.confirmability}% direct.
          </span>
        </p>
      </div>
    </div>
  )
}

function Connector({ show }) {
  return (
    <div className="flex items-center self-center">
      <ArrowRight
        className={cn(
          'h-4 w-4 text-faint transition-opacity duration-500',
          show ? 'opacity-100' : 'opacity-0'
        )}
      />
    </div>
  )
}
