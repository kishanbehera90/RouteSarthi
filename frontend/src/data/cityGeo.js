// Approximate coordinates for the mock corridors' stops, keyed exactly as
// they appear in routes.js leg.from/leg.to (plus a couple of bare city-name
// aliases). Phase B's real backend will supply real station geo instead.
const COORDS = {
  Rourkela: [84.8536, 22.2604],
  'Rourkela Bus Stand': [84.8536, 22.2604],
  Nashik: [73.7898, 19.9975],
  'Nashik Road': [73.8569, 19.9457],
  Ranchi: [85.3096, 23.3441],
  'Ranchi Bus Stand': [85.3096, 23.3441],
  Bhuj: [69.6669, 23.242],
  Ahmedabad: [72.5714, 23.0225],
  Kalka: [76.9352, 30.8398],
  Shimla: [77.1734, 31.1048],
  Imphal: [93.9368, 24.817],
  Guwahati: [91.7362, 26.1445],
  Bengaluru: [77.5946, 12.9716],
  'Bengaluru (KSR)': [77.5946, 12.9716],
}

export function getCityCoords(name) {
  if (!name) return null
  if (COORDS[name]) return COORDS[name]
  const stripped = name.replace(/\s*\([^)]*\)\s*$/, '').trim()
  return COORDS[stripped] ?? null
}
