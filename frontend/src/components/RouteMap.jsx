import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { getCityCoords } from '../data/cityGeo'

const MAP_STYLE = 'https://tiles.openfreemap.org/styles/positron'

// Prefer backend-supplied coords (real stations); fall back to the local
// city lookup (mock data).
function endpointCoords(leg, end) {
  const c = end === 'from' ? leg.fromCoords : leg.toCoords
  if (Array.isArray(c) && c.length === 2 && c[0] != null && c[1] != null) return c
  return getCityCoords(end === 'from' ? leg.from : leg.to)
}

// Ordered list of node stops (origin → hubs → destination), de-duped.
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

// One entry per moving leg, with the segment midpoint for a mode badge.
function buildSegments(legs) {
  const segs = []
  for (const leg of legs) {
    if (leg.mode === 'connection') continue
    const from = endpointCoords(leg, 'from')
    const to = endpointCoords(leg, 'to')
    if (!from || !to || (from[0] === to[0] && from[1] === to[1])) continue
    segs.push({ mode: leg.mode, mid: [(from[0] + to[0]) / 2, (from[1] + to[1]) / 2] })
  }
  return segs
}

// Recolor the stock positron basemap toward the RouteSarthi palette.
// Always light — a light map reads better even in dark mode.
function applyBrandTint(map) {
  const set = (id, prop, val) => {
    try {
      if (map.getLayer(id)) map.setPaintProperty(id, prop, val)
    } catch {
      /* layer absent in this style version — ignore */
    }
  }
  for (const layer of map.getStyle().layers ?? []) {
    const id = layer.id
    const src = layer['source-layer'] ?? ''
    if (layer.type === 'background') set(id, 'background-color', '#f4f2ec')
    else if (layer.type === 'fill' && /water/i.test(id + src)) set(id, 'fill-color', '#d9e6ec')
    else if (layer.type === 'fill' && /(park|wood|landcover|grass|forest)/i.test(id + src))
      set(id, 'fill-color', '#e7efe7')
    else if (layer.type === 'line' && /water/i.test(id + src)) set(id, 'line-color', '#cddde4')
  }
}

function nodeMarkerEl(kind) {
  const palette = {
    origin: { bg: '#161c45', ring: 'rgba(22,28,69,0.22)' },
    hub: { bg: '#2f9885', ring: 'rgba(47,152,133,0.22)' },
    destination: { bg: '#15a36e', ring: 'rgba(21,163,110,0.22)' },
  }
  const c = palette[kind]
  const el = document.createElement('div')
  el.style.cssText = `width:16px;height:16px;border-radius:50%;background:${c.bg};border:2.5px solid #fff;box-shadow:0 0 0 6px ${c.ring},0 1px 4px rgba(22,28,69,0.3)`
  return el
}

const MODE_ICONS = {
  train: {
    bg: '#2e3c97',
    svg: '<rect x="4" y="3" width="12" height="12.5" rx="3"/><line x1="4" y1="10" x2="16" y2="10"/><line x1="7" y1="19" x2="5" y2="22"/><line x1="13" y1="19" x2="15" y2="22"/>',
  },
  bus: {
    bg: '#237a6b',
    svg: '<rect x="3" y="4" width="14" height="11" rx="2.5"/><line x1="3" y1="10" x2="17" y2="10"/><circle cx="6.5" cy="16.5" r="1.3"/><circle cx="13.5" cy="16.5" r="1.3"/>',
  },
  cab: {
    bg: '#d98c12',
    svg: '<path d="M3 11l2-4.5h10L17 11"/><rect x="2.5" y="11" width="15" height="4.5" rx="1.5"/><circle cx="6.5" cy="16.8" r="1.3"/><circle cx="13.5" cy="16.8" r="1.3"/>',
  },
}

function modeBadgeEl(mode) {
  const m = MODE_ICONS[mode] ?? MODE_ICONS.train
  const el = document.createElement('div')
  el.style.cssText = `width:26px;height:26px;border-radius:50%;background:${m.bg};border:2px solid #fff;box-shadow:0 2px 6px rgba(22,28,69,0.3);display:flex;align-items:center;justify-content:center`
  el.innerHTML = `<svg width="15" height="15" viewBox="0 0 20 24" fill="none" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${m.svg}</svg>`
  return el
}

function lerp(a, b, t) {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
}

// Coordinates from the start up to fraction `t` of the total path length.
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

export default function RouteMap({ legs, className = '', live = false, liveProgress = 0 }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const liveMarkerRef = useRef(null)
  const coordsRef = useRef(null)

  useEffect(() => {
    const stops = buildStops(legs)
    if (stops.length < 2 || !containerRef.current) return

    const coords = stops.map((s) => s.coords)
    coordsRef.current = coords
    const segments = buildSegments(legs)
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: coords[0],
      zoom: 4,
      scrollZoom: false,
      attributionControl: false,
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')

    let raf

    map.on('load', () => {
      applyBrandTint(map)

      // Faint full "planned" path under the animated line.
      map.addSource('route-bg', {
        type: 'geojson',
        data: { type: 'Feature', geometry: { type: 'LineString', coordinates: coords } },
      })
      map.addLayer({
        id: 'route-bg',
        type: 'line',
        source: 'route-bg',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': '#9aa6d8', 'line-width': 2, 'line-dasharray': [1.5, 1.5], 'line-opacity': 0.55 },
      })

      // Solid brand line that draws itself.
      map.addSource('route-line', {
        type: 'geojson',
        data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [coords[0]] } },
      })
      map.addLayer({
        id: 'route-line',
        type: 'line',
        source: 'route-line',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': '#2e3c97', 'line-width': 3.5 },
      })

      stops.forEach((s, i) => {
        const kind = i === 0 ? 'origin' : i === stops.length - 1 ? 'destination' : 'hub'
        new maplibregl.Marker({ element: nodeMarkerEl(kind) })
          .setLngLat(s.coords)
          .setPopup(new maplibregl.Popup({ offset: 14, closeButton: false }).setText(s.name))
          .addTo(map)
      })

      segments.forEach((seg) => {
        new maplibregl.Marker({ element: modeBadgeEl(seg.mode) }).setLngLat(seg.mid).addTo(map)
      })

      const bounds = coords.reduce(
        (b, c) => b.extend(c),
        new maplibregl.LngLatBounds(coords[0], coords[0])
      )
      map.fitBounds(bounds, { padding: 56, duration: 0 })

      if (live) {
        // Live mode: a pulsing dot at the head; the traveled line is driven by
        // liveProgress in the effect below, not by a one-shot draw.
        const el = document.createElement('div')
        el.className = 'rs-live-dot'
        liveMarkerRef.current = new maplibregl.Marker({ element: el }).setLngLat(coords[0]).addTo(map)
      } else {
        const draw = () => {
          if (reduceMotion) {
            map.getSource('route-line')?.setData({
              type: 'Feature',
              geometry: { type: 'LineString', coordinates: coords },
            })
            return
          }
          const duration = 1300
          const start = performance.now()
          const tick = (now) => {
            const p = Math.min((now - start) / duration, 1)
            const eased = 1 - Math.pow(1 - p, 3)
            map.getSource('route-line')?.setData({
              type: 'Feature',
              geometry: { type: 'LineString', coordinates: pathAt(coords, eased) },
            })
            if (p < 1) raf = requestAnimationFrame(tick)
          }
          raf = requestAnimationFrame(tick)
        }
        draw()
      }
    })

    return () => {
      if (raf) cancelAnimationFrame(raf)
      liveMarkerRef.current = null
      map.remove()
    }
  }, [legs, live])

  // Drive the traveled line + moving dot from liveProgress (live mode only).
  useEffect(() => {
    if (!live) return
    const map = mapRef.current
    const coords = coordsRef.current
    const marker = liveMarkerRef.current
    if (!map || !coords || !marker) return
    const partial = pathAt(coords, Math.max(0, Math.min(1, liveProgress)))
    const head = partial[partial.length - 1]
    map.getSource?.('route-line')?.setData({
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: partial },
    })
    marker.setLngLat(head)
  }, [live, liveProgress])

  const stops = buildStops(legs)
  if (stops.length < 2) return null

  return (
    <div
      ref={containerRef}
      className={`overflow-hidden rounded-2xl border border-line ${className}`}
      style={{ height: 320 }}
    />
  )
}
