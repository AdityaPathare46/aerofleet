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

  const rows: TagRow[] = scene.violations.map((v) => ({
    label: 'FAIL',
    value: `${CONSTRAINT_LABELS[v.constraint_name] ?? v.constraint_name}  −${v.violation_magnitude.toFixed(1)}${CONSTRAINT_UNITS[v.constraint_name] ? ' ' + CONSTRAINT_UNITS[v.constraint_name] : ''}`,
    color: C.bad,
  }))
  rows.push({ label: 'ALT', value: `${Math.round(alt)} m attempted / ceiling ${Math.round(ceiling)} m`, color: altBreach ? C.bad : C.textDim })
  if (scene.in_red_zone) rows.push({ label: 'ZONE', value: 'destination inside DGCA red zone', color: C.bad })
  else if (scene.in_yellow_zone) rows.push({ label: 'ZONE', value: 'destination in airport permission zone', color: C.warn })

  const ringR = 0.03
  return (
    <group>
      {oGround && oCruise && (
        <>
          <mesh position={[oGround[0], 0.003, oGround[2]]}>
            <cylinderGeometry args={[0.013, 0.013, 0.005, 6]} />
            <meshStandardMaterial color={C.ok} emissive={C.ok} emissiveIntensity={0.3} />
          </mesh>
          <Label position={[oGround[0], 0.02, oGround[2]]} text="origin depot" color={C.ok} size={0.0085} />
          <Line points={[oGround, oCruise, dest]} color={C.accent} lineWidth={1.6} dashed dashSize={0.01} gapSize={0.006} />
          <Label position={[(oCruise[0] + dest[0]) / 2, oCruise[1] + 0.014, (oCruise[2] + dest[2]) / 2]}
            text="planned leg — straight-line; the flown path isn't in the frozen record" color={C.textFaint} size={0.0068} />
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
