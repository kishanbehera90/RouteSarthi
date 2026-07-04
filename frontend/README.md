# RouteSarthi — Frontend (Phase A)

**Peace of mind, every time.** RouteSarthi is an AI-powered travel assistant that
finds *confirmed, reliable* ways to travel across India — even from poorly
connected towns — by routing you through nearby better-connected hubs, scoring
connections on real delay history, and acting as a live lifeline if a leg breaks
mid-journey.

This is the **Phase A** frontend: a fully clickable prototype running on mock
data. It demonstrates the three signature pillars before any backend exists:

- **Cross-origin reasoning** — the Results page animates *how* a route was chosen
  (direct fails → nearby hubs scanned → winner), not just the result.
- **Delay-aware confidence** — a reliability score with a tappable breakdown
  (confirmation odds · on-time reliability · connection safety) and per-leg
  waitlist-clearance prediction.
- **The live lifeline** — a journey simulation with a moving map dot, legs
  progressing through states, escalating delay alerts, and auto Plan-B reroute.

## Tech

React 19 · Vite · React Router · Zustand · Tailwind CSS v4 · Framer Motion ·
MapLibre GL · MSW (mock API). Light/dark theming via semantic CSS tokens.

## Getting started

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production build
npm run preview  # serve the build locally
npm run lint
```

## Mock data & the API contract

There is **no backend yet**. All `/api/*` calls are served by MSW from
[`src/data/routes.js`](src/data/routes.js) via
[`src/mocks/handlers.js`](src/mocks/handlers.js). These shapes are the contract
the Phase B backend must reproduce — see **[API_CONTRACT.md](API_CONTRACT.md)**.

The mock runs in **both dev and production** so the deployed demo works. When the
real backend is ready, set the env flag to turn mocks off — no code change:

```bash
VITE_USE_REAL_API=true npm run build
```

## Project structure

```
src/
  pages/        Onboarding, Login, Search, Results, Compare,
                HubPicker, RouteDetail, LiveJourney, SavedTrips
  components/   RouteCard, RouteMap, DecisionReasoning, ReliabilityGauge,
                LegTimeline, ShareModal, ThemeToggle, Logo, …
  store/        Zustand stores (journey, auth, theme, toasts)
  data/         routes.js (mock fixtures), cityGeo.js, riskCalendar.js
  mocks/        MSW handlers + browser worker
  index.css     Tailwind theme + semantic tokens + light/dark
```

## Theming

Components use semantic tokens (`bg-surface`, `text-content`, `text-muted`,
`border-line`, `bg-primary`, …) defined in `src/index.css`. Dark mode is
class-based (`.dark` on `<html>`), toggled in the header and persisted. See the
theming notes for the gotchas (fixed-color graphics must use literal hex).
