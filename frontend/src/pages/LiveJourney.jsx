import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  LifeBuoy,
  CheckCircle2,
  AlertTriangle,
  RefreshCcw,
  Play,
  Pause,
  RotateCcw,
  Navigation,
  Circle,
} from 'lucide-react'
import ModeIcon from '../components/ModeIcon'
import EyebrowLabel from '../components/EyebrowLabel'
import ArrowButton from '../components/ArrowButton'
import BackLink from '../components/BackLink'
import PhotoEmptyState from '../components/PhotoEmptyState'
import { Skeleton, LiveJourneySkeleton } from '../components/Skeleton'
import { useToastStore } from '../store/useToastStore'
import emptyLive from '../assets/empty-live.webp'

const RouteMap = lazy(() => import('../components/RouteMap'))

const TOTAL_MS = 24000
const MODE_LABEL = { train: 'train', bus: 'bus', cab: 'shared cab' }

const STATUS = {
  upcoming: { label: 'Upcoming', cls: 'text-faint', Icon: Circle },
  boarding: { label: 'Boarding', cls: 'text-mist-600', Icon: Circle },
  moving: { label: 'On the way', cls: 'text-brand-600', Icon: Navigation },
  delayed: { label: 'Delayed', cls: 'text-risk-600', Icon: AlertTriangle },
  arrived: { label: 'Arrived', cls: 'text-safe-600', Icon: CheckCircle2 },
}

export default function LiveJourney() {
  const { routeId } = useParams()
  const toast = useToastStore((s) => s.toast)

  const [route, setRoute] = useState(null)
  const [progress, setProgress] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [delayMins, setDelayMins] = useState(0)
  const [planB, setPlanB] = useState(false)
  const [arrived, setArrived] = useState(false)
  const firedRef = useRef(new Set())

  useEffect(() => {
    if (!routeId) return
    fetch(`/api/routes/${routeId}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((r) => {
        setRoute(r)
        if (r) setPlaying(true)
      })
  }, [routeId])

  const movingLegs = route ? route.legs.filter((l) => l.mode !== 'connection') : []
  const n = movingLegs.length
  const dest = movingLegs[n - 1]?.to
  const firstMode = movingLegs[0]?.mode

  const triggerPlanB = (source) => {
    setPlanB((already) => {
      if (already) return already
      setDelayMins(0)
      toast({
        message:
          source === 'auto'
            ? 'Delay crossed the safe limit — Plan B auto-activated.'
            : 'Re-planning from your location — Plan B is now active.',
        tone: 'success',
      })
      return true
    })
  }

  // Advance the simulation clock.
  useEffect(() => {
    if (!playing || arrived) return
    let raf
    let last = performance.now()
    const tick = (now) => {
      const dt = now - last
      last = now
      setProgress((p) => Math.min(p + dt / TOTAL_MS, 1))
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [playing, arrived])

  // Fire scripted events as progress crosses their thresholds.
  useEffect(() => {
    if (!route || n === 0) return
    const events = []
    events.push({
      id: 'start',
      at: 0.02,
      run: () => toast({ message: `Journey started — boarding your ${MODE_LABEL[firstMode] ?? 'ride'}.`, tone: 'info' }),
    })
    if (n > 1) {
      const hub = route.hub?.name ?? 'the hub'
      events.push({
        id: 'delay1',
        at: 0.14,
        run: () => {
          setDelayMins(15)
          toast({ message: `Your ${MODE_LABEL[firstMode] ?? 'ride'} is ~15 min late — connection still safe (80 min buffer).`, tone: 'warning' })
        },
      })
      events.push({
        id: 'delay2',
        at: 0.26,
        run: () => {
          if (planB) return
          setDelayMins(55)
          toast({ message: `Delay now ~55 min — your connection at ${hub} is at risk.`, tone: 'danger' })
        },
      })
      events.push({ id: 'planb', at: 1 / n - 0.015, run: () => triggerPlanB('auto') })
    } else {
      events.push({
        id: 'delay1',
        at: 0.32,
        run: () => {
          setDelayMins(20)
          toast({ message: 'Running ~20 min late — no connection to miss, still fine.', tone: 'warning' })
        },
      })
      events.push({
        id: 'recover',
        at: 0.62,
        run: () => {
          setDelayMins(0)
          toast({ message: 'Back on time — delay recovered.', tone: 'success' })
        },
      })
    }
    events.push({
      id: 'arrive',
      at: 0.995,
      run: () => {
        toast({ message: `Arrived at ${dest} — you made it.`, tone: 'success' })
        setProgress(1)
        setArrived(true)
        setPlaying(false)
      },
    })

    for (const ev of events) {
      if (progress >= ev.at && !firedRef.current.has(ev.id)) {
        firedRef.current.add(ev.id)
        ev.run()
      }
    }
  }, [progress, route, n, firstMode, dest, planB, toast]) // eslint-disable-line react-hooks/exhaustive-deps

  const restart = () => {
    firedRef.current = new Set()
    setProgress(0)
    setDelayMins(0)
    setPlanB(false)
    setArrived(false)
    setPlaying(true)
  }

  const activeIndex = Math.min(n - 1, Math.floor(progress * n))

  const legStatus = (i) => {
    const a = i / n
    const b = (i + 1) / n
    if (progress >= b) return 'arrived'
    if (progress >= a) {
      if (delayMins > 0 && !planB && i === activeIndex) return 'delayed'
      const local = (progress - a) / (b - a)
      return local < 0.18 ? 'boarding' : 'moving'
    }
    return 'upcoming'
  }

  if (!routeId) {
    return (
      <PhotoEmptyState
        image={emptyLive}
        icon={LifeBuoy}
        title="No active journey"
        text="Start a journey from any route's plan page — we'll monitor every leg here and step in if something breaks."
      >
        <ArrowButton as={Link} to="/search" variant="light">
          Plan a journey
        </ArrowButton>
      </PhotoEmptyState>
    )
  }

  if (!route) return <LiveJourneySkeleton />

  const pct = Math.round(progress * 100)

  return (
    <div className="mx-auto max-w-2xl">
      <BackLink to={`/routes/${routeId}`}>Back to route</BackLink>
      <div className="flex items-start justify-between gap-3">
        <div>
          <EyebrowLabel>Lifeline</EyebrowLabel>
          <h1 className="mt-3 font-display text-xl font-bold text-content">
            {arrived ? 'Journey complete' : 'Journey in progress'}
          </h1>
          <p className="mt-1 text-sm text-muted">
            {route.type === 'cross-origin' ? `Via ${route.hub?.name}` : 'Direct'} · live monitoring active
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          {!arrived && (
            <button
              type="button"
              onClick={() => setPlaying((p) => !p)}
              aria-label={playing ? 'Pause' : 'Resume'}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-line bg-surface text-muted transition hover:text-content"
            >
              {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            </button>
          )}
          <button
            type="button"
            onClick={restart}
            aria-label="Restart simulation"
            className="flex h-9 w-9 items-center justify-center rounded-full border border-line bg-surface text-muted transition hover:text-content"
          >
            <RotateCcw className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="mt-5">
        <Suspense fallback={<Skeleton className="h-[320px] w-full rounded-2xl" />}>
          <RouteMap legs={route.legs} live liveProgress={progress} />
        </Suspense>
      </div>

      {/* Progress + ETA */}
      <div className="mt-4 rounded-2xl border border-line bg-surface p-4 shadow-card">
        <div className="flex items-center justify-between text-sm">
          <span className="font-semibold text-content">{arrived ? 'Arrived safely' : `${pct}% of the way`}</span>
          {delayMins > 0 && !planB ? (
            <span className="flex items-center gap-1 text-xs font-semibold text-risk-600">
              <AlertTriangle className="h-3.5 w-3.5" /> ETA +{delayMins} min
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs font-semibold text-safe-600">
              <CheckCircle2 className="h-3.5 w-3.5" /> {planB ? 'Recovered via Plan B' : 'On schedule'}
            </span>
          )}
        </div>
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-line">
          <div
            className="h-full rounded-full bg-mist-500 transition-[width] duration-150 ease-linear"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Legs */}
      <div className="mt-4 space-y-2">
        {movingLegs.map((leg, i) => {
          const s = STATUS[legStatus(i)]
          const Icon = s.Icon
          return (
            <div key={leg.id} className="flex items-center gap-3 rounded-xl border border-line bg-surface p-3">
              <ModeIcon mode={leg.mode} className="h-4 w-4 shrink-0 text-brand-500" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-content">{leg.name}</p>
                <p className="text-xs text-faint">
                  {leg.from} → {leg.to}
                </p>
              </div>
              <span className={`flex items-center gap-1 text-xs font-semibold ${s.cls}`}>
                <Icon className="h-3.5 w-3.5" /> {s.label}
              </span>
            </div>
          )
        })}
      </div>

      {/* Plan B panel */}
      {planB && (
        <div className="mt-4 rounded-2xl border border-safe-100 bg-safe-50 p-4">
          <div className="flex items-center gap-2 text-safe-600">
            <RefreshCcw className="h-4 w-4" />
            <p className="text-sm font-semibold">Re-routed — Plan B active</p>
          </div>
          <p className="mt-2 text-sm text-muted">{route.planB}</p>
        </div>
      )}

      {/* Save me! */}
      {!planB && !arrived && (
        <div className="mt-4 rounded-2xl border border-dashed border-line bg-surface p-4 text-center">
          <p className="text-sm text-muted">
            Worried about a delay or a missed connection? Tap below and we'll re-plan the rest of your journey from your current location.
          </p>
          <button
            type="button"
            onClick={() => triggerPlanB('manual')}
            className="mt-3 inline-flex items-center gap-2 rounded-xl bg-risk-500 px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90"
          >
            <LifeBuoy className="h-4 w-4" />
            Save me!
          </button>
        </div>
      )}

      {arrived && (
        <div className="mt-4 flex items-center justify-center gap-2 rounded-2xl border border-safe-100 bg-safe-50 p-4 text-safe-600">
          <CheckCircle2 className="h-5 w-5" />
          <p className="text-sm font-semibold">You reached {dest} — confirmed all the way.</p>
        </div>
      )}
    </div>
  )
}
