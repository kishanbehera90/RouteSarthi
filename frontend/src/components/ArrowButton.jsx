import { ArrowRight } from 'lucide-react'
import { cn } from '../lib/utils'

const variants = {
  solid: 'bg-primary text-white hover:bg-primary-hover',
  light: 'bg-white text-brand-900 hover:bg-white/90',
  outline: 'border border-line text-content hover:border-line',
  ghost: 'text-content',
}

export default function ArrowButton({
  as: Tag = 'button',
  variant = 'solid',
  children,
  className,
  ...props
}) {
  const isPill = variant !== 'ghost'
  return (
    <Tag
      className={cn(
        'group inline-flex items-center gap-2.5 text-sm font-semibold tracking-wide',
        isPill && 'rounded-full px-6 py-3.5',
        variants[variant],
        'transition-colors',
        className
      )}
      {...props}
    >
      <span className="relative">
        {children}
        <span className="absolute -bottom-1 left-0 h-px w-full origin-left scale-x-100 bg-current opacity-30 transition-transform group-hover:scale-x-0" />
      </span>
      <ArrowRight className="h-4 w-4 shrink-0 transition-transform group-hover:translate-x-0.5" />
    </Tag>
  )
}
