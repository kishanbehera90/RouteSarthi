import { Link } from 'react-router-dom'
import { ArrowRight, MapPinned } from 'lucide-react'
import ModeIcon from './ModeIcon'
import ReliabilityBadge from './ReliabilityBadge'
import ConfirmationPill from './ConfirmationPill'
import WhyThisRoute from './WhyThisRoute'
import { cn, formatDuration, formatFare } from '../lib/utils'

export default function RouteCard({ route }) {
  const modes = route.legs.filter((l) => l.mode !== 'connection').map((l) => l.mode)

  return (
    <div className="rounded-2xl border border-brand-100 bg-white p-4 shadow-sm transition hover:shadow-md sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {route.type === 'cross-origin' ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-brand-600 px-2.5 py-1 text-xs font-semibold text-white">
              <MapPinned className="h-3.5 w-3.5" />
              Via {route.hub?.name}
            </span>
          ) : (
            <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-1 text-xs font-semibold text-gray-600">
              Direct
            </span>
          )}
          <ConfirmationPill status={route.confirmation} waitlistPosition={route.waitlistPosition} />
        </div>
        <ReliabilityBadge score={route.reliability} />
      </div>

      <div className="mt-3 flex items-center gap-2 text-brand-900">
        {modes.map((m, i) => (
          <span key={i} className="flex items-center gap-1">
            <ModeIcon mode={m} className="h-4 w-4 text-brand-500" />
            {i < modes.length - 1 && <ArrowRight className="h-3.5 w-3.5 text-gray-300" />}
          </span>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="text-lg font-semibold text-brand-900">
          {route.totalTimeMins ? formatDuration(route.totalTimeMins) : '—'}
        </span>
        <span className="text-sm text-gray-500">{formatFare(route.totalFareInr)}</span>
      </div>

      <div className="mt-3">
        <WhyThisRoute text={route.why} />
      </div>

      <Link
        to={`/routes/${route.id}`}
        className={cn(
          'mt-4 inline-flex w-full items-center justify-center rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-700'
        )}
      >
        View full plan
      </Link>
    </div>
  )
}
