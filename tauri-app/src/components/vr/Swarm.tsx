import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Line } from '@react-three/drei'
import * as THREE from 'three'
import { Diorama, fmtDistance, toLocal } from './geo'
import { Label, Tag, TagRow } from './Tag'
import { C, FONT, WARN_BANDS } from './theme'
import type { DronePair, LiveConstants, LiveDrone } from './types'

type PosMap = React.MutableRefObject<Record<string, THREE.Vector3>>
export type DroneStatus = 'ok' | 'watch' | 'violation'

const G = 0.02 // drone symbol span in metres — a symbol, not to scale (stated in the legend)

export function droneStatus(drone: LiveDrone): DroneStatus {
  if (!drone.passed) return 'violation'
  for (const [name, band] of Object.entries(WARN_BANDS)) {
    const m = drone.safety_margins[name]
    if (m !== undefined && m < band) return 'watch'
  }
  return 'ok'
}

export const STATUS_COLOR: Record<DroneStatus, string> = { ok: C.ok, watch: C.warn, violation: C.bad }

function shortId(id: string): string {
  return id.length > 10 ? id.slice(-8) : id
}

// ── Drone glyph ────────────────────────────────────────────────────────

function QuadGlyph({ color, selected }: { color: string; selected: boolean }) {
  const rotors = useRef<THREE.Group>(null)
  const light = useRef<THREE.MeshBasicMaterial>(null)
  useFrame((state, dt) => {
    rotors.current?.children.forEach((r, i) => { r.rotation.y += dt * (i % 2 ? 38 : -38) })
    if (light.current) light.current.opacity = 0.55 + 0.45 * Math.sin(state.clock.elapsedTime * 5)
  })
  const tips: [number, number][] = [[0.36, 0.36], [-0.36, 0.36], [0.36, -0.36], [-0.36, -0.36]]
  return (
    <group>
      <mesh>
        <boxGeometry args={[0.3 * G, 0.12 * G, 0.34 * G]} />
        <meshStandardMaterial color="#D9E3EF" metalness={0.5} roughness={0.35} />
      </mesh>
      {[Math.PI / 4, -Math.PI / 4].map((a) => (
        <mesh key={a} rotation={[0, a, 0]}>
          <boxGeometry args={[1.02 * G, 0.045 * G, 0.06 * G]} />
          <meshStandardMaterial color="#9FB0C6" metalness={0.4} roughness={0.45} />
        </mesh>
      ))}
      <group ref={rotors}>
        {tips.map(([x, z]) => (
          <group key={`${x}${z}`} position={[x * G, 0.07 * G, z * G]}>
            <mesh>
              <boxGeometry args={[0.42 * G, 0.012 * G, 0.05 * G]} />
              <meshBasicMaterial color="#C8D6E8" />
            </mesh>
          </group>
        ))}
      </group>
      {tips.map(([x, z]) => (
        <mesh key={`d${x}${z}`} position={[x * G, 0.07 * G, z * G]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.17 * G, 0.22 * G, 20]} />
          <meshBasicMaterial color={color} transparent opacity={0.8} side={THREE.DoubleSide} />
        </mesh>
      ))}
      {/* nose: points along heading */}
      <mesh position={[0, 0, -0.3 * G]} rotation={[-Math.PI / 2, 0, 0]}>
        <coneGeometry args={[0.07 * G, 0.18 * G, 10]} />
        <meshBasicMaterial color={color} />
      </mesh>
      <mesh position={[0, 0.09 * G, 0]}>
        <sphereGeometry args={[0.05 * G, 10, 10]} />
        <meshBasicMaterial ref={light} color={color} transparent />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02 * G, 0]}>
        <ringGeometry args={[0.62 * G, (selected ? 0.78 : 0.7) * G, 40]} />
        <meshBasicMaterial color={selected ? C.text : color} transparent opacity={selected ? 1 : 0.75} side={THREE.DoubleSide} />
      </mesh>
    </group>
  )
}

function Drone({
  id, drone, d, cityCenter, pos, selected, expanded, constants, onSelect,
}: {
  id: string
  drone: LiveDrone
  d: Diorama
  cityCenter: [number, number]
  pos: PosMap
  selected: boolean
  expanded: boolean
  constants: LiveConstants
  onSelect: (id: string) => void
}) {
  const status = droneStatus(drone)
  const color = STATUS_COLOR[status]
  const [e, n] = toLocal(drone.lat, drone.lon, cityCenter)
  const target = useMemo(() => new THREE.Vector3(...d.point(e, n, drone.altitude_m)), [d, e, n, drone.altitude_m])

  const group = useRef<THREE.Group>(null)
  const stem = useRef<THREE.Mesh>(null)
  const shadow = useRef<THREE.Mesh>(null)
  const placed = useRef(false)
  useFrame((_, dt) => {
    const g = group.current
    if (!g) return
    if (!placed.current || g.position.distanceTo(target) > 0.3) g.position.copy(target)
    else g.position.lerp(target, 1 - Math.exp(-dt * 2.5))
    placed.current = true
    pos.current[id] = g.position
    const h = Math.max(g.position.y, 0.0001)
    if (stem.current) { stem.current.scale.y = h; stem.current.position.y = -h / 2 }
    if (shadow.current) shadow.current.position.y = -h + 0.0012
  })

  const route = useMemo(() => {
    if (drone.route.length < 2) return null
    return drone.route.map(([lat, lon]) => {
      const [re, rn] = toLocal(lat, lon, cityCenter)
      return d.point(re, rn, drone.altitude_m)
    })
  }, [drone.route, drone.altitude_m, d, cityCenter])
  const dest = route ? route[route.length - 1] : null

  const rows = useMemo<TagRow[]>(() => {
    const legal = constants.legal_ceiling_m
    const ceil = drone.altitude_ceiling_m
    const usable = drone.battery_available_wh + drone.battery_reserve_wh
    const capacity = drone.battery_soc_pct > 0 ? usable / (drone.battery_soc_pct / 100) : 0
    const reserveFrac = capacity > 0 ? drone.battery_reserve_wh / capacity : 0
    const sepH = drone.nearest_horizontal_m
    const hasNeighbour = drone.nearest_drone_id != null
    const r: TagRow[] = [
      {
        label: 'ALT', value: `${Math.round(drone.altitude_m)} m / ${Math.round(ceil)}`,
        bar: { frac: drone.altitude_m / legal, mark: ceil / legal, color: sepColor(ceil - drone.altitude_m, WARN_BANDS.altitude_ceiling) },
      },
      {
        label: 'BATT', value: `${Math.round(drone.battery_soc_pct)} %  ${Math.round(drone.battery_available_wh)} Wh`,
        bar: { frac: drone.battery_soc_pct / 100, mark: reserveFrac, color: sepColor(drone.battery_available_wh, WARN_BANDS.battery_reserve_margin) },
      },
      hasNeighbour
        ? {
          label: 'SEP', value: `${fmtDistance(sepH)} → ${shortId(drone.nearest_drone_id as string)} ↕${Math.round(drone.nearest_vertical_m)}m`,
          bar: { frac: sepH / (constants.min_separation_m * 4), mark: 0.25, color: sepColor(sepH - constants.min_separation_m, WARN_BANDS.min_separation) },
        }
        : { label: 'SEP', value: 'no other drone airborne', color: C.textDim },
    ]
    if (drone.progress != null) {
      r.push({
        label: 'LEG', value: drone.arrived ? 'arrived · holding' : `${Math.round(drone.progress * 100)} % · ${fmtDistance(drone.remaining_m ?? 0)} left`,
        bar: { frac: drone.progress, color: C.accent },
      })
    }
    r.push({
      label: 'SRC',
      value: drone.position_source === 'TELEMETRY' ? 'live MAVLink' : drone.position_source === 'ROUTE_DEAD_RECKONING' ? 'sim · on route' : 'sim · at depot',
      color: C.textDim,
    })
    return r
  }, [drone, constants])

  const title = expanded ? `${shortId(id)}  ${drone.state.replace('_', ' ')}` : shortId(id)
  const headingRad = drone.heading_deg != null ? -(drone.heading_deg * Math.PI) / 180 : 0

  return (
    <>
      {/* position is driven only by useFrame (lerp toward `target`) — a position prop would
          snap it back on every data poll and defeat the smoothing */}
      <group ref={group}>
        <group rotation={[0, headingRad, 0]} onClick={(ev) => { ev.stopPropagation(); onSelect(id) }}>
          <QuadGlyph color={color} selected={selected} />
          {/* generous invisible hit target — controller rays and mouse both need it */}
          <mesh visible={false}>
            <sphereGeometry args={[G * 0.9, 8, 8]} />
          </mesh>
        </group>
        <mesh ref={stem}>
          <cylinderGeometry args={[0.0007, 0.0007, 1, 6]} />
          <meshBasicMaterial color={color} transparent opacity={0.55} />
        </mesh>
        <mesh ref={shadow} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.003, 0.0055, 20]} />
          <meshBasicMaterial color={color} transparent opacity={0.9} side={THREE.DoubleSide} />
        </mesh>
        <Tag
          position={[0, G * 0.9, 0]}
          title={title}
          titleColor={expanded ? color : C.text}
          rows={expanded ? rows : []}
          size={expanded ? 0.0095 : 0.0082}
          accent={color}
          onClick={() => onSelect(id)}
        />
      </group>
      {route && (selected || expanded) && (
        <>
          <Line points={route} color={C.accent} lineWidth={1.4} dashed dashSize={0.008} gapSize={0.005} transparent opacity={0.8} />
          {dest && (
            <group position={[dest[0], 0.004, dest[2]]}>
              <mesh>
                <octahedronGeometry args={[0.0055]} />
                <meshBasicMaterial color={C.accent} />
              </mesh>
              {selected && <Label position={[0, 0.014, 0]} text={`${shortId(id)} destination`} color={C.accent} size={0.0068} />}
            </group>
          )}
        </>
      )}
      {route && !(selected || expanded) && (
        <Line points={route} color={C.accent} lineWidth={0.8} transparent opacity={0.28} />
      )}
    </>
  )
}

function sepColor(margin: number, warnBand: number): string {
  if (margin < 0) return C.bad
  if (margin < warnBand) return C.warn
  return C.ok
}

// ── Pair separation ────────────────────────────────────────────────────

function PairBeam({ pair, pos, minSep }: { pair: DronePair; pos: PosMap; minSep: number }) {
  const beam = useRef<THREE.Mesh>(null)
  const label = useRef<THREE.Group>(null)
  const tmp = useMemo(() => ({ mid: new THREE.Vector3(), dir: new THREE.Vector3(), up: new THREE.Vector3(0, 1, 0) }), [])
  const critical = pair.separation_margin_m < 0
  const color = critical ? C.bad : C.warn
  useFrame(() => {
    const a = pos.current[pair.a], b = pos.current[pair.b]
    if (!a || !b || !beam.current) return
    tmp.mid.addVectors(a, b).multiplyScalar(0.5)
    tmp.dir.subVectors(b, a)
    const len = tmp.dir.length()
    beam.current.position.copy(tmp.mid)
    beam.current.scale.set(1, Math.max(len, 1e-5), 1)
    if (len > 1e-6) beam.current.quaternion.setFromUnitVectors(tmp.up, tmp.dir.normalize())
    label.current?.position.set(tmp.mid.x, tmp.mid.y + 0.012, tmp.mid.z)
  })
  return (
    <>
      <mesh ref={beam}>
        <cylinderGeometry args={[critical ? 0.0012 : 0.0008, critical ? 0.0012 : 0.0008, 1, 6]} />
        <meshBasicMaterial color={color} transparent opacity={0.95} />
      </mesh>
      <group ref={label}>
        <Label position={[0, 0, 0]} font={FONT.mono} size={0.0068} color={color}
          text={`${Math.round(pair.horizontal_m)} m ↔  ↕${Math.round(pair.vertical_m)} m${critical ? `  < ${minSep} m min` : ''}`} />
      </group>
    </>
  )
}

function AwarenessLinks({ pairs, pos }: { pairs: DronePair[]; pos: PosMap }) {
  const geom = useMemo(() => {
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(pairs.length * 6), 3))
    return g
  }, [pairs])
  useFrame(() => {
    const attr = geom.getAttribute('position') as THREE.BufferAttribute
    pairs.forEach((p, i) => {
      const a = pos.current[p.a], b = pos.current[p.b]
      if (!a || !b) return
      attr.setXYZ(i * 2, a.x, a.y, a.z)
      attr.setXYZ(i * 2 + 1, b.x, b.y, b.z)
    })
    attr.needsUpdate = true
    geom.computeBoundingSphere()
  })
  return (
    <lineSegments geometry={geom}>
      <lineBasicMaterial color={C.accent} transparent opacity={0.35} />
    </lineSegments>
  )
}

// ── Swarm root ─────────────────────────────────────────────────────────

export function Swarm({
  drones, pairs, constants, d, cityCenter, selected, onSelect, detailAll,
}: {
  drones: Record<string, LiveDrone>
  pairs: DronePair[]
  constants: LiveConstants
  d: Diorama
  cityCenter: [number, number]
  selected: string | null
  onSelect: (id: string) => void
  detailAll: boolean
}) {
  const pos = useRef<Record<string, THREE.Vector3>>({})
  const watchBand = WARN_BANDS.min_separation
  const close = pairs.filter((p) => p.separation_margin_m < watchBand)
  const loose = pairs.filter((p) => p.separation_margin_m >= watchBand)

  return (
    <>
      {Object.entries(drones).map(([id, drone]) => {
        const [e, n] = toLocal(drone.lat, drone.lon, cityCenter)
        if (!d.contains(e, n, d.extentM * 0.02)) return null
        return (
          <Drone key={id} id={id} drone={drone} d={d} cityCenter={cityCenter} pos={pos}
            selected={selected === id} expanded={detailAll || selected === id || droneStatus(drone) !== 'ok'}
            constants={constants} onSelect={onSelect} />
        )
      })}
      <AwarenessLinks pairs={loose} pos={pos} />
      {close.map((p) => <PairBeam key={`${p.a}|${p.b}`} pair={p} pos={pos} minSep={constants.min_separation_m} />)}
    </>
  )
}
