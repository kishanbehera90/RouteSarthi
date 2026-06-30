# RouteSarthi — API contract (Phase A → Phase B)

The Phase A frontend talks to a mock API (MSW) whose shapes **are the contract**
for the real Phase B backend. Reproduce these endpoints and response shapes
exactly and the frontend works untouched — then set `VITE_USE_REAL_API=true`
to turn the mocks off.

Reference implementation: [`src/mocks/handlers.js`](src/mocks/handlers.js) +
[`src/data/routes.js`](src/data/routes.js).

All responses are JSON. Paths are relative to the app origin (`/api/...`). If the
backend lives elsewhere, serve it same-origin or add a dev proxy / base URL.

---

## Endpoints

### `GET /api/corridors`
Returns all supported corridors. → `Corridor[]`

### `GET /api/corridors/:corridorId`
→ `{ corridor: Corridor, routes: Route[] }` · `404` if unknown id.

### `GET /api/routes?from=<str>&to=<str>&pref=<pref>`
Resolves a corridor from free-text `from`/`to` (current mock matches by city
name substring) and returns ranked routes.
- `pref` ∈ `cheapest | fastest | confirmed` (default `confirmed`). Server returns
  `routes` already sorted: cheapest→`totalFareInr` asc, fastest→`totalTimeMins`
  asc, confirmed→`reliability` desc.
- No match → `{ "corridor": null, "routes": [] }` (HTTP 200, **not** 404).
→ `{ corridor: Corridor, routes: Route[] }`

### `GET /api/routes/:routeId`
→ `Route` · `404` if unknown id.

---

## Shapes

### Corridor
```jsonc
{
  "id": "rourkela-nashik",
  "from": { "code": "ROU", "name": "Rourkela", "state": "Odisha" },
  "to":   { "code": "NK",  "name": "Nashik",   "state": "Maharashtra" },
  "tagline": "Direct trains are scarce …",
  "reasoning": {                          // powers the Results "decision" strip
    "direct": { "confirmability": 12, "note": "WL 38 in sleeper" },
    "hubsScanned": [
      { "name": "Bhubaneswar", "dailyTrains": 5, "confirmPct": 71, "note": "Wrong direction, +6h" },
      { "name": "Ranchi", "dailyTrains": 8, "confirmPct": 87, "winner": true, "note": "2h by bus" }
    ]
  }
}
```

### Route
```jsonc
{
  "id": "ron-cross-1",
  "type": "cross-origin",               // "direct" | "cross-origin"
  "totalTimeMins": 1590,
  "totalFareInr": 780,
  "reliability": 92,                     // 0–100 composite
  "confirmation": "confirmed",           // "confirmed" | "rac" | "waitlisted"
  "waitlistPosition": null,              // number when waitlisted
  "confirmationPct": 94,                 // null | 0–100; feeds reliability breakdown
  "clearProbabilityPct": null,           // null | 0–100; WL-clearance widget (waitlisted only)
  "hub": { "code": "RNC", "name": "Ranchi" },  // present for cross-origin
  "why": "Direct trains from Rourkela are only ~12% confirmable …",
  "planB": "Miss the 19:10 from Ranchi? The 12724 at 22:45 …",
  "legs": [ /* Leg[] in travel order, including connection markers */ ]
}
```

### Leg — moving (`mode` = `train | bus | cab`)
```jsonc
{
  "id": "ron-c1-l1",
  "mode": "bus",
  "name": "Rourkela → Ranchi (State Highway Express)",
  "from": "Rourkela Bus Stand",
  "to": "Ranchi Bus Stand",
  "depart": "15:30",                     // "HH:MM", may carry "+N" day suffix on arrive
  "arrive": "17:35",
  "durationMins": 125,
  "fareInr": 220,
  "confirmation": "confirmed",
  "waitlistPosition": null,              // when waitlisted
  "clearProbabilityPct": null,           // when waitlisted
  "delayProfile": { "avgMins": 12, "onTimePct": 88 }
}
```

### Leg — connection (between two moving legs)
```jsonc
{
  "id": "ron-c1-l2",
  "mode": "connection",
  "connectionSafetyPct": 94,             // P(make the transfer)
  "bufferMins": 95,
  "note": "Bus historically arrives with ~95 min to spare …"
}
```

---

## Notes for Phase B
- Station geo (for the map) currently lives client-side in `src/data/cityGeo.js`,
  keyed by `leg.from`/`leg.to` strings. Either keep supplying those exact strings
  or extend the API to return `[lng, lat]` per stop.
- `reasoning`, `confirmationPct`, `clearProbabilityPct`, `delayProfile`, and
  `connectionSafetyPct` are the outputs of the real engine — start with
  transparent historical averages, improve with ML later (per the plan).
