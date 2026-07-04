import { ArrowRight } from 'lucide-react'
import Logo from './Logo'
import ModeIcon from './ModeIcon'
import ConfirmationPill from './ConfirmationPill'
import ReliabilityBadge from './ReliabilityBadge'
import { formatDuration, formatFare } from '../lib/utils'

// Clean, screenshot-friendly summary of a route — what gets "sent to a friend".
export default function ShareJourneyCard({ route }) {
  const movingLegs = route.legs.filter((l) => l.mode !== 'connection')
  const from = movingLegs[0]?.from ?? ''
  const to = movingLegs[movingLegs.length - 1]?.to ?? ''
  const modes = movingLegs.map((l) => l.mode)

  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-surface shadow-lift">
      <div className="bg-gradient-to-br from-[#161c45] via-[#1f2860] to-[#237a6b] px-5 pb-6 pt-5">
        <Logo size={24} tone="light" />
        <p className="mt-4 text-xs font-medium uppercase tracking-wide text-white/60">
          {route.type === 'cross-origin' ? `Via ${route.hub?.name}` : 'Direct route'}
        </p>
        <div className="mt-1.5 flex items-center gap-2 text-lg font-bold text-white">
          <span>{from}</span>
          <ArrowRight className="h-4 w-4 shrink-0 text-white/60" />
          <span>{to}</span>
        </div>
      </div>

      <div className="px-5 py-4">
        <div className="flex items-center gap-2">
          {modes.map((m, i) => (
            <span key={i} className="flex items-center gap-2">
              <ModeIcon mode={m} className="h-4 w-4 text-brand-500" />
              {i < modes.length - 1 && <ArrowRight className="h-3 w-3 text-faint" />}
            </span>
          ))}
        </div>

        <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <span className="font-display text-2xl font-bold text-content">
            {formatFare(route.totalFareInr)}
          </span>
          <span className="text-sm text-muted">
            {route.totalTimeMins ? formatDuration(route.totalTimeMins) : '—'}
          </span>
        </div>

        <div className="mt-3 flex items-center gap-2">
          <ConfirmationPill status={route.confirmation} waitlistPosition={route.waitlistPosition} />
          <ReliabilityBadge score={route.reliability} />
        </div>

        {route.why && <p className="mt-3 text-xs leading-snug text-muted">{route.why}</p>}

        <p className="mt-4 border-t border-line-soft pt-3 text-[11px] font-medium text-faint">
          Planned with RouteSarthi · Peace of mind, every time.
        </p>
      </div>
    </div>
  )
}
