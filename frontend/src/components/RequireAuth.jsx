import { useEffect } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/useAuthStore'
import { useJourneyStore } from '../store/useJourneyStore'

// Wraps every page except the landing page and the auth flow (see App.jsx).
// Waits for hydrate() to resolve before deciding — a plain boolean can't tell
// "verifying a persisted token" from "definitely logged out," which either
// flashes protected content or flash-redirects a valid session.
export default function RequireAuth() {
  const status = useAuthStore((s) => s.status)
  const hydrate = useAuthStore((s) => s.hydrate)
  const loadSavedTrips = useJourneyStore((s) => s.loadSavedTrips)
  const location = useLocation()

  useEffect(() => {
    if (status === 'idle') hydrate()
  }, [status, hydrate])

  // Load personalization once a session is confirmed — RouteCard's "isSaved"
  // check and SavedTrips.jsx both depend on savedTrips already being populated.
  useEffect(() => {
    if (status === 'authenticated') loadSavedTrips()
  }, [status, loadSavedTrips])

  if (status === 'idle' || status === 'checking') {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
      </div>
    )
  }

  if (status === 'unauthenticated') {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <Outlet />
}
