// Custom hand-built decorative backdrop (no external/AI image dependency).
// A faint dot-grid + soft route-line wash, meant to sit behind otherwise-flat
// sand/white sections so large empty areas feel intentional, not empty.
export default function JourneyBackdrop({ className = '' }) {
  return (
    <div className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`} aria-hidden="true">
      <div
        className="absolute inset-0"
        style={{
          backgroundImage: 'radial-gradient(circle, rgba(22,28,69,0.16) 1.4px, transparent 1.8px)',
          backgroundSize: '22px 22px',
        }}
      />
      <svg
        viewBox="0 0 800 400"
        preserveAspectRatio="none"
        className="absolute inset-0 h-full w-full"
      >
        <path
          d="M-20,320 C120,260 180,360 320,300 C460,240 520,120 680,160 C760,180 800,140 840,90"
          fill="none"
          stroke="#2f9885"
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray="2 9"
          opacity="0.55"
        />
        <path
          d="M-40,80 C100,140 200,40 340,90 C480,140 540,60 700,40"
          fill="none"
          stroke="#2e3c97"
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray="2 9"
          opacity="0.45"
        />
        <circle cx="320" cy="300" r="4" fill="#2f9885" opacity="0.5" />
        <circle cx="680" cy="160" r="4" fill="#2f9885" opacity="0.5" />
        <circle cx="340" cy="90" r="4" fill="#2e3c97" opacity="0.4" />
      </svg>
    </div>
  )
}
