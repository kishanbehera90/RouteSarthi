import { cn } from '../lib/utils'

// The mark encodes RouteSarthi's core idea: a route arching from an origin,
// up through a smarter nearby hub (the emphasised teal node), to the
// destination. tone="light" recolors it for dark backgrounds.
export function LogoMark({ size = 28, tone = 'dark', className = '' }) {
  const onDark = tone === 'light'
  const path = onDark ? 'rgba(255,255,255,0.92)' : 'var(--color-brand-700)'
  const origin = onDark ? 'rgba(255,255,255,0.7)' : 'var(--color-brand-400)'
  const dest = onDark ? '#ffffff' : 'var(--color-brand-900)'
  const hub = onDark ? 'var(--color-mist-300)' : 'var(--color-mist-500)'
  const halo = onDark ? 'rgba(122,204,189,0.28)' : 'rgba(47,152,133,0.18)'

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      role="img"
      aria-label="RouteSarthi"
    >
      <circle cx="16.5" cy="7" r="6" fill={halo} />
      <path
        d="M6 25 C 10 18 13 9 16.5 7 C 20 5 22.5 15 26 22"
        stroke={path}
        strokeWidth="2.6"
        strokeLinecap="round"
        fill="none"
      />
      <circle cx="6" cy="25" r="2.6" fill={origin} />
      <circle cx="26" cy="22" r="2.6" fill={dest} />
      <circle cx="16.5" cy="7" r="3.4" fill={hub} />
      <circle cx="16.5" cy="7" r="1.3" fill={onDark ? 'var(--color-brand-900)' : '#ffffff'} />
    </svg>
  )
}

export default function Logo({ size = 28, withWordmark = true, tone = 'dark', className = '' }) {
  const onDark = tone === 'light'
  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <LogoMark size={size} tone={tone} />
      {withWordmark && (
        <span className="font-display text-lg font-bold leading-none tracking-tight">
          <span className={onDark ? 'text-white' : 'text-content'}>Route</span>
          <span className={onDark ? 'text-mist-200' : 'text-brand-500'}>Sarthi</span>
        </span>
      )}
    </span>
  )
}
