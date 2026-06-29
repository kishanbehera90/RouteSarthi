export default function VerticalRail({ top, bottom, tone = 'dark' }) {
  const textColor = tone === 'dark' ? 'text-brand-900/60' : 'text-white/60'
  const lineColor = tone === 'dark' ? 'bg-brand-900/20' : 'bg-white/25'

  return (
    <div className="pointer-events-none absolute inset-y-0 left-6 hidden flex-col items-center py-12 lg:flex">
      <span className={`h-16 w-px ${lineColor}`} />
      <span
        className={`mt-6 origin-top whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.3em] ${textColor}`}
        style={{ writingMode: 'vertical-rl' }}
      >
        {top}
      </span>
      <span className="flex-1" />
      <span
        className={`mb-6 origin-bottom whitespace-nowrap text-[11px] font-medium uppercase tracking-[0.3em] ${textColor}`}
        style={{ writingMode: 'vertical-rl' }}
      >
        {bottom}
      </span>
      <span className={`h-16 w-px ${lineColor}`} />
    </div>
  )
}
