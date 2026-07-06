import MapplsMap from './MapplsMap'
import MapLibreMap from './MapLibreMap'

// Use Mappls (MapmyIndia) when a key is configured; otherwise the free
// MapLibre map. MapplsMap itself also falls back to MapLibre if the SDK errors,
// so a map always renders.
export default function RouteMap(props) {
  return import.meta.env.VITE_MAPPLS_KEY ? <MapplsMap {...props} /> : <MapLibreMap {...props} />
}
