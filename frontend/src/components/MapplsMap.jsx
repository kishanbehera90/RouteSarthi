import { useEffect, useRef, useState } from 'react'
import MapLibreMap from './MapLibreMap'
import { getCityCoords } from '../data/cityGeo'

// Mappls (MapmyIndia) map — India-accurate basemap. Draws the route polyline +
// origin/hub/destination markers + mode badges, matching the MapLibre version.
// If the key is missing or the SDK fails, it transparently falls back to
// MapLibreMap so the user always sees a working map.
const KEY = import.meta.env.VITE_MAPPLS_KEY

let sdkPromise = null
function loadMappls() {
  if (typeof window !== 'undefined' && window.mappls && window.mappls.Map) {
    return Promise.resolve(window.mappls)
  }
  if (sdkPromise) return sdkPromise
  sdkPromise = new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = `https://sdk.mappls.com/map/sdk/web?v=3.0&access_token=${KEY}`
    s.async = true
    s.onload = () => {
      let tries = 40
      const check = () => {
        if (window.mappls && window.mappls.Map) resolve(window.mappls)
        else if (tries-- > 0) setTimeout(check, 100)
        else reject(new Error('Mappls SDK loaded but global not ready'))
      }
      check()
    }
    s.onerror = () => reject(new Error('Mappls SDK failed to load'))
    document.head.appendChild(s)
  })
  return sdkPromise
}

// --- geometry (coords stored [lng, lat]; Mappls wants {lat, lng}) ---
function endpointCoords(leg, end) {
  const c = end === 'from' ? leg.fromCoords : leg.toCoords
  if (Array.isArray(c) && c.length === 2 && c[0] != null && c[1] != null) return c
  return getCityCoords(end === 'from' ? leg.from : leg.to)
}
const toLatLng = (c) => ({ lat: c[1], lng: c[0] })

function buildStops(legs) {
  const pts = []
  for (const leg of legs) {
    if (leg.mode === 'connection') continue
    pts.push({ name: leg.from, coords: endpointCoords(leg, 'from') })
    pts.push({ name: leg.to, coords: endpointCoords(leg, 'to') })
  }
  const stops = []
  for (const p of pts) {
    if (!p.coords) continue
    const last = stops[stops.length - 1]
    if (last && last.coords[0] === p.coords[0] && last.coords[1] === p.coords[1]) continue
    stops.push(p)
  }
  return stops
}

function buildLineCoords(legs) {
  const out = []
  const push = (c) => {
    if (c && c.length === 2 && c[0] != null && c[1] != null) {
      const last = out[out.length - 1]
      if (!last || last[0] !== c[0] || last[1] !== c[1]) out.push(c)
    }
  }
  for (const leg of legs) {
    if (leg.mode === 'connection') continue
    if (Array.isArray(leg.pathCoords) && leg.pathCoords.length >= 2) {
      for (const c of leg.pathCoords) push(c)
    } else {
      push(endpointCoords(leg, 'from'))
      push(endpointCoords(leg, 'to'))
    }
  }
  return out
}

function buildSegments(legs) {
  const segs = []
  for (const leg of legs) {
    if (leg.mode === 'connection') continue
    const path = Array.isArray(leg.pathCoords) && leg.pathCoords.length >= 2 ? leg.pathCoords : null
    if (path) {
      segs.push({ mode: leg.mode, mid: path[Math.floor(path.length / 2)] })
      continue
    }
    const from = endpointCoords(leg, 'from')
    const to = endpointCoords(leg, 'to')
    if (!from || !to || (from[0] === to[0] && from[1] === to[1])) continue
    segs.push({ mode: leg.mode, mid: [(from[0] + to[0]) / 2, (from[1] + to[1]) / 2] })
  }
  return segs
}

function lerp(a, b, t) {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
}
function pathAt(coords, t) {
  if (t <= 0) return [coords[0]]
  if (t >= 1) return coords.slice()
  const lens = []
  let total = 0
  for (let i = 0; i < coords.length - 1; i++) {
    const l = Math.hypot(coords[i + 1][0] - coords[i][0], coords[i + 1][1] - coords[i][1])
    lens.push(l)
    total += l
  }
  let target = total * t
  const out = [coords[0]]
  for (let i = 0; i < lens.length; i++) {
    if (target > lens[i]) {
      out.push(coords[i + 1])
      target -= lens[i]
    } else {
      out.push(lerp(coords[i], coords[i + 1], lens[i] === 0 ? 0 : target / lens[i]))
      break
    }
  }
  return out
}

// --- marker icons as data-URI SVGs (reliable across SDK versions) ---
const svgUri = (svg) => 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg)

function nodeIcon(kind) {
  const bg = { origin: '#161c45', hub: '#2f9885', destination: '#15a36e' }[kind]
  // Clean ringed "target" dot. Soft shadow faked with a translucent halo ring
  // (SVG filters break when the data-URI is used as a marker image).
  return svgUri(
    `<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 30 30"><circle cx="15" cy="15" r="10" fill="#161c45" opacity="0.14"/><circle cx="15" cy="15" r="7.5" fill="#ffffff"/><circle cx="15" cy="15" r="5.5" fill="${bg}"/><circle cx="15" cy="15" r="2.2" fill="#ffffff" opacity="0.9"/></svg>`
  )
}

const MODE_GLYPH = {
  train: { bg: '#2e3c97', d: '<rect x="7" y="5" width="12" height="12.5" rx="3"/><line x1="7" y1="12" x2="19" y2="12"/><line x1="10" y1="21" x2="8" y2="24"/><line x1="16" y1="21" x2="18" y2="24"/>' },
  bus: { bg: '#237a6b', d: '<rect x="6" y="6" width="14" height="11" rx="2.5"/><line x1="6" y1="12" x2="20" y2="12"/><circle cx="9.5" cy="18.5" r="1.3"/><circle cx="16.5" cy="18.5" r="1.3"/>' },
  cab: { bg: '#d98c12', d: '<path d="M6 13l2-4.5h10L20 13"/><rect x="5.5" y="13" width="15" height="4.5" rx="1.5"/><circle cx="9.5" cy="18.8" r="1.3"/><circle cx="16.5" cy="18.8" r="1.3"/>' },
}
function modeIcon(mode) {
  const m = MODE_GLYPH[mode] ?? MODE_GLYPH.train
  // Translucent halo = soft shadow; content authored for a 28-box, shifted +3.
  return svgUri(
    `<svg xmlns="http://www.w3.org/2000/svg" width="34" height="34" viewBox="0 0 34 34"><circle cx="17" cy="17" r="14" fill="#161c45" opacity="0.13"/><g transform="translate(3,3)"><circle cx="14" cy="14" r="11.5" fill="${m.bg}" stroke="#ffffff" stroke-width="2.5"/><g fill="none" stroke="#ffffff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${m.d}</g></g></svg>`
  )
}
function liveIcon() {
  return svgUri(
    `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><circle cx="10" cy="10" r="6" fill="#2f9885" stroke="#fff" stroke-width="3"/></svg>`
  )
}

export default function MapplsMap({ legs, className = '', live = false, liveProgress = 0 }) {
  const idRef = useRef('mappls-' + Math.random().toString(36).slice(2))
  const mapRef = useRef(null)
  const liveMarkerRef = useRef(null)
  const coordsRef = useRef(null)
  const [failed, setFailed] = useState(!KEY)

  useEffect(() => {
    if (!KEY) return
    let cancelled = false

    const stops = buildStops(legs)
    const line = buildLineCoords(legs)
    if (stops.length < 2 || line.length < 2) return
    coordsRef.current = line

    loadMappls()
      .then((mappls) => {
        if (cancelled || !document.getElementById(idRef.current)) return
        let map
        try {
          map = new mappls.Map(idRef.current, { center: toLatLng(line[0]), zoom: 5, zoomControl: true })
        } catch {
          if (!cancelled) setFailed(true)
          return
        }
        mapRef.current = map

        let built = false
        const build = () => {
          if (built || cancelled) return
          built = true
          try {
            const path = line.map(toLatLng)
            // White casing underneath so the route pops off the basemap…
            new mappls.Polyline({
              map, path, strokeColor: '#ffffff', strokeWeight: 9, strokeOpacity: 0.95,
              fitbounds: true, fitboundOptions: { padding: 70 },
            })
            // …then the brand line on top.
            new mappls.Polyline({
              map, path, strokeColor: '#3d4fb8', strokeWeight: 4.5, strokeOpacity: 1,
            })
            stops.forEach((s, i) => {
              const kind = i === 0 ? 'origin' : i === stops.length - 1 ? 'destination' : 'hub'
              new mappls.Marker({
                map,
                position: toLatLng(s.coords),
                icon: nodeIcon(kind),
                popupHtml: `<b>${s.name}</b>`,
              })
            })
            buildSegments(legs).forEach((seg) => {
              new mappls.Marker({ map, position: toLatLng(seg.mid), icon: modeIcon(seg.mode) })
            })
            if (live) {
              liveMarkerRef.current = new mappls.Marker({ map, position: toLatLng(line[0]), icon: liveIcon() })
            }
          } catch {
            // A marker/polyline hiccup shouldn't discard the whole map — the
            // basemap + whatever rendered stays. (Only a real SDK/map-init
            // failure falls back to MapLibre.)
          }
        }

        if (typeof map.on === 'function') map.on('load', build)
        // Fallback in case 'load' doesn't fire in this SDK build.
        setTimeout(build, 1600)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })

    return () => {
      cancelled = true
      try {
        mapRef.current?.remove?.()
      } catch {
        /* ignore */
      }
      mapRef.current = null
      liveMarkerRef.current = null
    }
  }, [legs, live])

  // Move the live marker along the path as progress advances.
  useEffect(() => {
    if (!live || !coordsRef.current || !liveMarkerRef.current) return
    const partial = pathAt(coordsRef.current, Math.max(0, Math.min(1, liveProgress)))
    const head = partial[partial.length - 1]
    try {
      liveMarkerRef.current.setPosition?.(toLatLng(head))
    } catch {
      /* ignore */
    }
  }, [live, liveProgress])

  if (failed) {
    return <MapLibreMap legs={legs} className={className} live={live} liveProgress={liveProgress} />
  }

  const stops = buildStops(legs)
  if (stops.length < 2) return null

  return (
    <div
      id={idRef.current}
      className={`overflow-hidden rounded-2xl border border-line ${className}`}
      style={{ height: 320 }}
    />
  )
}
