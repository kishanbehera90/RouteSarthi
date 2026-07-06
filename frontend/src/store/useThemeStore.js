import { create } from 'zustand'

const STORAGE_KEY = 'routesarthi-theme'

function readInitial() {
  if (typeof window === 'undefined') return 'light'
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'light' || saved === 'dark') return saved
  // Default to LIGHT regardless of the OS setting — light is our intended
  // default look. (Dark only if the user has explicitly toggled to it.)
  return 'light'
}

function apply(theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark')
}

export const useThemeStore = create((set, get) => ({
  theme: readInitial(),
  toggle: () => {
    const next = get().theme === 'dark' ? 'light' : 'dark'
    localStorage.setItem(STORAGE_KEY, next)
    apply(next)
    set({ theme: next })
  },
}))
