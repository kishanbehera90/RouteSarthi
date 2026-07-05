import { Link } from 'react-router-dom'
import { motion } from 'motion/react'
import { ArrowRight, MapPinned, TrainFront } from 'lucide-react'
import ModeIcon from './ModeIcon'
import ReliabilityBadge from './ReliabilityBadge'
import ConfirmationPill from './ConfirmationPill'
import WhyThisRoute from './WhyThisRoute'
import ConfirmationProbability from './ConfirmationProbability'
import ClassFares from './ClassFares'
import ArrowButton from './ArrowButton'
import { formatDuration, formatFare } from '../lib/utils'

export default function RouteCard({ route, index = 0, tag = null }) {
  const modes = route.legs.filter((l) => l.mode !== 'connection').map((l) => l.mode)
  // The train the traveller actually rides most of the way.
  const main =
    route.mainTrain ??
    (() => {
      const t = route.legs.filter((l) => l.mode === 'train')
      return t.length ? { name: t.sort((a, b) => (b.durationMins || 0) - (a.durationMins || 0))[0].name } : null
    })()

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4 }}
      transition={{ type: 'spring', stiffness: 300, damping: 24, delay: index * 0.07 }}
      className="rounded-2xl border border-line bg-surface p-4 shadow-card transition-shadow hover:shadow-lift sm:p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {route.type === 'cross-origin' ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-primary px-2.5 py-1 text-xs font-semibold text-white">
              <MapPinned className="h-3.5 w-3.5" />
              Via {route.hub?.name}
            </span>
          ) : (
            <span className="inline-flex items-center rounded-full bg-sunken px-2.5 py-1 text-xs font-semibold text-muted">
              Direct
            </span>
          )}
          <ConfirmationPill status={route.confirmation} waitlistPosition={route.waitlistPosition} />
          {tag && (
            <span className="inline-flex items-center rounded-full bg-mist-50 px-2 py-0.5 text-xs font-semibold text-mist-600">
              {tag}
            </span>
          )}
        </div>
        <ReliabilityBadge score={route.reliability} />
      </div>

      <div className="mt-3 flex items-center gap-2 text-content">
        {modes.map((m, i) => (
          <span key={i} className="flex items-center gap-1">
            <ModeIcon mode={m} className="h-4 w-4 text-brand-500" />
            {i < modes.length - 1 && <ArrowRight className="h-3.5 w-3.5 text-faint" />}
          </span>
        ))}
      </div>

      {route.roadOnly ? (
        <div className="mt-2 flex items-center gap-1.5 text-sm font-medium text-content">
          <ModeIcon mode="cab" className="h-4 w-4 shrink-0 text-brand-500" />
          <span>Direct by road (cab or bus)</span>
        </div>
      ) : (
        main && (
          <div className="mt-2 flex items-center gap-1.5 text-sm font-medium text-content">
            <TrainFront className="h-4 w-4 shrink-0 text-brand-500" />
            <span className="truncate">{main.name}</span>
            {route.transfers > 0 && <span className="shrink-0 text-xs text-faint">+1 change</span>}
          </div>
        )
      )}
      {main?.depart && (
        <p className="mt-0.5 text-xs text-faint">
          {main.from} {main.depart} → {main.to} {main.arrive}
          {main.days && <span className="text-mist-600"> · {main.days}</span>}
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="text-lg font-semibold text-content">
          {route.totalTimeMins ? formatDuration(route.totalTimeMins) : '—'}
        </span>
        <span className="text-sm text-muted">from {formatFare(route.totalFareInr)}</span>
      </div>

      {main?.classFares?.length > 1 && <ClassFares fares={main.classFares} className="mt-2" />}

      {route.clearProbabilityPct != null && (
        <ConfirmationProbability
          waitlistPosition={route.waitlistPosition}
          probability={route.clearProbabilityPct}
          className="mt-3"
        />
      )}

      <div className="mt-3">
        <WhyThisRoute text={route.why} />
      </div>

      <ArrowButton as={Link} to={`/routes/${route.id}`} variant="solid" className="mt-4 w-full justify-center">
        View full plan
      </ArrowButton>
    </motion.div>
  )
}
