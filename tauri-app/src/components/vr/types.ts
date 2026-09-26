// Mirrors GET /api/v1/safety/live-margins
export interface LiveDrone {
  lat: number
  lon: number
  link_mode: 'SIMULATED' | 'LIVE'
  safety_margins: Record<string, number>
  passed: boolean
  state: string
  order_id: string | null
  altitude_m: number
  altitude_ceiling_m: number
  zone: 'GREEN' | 'YELLOW' | 'RED'
  battery_soc_pct: number
  battery_available_wh: number
  battery_reserve_wh: number
  payload_kg: number
  nearest_drone_id: string | null
  nearest_horizontal_m: number
  nearest_vertical_m: number
  heading_deg: number | null
  progress: number | null
  remaining_m: number | null
  arrived: boolean
  route: [number, number][]
  position_source: 'TELEMETRY' | 'ROUTE_DEAD_RECKONING' | 'DEPOT_NODE'
}

export interface DronePair {
  a: string
  b: string
  horizontal_m: number
  vertical_m: number
  slant_m: number
  separation_margin_m: number
}

export interface LiveConstants {
  min_separation_m: number
  operational_ceiling_m: number
  legal_ceiling_m: number
  pair_awareness_radius_m: number
  cruise_speed_mps: number
}

export interface LiveMarginsDto {
  city: string
  generated_at: number
  drone_count: number
  drones: Record<string, LiveDrone>
  pairs: DronePair[]
  fleet_worst_case: Record<string, number>
  constants: LiveConstants
  constraint_sources: { live: string[]; default: string[] }
}

export interface ZoneDto {
  zone_id: string
  zone_type: 'GREEN' | 'YELLOW' | 'RED'
  reason?: string | null
  center_lat: number
  center_lon: number
  radius_m: number
}

export interface DepotDto {
  depot_id: string
  name: string
  lat: number | null
  lon: number | null
}

export interface CityDto {
  slug: string
  name?: string
  center: [number, number]
  airport_name?: string
}

export interface RoadsDto {
  center: [number, number]
  synthetic: boolean
  major: number[][]
  minor: number[][]
}

// Mirrors GET /api/v1/incidents/ and /{id}/vr-scene
export interface IncidentSummaryDto {
  incident_id: string
  city: string
  trigger_type: string
  status: string
  created_at: string
}

export interface ClaimRow {
  factor: string
  council_claim: string | null
  council_confidence: number | null
  implicated_by_geometry: boolean
  evidence_constraints: string[]
  status: 'CONFIRMED' | 'MISSED' | 'NO_GEOMETRIC_EVIDENCE' | 'UNCERTAIN' | 'AGREES_NOT_INVOLVED' | 'NO_CLAIM' | 'NOT_CHECKABLE'
}

export interface VRSceneDto {
  incident_id: string
  city: string
  drone_id: string | null
  trigger_type: string
  status: string
  position: { lat: number | null; lon: number | null }
  origin: { lat: number | null; lon: number | null }
  altitude_m: number | null
  max_altitude_m: number | null
  in_red_zone: boolean
  in_yellow_zone: boolean
  safety_margins: Record<string, number>
  violations: { constraint_name: string; violation_magnitude: number; required_correction: number }[]
  root_cause_summary: string | null
  systemic_factor_note: string | null
  recommended_action: string | null
  claim_check: {
    rows: ClaimRow[]
    counts: Record<string, number>
    agrees_with_geometry: boolean
    has_council_claims: boolean
  }
}
