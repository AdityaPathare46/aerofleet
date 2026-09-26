import { fmtDistance } from './geo'
import { droneStatus } from './Swarm'
import { C, CLAIM_STATUS, CONSTRAINT_LABELS, CONSTRAINT_UNITS, FACTOR_LABELS, WARN_BANDS } from './theme'
import type { LiveMarginsDto, VRSceneDto } from './types'

// One view-model per board, rendered two ways: in-world (headset) and HTML (desktop).

export interface Kpi { key: string; value: string; color: string; sub?: string }
export interface ConstraintRow { name: string; label: string; value: string; color: string; live: boolean }

export function fleetKpis(data: LiveMarginsDto | null): Kpi[] {
  const drones = data ? Object.values(data.drones) : []
  const minSep = data?.constants.min_separation_m ?? 15
  const loss = data?.pairs.filter((p) => p.separation_margin_m < 0).length ?? 0
  const watch = drones.filter((d) => droneStatus(d) !== 'ok').length
  const closest = data?.pairs[0]
  return [
    { key: 'AIRBORNE', value: String(drones.length), color: C.text },
    { key: 'LOSS OF SEP.', value: String(loss), color: loss ? C.bad : C.ok, sub: `pairs < ${minSep} m` },
    { key: 'WATCH / VIOL.', value: String(watch), color: watch ? C.warn : C.ok, sub: 'drones' },
    {
      key: 'CLOSEST PAIR', value: closest ? fmtDistance(closest.horizontal_m) : '—',
      color: closest && closest.separation_margin_m < 0 ? C.bad : C.text, sub: 'horizontal',
    },
  ]
}

export function constraintRows(data: LiveMarginsDto | null): ConstraintRow[] {
  const live = new Set(data?.constraint_sources.live ?? [])
  return Object.keys(CONSTRAINT_LABELS).map((name) => {
    const m = data?.fleet_worst_case[name]
    const isLive = live.has(name)
    const unit = CONSTRAINT_UNITS[name]
    const color = m === undefined ? C.textFaint
      : m < 0 ? C.bad
        : name in WARN_BANDS && m < WARN_BANDS[name] ? C.warn
          : isLive ? C.ok : C.textDim
    const value = m === undefined ? '—'
      : name === 'geofence_exclusion' ? (m < 0 ? 'INSIDE' : 'clear')
        : `${m >= 1000 ? Math.round(m) : m.toFixed(m < 10 ? 1 : 0)}${unit ? ' ' + unit : ''}`
    return { name, label: CONSTRAINT_LABELS[name], value, color, live: isLive }
  })
}

export function legendNote(minSep: number, vExag: number): string {
  return `Drop-line to the ground = altitude · beam = pair within ${WARN_BANDS.min_separation + minSep} m · `
    + `dashed = remaining route · ASSUMED = no live per-drone sensor yet, dispatch-time default used · `
    + `symbols not to scale, vertical ×${vExag.toFixed(0)}`
}

export interface ClaimVerdict { color: string; text: string }

export function claimVerdict(scene: VRSceneDto): ClaimVerdict {
  const check = scene.claim_check
  const disagreements = (check.counts.MISSED ?? 0) + (check.counts.NO_GEOMETRIC_EVIDENCE ?? 0)
  if (!check.has_council_claims) return { color: C.neutral, text: 'Council has not produced factor claims for this incident yet' }
  if (disagreements === 0) return { color: C.ok, text: "Council's factor claims are consistent with the rejection geometry" }
  return {
    color: disagreements > 1 ? C.bad : C.warn,
    text: `Council disagrees with the geometry on ${disagreements} factor${disagreements === 1 ? '' : 's'} — verify before acting on its report`,
  }
}

export interface ClaimViewRow {
  factor: string; label: string; claim: string; evidence: string; evidenceHot: boolean
  status: string; statusColor: string; statusNote: string; checkable: boolean
}

export function claimRows(scene: VRSceneDto): ClaimViewRow[] {
  return scene.claim_check.rows.map((r) => {
    const st = CLAIM_STATUS[r.status]
    return {
      factor: r.factor,
      label: FACTOR_LABELS[r.factor] ?? r.factor,
      claim: r.council_claim
        ? `${r.council_claim.replace('_', ' ').toLowerCase()}${r.council_confidence != null ? ` · ${Math.round(r.council_confidence * 100)}%` : ''}`
        : '—',
      evidence: r.evidence_constraints.length
        ? r.evidence_constraints.map((c) => CONSTRAINT_LABELS[c] ?? c).join(', ')
        : r.status === 'NOT_CHECKABLE' ? 'no CBF margin' : 'none violated',
      evidenceHot: r.implicated_by_geometry,
      status: st.label, statusColor: st.color, statusNote: st.note,
      checkable: r.status !== 'NOT_CHECKABLE',
    }
  })
}
