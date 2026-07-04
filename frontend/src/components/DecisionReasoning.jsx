import { Fragment, useEffect, useRef, useState } from 'react'
import { Sparkles, X, Radar, Check, ArrowRight, RotateCcw, TrainFront } from 'lucide-react'
import { cn } from '../lib/utils'

// Animated "watch the engine choose" strip. Two modes:
//  - cross-origin: direct fails → nearby hubs scanned → winning hub revealed.
//  - direct: a through train wins directly (also-checked hubs shown muted).
// Plays once on mount; replayable.
export default function DecisionReasoning({ reasoning, from, to }) {
  const items = buildItems(reasoning, from, to)
  const total = items.length + 1 // +1 for the conclusion stage

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
    }, 550)
  }

  useEffect(() => {
    play()
    return () => clearInterval(timer.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reasoning])

  if (!reasoning || items.length === 0) return null
  const vis = (i) => step > i
  const stageCls = (i) =>
    cn('transition-all duration-500 ease-out', vis(i) ? 'opacity-100 translate-y-0' : 'translate-y-1 opacity-0')

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
        {items.map((it, i) => (
          <Fragment key={i}>
            {i > 0 && <Connector show={vis(i)} />}
            <div className={stageCls(i)}>
              <ItemChip item={it} />
            </div>
          </Fragment>
        ))}
      </div>

      <div className={cn('mt-3', stageCls(items.length))}>
        <p className="flex items-start gap-1.5 text-sm text-content">
          <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-mist-500" />
          <span>
            <span className="font-semibold">{reasoning.conclusion.split(' — ')[0]}</span>
            {reasoning.conclusion.includes(' — ')
              ? ` — ${reasoning.conclusion.split(' — ').slice(1).join(' — ')}`
              : ''}
          </span>
        </p>
      </div>
    </div>
  )
}

function buildItems(reasoning, from, to) {
  if (!reasoning) return []
  if (reasoning.mode === 'direct') {
    const w = reasoning.winner ?? {}
    const also = reasoning.alsoChecked ?? []
    return [
      { kind: 'directWin', title: `Direct ${from} → ${to}`, sub: `${w.dailyTrains ?? ''} daily direct trains` },
      ...(also.length ? [{ kind: 'scan', label: `Also checked ${also.length} nearby hub${also.length > 1 ? 's' : ''}` }] : []),
      ...also.map((h) => ({ kind: 'muted', title: h.name, sub: h.note })),
    ]
  }
  const hubs = reasoning.hubsScanned ?? []
  return [
    {
      kind: 'directFail',
      title: `Direct ${from} → ${to}`,
      sub: `${reasoning.direct.confirmability}% confirmable · ${reasoning.direct.note}`,
    },
    { kind: 'scan', label: `Scanned ${hubs.length} nearby hub${hubs.length > 1 ? 's' : ''}` },
    ...hubs.map((h) => ({
      kind: h.winner ? 'winner' : 'muted',
      title: h.name,
      sub: `${h.dailyTrains}/day · ${h.confirmPct}%`,
    })),
  ]
}

function ItemChip({ item }) {
  if (item.kind === 'scan') {
    return (
      <div className="flex h-full items-center gap-2 rounded-xl bg-sunken px-3 py-2 text-muted">
        <Radar className="h-4 w-4 text-mist-500" />
        <p className="text-xs font-semibold">{item.label}</p>
      </div>
    )
  }
  const styles = {
    directFail: { wrap: 'border-risk-500/20 bg-risk-50', icon: X, badge: 'bg-risk-500/15 text-risk-600', sub: 'text-risk-600' },
    directWin: { wrap: 'border-safe-100 bg-safe-50 ring-1 ring-safe-500/20', icon: TrainFront, badge: 'bg-safe-500/15 text-safe-600', title: 'text-safe-600', sub: 'text-safe-600' },
    winner: { wrap: 'border-safe-100 bg-safe-50 ring-1 ring-safe-500/20', icon: Check, badge: 'bg-safe-500/15 text-safe-600', title: 'text-safe-600', sub: 'text-safe-600' },
    muted: { wrap: 'border-line bg-surface', icon: null, sub: 'text-faint' },
  }[item.kind]
  const Icon = styles.icon
  return (
    <div className={cn('flex h-full items-center gap-2 rounded-xl border px-3 py-2', styles.wrap)}>
      {Icon && (
        <span className={cn('flex h-6 w-6 shrink-0 items-center justify-center rounded-full', styles.badge)}>
          <Icon className="h-3.5 w-3.5" />
        </span>
      )}
      <div className="leading-tight">
        <p className={cn('text-xs font-semibold', styles.title ?? 'text-content')}>{item.title}</p>
        {item.sub && <p className={cn('text-[11px] font-medium', styles.sub)}>{item.sub}</p>}
      </div>
    </div>
  )
}

function Connector({ show }) {
  return (
    <div className="flex items-center self-center">
      <ArrowRight className={cn('h-4 w-4 text-faint transition-opacity duration-500', show ? 'opacity-100' : 'opacity-0')} />
    </div>
  )
}
