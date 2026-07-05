import { useState } from 'react'
import { motion } from 'motion/react'
import { ShieldCheck, ShieldAlert, Navigation, ChevronDown } from 'lucide-react'
import ModeIcon from './ModeIcon'
import ConfirmationPill from './ConfirmationPill'
import ConfirmationProbability from './ConfirmationProbability'
import ClassFares from './ClassFares'
import { formatFare } from '../lib/utils'

function OnTimeBar({ pct }) {
  const color =
    pct >= 80 ? 'var(--color-safe-500)' : pct >= 60 ? 'var(--color-caution-500)' : 'var(--color-risk-500)'
  return (
    <div className="mt-1.5 h-1.5 w-full max-w-[200px] overflow-hidden rounded-full bg-line">
      <motion.div
        className="h-full rounded-full"
        style={{ backgroundColor: color }}
        initial={{ width: 0 }}
        whileInView={{ width: `${pct}%` }}
        viewport={{ once: true }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
      />
    </div>
  )
}

function ConnectionRow({ leg }) {
  // Road-access legs (first/last mile) carry no train-connection safety —
  // show them as a simple road note, not an empty "% connection safety".
  if (leg.connectionSafetyPct == null) {
    return (
      <div className="ml-5 flex items-start gap-2 border-l-2 border-dashed border-line py-3 pl-4">
        <Navigation className="h-4 w-4 text-mist-500" />
        <p className="text-xs text-muted">{leg.note || 'Road transfer'}</p>
      </div>
    )
  }
  const safe = leg.connectionSafetyPct >= 85
  const Icon = safe ? ShieldCheck : ShieldAlert
  return (
    <div className="ml-5 flex items-start gap-2 border-l-2 border-dashed border-line py-3 pl-4">
      <Icon className={safe ? 'h-4 w-4 text-safe-600' : 'h-4 w-4 text-caution-600'} />
      <div className="text-xs text-muted">
        <span className={safe ? 'font-semibold text-safe-600' : 'font-semibold text-caution-600'}>
          {leg.connectionSafetyPct}% connection safety
        </span>
        {leg.bufferMins != null ? ` · ${leg.bufferMins} min buffer` : ''}
        <p className="mt-0.5 text-muted">{leg.note}</p>
      </div>
    </div>
  )
}

function LegRow({ leg }) {
  const [showStops, setShowStops] = useState(false)
  return (
    <div className="flex gap-3 rounded-xl border border-line bg-surface p-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-50">
        <ModeIcon mode={leg.mode} className="h-4.5 w-4.5 text-brand-600" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-medium text-content">{leg.name}</p>
          <ConfirmationPill status={leg.confirmation} waitlistPosition={leg.waitlistPosition} />
        </div>
        <p className="text-sm text-muted">
          {leg.from} {leg.depart} → {leg.to} {leg.arrive}
        </p>
        {(leg.days || leg.halts != null) && (
          <p className="mt-0.5 text-xs text-faint">
            {leg.days && <span className="text-mist-600">{leg.days}</span>}
            {leg.days && leg.halts != null ? ' · ' : ''}
            {leg.halts != null && `${leg.halts} halts`}
          </p>
        )}
        {leg.stops?.length > 2 && (
          <div className="mt-1">
            <button
              type="button"
              onClick={() => setShowStops((s) => !s)}
              className="flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700"
            >
              {showStops ? 'Hide stops' : `View all ${leg.stops.length} stops`}
              <ChevronDown className={`h-3 w-3 transition-transform ${showStops ? 'rotate-180' : ''}`} />
            </button>
            {showStops && (
              <p className="mt-1 text-xs leading-relaxed text-muted">{leg.stops.join(' · ')}</p>
            )}
          </div>
        )}
        {leg.delayProfile && (
          <div className="mt-1">
            <p className="text-xs text-faint">
              Historically {leg.delayProfile.onTimePct}% on time · avg delay {leg.delayProfile.avgMins} min
            </p>
            <OnTimeBar pct={leg.delayProfile.onTimePct} />
          </div>
        )}
        {leg.confirmation === 'waitlisted' && leg.clearProbabilityPct != null && (
          <ConfirmationProbability
            waitlistPosition={leg.waitlistPosition}
            probability={leg.clearProbabilityPct}
            className="mt-2 max-w-[220px]"
          />
        )}
        {leg.classFares?.length > 0 && (
          <div className="mt-2 border-t border-line-soft pt-2">
            <ClassFares fares={leg.classFares} />
          </div>
        )}
      </div>
      <p className="shrink-0 self-start text-sm font-semibold text-content">
        {formatFare(leg.fareInr)}
      </p>
    </div>
  )
}

export default function LegTimeline({ legs }) {
  return (
    <div className="space-y-2">
      {legs.map((leg) =>
        leg.mode === 'connection' ? (
          <ConnectionRow key={leg.id} leg={leg} />
        ) : (
          <LegRow key={leg.id} leg={leg} />
        )
      )}
    </div>
  )
}
