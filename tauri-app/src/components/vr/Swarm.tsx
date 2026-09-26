import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Line } from '@react-three/drei'
import * as THREE from 'three'
import { Diorama, fmtDistance, toLocal } from './geo'
import { Label, Tag, TagRow } from './Tag'
import { C, FONT, WARN_BANDS } from './theme'
import type { DronePair, LiveConstants, LiveDrone, PredictedConflict } from './types'

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

const TICK_EVERY_S = 30
const MAX_TICKS = 4

export function clock(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))
  return s >= 60 ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}` : `${s} s`
}

type Traj = [number, number, number, number][]

/** Trajectory position at t seconds from now (linear between samples). */
function atTime(traj: Traj, t: number): [number, number, number] {
  for (let i = 0; i + 1 < traj.length; i++) {
    const a = traj[i], b = traj[i + 1]
    if (t < a[3] || t > b[3]) continue
    const u = b[3] > a[3] ? (t - a[3]) / (b[3] - a[3]) : 0
    return [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u]
  }
  const last = traj[traj.length - 1]
  return [last[0], last[1], last[2]]
}

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

  // 4D trajectory: flown part faint, the part ahead bright, +30 s ticks and touchdown.
  const path = useMemo(() => {
    const pt = (lat: number, lon: number, alt: number) => {
      const [pe, pn] = toLocal(lat, lon, cityCenter)
      return d.point(pe, pn, alt)
    }
    const traj = drone.trajectory ?? []
    if (traj.length >= 2) {
      const last = traj[traj.length - 1]
      return {
        past: traj.filter((p) => p[3] <= 0).map((p) => pt(p[0], p[1], p[2])),
        ahead: traj.filter((p) => p[3] >= 0).map((p) => pt(p[0], p[1], p[2])),
        ticks: Array.from({ length: MAX_TICKS }, (_, i) => (i + 1) * TICK_EVERY_S)
          .filter((t) => t < last[3]).map((t) => ({ t, pos: pt(...atTime(traj, t)) })),
        touchdown: last[3] > 0 ? { pos: pt(last[0], last[1], 0), eta: last[3] } : null,
      }
    }
    // no plan (e.g. LIVE telemetry): remaining route at the current altitude only
    const ahead = drone.route.length >= 2 ? drone.route.map(([lat, lon]) => pt(lat, lon, drone.altitude_m)) : []
    return { past: [], ahead, ticks: [], touchdown: ahead.length ? { pos: ahead[ahead.length - 1], eta: null } : null }
  }, [drone.trajectory, drone.route, drone.altitude_m, d, cityCenter])

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
      const eta = clock(drone.eta_s ?? 0)
      const value = drone.phase === 'CLIMB' ? `climbing to ${Math.round(Math.max(...(drone.trajectory ?? []).map((p) => p[2]), drone.altitude_m))} m`
        : drone.phase === 'DESCENT' ? `descending · lands in ${eta}`
          : drone.phase === 'LANDED' ? 'landed at destination'
            : `${Math.round(drone.progress * 100)} % · ${fmtDistance(drone.remaining_m ?? 0)} left · lands in ${eta}`
      r.push({ label: 'LEG', value, bar: { frac: drone.progress, color: C.accent } })
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
      {path.past.length >= 2 && (
        <Line points={path.past} color={C.accent} lineWidth={0.8} transparent opacity={selected || expanded ? 0.3 : 0.12} />
      )}
      {path.ahead.length >= 2 && (selected || expanded) && (
        <>
          <Line points={path.ahead} color={C.accent} lineWidth={1.6} transparent opacity={0.9} />
          {path.ticks.map(({ t, pos }) => (
            <group key={t} position={pos}>
              <mesh>
                <sphereGeometry args={[0.0021, 10, 10]} />
                <meshBasicMaterial color={C.accent} />
              </mesh>
              <Label position={[0.009, 0.005, 0]} anchorX="left" text={`+${t} s`} color={C.accent} size={0.0058} font={FONT.mono} />
            </group>
          ))}
          {path.touchdown && (
            <group position={[path.touchdown.pos[0], 0.004, path.touchdown.pos[2]]}>
              <mesh>
                <octahedronGeometry args={[0.0055]} />
                <meshBasicMaterial color={C.accent} />
              </mesh>
              <Label position={[0, 0.014, 0]} color={C.accent} size={0.0068}
                text={path.touchdown.eta != null ? `${shortId(id)} lands in ${clock(path.touchdown.eta)}` : `${shortId(id)} destination`} />
            </group>
          )}
        </>
      )}
      {path.ahead.length >= 2 && !(selected || expanded) && (
        <Line points={path.ahead} color={C.accent} lineWidth={0.8} transparent opacity={0.28} />
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

// ── Predicted conflicts (look-ahead over planned trajectories) ─────────

function PredictedConflictMarker({ c, d, cityCenter }: { c: PredictedConflict; d: Diorama; cityCenter: [number, number] }) {
  const conflict = c.severity === 'CONFLICT'
  const color = conflict ? C.bad : C.warn
  const at = (p: [number, number, number]) => {
    const [e, n] = toLocal(p[0], p[1], cityCenter)
    return d.point(e, n, p[2])
  }
  const pa = at(c.a_at), pb = at(c.b_at)
  const mid: [number, number, number] = [(pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2 - 0.014, (pa[2] + pb[2]) / 2]
  return (
    <group>
      {[pa, pb].map((p, i) => (
        <mesh key={i} position={p} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.0075, 0.0095, 28]} />
          <meshBasicMaterial color={color} side={THREE.DoubleSide} />
        </mesh>
      ))}
      <Line points={[pa, pb]} color={color} lineWidth={1.4} />
      {/* below the rings: the space above is where the drones' tags are */}
      <Label position={mid} color={color} size={0.0066} font={FONT.mono}
        text={`${conflict ? 'PREDICTED CONFLICT' : 'near miss'} in ${clock(c.t_s)} · ${Math.round(c.horizontal_m)} m ↔ ↕${Math.round(c.vertical_m)} m`} />
    </group>
  )
}

// ── Swarm root ─────────────────────────────────────────────────────────

export function Swarm({
  drones, pairs, predicted = [], constants, d, cityCenter, selected, onSelect, detailAll,
}: {
  drones: Record<string, LiveDrone>
  pairs: DronePair[]
  predicted?: PredictedConflict[]
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
  const inConflict = new Set(predicted.filter((c) => c.severity === 'CONFLICT').flatMap((c) => [c.a, c.b]))
  const onTable = (p: [number, number, number]) => { const [e, n] = toLocal(p[0], p[1], cityCenter); return d.contains(e, n) }

  return (
    <>
      {Object.entries(drones).map(([id, drone]) => {
        const [e, n] = toLocal(drone.lat, drone.lon, cityCenter)
        if (!d.contains(e, n, d.extentM * 0.02)) return null
        return (
          <Drone key={id} id={id} drone={drone} d={d} cityCenter={cityCenter} pos={pos}
            selected={selected === id} expanded={detailAll || selected === id || droneStatus(drone) !== 'ok' || inConflict.has(id)}
            constants={constants} onSelect={onSelect} />
        )
      })}
      <AwarenessLinks pairs={loose} pos={pos} />
      {close.map((p) => <PairBeam key={`${p.a}|${p.b}`} pair={p} pos={pos} minSep={constants.min_separation_m} />)}
      {predicted.filter((c) => drones[c.a] && drones[c.b] && onTable(c.a_at) && onTable(c.b_at)).map((c) => (
        <PredictedConflictMarker key={`${c.a}|${c.b}`} c={c} d={d} cityCenter={cityCenter} />
      ))}
    </>
  )
}
