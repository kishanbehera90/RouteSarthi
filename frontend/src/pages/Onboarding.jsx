import { useNavigate } from 'react-router-dom'
import { ShieldCheck, RefreshCcw, AlertTriangle, CheckCircle2 } from 'lucide-react'
import EyebrowLabel from '../components/EyebrowLabel'
import ArrowButton from '../components/ArrowButton'
import AuthMenu from '../components/AuthMenu'
import VerticalRail from '../components/VerticalRail'
import RouteDoodle from '../components/RouteDoodle'
import RouteMapHero from '../components/RouteMapHero'
import journeyValley from '../assets/journey-valley.webp'

function PillarSection({ eyebrow, title, body, reverse, visual }) {
  return (
    <div
      className={
        'grid items-center gap-10 py-14 lg:grid-cols-2 lg:gap-16 lg:py-20 ' +
        (reverse ? 'lg:[&>*:first-child]:order-2' : '')
      }
    >
      <div>
        <EyebrowLabel>{eyebrow}</EyebrowLabel>
        <h2 className="mt-4 font-display text-2xl font-bold leading-tight text-brand-900 sm:text-3xl">
          {title}
        </h2>
        <p className="mt-3 max-w-md text-[15px] leading-relaxed text-gray-500">{body}</p>
      </div>
      <div>{visual}</div>
    </div>
  )
}

function VisualCard({ children }) {
  return (
    <div className="rounded-3xl border border-brand-900/5 bg-sand-50 p-6 shadow-sm sm:p-8">
      {children}
    </div>
  )
}

export default function Onboarding() {
  const navigate = useNavigate()

  return (
    <div className="relative overflow-x-clip bg-white">
      <VerticalRail top="RouteSarthi" bottom="Made for India" />

      <header className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6 lg:px-16">
        <span className="font-display text-lg font-bold text-brand-900">RouteSarthi</span>
        <div className="flex items-center gap-5">
          <AuthMenu />
          <ArrowButton variant="outline" onClick={() => navigate('/search')} className="hidden sm:inline-flex">
            Plan a journey
          </ArrowButton>
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl items-center gap-12 px-6 pb-16 pt-6 lg:grid-cols-2 lg:gap-10 lg:px-16 lg:pb-28 lg:pt-12">
        <div>
          <EyebrowLabel>RouteSarthi</EyebrowLabel>
          <h1 className="mt-5 font-display text-4xl font-extrabold leading-[1.08] tracking-tight text-brand-900 sm:text-5xl lg:text-6xl">
            Every journey
            <br />
            deserves peace of mind.
          </h1>
          <p className="mt-5 max-w-md text-base leading-relaxed text-gray-500">
            Not just tickets. Not just trains.
            <br />
            A complete travel companion.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-5">
            <ArrowButton variant="solid" onClick={() => navigate('/search')}>
              Plan a journey
            </ArrowButton>
            <ArrowButton variant="ghost" as="a" href="#how-it-works">
              See how it works
            </ArrowButton>
          </div>
        </div>

        <RouteMapHero />
      </section>

      <section className="relative overflow-hidden">
        <div className="relative h-[260px] sm:h-[360px] lg:h-[440px]">
          <img src={journeyValley} alt="" className="absolute inset-0 h-full w-full object-cover" />
          <div className="absolute inset-0 bg-gradient-to-t from-brand-900/90 via-brand-900/35 to-brand-900/10" />
          <div className="absolute inset-0 flex items-end">
            <div className="mx-auto w-full max-w-7xl px-6 pb-10 lg:px-16 lg:pb-16">
              <p className="max-w-2xl font-display text-2xl font-bold leading-tight text-white sm:text-3xl lg:text-4xl">
                From the smallest town to the biggest city — one calm, confident way through.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section id="how-it-works" className="mx-auto max-w-7xl px-6 lg:px-16 pt-16 lg:pt-24">
        <PillarSection
          eyebrow="Cross-origin routing"
          title="Routes through smarter hubs"
          body="If your town is poorly connected, we look beyond it — routing you via a nearby city with far better options, and showing you exactly how to get there."
          visual={
            <VisualCard>
              <div className="space-y-3">
                <div className="flex items-center justify-between rounded-xl bg-white px-4 py-3 shadow-sm">
                  <div>
                    <p className="text-sm font-semibold text-brand-900">Direct</p>
                    <p className="text-xs text-gray-400">Rourkela → Nashik</p>
                  </div>
                  <span className="rounded-full bg-risk-50 px-2.5 py-1 text-xs font-semibold text-risk-600">
                    Waitlisted 38
                  </span>
                </div>
                <div className="flex items-center justify-between rounded-xl bg-white px-4 py-3 shadow-sm ring-1 ring-mist-200">
                  <div>
                    <p className="text-sm font-semibold text-brand-900">Via Ranchi</p>
                    <p className="text-xs text-gray-400">2h bus + confirmed express</p>
                  </div>
                  <span className="rounded-full bg-safe-50 px-2.5 py-1 text-xs font-semibold text-safe-600">
                    92% Safe
                  </span>
                </div>
              </div>
            </VisualCard>
          }
        />

        <PillarSection
          reverse
          eyebrow="Delay-aware scoring"
          title="Connections you can trust"
          body="Every transfer is scored on real historical delay data — we only recommend the ones you can actually make, with the buffer to prove it."
          visual={
            <VisualCard>
              <div className="flex items-start gap-3 rounded-xl bg-white p-4 shadow-sm">
                <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-safe-600" />
                <div>
                  <p className="text-sm font-semibold text-safe-600">94% connection safety</p>
                  <p className="text-xs text-gray-400">95 min buffer at Ranchi</p>
                  <p className="mt-2 text-xs leading-relaxed text-gray-500">
                    Bus historically arrives with ~95 min to spare before your train departs — a wide safety margin.
                  </p>
                </div>
              </div>
            </VisualCard>
          }
        />

        <PillarSection
          eyebrow="The lifeline"
          title="A lifeline if it breaks"
          body="If a leg runs late mid-journey, tap “Save me!” and we re-plan the rest of your trip from where you are — in seconds, not panic."
          visual={
            <VisualCard>
              <div className="space-y-2.5">
                <div className="flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm shadow-sm">
                  <AlertTriangle className="h-4 w-4 text-risk-600" />
                  <span className="font-medium text-brand-900">Bus delayed</span>
                </div>
                <div className="flex items-center gap-2 rounded-xl bg-mist-50 px-4 py-2.5 text-sm text-mist-600 shadow-sm">
                  <RefreshCcw className="h-4 w-4" />
                  <span className="font-semibold">Re-routed from your location</span>
                </div>
                <div className="flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm shadow-sm">
                  <CheckCircle2 className="h-4 w-4 text-safe-600" />
                  <span className="font-medium text-brand-900">Still confirmed, still on time</span>
                </div>
              </div>
            </VisualCard>
          }
        />
      </section>

      <section className="relative mx-6 mb-10 overflow-hidden rounded-[2.5rem] bg-gradient-to-br from-mist-50 via-sand-50 to-white px-6 py-16 sm:mx-10 sm:px-12 lg:mx-16 lg:px-20 lg:py-20">
        <RouteDoodle className="absolute -right-6 -top-6 h-32 w-32 text-mist-300/70" />
        <RouteDoodle className="absolute -bottom-10 left-6 h-28 w-28 rotate-180 text-brand-200/60" />
        <div className="relative mx-auto max-w-xl text-center">
          <EyebrowLabel align="center">Ready when you are</EyebrowLabel>
          <h2 className="mt-4 font-display text-3xl font-bold text-brand-900 sm:text-4xl">
            Where to, today?
          </h2>
          <p className="mt-3 text-sm text-gray-500">
            Tell us where you're starting — we'll find the way, even if it isn't direct.
          </p>
          <div className="mt-7 flex justify-center">
            <ArrowButton variant="solid" onClick={() => navigate('/search')}>
              Plan a journey
            </ArrowButton>
          </div>
        </div>
      </section>
    </div>
  )
}
