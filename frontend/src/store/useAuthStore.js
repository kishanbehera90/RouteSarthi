import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// Deliberately self-contained: does NOT import useJourneyStore or lib/api.js,
// so there's no risk of a store-to-store circular import. signup/login/etc
// talk to the backend directly (no token exists yet for most of these calls
// anyway); other stores import lib/api.js, which imports THIS store to read
// the token — that's the only cross-module edge, and it only goes one way.
async function authPost(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || 'Something went wrong')
  return data
}

export const useAuthStore = create(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      // 'idle' | 'checking' | 'authenticated' | 'unauthenticated' — a boolean
      // can't distinguish "verifying a token" from "logged out," which either
      // flashes protected content or flash-redirects a valid session.
      status: 'idle',
      error: null,

      // Called once on app boot. If a token was persisted, confirm it's still
      // valid (and refresh the user record) before treating the session as real.
      hydrate: async () => {
        const token = get().token
        if (!token) {
          set({ status: 'unauthenticated' })
          return
        }
        set({ status: 'checking' })
        try {
          const res = await fetch('/api/auth/me', { headers: { Authorization: `Bearer ${token}` } })
          if (!res.ok) throw new Error()
          const data = await res.json()
          set({ user: data.user, status: 'authenticated' })
        } catch {
          set({ token: null, user: null, status: 'unauthenticated' })
        }
      },

      signup: async ({ email, password, name }) => {
        set({ error: null })
        try {
          const data = await authPost('/api/auth/signup', { email, password, name })
          set({ token: data.token, user: data.user, status: 'authenticated' })
          return true
        } catch (e) {
          set({ error: e.message })
          return false
        }
      },

      login: async ({ email, password }) => {
        set({ error: null })
        try {
          const data = await authPost('/api/auth/login', { email, password })
          set({ token: data.token, user: data.user, status: 'authenticated' })
          return true
        } catch (e) {
          set({ error: e.message })
          return false
        }
      },

      forgotPassword: async (email) => {
        set({ error: null })
        try {
          await authPost('/api/auth/forgot-password', { email })
          return true
        } catch (e) {
          set({ error: e.message })
          return false
        }
      },

      resetPassword: async ({ token, newPassword }) => {
        set({ error: null })
        try {
          await authPost('/api/auth/reset-password', { token, new_password: newPassword })
          return true
        } catch (e) {
          set({ error: e.message })
          return false
        }
      },

      clearError: () => set({ error: null }),

      // Clears only THIS store's state. The explicit "Log out" button (see
      // AuthMenu.jsx) additionally clears useJourneyStore's personalized data
      // and hard-navigates — that cross-store reset belongs at the UI layer,
      // not here, to avoid a store-to-store circular import.
      logout: () => set({ token: null, user: null, status: 'unauthenticated', error: null }),
    }),
    {
      name: 'routesarthi-auth',
      partialize: (s) => ({ token: s.token, user: s.user }),
    }
  )
)
