import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Bookmark, BookmarkCheck, ExternalLink, LifeBuoy } from 'lucide-react'
import LegTimeline from '../components/LegTimeline'
import WhyThisRoute from '../components/WhyThisRoute'
import PlanBChip from '../components/PlanBChip'
import ReliabilityBadge from '../components/ReliabilityBadge'
import { useJourneyStore } from '../store/useJourneyStore'
import { formatDuration, formatFare } from '../lib/utils'

const bookingLinks = {
  train: { label: 'Book on IRCTC', href: 'https://www.irctc.co.in' },
  bus: { label: 'Book on RedBus', href: 'https://www.redbus.in' },
  cab: { label: 'Book a cab', href: 'https://www.olacabs.com' },
}

export default function RouteDetail() {
  const { routeId } = useParams()
  const navigate = useNavigate()
  const [route, setRoute] = useState(null)

  const savedTrips = useJourneyStore((s) => s.savedTrips)
  const saveTrip = useJourneyStore((s) => s.saveTrip)
  const removeTrip = useJourneyStore((s) => s.removeTrip)

  useEffect(() => {
    fetch(`/api/routes/${routeId}`)
      .then((res) => (res.ok ? res.json() : null))
      .then(setRoute)
  }, [routeId])

  if (!route) return <p className="text-sm text-gray-400">Loading route…</p>

  const isSaved = savedTrips.some((r) => r.id === route.id)

  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
            {route.type === 'cross-origin' ? `Via ${route.hub?.name}` : 'Direct'}
          </p>
          <h1 className="font-display text-xl font-bold text-brand-900">
            {route.totalTimeMins ? formatDuration(route.totalTimeMins) : '—'} ·{' '}
            {formatFare(route.totalFareInr)}
          </h1>
        </div>
        <ReliabilityBadge score={route.reliability} />
      </div>

      <div className="mt-3">
        <WhyThisRoute text={route.why} />
      </div>

      <div className="mt-5">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
          Full itinerary
        </p>
        <LegTimeline legs={route.legs} />
      </div>

      <div className="mt-4">
        <PlanBChip text={route.planB} />
      </div>

      <div className="mt-5 space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Book each leg</p>
        {route.legs
          .filter((l) => l.mode !== 'connection')
          .map((leg) => {
            const link = bookingLinks[leg.mode]
            if (!link) return null
            return (
              <a
                key={leg.id}
                href={link.href}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between rounded-xl border border-brand-100 bg-white px-4 py-3 text-sm font-medium text-brand-700"
              >
                {leg.name}
                <span className="flex items-center gap-1 text-brand-600">
                  {link.label} <ExternalLink className="h-3.5 w-3.5" />
                </span>
              </a>
            )
          })}
      </div>

      <div className="mt-6 flex gap-2">
        <button
          type="button"
          onClick={() => (isSaved ? removeTrip(route.id) : saveTrip(route))}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-brand-100 bg-white px-4 py-3 text-sm font-semibold text-brand-700"
        >
          {isSaved ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
          {isSaved ? 'Saved' : 'Save trip'}
        </button>
        <button
          type="button"
          onClick={() => navigate(`/live/${route.id}`)}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-brand-600 px-4 py-3 text-sm font-semibold text-white"
        >
          <LifeBuoy className="h-4 w-4" />
          Start journey
        </button>
      </div>

      <button
        type="button"
        onClick={() => navigate(-1)}
        className="mt-4 block w-full text-center text-sm text-gray-400"
      >
        ← Back
      </button>
    </div>
  )
}
