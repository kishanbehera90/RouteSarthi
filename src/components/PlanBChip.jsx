import { LifeBuoy } from 'lucide-react'

export default function PlanBChip({ text }) {
  if (!text) return null
  return (
    <div className="flex items-start gap-2 rounded-lg border border-dashed border-brand-200 bg-white px-3 py-2 text-xs text-brand-700">
      <LifeBuoy className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-400" />
      <p>
        <span className="font-semibold">Plan B — </span>
        {text}
      </p>
    </div>
  )
}
