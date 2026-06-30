import { useEffect, useMemo, useRef, useState } from 'react'
import { CalendarDays, ChevronLeft, ChevronRight, Info } from 'lucide-react'
import { getRiskForDate, toLocalISODate } from '../data/riskCalendar'
import { cn } from '../lib/utils'

const dotStyles = {
  low: 'bg-safe-500',
  medium: 'bg-caution-500',
  high: 'bg-risk-500',
}

const weekdays = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']
const monthFmt = new Intl.DateTimeFormat('en-IN', { month: 'long', year: 'numeric' })
const triggerFmt = new Intl.DateTimeFormat('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })
const reasonFmt = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short' })

function startOfDay(d) {
  const x = new Date(d)
  x.setHours(0, 0, 0, 0)
  return x
}

export default function JourneyDatePicker({ value, onChange, routeLabel }) {
  const today = useMemo(() => startOfDay(new Date()), [])
  const maxDate = useMemo(() => {
    const d = new Date(today)
    d.setMonth(d.getMonth() + 3)
    return d
  }, [today])

  const selected = value ? startOfDay(new Date(value + 'T00:00:00')) : null

  const [open, setOpen] = useState(false)
  const [view, setView] = useState(() => new Date(selected ?? today))
  const [hovered, setHovered] = useState(null)
  const wrapRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const onDoc = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false)
    }
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const viewYear = view.getFullYear()
  const viewMonth = view.getMonth()
  const firstWeekday = new Date(viewYear, viewMonth, 1).getDay()
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate()

  const cells = useMemo(() => {
    const out = []
    for (let i = 0; i < firstWeekday; i++) out.push(null)
    for (let day = 1; day <= daysInMonth; day++) {
      const date = startOfDay(new Date(viewYear, viewMonth, day))
      const disabled = date < today || date > maxDate
      out.push({ date, iso: toLocalISODate(date), disabled, ...getRiskForDate(date) })
    }
    return out
  }, [viewYear, viewMonth, firstWeekday, daysInMonth, today, maxDate])

  const canPrev = viewYear > today.getFullYear() || viewMonth > today.getMonth()
  const canNext =
    viewYear < maxDate.getFullYear() ||
    (viewYear === maxDate.getFullYear() && viewMonth < maxDate.getMonth())

  const stepMonth = (delta) => setView(new Date(viewYear, viewMonth + delta, 1))

  const active = hovered ?? cells.find((c) => c && c.iso === value) ?? null

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          'flex w-full items-center gap-3 rounded-2xl border bg-surface px-4 py-3 text-left transition',
          open ? 'border-brand-600 ring-2 ring-brand-600/15' : 'border-line hover:border-line'
        )}
      >
        <CalendarDays className="h-5 w-5 shrink-0 text-mist-500" />
        <span className="min-w-0 flex-1">
          <span className="block text-[11px] font-medium uppercase tracking-wide text-faint">
            Travel date
          </span>
          <span className={cn('block text-sm font-semibold', selected ? 'text-content' : 'text-faint')}>
            {selected ? triggerFmt.format(selected) : 'Select a date'}
          </span>
        </span>
        {selected && (
          <span className={cn('h-2.5 w-2.5 shrink-0 rounded-full', dotStyles[getRiskForDate(selected).level])} />
        )}
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-full z-30 mt-2 rounded-2xl border border-line bg-surface p-4 shadow-pop sm:right-auto sm:w-80">
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => stepMonth(-1)}
              disabled={!canPrev}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-brand-700 transition hover:bg-sunken disabled:opacity-30"
              aria-label="Previous month"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <p className="font-display text-sm font-bold text-content">{monthFmt.format(view)}</p>
            <button
              type="button"
              onClick={() => stepMonth(1)}
              disabled={!canNext}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-brand-700 transition hover:bg-sunken disabled:opacity-30"
              aria-label="Next month"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-3 grid grid-cols-7 gap-1 text-center">
            {weekdays.map((w) => (
              <span key={w} className="text-[10px] font-semibold uppercase tracking-wide text-faint">
                {w}
              </span>
            ))}
          </div>

          <div className="mt-1 grid grid-cols-7 gap-1">
            {cells.map((c, i) =>
              c === null ? (
                <span key={`pad-${i}`} />
              ) : (
                <button
                  key={c.iso}
                  type="button"
                  disabled={c.disabled}
                  onClick={() => {
                    onChange?.(c.iso)
                    setOpen(false)
                  }}
                  onMouseEnter={() => setHovered(c)}
                  onMouseLeave={() => setHovered(null)}
                  className={cn(
                    'relative flex aspect-square flex-col items-center justify-center rounded-lg text-sm transition',
                    c.disabled
                      ? 'cursor-not-allowed text-faint'
                      : 'text-brand-800 hover:bg-sunken',
                    c.iso === value && 'bg-primary text-white hover:bg-primary'
                  )}
                >
                  <span className={cn(c.iso === value ? 'font-bold' : 'font-medium')}>
                    {c.date.getDate()}
                  </span>
                  {!c.disabled && (
                    <span
                      className={cn(
                        'mt-0.5 h-1.5 w-1.5 rounded-full',
                        c.iso === value ? 'bg-surface/80' : dotStyles[c.level]
                      )}
                    />
                  )}
                </button>
              )
            )}
          </div>

          <div className="mt-3 flex items-center justify-between border-t border-brand-50 pt-3 text-[11px] text-faint">
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-safe-500" /> Low
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-caution-500" /> Medium
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-risk-500" /> High
            </span>
          </div>

          <div className="mt-2 flex items-start gap-1.5 rounded-xl bg-sunken px-3 py-2 text-xs text-brand-800">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-mist-500" />
            {active ? (
              <span>
                <span className="font-semibold">{reasonFmt.format(active.date)}</span> — {active.label}
              </span>
            ) : (
              <span className="text-faint">
                {routeLabel ? `${routeLabel}: ` : ''}hover a date to see the travel-risk outlook.
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
