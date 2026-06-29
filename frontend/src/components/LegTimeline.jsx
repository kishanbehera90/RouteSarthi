import { motion } from 'motion/react'
import { ShieldCheck, ShieldAlert } from 'lucide-react'
import ModeIcon from './ModeIcon'
import ConfirmationPill from './ConfirmationPill'
import { formatFare } from '../lib/utils'

function OnTimeBar({ pct }) {
  const color =
    pct >= 80 ? 'var(--color-safe-500)' : pct >= 60 ? 'var(--color-caution-500)' : 'var(--color-risk-500)'
  return (
    <div className="mt-1.5 h-1.5 w-full max-w-[200px] overflow-hidden rounded-full bg-brand-900/[0.07]">
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
  const safe = leg.connectionSafetyPct >= 85
  const Icon = safe ? ShieldCheck : ShieldAlert
  return (
    <div className="ml-5 flex items-start gap-2 border-l-2 border-dashed border-gray-200 py-3 pl-4">
      <Icon className={safe ? 'h-4 w-4 text-safe-600' : 'h-4 w-4 text-caution-600'} />
      <div className="text-xs text-gray-600">
        <span className={safe ? 'font-semibold text-safe-600' : 'font-semibold text-caution-600'}>
          {leg.connectionSafetyPct}% connection safety
        </span>
        {' · '}
        {leg.bufferMins} min buffer
        <p className="mt-0.5 text-gray-500">{leg.note}</p>
      </div>
    </div>
  )
}

function LegRow({ leg }) {
  return (
    <div className="flex gap-3 rounded-xl border border-gray-100 bg-white p-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-50">
        <ModeIcon mode={leg.mode} className="h-4.5 w-4.5 text-brand-600" />
      </div>
      <div className="flex-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-medium text-brand-900">{leg.name}</p>
          <ConfirmationPill status={leg.confirmation} waitlistPosition={leg.waitlistPosition} />
        </div>
        <p className="text-sm text-gray-500">
          {leg.from} {leg.depart} → {leg.to} {leg.arrive}
        </p>
        {leg.delayProfile && (
          <div className="mt-1">
            <p className="text-xs text-gray-400">
              Historically {leg.delayProfile.onTimePct}% on time · avg delay {leg.delayProfile.avgMins} min
            </p>
            <OnTimeBar pct={leg.delayProfile.onTimePct} />
          </div>
        )}
      </div>
      <p className="shrink-0 self-start text-sm font-semibold text-brand-900">
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
