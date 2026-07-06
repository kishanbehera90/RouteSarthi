import { Route } from 'lucide-react'

// Quiet "why we chose this" footnote — a route mark + muted text, no boxed
// callout. Intentionally understated so it doesn't compete with the card.
export default function WhyThisRoute({ text }) {
  if (!text) return null
  return (
    <div className="flex gap-1.5 text-xs leading-relaxed text-muted">
      <Route className="mt-0.5 h-3.5 w-3.5 shrink-0 text-mist-500" />
      <p>{text}</p>
    </div>
  )
}
