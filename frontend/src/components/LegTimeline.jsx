import { useState } from 'react'
import { motion } from 'motion/react'
import { ShieldCheck, ShieldAlert, Navigation, ChevronDown } from 'lucide-react'
import ModeIcon from './ModeIcon'
import ConfirmationPill from './ConfirmationPill'
import ConfirmationProbability from './ConfirmationProbability'
import ClassFares from './ClassFares'
import { formatFare } from '../lib/utils'

// How the on-time / delay number for a leg was produced. The backend tags each
// train leg's delayProfile.source; we surface it so a "predicted for your date"
// number is never mistaken for a flat historical average (or a rough estimate).
const DELAY_SOURCE = {
  predicted: {
    chip: 'Predicted',
    chipClass: 'bg-brand-50 text-brand-600',
    tip: 'Estimated for your travel date by a model trained on a year of real arrivals — conditioned on day of week, month and where you get off.',
    line: (p) => `Predicted ~${p.onTimePct}% on-time · ~${p.avgMins} min delay on your date`,
  },
  measured: {
    chip: 'Measured',
    chipClass: 'bg-safe-50 text-safe-600',
    tip: "From a full year of this train's real arrivals.",
    line: (p) => `Historically ${p.onTimePct}% on time · avg delay ${p.avgMins} min`,
  },
  modelled: {
    chip: 'Estimate',
    chipClass: 'bg-sunken text-faint',
    tip: 'No historical record for this train yet — a rough estimate from its class, distance and number of stops.',
    line: (p) => `Est. ~${p.onTimePct}% on-time · ~${p.avgMins} min delay`,
  },
}

function DelayLine({ profile }) {
  // Mock corridors carry no source → read as historical (measured).
  const meta = DELAY_SOURCE[profile.source] || DELAY_SOURCE.measured
  return (
    <div className="mt-1">
      <p className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs text-faint">
        <span
          className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${meta.chipClass}`}
          title={meta.tip}
        >
          {meta.chip}
        </span>
        {meta.line(profile)}
      </p>
      <OnTimeBar pct={profile.onTimePct} />
    </div>
  )
}

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
        {leg.delayProfile && <DelayLine profile={leg.delayProfile} />}
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
