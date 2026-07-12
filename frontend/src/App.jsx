import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import RequireAuth from './components/RequireAuth'
import Toaster from './components/Toaster'
import Onboarding from './pages/Onboarding'
import Auth from './pages/Auth'
import ResetPassword from './pages/ResetPassword'
import Search from './pages/Search'
import Results from './pages/Results'
import Compare from './pages/Compare'
import HubPicker from './pages/HubPicker'
import RouteDetail from './pages/RouteDetail'
import LiveJourney from './pages/LiveJourney'
import SavedTrips from './pages/SavedTrips'

export default function App() {
  return (
    <>
    <Routes>
      {/* Public: the landing page and the auth flow. Everything else requires login. */}
      <Route path="/" element={<Onboarding />} />
      <Route path="/login" element={<Auth />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route path="/search" element={<Search />} />
          <Route path="/results" element={<Results />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/hub-picker" element={<HubPicker />} />
          <Route path="/routes/:routeId" element={<RouteDetail />} />
          <Route path="/live" element={<LiveJourney />} />
          <Route path="/live/:routeId" element={<LiveJourney />} />
          <Route path="/saved" element={<SavedTrips />} />
        </Route>
      </Route>
    </Routes>
    <Toaster />
    </>
  )
}
