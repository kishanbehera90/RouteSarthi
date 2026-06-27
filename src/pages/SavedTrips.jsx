import { Bookmark } from 'lucide-react'
import { useJourneyStore } from '../store/useJourneyStore'
import RouteCard from '../components/RouteCard'

export default function SavedTrips() {
  const savedTrips = useJourneyStore((s) => s.savedTrips)

  if (savedTrips.length === 0) {
    return (
      <div className="text-center">
        <Bookmark className="mx-auto h-10 w-10 text-brand-300" />
        <h1 className="mt-3 font-display text-lg font-bold text-brand-900">No saved trips yet</h1>
        <p className="mt-1 text-sm text-gray-500">
          Save a route from its plan page to compare it later or revisit before you travel.
        </p>
      </div>
    )
  }

  return (
    <div>
      <h1 className="font-display text-xl font-bold text-brand-900">Saved trips</h1>
      <div className="mt-4 space-y-3">
        {savedTrips.map((route) => (
          <RouteCard key={route.id} route={route} />
        ))}
      </div>
    </div>
  )
}
