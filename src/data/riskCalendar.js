// Mock seasonal risk model for the Risk Calendar. Not real forecasting —
// illustrates the "proactive intelligence" UX with a believable, explainable
// signal (monsoon season + weekend travel rush + occasional regional spikes).

export function toLocalISODate(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function hashDate(dateStr) {
  let h = 0
  for (let i = 0; i < dateStr.length; i++) {
    h = (h * 31 + dateStr.charCodeAt(i)) >>> 0
  }
  return h
}

function monsoonBase(month) {
  // 0-indexed months. Peak monsoon Jul(6)/Aug(7), shoulder Jun(5)/Sep(8).
  if (month === 6 || month === 7) return 60
  if (month === 5 || month === 8) return 42
  if (month === 4 || month === 9) return 28
  return 16
}

export function getRiskForDate(date) {
  const dateStr = toLocalISODate(date)
  const month = date.getMonth()
  const day = date.getDay()

  let score = monsoonBase(month)
  const isWeekend = day === 0 || day === 5 || day === 6
  if (isWeekend) score += 14

  const hash = hashDate(dateStr)
  const jitter = (hash % 21) - 10 // -10..+10
  score += jitter

  const isSpike = hash % 11 === 0
  if (isSpike) score += 22

  score = Math.max(4, Math.min(96, Math.round(score)))

  let level = 'low'
  if (score >= 65) level = 'high'
  else if (score >= 38) level = 'medium'

  let label = 'Normal conditions'
  if (isSpike && score >= 55) label = 'Regional holiday rush expected'
  else if (level === 'high') label = 'Monsoon disruption likely'
  else if (level === 'medium' && isWeekend) label = 'Weekend travel rush'
  else if (level === 'medium') label = 'Some monsoon risk'
  else label = 'Good time to travel'

  return { score, level, label, isWeekend }
}
