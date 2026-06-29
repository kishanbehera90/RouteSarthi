export default function RouteDoodle({ className }) {
  return (
    <svg
      viewBox="0 0 160 160"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M6 18c24 0 24 30 48 30s24-26 48-22 30 36 54 30"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeDasharray="2 9"
      />
      <circle cx="6" cy="18" r="4" fill="currentColor" />
      <path
        d="M152 56v-12a4 4 0 0 1 4-4h0a4 4 0 0 1 4 4v22l8-6"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        transform="translate(-12 -6)"
      />
    </svg>
  )
}
