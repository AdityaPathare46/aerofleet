import { Line } from '@react-three/drei'
import * as THREE from 'three'
import { Diorama, toLocal } from './geo'
import { Label, Tag, TagRow } from './Tag'
import { C, CONSTRAINT_LABELS, CONSTRAINT_UNITS, FONT } from './theme'
import type { VRSceneDto } from './types'

/** Where the replay should centre and how much ground it needs to show. */
export function replayFrame(scene: VRSceneDto, cityCenter: [number, number]): { east: number; north: number; extentM: number } | null {
  if (scene.position.lat == null || scene.position.lon == null) return null
  const [de, dn] = toLocal(scene.position.lat, scene.position.lon, cityCenter)
  if (scene.origin.lat == null || scene.origin.lon == null) return { east: de, north: dn, extentM: 700 }
  const [oe, on] = toLocal(scene.origin.lat, scene.origin.lon, cityCenter)
  const span = Math.hypot(de - oe, dn - on)
  return { east: (de + oe) / 2, north: (dn + on) / 2, extentM: Math.min(Math.max(span * 0.75, 600), 6000) }
}

type Waypoint = [number, number, number, number, number]  // lat, lon, altitude_m, in_red_zone, battery_margin_wh

/** Why a waypoint fails the gate, or null: no-fly zone, battery margin below zero, or above the ceiling. */
function failure(w: Waypoint, ceilingM: number | null): string | null {
  if (w[3] > 0.5) return 'route enters a DGCA no-fly zone here'
  if (w[4] < 0) return `battery reserve exhausted here (${Math.round(w[4])} Wh)`
  if (ceilingM != null && w[2] > ceilingM + 1e-6) return `above the ${Math.round(ceilingM)} m ceiling from here (${Math.round(w[2])} m)`
  return null
}

/** The gate reports a violation per failing waypoint; group them per constraint, keeping the worst. */
export function groupViolations(vs: VRSceneDto['violations']) {
  const by = new Map<string, { constraint_name: string; violation_magnitude: number; waypoints: number }>()
  for (const v of vs) {
    const g = by.get(v.constraint_name)
    if (!g) by.set(v.constraint_name, { constraint_name: v.constraint_name, violation_magnitude: v.violation_magnitude, waypoints: 1 })
    else { g.waypoints += 1; g.violation_magnitude = Math.max(g.violation_magnitude, v.violation_magnitude) }
  }
  return [...by.values()]
}

/** The route the CBF gate actually checked: climb at the depot, each waypoint at its assigned
 *  altitude, descent at the destination. Runs of failing waypoints (no-fly zone, or battery margin
 *  below zero) are red, and the first failing waypoint is marked with the reason. */
function CheckedRoute({ route, ceilingM, d, cityCenter }: {
  route: Waypoint[]; ceilingM: number | null; d: Diorama; cityCenter: [number, number]
}) {
  const fails = (w: Waypoint) => failure(w, ceilingM) != null
  const pt = (w: Waypoint, alt = w[2]) => {
    const [e, n] = toLocal(w[0], w[1], cityCenter)
    return d.point(e, n, alt)
  }
  const runs: { bad: boolean; pts: [number, number, number][] }[] = []
  let start = 0
  for (let i = 1; i <= route.length; i++) {
    if (i < route.length && fails(route[i]) === fails(route[start])) continue
    runs.push({ bad: fails(route[start]), pts: route.slice(Math.max(start - 1, 0), i).map((w) => pt(w)) })
    start = i
  }
  const first = route[0], last = route[route.length - 1]
  const failAt = route.findIndex(fails)
  const mid = pt(route[Math.floor(route.length / 2)])
  return (
    <group>
      <mesh position={pt(first, 0).map((v, i) => (i === 1 ? 0.003 : v)) as [number, number, number]}>
        <cylinderGeometry args={[0.013, 0.013, 0.005, 6]} />
        <meshStandardMaterial color={C.ok} emissive={C.ok} emissiveIntensity={0.3} />
      </mesh>
      <Label position={pt(first, 0).map((v, i) => (i === 1 ? 0.02 : v)) as [number, number, number]} text="origin depot" color={C.ok} size={0.0085} />
      <Line points={[pt(first, 0), pt(first)]} color={C.accent} lineWidth={1.4} />
      {runs.filter((r) => r.pts.length >= 2).map((r, i) => (
        <Line key={i} points={r.pts} color={r.bad ? C.bad : C.accent} lineWidth={r.bad ? 3 : 1.8} />
      ))}
      <Line points={[pt(last), pt(last, 0)]} color={C.accent} lineWidth={1.4} />
      {failAt >= 0 && (
        <group position={pt(route[failAt])}>
          <mesh>
            <sphereGeometry args={[0.0055, 16, 16]} />
            <meshBasicMaterial color={C.bad} />
          </mesh>
          <Label position={[0, 0.018, 0]} color={C.bad} size={0.0075}
            text={`${failure(route[failAt], ceilingM)} · waypoint ${failAt + 1} of ${route.length}`} />
        </group>
      )}
      <Label position={[mid[0], mid[1] + 0.03, mid[2]]} text={`route the CBF gate checked · ${route.length} waypoints`} color={C.textDim} size={0.0068} />
    </group>
  )
}

export function ReplayGeometry({ scene, d, cityCenter }: { scene: VRSceneDto; d: Diorama; cityCenter: [number, number] }) {
  if (scene.position.lat == null || scene.position.lon == null) return null
  const [de, dn] = toLocal(scene.position.lat, scene.position.lon, cityCenter)
  const alt = scene.altitude_m ?? 40
  const ceiling = scene.max_altitude_m ?? 100
  const violated = new Set(scene.violations.map((v) => v.constraint_name))
  const altBreach = violated.has('altitude_ceiling')
  const geofence = violated.has('geofence_exclusion') || scene.in_red_zone

  const dest = d.point(de, dn, alt)
  const destGround = d.point(de, dn, 0)
  const origin = scene.origin.lat != null && scene.origin.lon != null
    ? toLocal(scene.origin.lat, scene.origin.lon, cityCenter) : null
  const oGround = origin ? d.point(origin[0], origin[1], 0) : null
  const oCruise = origin ? d.point(origin[0], origin[1], alt) : null

  const rows: TagRow[] = groupViolations(scene.violations).map((v) => ({
    label: 'FAIL',
    value: `${CONSTRAINT_LABELS[v.constraint_name] ?? v.constraint_name}  −${v.violation_magnitude.toFixed(1)}${CONSTRAINT_UNITS[v.constraint_name] ? ' ' + CONSTRAINT_UNITS[v.constraint_name] : ''}`
      + (v.waypoints > 1 ? `  at ${v.waypoints} waypoints` : ''),
    color: C.bad,
  }))
  rows.push({ label: 'ALT', value: `${Math.round(alt)} m attempted / ceiling ${Math.round(ceiling)} m`, color: altBreach ? C.bad : C.textDim })
  if (scene.in_red_zone) rows.push({ label: 'ZONE', value: 'destination inside DGCA red zone', color: C.bad })
  else if (scene.in_yellow_zone) rows.push({ label: 'ZONE', value: 'destination in airport permission zone', color: C.warn })

  const ringR = 0.03
  return (
    <group>
      {scene.planned_route && scene.planned_route.length >= 2 && (
        <CheckedRoute route={scene.planned_route} ceilingM={scene.max_altitude_m} d={d} cityCenter={cityCenter} />
      )}
      {!(scene.planned_route && scene.planned_route.length >= 2) && oGround && oCruise && (
        <>
          <mesh position={[oGround[0], 0.003, oGround[2]]}>
            <cylinderGeometry args={[0.013, 0.013, 0.005, 6]} />
            <meshStandardMaterial color={C.ok} emissive={C.ok} emissiveIntensity={0.3} />
          </mesh>
          <Label position={[oGround[0], 0.02, oGround[2]]} text="origin depot" color={C.ok} size={0.0085} />
          <Line points={[oGround, oCruise, dest]} color={C.accent} lineWidth={1.6} dashed dashSize={0.01} gapSize={0.006} />
          <Label position={[(oCruise[0] + dest[0]) / 2, oCruise[1] + 0.014, (oCruise[2] + dest[2]) / 2]}
            text="planned leg — straight line; this incident predates stored routes" color={C.textFaint} size={0.0068} />
        </>
      )}

      {/* the attempted cruise altitude at the rejection point — the exact number the gate checked */}
      <Line points={[destGround, dest]} color={altBreach ? C.bad : C.textDim} lineWidth={altBreach ? 3 : 1.5} />
      <mesh position={dest}>
        <sphereGeometry args={[0.009, 20, 20]} />
        <meshStandardMaterial color={geofence || altBreach ? C.bad : C.warn} emissive={C.bad} emissiveIntensity={0.5} />
      </mesh>
      <mesh position={[destGround[0], 0.002, destGround[2]]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.012, 0.016, 32]} />
        <meshBasicMaterial color={C.bad} side={THREE.DoubleSide} />
      </mesh>

      {/* legal ceiling at this location */}
      <group position={[dest[0], d.y(ceiling), dest[2]]}>
        <mesh rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[ringR * 0.92, ringR, 48]} />
          <meshBasicMaterial color={altBreach ? C.bad : C.accent} side={THREE.DoubleSide} transparent opacity={0.9} />
        </mesh>
        <mesh rotation={[-Math.PI / 2, 0, 0]}>
          <circleGeometry args={[ringR * 0.92, 48]} />
          <meshBasicMaterial color={altBreach ? C.bad : C.accent} side={THREE.DoubleSide} transparent opacity={0.12} depthWrite={false} />
        </mesh>
        <Label position={[ringR + 0.006, 0, 0]} anchorX="left" text={`ceiling here ${Math.round(ceiling)} m`}
          color={altBreach ? C.bad : C.accent} size={0.0078} font={FONT.mono} />
      </group>

      <Tag position={[dest[0], Math.max(dest[1], d.y(ceiling)) + 0.02, dest[2]]}
        title={`REJECTED${scene.drone_id ? ' · ' + scene.drone_id : ''}`} titleColor={C.bad} rows={rows}
        size={0.0082} accent={C.bad} />
    </group>
  )
}
