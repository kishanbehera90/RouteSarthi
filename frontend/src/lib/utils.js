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

// RedBus-style "preferred departure time" buckets. Four windows, full 24h
// coverage, no gaps — matches the "4am-10am" / "after 10pm" anchors from the
// product ask. `test` takes an hour (0-23); Late Night wraps midnight.
export const DEPARTURE_WINDOWS = [
  { key: 'early-morning', label: 'Early morning', hint: '4 AM – 10 AM', test: (h) => h >= 4 && h < 10 },
  { key: 'afternoon', label: 'Afternoon', hint: '10 AM – 5 PM', test: (h) => h >= 10 && h < 17 },
  { key: 'evening', label: 'Evening', hint: '5 PM – 10 PM', test: (h) => h >= 17 && h < 22 },
  { key: 'late-night', label: 'Late night', hint: '10 PM – 4 AM', test: (h) => h >= 22 || h < 4 },
]

// A departing "HH:MM" string matches if it falls in ANY of the selected
// windows. An empty selection means "no filter" — the caller should skip
// calling this entirely in that case (see Results.jsx).
export function matchesDepartureWindow(timeStr, selectedKeys) {
  if (!timeStr || !selectedKeys.length) return true
  const hour = Number(timeStr.slice(0, 2))
  if (Number.isNaN(hour)) return true
  return DEPARTURE_WINDOWS.some((w) => selectedKeys.includes(w.key) && w.test(hour))
}
