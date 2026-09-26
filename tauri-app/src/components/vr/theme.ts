import displayFont from '@fontsource/space-grotesk/files/space-grotesk-latin-600-normal.woff?url'
import uiFont from '@fontsource/space-grotesk/files/space-grotesk-latin-500-normal.woff?url'
import monoFont from '@fontsource/jetbrains-mono/files/jetbrains-mono-latin-500-normal.woff?url'
import monoBoldFont from '@fontsource/jetbrains-mono/files/jetbrains-mono-latin-700-normal.woff?url'

// Bundled locally (not Google Fonts) so 3D text renders inside a headset and offline.
export const FONT = { display: displayFont, ui: uiFont, mono: monoFont, monoBold: monoBoldFont }

// JetBrains Mono advance width is 0.6 em — lets label plates size to their text exactly.
export const MONO_ADVANCE = 0.6

// Night-ops palette built off the app's navy accent (#244975). Semantic colours are
// kept separate from the accent so status always reads as status.
export const C = {
  void: '#050A13',
  floor: '#08101C',
  table: '#0B1626',
  tableEdge: '#1D3858',
  bezel: '#132740',
  grid: '#12233A',
  roadMajor: '#4D7CB3',
  roadMinor: '#1E3656',
  text: '#EAF1FA',
  textDim: '#93A8C4',
  textFaint: '#5E7493',
  accent: '#86B7F2',
  panel: '#0A1526',
  panelEdge: '#2A507E',
  ok: '#2ED47A',
  warn: '#F5A524',
  bad: '#F0484B',
  neutral: '#94A3B8',
  zoneRed: '#F0484B',
  zoneYellow: '#F5A524',
  depot: '#86B7F2',
}

export const CONSTRAINT_LABELS: Record<string, string> = {
  min_separation: 'Separation',
  geofence_exclusion: 'Geofence',
  battery_reserve_margin: 'Battery reserve',
  altitude_ceiling: 'Altitude ceiling',
  wind_limit: 'Wind envelope',
  payload_weight_limit: 'Payload',
  noise_limit: 'Ground noise',
  collision_probability: 'Conflict prob.',
  comms_link_margin: 'C2 link margin',
  depot_capacity: 'Depot pad slots',
  weather_visibility: 'Visibility',
}

export const CONSTRAINT_UNITS: Record<string, string> = {
  min_separation: 'm',
  geofence_exclusion: '',
  battery_reserve_margin: 'Wh',
  altitude_ceiling: 'm',
  wind_limit: 'm/s',
  payload_weight_limit: 'kg',
  noise_limit: 'dB',
  collision_probability: '',
  comms_link_margin: 'dB',
  depot_capacity: 'slots',
  weather_visibility: 'm',
}

export const FACTOR_LABELS: Record<string, string> = {
  battery_energy: 'Battery / energy',
  airspace_conflict: 'Airspace conflict',
  weather_environmental: 'Weather',
  communications_link: 'Comms link',
  routing_navigation: 'Routing / navigation',
  ops_scheduling_capacity: 'Ops / depot capacity',
  cross_check_anomaly: 'Cross-check anomaly',
}

export const CLAIM_STATUS: Record<string, { label: string; color: string; note: string }> = {
  CONFIRMED: { label: 'CONFIRMED', color: C.ok, note: 'council claim matches a violated constraint' },
  MISSED: { label: 'MISSED', color: C.bad, note: 'geometry shows a violation the council did not claim' },
  NO_GEOMETRIC_EVIDENCE: { label: 'UNBACKED', color: C.warn, note: 'claimed, but no violated constraint supports it' },
  UNCERTAIN: { label: 'UNCERTAIN', color: C.neutral, note: 'council could not decide' },
  AGREES_NOT_INVOLVED: { label: 'AGREES', color: C.textDim, note: 'neither side implicates it' },
  NO_CLAIM: { label: 'NO CLAIM', color: C.textFaint, note: 'council made no statement' },
  NOT_CHECKABLE: { label: 'N/A', color: C.textFaint, note: 'no CBF margin exists to check this factor' },
}

export function marginColor(margin: number, warnBand: number): string {
  if (margin < 0) return C.bad
  if (margin < warnBand) return C.warn
  return C.ok
}

// How close to a limit counts as "watch this" per live constraint, in its own units.
export const WARN_BANDS: Record<string, number> = {
  min_separation: 35,
  battery_reserve_margin: 40,
  altitude_ceiling: 5,
  payload_weight_limit: 0.5,
  geofence_exclusion: 0.5,
}
