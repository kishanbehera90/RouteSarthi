import { http, HttpResponse } from 'msw'
import { corridors, getCorridor, getRoutes, findRoute } from '../data/routes'

// Endpoint shapes here are the contract Phase B's FastAPI service will
// reproduce — Phase C swaps this mock layer out, not the call sites.

function matchCorridor(fromQuery, toQuery) {
  const norm = (s) => (s ?? '').toLowerCase()
  return corridors.find(
    (c) =>
      norm(c.from.name).includes(norm(fromQuery)) &&
      norm(c.to.name).includes(norm(toQuery))
  )
}

function weightRoutes(routes, pref) {
  // pref: 'cheapest' | 'fastest' | 'confirmed' (default)
  const sorted = [...routes]
  if (pref === 'cheapest') sorted.sort((a, b) => a.totalFareInr - b.totalFareInr)
  else if (pref === 'fastest') sorted.sort((a, b) => a.totalTimeMins - b.totalTimeMins)
  else sorted.sort((a, b) => b.reliability - a.reliability)
  return sorted
}

export const handlers = [
  http.get('/api/corridors', () => HttpResponse.json(corridors)),

  http.get('/api/routes', ({ request }) => {
    const url = new URL(request.url)
    const from = url.searchParams.get('from') ?? ''
    const to = url.searchParams.get('to') ?? ''
    const pref = url.searchParams.get('pref') ?? 'confirmed'

    const corridor = matchCorridor(from, to)
    if (!corridor) {
      return HttpResponse.json({ corridor: null, routes: [] })
    }
    const routes = weightRoutes(getRoutes(corridor.id), pref)
    return HttpResponse.json({ corridor, routes })
  }),

  http.get('/api/routes/:routeId', ({ params }) => {
    const route = findRoute(params.routeId)
    if (!route) return new HttpResponse(null, { status: 404 })
    return HttpResponse.json(route)
  }),

  http.get('/api/corridors/:corridorId', ({ params }) => {
    const corridor = getCorridor(params.corridorId)
    if (!corridor) return new HttpResponse(null, { status: 404 })
    return HttpResponse.json({ corridor, routes: getRoutes(corridor.id) })
  }),
]
