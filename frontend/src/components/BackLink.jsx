import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

export default function BackLink({ to, children = 'Back', className = '' }) {
  const navigate = useNavigate()
  return (
    <button
      type="button"
      onClick={() => (to ? navigate(to) : navigate(-1))}
      className={`mb-4 flex items-center gap-1.5 text-sm font-medium text-faint transition-colors hover:text-brand-600 ${className}`}
    >
      <ArrowLeft className="h-4 w-4" />
      {children}
    </button>
  )
}
