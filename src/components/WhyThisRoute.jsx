import { Sparkles } from 'lucide-react'

export default function WhyThisRoute({ text }) {
  if (!text) return null
  return (
    <div className="flex gap-2 rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-800">
      <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />
      <p className="leading-snug">{text}</p>
    </div>
  )
}
