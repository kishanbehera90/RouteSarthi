// Mock fixtures for Phase A. Shapes here are the contract the real backend
// (Phase B/C) will reproduce, so swapping MSW for real API calls later is a
// near drop-in.

export const corridors = [
  {
    id: 'rourkela-nashik',
    from: { code: 'ROU', name: 'Rourkela', state: 'Odisha' },
    to: { code: 'NK', name: 'Nashik', state: 'Maharashtra' },
    tagline: 'Direct trains are scarce and mostly waitlisted — Ranchi unlocks 8 daily confirmed options.',
    reasoning: {
      direct: { confirmability: 12, note: 'WL 38 in sleeper' },
      hubsScanned: [
        { name: 'Bhubaneswar', dailyTrains: 5, confirmPct: 71, note: 'Wrong direction, +6h' },
        { name: 'Jamshedpur', dailyTrains: 3, confirmPct: 64, note: 'Few onward trains' },
        { name: 'Ranchi', dailyTrains: 8, confirmPct: 87, winner: true, note: '2h by bus' },
      ],
    },
  },
  {
    id: 'bhuj-shimla',
    from: { code: 'BHUJ', name: 'Bhuj', state: 'Gujarat' },
    to: { code: 'SML', name: 'Shimla', state: 'Himachal Pradesh' },
    tagline: 'No sensible direct rail link — Ahmedabad gives you the whole north-India trunk line.',
    reasoning: {
      direct: { confirmability: 6, note: 'No real direct route' },
      hubsScanned: [
        { name: 'Gandhidham', dailyTrains: 4, confirmPct: 68, note: 'Still a branch line' },
        { name: 'Rajkot', dailyTrains: 6, confirmPct: 74, note: 'Limited northbound' },
        { name: 'Ahmedabad', dailyTrains: 9, confirmPct: 88, winner: true, note: 'Trunk junction to Kalka' },
      ],
    },
  },
  {
    id: 'imphal-bengaluru',
    from: { code: 'IMP', name: 'Imphal', state: 'Manipur' },
    to: { code: 'BLR', name: 'Bengaluru', state: 'Karnataka' },
    tagline: 'Imphal has no rail link at all — Guwahati is the real starting line.',
    reasoning: {
      direct: { confirmability: 0, note: 'No rail link at all' },
      hubsScanned: [
        { name: 'Dimapur', dailyTrains: 3, confirmPct: 61, note: 'Far, few southbound' },
        { name: 'Guwahati', dailyTrains: 6, confirmPct: 84, winner: true, note: 'Nearest major junction' },
      ],
    },
  },
]

const route = (overrides) => ({
  id: undefined,
  type: 'cross-origin', // 'direct' | 'cross-origin'
  totalTimeMins: 0,
  totalFareInr: 0,
  reliability: 0, // 0-100 composite score
  confirmation: 'confirmed', // 'confirmed' | 'rac' | 'waitlisted'
  waitlistPosition: null,
  confirmationPct: null, // odds this route ends up confirmed (one input to reliability)
  clearProbabilityPct: null, // for waitlisted routes: chance the WL clears
  why: '',
  legs: [],
  ...overrides,
})

export const routesByCorridor = {
  'rourkela-nashik': [
    route({
      id: 'ron-direct-1',
      type: 'direct',
      totalTimeMins: 32 * 60,
      totalFareInr: 450,
      reliability: 28,
      confirmation: 'waitlisted',
      waitlistPosition: 38,
      confirmationPct: 14,
      clearProbabilityPct: 18,
      why: 'The only direct train (Rourkela–Nashik Road Express) runs 3x/week and is almost always heavily waitlisted in sleeper class.',
      legs: [
        {
          id: 'ron-d1-l1',
          mode: 'train',
          name: '18030 Rourkela–LTT Express',
          from: 'Rourkela',
          to: 'Nashik Road',
          depart: '21:40',
          arrive: '05:10+2',
          durationMins: 32 * 60 - 30,
          fareInr: 450,
          confirmation: 'waitlisted',
          waitlistPosition: 38,
          clearProbabilityPct: 18,
          delayProfile: { avgMins: 45, onTimePct: 52 },
        },
      ],
      planB: 'If WL doesn’t clear by chart prep, switch to the Ranchi route below — book it as backup before you travel.',
    }),
    route({
      id: 'ron-cross-1',
      type: 'cross-origin',
      totalTimeMins: 26 * 60 + 30,
      totalFareInr: 780,
      reliability: 92,
      confirmation: 'confirmed',
      confirmationPct: 94,
      hub: { code: 'RNC', name: 'Ranchi' },
      why: 'Direct trains from Rourkela are only ~12% confirmable. Ranchi (2h away by bus) has 8 daily trains toward the Mumbai/Nashik line at 85%+ confirmation — and your connection there is historically very safe.',
      legs: [
        {
          id: 'ron-c1-l1',
          mode: 'bus',
          name: 'Rourkela → Ranchi (State Highway Express)',
          from: 'Rourkela Bus Stand',
          to: 'Ranchi Bus Stand',
          depart: '15:30',
          arrive: '17:35',
          durationMins: 125,
          fareInr: 220,
          confirmation: 'confirmed',
          delayProfile: { avgMins: 12, onTimePct: 88 },
        },
        {
          id: 'ron-c1-l2',
          mode: 'connection',
          connectionSafetyPct: 94,
          bufferMins: 95,
          note: 'Bus historically arrives with ~95 min to spare before departure — high safety margin.',
        },
        {
          id: 'ron-c1-l3',
          mode: 'train',
          name: '12810 Ranchi–LTT SF Express',
          from: 'Ranchi',
          to: 'Nashik Road',
          depart: '19:10',
          arrive: '18:00+1',
          durationMins: 23 * 60 + 10,
          fareInr: 560,
          confirmation: 'confirmed',
          delayProfile: { avgMins: 22, onTimePct: 81 },
        },
      ],
      planB: 'Miss the 19:10 from Ranchi? The 12724 at 22:45 reaches Nashik Road ~3h later — still confirmed in 3A.',
    }),
    route({
      id: 'ron-cross-2',
      type: 'cross-origin',
      totalTimeMins: 29 * 60,
      totalFareInr: 690,
      reliability: 81,
      confirmation: 'confirmed',
      confirmationPct: 83,
      hub: { code: 'RNC', name: 'Ranchi' },
      why: 'A cheaper, slightly slower confirmed alternative via the same Ranchi hub on a different train.',
      legs: [
        {
          id: 'ron-c2-l1',
          mode: 'bus',
          name: 'Rourkela → Ranchi (Express)',
          from: 'Rourkela Bus Stand',
          to: 'Ranchi Bus Stand',
          depart: '13:00',
          arrive: '15:05',
          durationMins: 125,
          fareInr: 220,
          confirmation: 'confirmed',
          delayProfile: { avgMins: 12, onTimePct: 88 },
        },
        {
          id: 'ron-c2-l2',
          mode: 'connection',
          connectionSafetyPct: 88,
          bufferMins: 65,
          note: 'Comfortable buffer; this train’s delay profile is slightly higher-variance.',
        },
        {
          id: 'ron-c2-l3',
          mode: 'train',
          name: '18182 Ranchi–Pune Express',
          from: 'Ranchi',
          to: 'Nashik Road',
          depart: '16:10',
          arrive: '21:10+1',
          durationMins: 29 * 60,
          fareInr: 470,
          confirmation: 'confirmed',
          delayProfile: { avgMins: 38, onTimePct: 66 },
        },
      ],
      planB: 'If this train runs >1h late, the 12810 (route above) departs Ranchi later the same evening as a fallback.',
    }),
  ],

  'bhuj-shimla': [
    route({
      id: 'bs-direct-1',
      type: 'direct',
      totalTimeMins: 40 * 60,
      totalFareInr: 520,
      reliability: 18,
      confirmation: 'waitlisted',
      waitlistPosition: 64,
      confirmationPct: 8,
      clearProbabilityPct: 9,
      why: 'No real direct rail route exists; the only "direct" option is a multi-change unreserved itinerary nobody should rely on.',
      legs: [
        {
          id: 'bs-d1-l1',
          mode: 'train',
          name: '19568 Bhuj–Bandra Express (unreserved leg)',
          from: 'Bhuj',
          to: 'Ahmedabad',
          depart: '20:15',
          arrive: '05:40+1',
          durationMins: 565,
          fareInr: 180,
          confirmation: 'waitlisted',
          waitlistPosition: 64,
          clearProbabilityPct: 9,
          delayProfile: { avgMins: 50, onTimePct: 47 },
        },
      ],
      planB: 'Skip this entirely — use the Ahmedabad cross-origin route below.',
    }),
    route({
      id: 'bs-cross-1',
      type: 'cross-origin',
      totalTimeMins: 33 * 60,
      totalFareInr: 1450,
      reliability: 89,
      confirmation: 'confirmed',
      confirmationPct: 91,
      hub: { code: 'ADI', name: 'Ahmedabad' },
      why: 'Bhuj sits at the end of a branch line. Ahmedabad (5h away) is a major trunk junction with multiple daily confirmed trains toward Shimla via Kalka.',
      legs: [
        {
          id: 'bs-c1-l1',
          mode: 'train',
          name: '19568 Bhuj–Bandra Express',
          from: 'Bhuj',
          to: 'Ahmedabad',
          depart: '20:15',
          arrive: '05:40+1',
          durationMins: 565,
          fareInr: 340,
          confirmation: 'confirmed',
          delayProfile: { avgMins: 28, onTimePct: 79 },
        },
        {
          id: 'bs-c1-l2',
          mode: 'connection',
          connectionSafetyPct: 90,
          bufferMins: 140,
          note: 'Plenty of buffer in Ahmedabad to also grab breakfast.',
        },
        {
          id: 'bs-c1-l3',
          mode: 'train',
          name: '12903 Ahmedabad–Kalka Express',
          from: 'Ahmedabad',
          to: 'Kalka',
          depart: '08:00',
          arrive: '12:20+1',
          durationMins: 1700,
          fareInr: 890,
          confirmation: 'confirmed',
          delayProfile: { avgMins: 35, onTimePct: 74 },
        },
        {
          id: 'bs-c1-l4',
          mode: 'connection',
          connectionSafetyPct: 86,
          bufferMins: 70,
          note: 'Kalka to Shimla toy train has limited daily departures — this buffer is built in.',
        },
        {
          id: 'bs-c1-l5',
          mode: 'train',
          name: 'Kalka–Shimla Toy Train',
          from: 'Kalka',
          to: 'Shimla',
          depart: '13:30',
          arrive: '18:50',
          durationMins: 320,
          fareInr: 220,
          confirmation: 'confirmed',
          delayProfile: { avgMins: 18, onTimePct: 85 },
        },
      ],
      planB: 'If the Kalka Express runs very late, a Chandigarh-bound train + bus to Shimla recovers most of the day.',
    }),
  ],

  'imphal-bengaluru': [
    route({
      id: 'ib-direct-1',
      type: 'direct',
      totalTimeMins: 0,
      totalFareInr: 0,
      reliability: 0,
      confirmation: 'waitlisted',
      waitlistPosition: null,
      why: 'There is no direct or sensible same-line rail option — Imphal has no broad-gauge passenger rail link to the south at all.',
      legs: [],
      planB: 'Use the Guwahati cross-origin route below — it is the only realistic confirmed path.',
    }),
    route({
      id: 'ib-cross-1',
      type: 'cross-origin',
      totalTimeMins: 38 * 60,
      totalFareInr: 2350,
      reliability: 85,
      confirmation: 'confirmed',
      confirmationPct: 88,
      hub: { code: 'GHY', name: 'Guwahati' },
      why: 'Imphal has no rail link; Guwahati (~8h by bus/shared cab) is the nearest major junction with direct confirmed trains to Bengaluru.',
      legs: [
        {
          id: 'ib-c1-l1',
          mode: 'cab',
          name: 'Imphal → Guwahati (shared cab)',
          from: 'Imphal',
          to: 'Guwahati',
          depart: '06:00',
          arrive: '14:30',
          durationMins: 510,
          fareInr: 900,
          confirmation: 'confirmed',
          delayProfile: { avgMins: 35, onTimePct: 70 },
        },
        {
          id: 'ib-c1-l2',
          mode: 'connection',
          connectionSafetyPct: 91,
          bufferMins: 180,
          note: 'Hill-route cabs run long delays sometimes — this plan books the evening train, not the same-day one, to stay safe.',
        },
        {
          id: 'ib-c1-l3',
          mode: 'train',
          name: '12508 Guwahati–Bengaluru SF Express',
          from: 'Guwahati',
          to: 'Bengaluru (KSR)',
          depart: '17:30',
          arrive: '23:30+1',
          durationMins: 1800,
          fareInr: 1450,
          confirmation: 'confirmed',
          delayProfile: { avgMins: 40, onTimePct: 72 },
        },
      ],
      planB: 'If the cab runs over 3h late, a same-evening Guwahati–Bengaluru flight (deep-linked) recovers the day at extra cost.',
    }),
  ],
}

export function getCorridor(id) {
  return corridors.find((c) => c.id === id)
}

export function getRoutes(id) {
  return routesByCorridor[id] ?? []
}

export function findRoute(routeId) {
  for (const list of Object.values(routesByCorridor)) {
    const found = list.find((r) => r.id === routeId)
    if (found) return found
  }
  return null
}
