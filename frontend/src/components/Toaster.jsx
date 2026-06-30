import { AnimatePresence, motion } from 'motion/react'
import { CheckCircle2, Info, AlertTriangle, AlertCircle, X } from 'lucide-react'
import { useToastStore } from '../store/useToastStore'
import { cn } from '../lib/utils'

const toneStyles = {
  success: { icon: CheckCircle2, accent: 'text-safe-500' },
  info: { icon: Info, accent: 'text-mist-500' },
  warning: { icon: AlertTriangle, accent: 'text-caution-500' },
  danger: { icon: AlertCircle, accent: 'text-risk-500' },
}

export default function Toaster() {
  const toasts = useToastStore((s) => s.toasts)
  const dismiss = useToastStore((s) => s.dismiss)

  return (
    <div
      className="pointer-events-none fixed inset-x-0 bottom-20 z-50 flex flex-col items-center gap-2 px-4 sm:bottom-6"
      aria-live="polite"
    >
      <AnimatePresence initial={false}>
        {toasts.map((t) => {
          const { icon: Icon, accent } = toneStyles[t.tone] ?? toneStyles.info
          return (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, y: 24, scale: 0.92 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.92, transition: { duration: 0.15 } }}
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              className="pointer-events-auto flex items-center gap-2.5 rounded-2xl border border-line bg-surface px-4 py-3 shadow-pop"
            >
              <Icon className={cn('h-5 w-5 shrink-0', accent)} />
              <span className="text-sm font-medium text-content">{t.message}</span>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss"
                className="ml-1 text-faint transition hover:text-brand-700"
              >
                <X className="h-4 w-4" />
              </button>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
