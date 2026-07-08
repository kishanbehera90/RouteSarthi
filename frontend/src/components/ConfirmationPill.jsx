import { cn } from '../lib/utils'

const styles = {
  confirmed: 'bg-safe-50 text-safe-600',
  rac: 'bg-caution-50 text-caution-600',
  waitlisted: 'bg-risk-50 text-risk-600',
}

const labels = {
  confirmed: 'Confirmed',
  rac: 'RAC',
  waitlisted: 'Waitlisted',
}

export default function ConfirmationPill({ status, waitlistPosition, estimated = false, className }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium',
        styles[status],
        className
      )}
      title={estimated ? 'Estimated from class, lead time and season — no live seat feed' : undefined}
    >
      {labels[status]}
      {status === 'waitlisted' && waitlistPosition ? ` ${waitlistPosition}` : ''}
      {estimated && <span className="font-normal opacity-70">est.</span>}
    </span>
  )
}
