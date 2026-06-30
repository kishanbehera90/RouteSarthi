import { lazy, Suspense, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Bookmark, BookmarkCheck, ExternalLink, LifeBuoy, Share2 } from 'lucide-react'
import LegTimeline from '../components/LegTimeline'
import { Skeleton } from '../components/Skeleton'
import WhyThisRoute from '../components/WhyThisRoute'
import PlanBChip from '../components/PlanBChip'
import ReliabilityGauge from '../components/ReliabilityGauge'
import EyebrowLabel from '../components/EyebrowLabel'
import BackLink from '../components/BackLink'
import ShareModal from '../components/ShareModal'
import { RouteDetailSkeleton } from '../components/Skeleton'
import { useJourneyStore } from '../store/useJourneyStore'
import { useToastStore } from '../store/useToastStore'
import { formatDuration, formatFare } from '../lib/utils'

const RouteMap = lazy(() => import('../components/RouteMap'))

const bookingLinks = {
  train: { label: 'Book on IRCTC', href: 'https://www.irctc.co.in' },
  bus: { label: 'Book on RedBus', href: 'https://www.redbus.in' },
  cab: { label: 'Book a cab', href: 'https://www.olacabs.com' },
}

// The three real inputs behind the single reliability number.
function buildBreakdown(route) {
  const moving = route.legs.filter((l) => l.mode !== 'connection' && l.delayProfile)
  const conns = route.legs.filter(
    (l) => l.mode === 'connection' && typeof l.connectionSafetyPct === 'number'
  )
  const avg = (arr, sel) => Math.round(arr.reduce((a, x) => a + sel(x), 0) / arr.length)
  const items = []
  if (route.confirmationPct != null) items.push({ label: 'Confirmation odds', value: route.confirmationPct })
  if (moving.length) items.push({ label: 'On-time reliability', value: avg(moving, (l) => l.delayProfile.onTimePct) })
  if (conns.length) items.push({ label: 'Connection safety', value: avg(conns, (l) => l.connectionSafetyPct) })
  return items
}

export default function RouteDetail() {
  const { routeId } = useParams()
  const navigate = useNavigate()
  const [route, setRoute] = useState(null)
  const [shareOpen, setShareOpen] = useState(false)

  const savedTrips = useJourneyStore((s) => s.savedTrips)
  const saveTrip = useJourneyStore((s) => s.saveTrip)
  const removeTrip = useJourneyStore((s) => s.removeTrip)
  const toast = useToastStore((s) => s.toast)

  useEffect(() => {
    fetch(`/api/routes/${routeId}`)
      .then((res) => (res.ok ? res.json() : null))
      .then(setRoute)
  }, [routeId])

  if (!route) return <RouteDetailSkeleton />

  const isSaved = savedTrips.some((r) => r.id === route.id)

  const handleSaveToggle = () => {
    if (isSaved) {
      removeTrip(route.id)
      toast({ message: 'Removed from saved trips', tone: 'info' })
    } else {
      saveTrip(route)
      toast({ message: 'Trip saved — find it under Saved', tone: 'success' })
    }
  }

  const summaryCard = (
    <div className="rounded-2xl border border-line bg-surface p-5 shadow-lift">
      <EyebrowLabel>{route.type === 'cross-origin' ? `Via ${route.hub?.name}` : 'Direct'}</EyebrowLabel>

      <div className="mt-4 flex justify-center">
        <ReliabilityGauge score={route.reliability} showLabel={false} breakdown={buildBreakdown(route)} />
      </div>

      <div className="mt-4 flex items-baseline justify-center gap-3 border-t border-brand-50 pt-4">
        <span className="font-display text-2xl font-bold text-content">
          {formatFare(route.totalFareInr)}
        </span>
        <span className="text-sm text-muted">
          {route.totalTimeMins ? formatDuration(route.totalTimeMins) : '—'}
        </span>
      </div>

      <div className="mt-5 flex flex-col gap-2">
        <button
          type="button"
          onClick={() => navigate(`/live/${route.id}`)}
          className="flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-white transition hover:bg-primary-hover"
        >
          <LifeBuoy className="h-4 w-4" />
          Start journey
        </button>
        <button
          type="button"
          onClick={handleSaveToggle}
          className="flex items-center justify-center gap-2 rounded-xl border border-line bg-surface px-4 py-3 text-sm font-semibold text-brand-700 transition hover:border-line"
        >
          {isSaved ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
          {isSaved ? 'Saved' : 'Save trip'}
        </button>
        <button
          type="button"
          onClick={() => setShareOpen(true)}
          className="flex items-center justify-center gap-2 rounded-xl border border-line bg-surface px-4 py-3 text-sm font-semibold text-brand-700 transition hover:border-line"
        >
          <Share2 className="h-4 w-4" />
          Share journey
        </button>
      </div>
    </div>
  )

  return (
    <div className="mx-auto max-w-5xl">
      <BackLink>Back to results</BackLink>

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <div className="lg:order-1">
          <div className="lg:hidden">{summaryCard}</div>

          <div className="mt-5 lg:mt-0">
            <WhyThisRoute text={route.why} />
          </div>

          <div className="mt-5">
            <Suspense fallback={<Skeleton className="h-[320px] w-full rounded-2xl" />}>
              <RouteMap legs={route.legs} />
            </Suspense>
          </div>

          <div className="mt-5">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-faint">
              Full itinerary
            </p>
            <LegTimeline legs={route.legs} />
          </div>

          <div className="mt-4">
            <PlanBChip text={route.planB} />
          </div>

          <div className="mt-5 space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-faint">Book each leg</p>
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
                    className="flex items-center justify-between rounded-xl border border-line bg-surface px-4 py-3 text-sm font-medium text-brand-700"
                  >
                    {leg.name}
                    <span className="flex items-center gap-1 text-mist-600">
                      {link.label} <ExternalLink className="h-3.5 w-3.5" />
                    </span>
                  </a>
                )
              })}
          </div>
        </div>

        <div className="hidden lg:order-2 lg:block">
          <div className="sticky top-20">{summaryCard}</div>
        </div>
      </div>

      <ShareModal route={route} open={shareOpen} onClose={() => setShareOpen(false)} />
    </div>
  )
}
