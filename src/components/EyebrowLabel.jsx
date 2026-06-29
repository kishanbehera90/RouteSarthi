export default function EyebrowLabel({ children, tone = 'light', align = 'left' }) {
  return (
    <p
      className={
        'flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] ' +
        (tone === 'light' ? 'text-mist-500' : 'text-white/70') +
        (align === 'center' ? ' justify-center' : '')
      }
    >
      <span className="h-px w-5 bg-current opacity-60" />
      {children}
    </p>
  )
}
