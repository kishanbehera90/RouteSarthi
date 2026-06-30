import { Link } from 'react-router-dom'
import { Bookmark } from 'lucide-react'
import { useJourneyStore } from '../store/useJourneyStore'
import RouteCard from '../components/RouteCard'
import EyebrowLabel from '../components/EyebrowLabel'
import ArrowButton from '../components/ArrowButton'
import PhotoEmptyState from '../components/PhotoEmptyState'
import emptySaved from '../assets/empty-saved.webp'

export default function SavedTrips() {
  const savedTrips = useJourneyStore((s) => s.savedTrips)

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
          <RouteCard key={route.id} route={route} />
        ))}
      </div>
    </div>
  )
}
