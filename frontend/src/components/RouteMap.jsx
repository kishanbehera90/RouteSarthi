import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { getCityCoords } from '../data/cityGeo'

const MAP_STYLE = 'https://tiles.openfreemap.org/styles/positron'

function buildStops(legs) {
  const named = []
  for (const leg of legs) {
    if (leg.mode === 'connection') continue
    named.push(leg.from, leg.to)
  }

  const stops = []
  for (const name of named) {
    const coords = getCityCoords(name)
    if (!coords) continue
    const last = stops[stops.length - 1]
    if (last && last.coords[0] === coords[0] && last.coords[1] === coords[1]) continue
    stops.push({ name, coords })
  }
  return stops
}

function markerEl(kind) {
  const el = document.createElement('div')
  const palette = {
    origin: { bg: '#161c45', ring: 'rgba(22,28,69,0.25)' },
    hub: { bg: '#2f9885', ring: 'rgba(47,152,133,0.25)' },
    destination: { bg: '#15a36e', ring: 'rgba(21,163,110,0.25)' },
  }
  const c = palette[kind]
  el.style.width = '18px'
  el.style.height = '18px'
  el.style.borderRadius = '50%'
  el.style.background = c.bg
  el.style.border = '2.5px solid white'
  el.style.boxShadow = `0 0 0 6px ${c.ring}, 0 1px 4px rgba(22,28,69,0.3)`
  return el
}

export default function RouteMap({ legs, className = '' }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)

  useEffect(() => {
    const stops = buildStops(legs)
    if (stops.length < 2 || !containerRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: stops[0].coords,
      zoom: 4,
      scrollZoom: false,
      attributionControl: false,
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')

    map.on('load', () => {
      map.addSource('route-line', {
        type: 'geojson',
        data: {
          type: 'Feature',
          geometry: { type: 'LineString', coordinates: stops.map((s) => s.coords) },
        },
      })
      map.addLayer({
        id: 'route-line',
        type: 'line',
        source: 'route-line',
        paint: {
          'line-color': '#2e3c97',
          'line-width': 3,
          'line-dasharray': [0.2, 1.6],
        },
      })

      stops.forEach((s, i) => {
        const kind = i === 0 ? 'origin' : i === stops.length - 1 ? 'destination' : 'hub'
        new maplibregl.Marker({ element: markerEl(kind) })
          .setLngLat(s.coords)
          .setPopup(new maplibregl.Popup({ offset: 14, closeButton: false }).setText(s.name))
          .addTo(map)
      })

      const bounds = stops.reduce(
        (b, s) => b.extend(s.coords),
        new maplibregl.LngLatBounds(stops[0].coords, stops[0].coords)
      )
      map.fitBounds(bounds, { padding: 56, duration: 0 })
    })

    return () => map.remove()
  }, [legs])

  const stops = buildStops(legs)
  if (stops.length < 2) return null

  return (
    <div
      ref={containerRef}
      className={`overflow-hidden rounded-2xl border border-brand-900/10 ${className}`}
      style={{ height: 320 }}
    />
  )
}
