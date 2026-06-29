import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      usersByPhone: {},

      knowsPhone: (phone) => Boolean(get().usersByPhone[phone]),

      login: (phone, name) => {
        const existing = get().usersByPhone[phone]
        const resolvedName = existing?.name ?? name
        set((s) => ({
          user: { phone, name: resolvedName },
          isAuthenticated: true,
          usersByPhone: { ...s.usersByPhone, [phone]: { name: resolvedName } },
        }))
      },

      logout: () => set({ user: null, isAuthenticated: false }),
    }),
    { name: 'routesarthi-auth' }
  )
)
