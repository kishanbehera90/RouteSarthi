import { Link } from 'react-router-dom'
import { Bookmark } from 'lucide-react'
import { useJourneyStore } from '../store/useJourneyStore'
import RouteCard from '../components/RouteCard'
import EyebrowLabel from '../components/EyebrowLabel'
import ArrowButton from '../components/ArrowButton'
import PhotoEmptyState from '../components/PhotoEmptyState'
import { RouteCardSkeleton } from '../components/Skeleton'
import emptySaved from '../assets/empty-saved.webp'

function savedOnLabel(iso) {
  if (!iso) return null
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function SavedTrips() {
  const savedTrips = useJourneyStore((s) => s.savedTrips)
  const savedTripsLoaded = useJourneyStore((s) => s.savedTripsLoaded)

  if (!savedTripsLoaded) {
    return (
      <div className="mx-auto max-w-5xl">
        <EyebrowLabel>Your trips</EyebrowLabel>
        <h1 className="mt-3 font-display text-xl font-bold text-content">Saved trips</h1>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <RouteCardSkeleton key={i} />
          ))}
        </div>
      </div>
    )
  }

  if (savedTrips.length === 0) {
    return (
      <PhotoEmptyState
        image={emptySaved}
        icon={Bookmark}
        title="No saved trips yet"
        text="Save a route from its plan page to compare it later or revisit before you travel."
      >
        <ArrowButton as={Link} to="/search" variant="light">
          Plan a journey
        </ArrowButton>
      </PhotoEmptyState>
    )
  }

  return (
    <div className="mx-auto max-w-5xl">
      <EyebrowLabel>Your trips</EyebrowLabel>
      <h1 className="mt-3 font-display text-xl font-bold text-content">Saved trips</h1>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {savedTrips.map((route) => (
          <div key={route.id}>
            {/* A saved trip is a frozen snapshot — fares/reliability can go
                stale, so say when it was saved rather than presenting old
                numbers as live. */}
            {savedOnLabel(route.savedAt) && (
              <p className="mb-1.5 text-xs text-faint">Saved on {savedOnLabel(route.savedAt)}</p>
            )}
            <RouteCard route={route} />
          </div>
        ))}
      </div>
    </div>
  )
}
