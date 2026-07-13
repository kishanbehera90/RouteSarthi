import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { apiFetch } from '../lib/api'

export const useJourneyStore = create(
  persist(
    (set, get) => ({
      search: { from: '', to: '', date: '', pref: 'confirmed' },
      setSearch: (patch) => set((s) => ({ search: { ...s.search, ...patch } })),

      filters: {
        acOnly: false,
        fewerTransfers: false,
        avoidLateNight: false,
        travelClass: '',
        departureWindows: [], // RedBus-style multi-select; empty = no filtering
      },
      toggleFilter: (key) =>
        set((s) => ({ filters: { ...s.filters, [key]: !s.filters[key] } })),
      setTravelClass: (travelClass) =>
        set((s) => ({ filters: { ...s.filters, travelClass } })),
      toggleDepartureWindow: (key) =>
        set((s) => {
          const cur = s.filters.departureWindows
          const next = cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key]
          return { filters: { ...s.filters, departureWindows: next } }
        }),

      // --- saved trips: backend-owned, per-user (see /api/saved-trips) ---
      savedTrips: [],
      savedTripsLoaded: false,
      loadSavedTrips: async () => {
        try {
          const data = await apiFetch('/api/saved-trips')
          set({
            savedTrips: data.trips.map((t) => ({ ...t.route, savedAt: t.savedAt })),
            savedTripsLoaded: true,
          })
        } catch {
          set({ savedTripsLoaded: true })
        }
      },
      saveTrip: async (route) => {
        set((s) =>
          s.savedTrips.find((r) => r.id === route.id) ? s : { savedTrips: [...s.savedTrips, route] }
        )
        try {
          await apiFetch('/api/saved-trips', { method: 'POST', body: { route } })
        } catch {
          // optimistic add stands even if the write failed silently; the next
          // loadSavedTrips() call will reconcile with the server's truth
        }
      },
      removeTrip: async (routeId) => {
        set((s) => ({ savedTrips: s.savedTrips.filter((r) => r.id !== routeId) }))
        try {
          await apiFetch(`/api/saved-trips/${encodeURIComponent(routeId)}`, { method: 'DELETE' })
        } catch {
          /* see saveTrip note */
        }
      },

      // --- recent searches: backend-owned, per-user (see /api/recent-searches) ---
      recentSearches: [],
      loadRecentSearches: async () => {
        try {
          const data = await apiFetch('/api/recent-searches')
          set({ recentSearches: data.searches })
        } catch {
          /* not logged in yet, or offline — leave empty */
        }
      },
      recordSearch: (search) => {
        // Optimistic prepend, deduped by (from,to) case-insensitively — mirrors
        // the backend's own upsert key so the UI never shows a near-duplicate.
        set((s) => {
          const key = (v) => v.trim().toLowerCase()
          const rest = s.recentSearches.filter(
            (r) => key(r.from) !== key(search.from) || key(r.to) !== key(search.to)
          )
          return { recentSearches: [{ ...search, searchedAt: new Date().toISOString() }, ...rest].slice(0, 8) }
        })
        apiFetch('/api/recent-searches', { method: 'POST', body: search }).catch(() => {})
      },

      // Called on explicit logout so a different user on the same browser tab
      // never sees the previous user's personalization, even for a frame.
      resetPersonalization: () =>
        set({ savedTrips: [], savedTripsLoaded: false, recentSearches: [] }),

      // --- delay model metadata (public, not per-user) — fetched once and
      // cached, used to enrich the "Predicted" chip tooltip with what data
      // the model is actually based on. ---
      delayModelInfo: null,
      delayModelInfoLoaded: false,
      loadDelayModelInfo: async () => {
        if (get().delayModelInfoLoaded) return
        try {
          const res = await fetch('/api/delay-model-info')
          const data = await res.json()
          set({ delayModelInfo: data.loaded === false ? null : data, delayModelInfoLoaded: true })
        } catch {
          set({ delayModelInfoLoaded: true })
        }
      },
    }),
    {
      name: 'routesarthi-journey',
      // Personalization is server-owned now — nothing here is safe to persist
      // across accounts, so only ephemeral UI prefs (not tied to a user) survive.
      partialize: () => ({}),
    }
  )
)
