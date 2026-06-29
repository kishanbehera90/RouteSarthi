import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Toaster from './components/Toaster'
import Onboarding from './pages/Onboarding'
import Login from './pages/Login'
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
      <Route path="/" element={<Onboarding />} />
      <Route path="/login" element={<Login />} />
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
    </Routes>
    <Toaster />
    </>
  )
}
