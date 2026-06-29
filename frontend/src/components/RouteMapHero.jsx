import { MapPin, Waypoints, ShieldCheck } from 'lucide-react'

const nodes = [
  { key: 'origin', label: 'Rourkela', sub: 'You are here', left: 14, top: 14, icon: MapPin },
  { key: 'hub', label: 'Ranchi', sub: 'Smarter hub', left: 60, top: 42, icon: Waypoints, highlight: true },
  { key: 'destination', label: 'Nashik', sub: 'Confirmed seat', left: 30, top: 78, icon: MapPin },
]

export default function RouteMapHero() {
  return (
    <div className="relative mx-auto aspect-[4/5] w-full max-w-lg lg:max-w-none">
      <div
        className="absolute inset-0 overflow-hidden rounded-[2rem] bg-gradient-to-br from-brand-900 via-brand-800 to-mist-600"
        style={{
          WebkitMaskImage: 'linear-gradient(to bottom, black 0%, black 62%, transparent 96%)',
          maskImage: 'linear-gradient(to bottom, black 0%, black 62%, transparent 96%)',
        }}
      >
        <div
          className="absolute inset-0 opacity-[0.15]"
          style={{
            backgroundImage:
              'radial-gradient(circle, rgba(255,255,255,0.9) 1px, transparent 1.5px)',
            backgroundSize: '18px 18px',
          }}
        />
        <svg
          viewBox="0 0 100 125"
          preserveAspectRatio="none"
          className="absolute inset-0 h-full w-full"
        >
          <path
            d="M14,17.5 C42,8 54,36 60,52.5 C66,68 38,82 30,97.5"
            fill="none"
            stroke="white"
            strokeOpacity="0.55"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeDasharray="1.2 5"
          />
        </svg>
      </div>

      {nodes.map(({ key, label, sub, left, top, icon: Icon, highlight }) => (
        <div
          key={key}
          className="absolute flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1.5"
          style={{ left: `${left}%`, top: `${top}%` }}
        >
          <span
            className={
              'flex h-10 w-10 items-center justify-center rounded-full shadow-lg ring-4 ' +
              (highlight
                ? 'bg-white text-mist-600 ring-mist-300/50'
                : 'bg-white/95 text-brand-700 ring-white/30')
            }
          >
            <Icon className="h-4.5 w-4.5" />
          </span>
          <span className="rounded-md bg-white/95 px-2 py-0.5 text-center text-[11px] font-semibold leading-tight text-brand-900 shadow-sm">
            {label}
            <span className="block text-[9px] font-medium text-gray-400">{sub}</span>
          </span>
        </div>
      ))}

      <div className="absolute right-5 top-6 flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-mist-600 shadow-lg">
        <ShieldCheck className="h-3.5 w-3.5" />
        92% connection safety
      </div>
    </div>
  )
}
