import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useJourneyStore = create(
  persist(
    (set) => ({
      search: { from: 'Rourkela', to: 'Nashik', date: '', pref: 'confirmed' },
      setSearch: (patch) => set((s) => ({ search: { ...s.search, ...patch } })),

      filters: { acOnly: false, fewerTransfers: false, avoidLateNight: false, travelClass: '' },
      toggleFilter: (key) =>
        set((s) => ({ filters: { ...s.filters, [key]: !s.filters[key] } })),
      setTravelClass: (travelClass) =>
        set((s) => ({ filters: { ...s.filters, travelClass } })),

      savedTrips: [],
      saveTrip: (route) =>
        set((s) =>
          s.savedTrips.find((r) => r.id === route.id)
            ? s
            : { savedTrips: [...s.savedTrips, route] }
        ),
      removeTrip: (routeId) =>
        set((s) => ({ savedTrips: s.savedTrips.filter((r) => r.id !== routeId) })),
    }),
    {
      name: 'routesarthi-journey',
      partialize: (s) => ({ savedTrips: s.savedTrips }),
    }
  )
)
