import { TrainFront, Bus, Car } from 'lucide-react'

const icons = { train: TrainFront, bus: Bus, cab: Car }

export default function ModeIcon({ mode, className }) {
  const Icon = icons[mode]
  if (!Icon) return null
  return <Icon className={className} />
}
