import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs) {
  return twMerge(clsx(...inputs))
}

export function formatDuration(mins) {
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return `${h}h ${m}min`
}

export function formatFare(inr) {
  return `₹${inr.toLocaleString('en-IN')}`
}

// Arrival times look like "05:10+2" (HH:MM, optionally +N days). Late night
// is defined as arriving between 11pm and 5am, when stations/stands are
// hardest to navigate safely.
export function isLateNightTime(timeStr) {
  if (!timeStr) return false
  const hour = Number(timeStr.slice(0, 2))
  return hour >= 23 || hour < 5
}
