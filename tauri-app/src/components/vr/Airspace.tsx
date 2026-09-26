import { useMemo } from 'react'
import { Line } from '@react-three/drei'
import * as THREE from 'three'
import { Diorama, fmtDistance, niceScaleBar, toLocal } from './geo'
import { Label } from './Tag'
import { C, FONT } from './theme'
import type { DepotDto, RoadsDto, ZoneDto } from './types'

const ALTITUDE_BANDS = [
  { name: 'LOW', floor: 0, ceiling: 60, color: '#3B82F6' },
  { name: 'MID', floor: 60, ceiling: 80, color: '#8B5CF6' },
  { name: 'HIGH', floor: 80, ceiling: 100, color: '#EC4899' },
]
const REDUCED_CEILING_NEAR_AIRPORT_M = 60

// ── Table ──────────────────────────────────────────────────────────────

export function Table({ d, showPlinth }: { d: Diorama; showPlinth: boolean }) {
  const H = d.tableHalf
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[H * 2, H * 2]} />
        <meshStandardMaterial color={C.table} roughness={0.92} metalness={0.05} />
      </mesh>
      {/* bezel */}
      {[
        [0, -0.012, H + 0.02, H * 2 + 0.08, 0.04],
        [0, -0.012, -H - 0.02, H * 2 + 0.08, 0.04],
      ].map(([x, y, z, w, dpt], i) => (
        <mesh key={`bz${i}`} position={[x, y, z]}>
          <boxGeometry args={[w, 0.028, dpt]} />
          <meshStandardMaterial color={C.bezel} roughness={0.6} metalness={0.3} />
        </mesh>
      ))}
      {[
        [H + 0.02, -0.012, 0],
        [-H - 0.02, -0.012, 0],
      ].map(([x, y, z], i) => (
        <mesh key={`bs${i}`} position={[x, y, z]}>
          <boxGeometry args={[0.04, 0.028, H * 2]} />
          <meshStandardMaterial color={C.bezel} roughness={0.6} metalness={0.3} />
        </mesh>
      ))}
      <lineSegments position={[0, 0.0015, 0]}>
        <edgesGeometry args={[new THREE.PlaneGeometry(H * 2, H * 2).rotateX(-Math.PI / 2)]} />
        <lineBasicMaterial color={C.tableEdge} />
      </lineSegments>
      {showPlinth && (
        <mesh position={[0, -0.41, 0]}>
          <boxGeometry args={[H * 2 + 0.04, 0.78, H * 2 + 0.04]} />
          <meshStandardMaterial color={C.floor} roughness={0.8} metalness={0.2} />
        </mesh>
      )}
    </group>
  )
}

// ── Streets ────────────────────────────────────────────────────────────

function roadGeometry(polylines: number[][], d: Diorama): THREE.BufferGeometry {
  const pts: number[] = []
  const pad = -d.extentM * 0.002
  for (const flat of polylines) {
    for (let i = 0; i + 3 < flat.length; i += 2) {
      const e1 = flat[i], n1 = flat[i + 1], e2 = flat[i + 2], n2 = flat[i + 3]
      if (!d.contains(e1, n1, pad) || !d.contains(e2, n2, pad)) continue
      pts.push(d.x(e1), 0, d.z(n1), d.x(e2), 0, d.z(n2))
    }
  }
  const g = new THREE.BufferGeometry()
  g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3))
  return g
}

export function Streets({ roads, d, cityCenter }: { roads: RoadsDto; d: Diorama; cityCenter: [number, number] }) {
  // Roads are served relative to the city center; the diorama may be focused elsewhere.
  const [offE, offN] = toLocal(roads.center[0], roads.center[1], cityCenter)
  const shifted = useMemo(
    () => new Diorama(d.focusEast - offE, d.focusNorth - offN, d.extentM, d.tableHalf, d.columnHeight, d.legalCeilingM),
    [d, offE, offN],
  )
  const minor = useMemo(() => roadGeometry(roads.minor, shifted), [roads, shifted])
  const major = useMemo(() => roadGeometry(roads.major, shifted), [roads, shifted])
  return (
    <group position={[0, 0.0008, 0]}>
      <lineSegments geometry={minor}>
        <lineBasicMaterial color={C.roadMinor} transparent opacity={0.85} />
      </lineSegments>
      <lineSegments geometry={major} position={[0, 0.0003, 0]}>
        <lineBasicMaterial color={C.roadMajor} />
      </lineSegments>
    </group>
  )
}

// ── Geofence zones: exact (circle ∩ table) prisms ─────────────────────

type P2 = [number, number]

function clipToSquare(poly: P2[], h: number): P2[] {
  const edges: [(p: P2) => boolean, (a: P2, b: P2) => P2][] = [
    [(p) => p[0] >= -h, (a, b) => { const t = (-h - a[0]) / (b[0] - a[0]); return [-h, a[1] + t * (b[1] - a[1])] }],
    [(p) => p[0] <= h, (a, b) => { const t = (h - a[0]) / (b[0] - a[0]); return [h, a[1] + t * (b[1] - a[1])] }],
    [(p) => p[1] >= -h, (a, b) => { const t = (-h - a[1]) / (b[1] - a[1]); return [a[0] + t * (b[0] - a[0]), -h] }],
    [(p) => p[1] <= h, (a, b) => { const t = (h - a[1]) / (b[1] - a[1]); return [a[0] + t * (b[0] - a[0]), h] }],
  ]
  let out = poly
  for (const [inside, cut] of edges) {
    const input = out
    out = []
    for (let i = 0; i < input.length; i++) {
      const cur = input[i], prev = input[(i + input.length - 1) % input.length]
      if (inside(cur)) {
        if (!inside(prev)) out.push(cut(prev, cur))
        out.push(cur)
      } else if (inside(prev)) {
        out.push(cut(prev, cur))
      }
    }
    if (!out.length) break
  }
  return out
}

function Zone({ zone, d, cityCenter }: { zone: ZoneDto; d: Diorama; cityCenter: [number, number] }) {
  const isRed = zone.zone_type === 'RED'
  const color = isRed ? C.zoneRed : C.zoneYellow
  // A red zone prohibits the whole column; a yellow (airport-vicinity) zone caps flight at 60 m.
  const topM = isRed ? d.legalCeilingM : REDUCED_CEILING_NEAR_AIRPORT_M
  const [ce, cn] = toLocal(zone.center_lat, zone.center_lon, cityCenter)

  const built = useMemo(() => {
    const r = zone.radius_m * d.scale
    const cx = d.x(ce), cz = d.z(cn)
    const circle: P2[] = Array.from({ length: 96 }, (_, i) => {
      const a = (i / 96) * Math.PI * 2
      return [cx + Math.cos(a) * r, cz + Math.sin(a) * r]
    })
    const poly = clipToSquare(circle, d.tableHalf - 0.0005)
    if (poly.length < 3) return null
    // Shape is in (x, -z) so the extrusion (along +z, rotated up) keeps orientation.
    const shape = new THREE.Shape(poly.map(([x, z]) => new THREE.Vector2(x, -z)))
    const height = d.y(topM)
    const volume = new THREE.ExtrudeGeometry(shape, { depth: height, bevelEnabled: false })
    volume.rotateX(-Math.PI / 2)
    const outline = (y: number): [number, number, number][] => [...poly, poly[0]].map(([x, z]) => [x, y, z])
    // Label sits over the zone centre if it's on the table, else at the clipped centroid.
    const onTable = Math.abs(cx) < d.tableHalf && Math.abs(cz) < d.tableHalf
    const cxm = onTable ? cx : poly.reduce((s, p) => s + p[0], 0) / poly.length
    const czm = onTable ? cz : poly.reduce((s, p) => s + p[1], 0) / poly.length
    return { volume, ground: outline(0.0012), top: outline(height), height, labelAt: [cxm, height + 0.02, czm] as [number, number, number] }
  }, [zone, d, ce, cn, topM])

  if (!built) return null
  const title = isRed ? 'NO-FLY ZONE' : `PERMISSION ZONE · ceiling ${REDUCED_CEILING_NEAR_AIRPORT_M} m`
  return (
    <group>
      <mesh geometry={built.volume} renderOrder={2}>
        <meshBasicMaterial color={color} transparent opacity={isRed ? 0.13 : 0.035} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
      <Line points={built.ground} color={color} lineWidth={1.6} />
      <Line points={built.top} color={color} lineWidth={1} transparent opacity={0.7} />
      <Label position={built.labelAt} text={title} color={color} size={0.0095} font={FONT.display} />
      {zone.reason && (
        <Label position={[built.labelAt[0], built.labelAt[1] - 0.014, built.labelAt[2]]}
          text={zone.reason.length > 48 ? zone.reason.slice(0, 46) + '…' : zone.reason} color={C.textDim} size={0.0072} />
      )}
    </group>
  )
}

export function Zones({ zones, d, cityCenter }: { zones: ZoneDto[]; d: Diorama; cityCenter: [number, number] }) {
  // Yellow first so red volumes (more important) draw over them.
  const ordered = [...zones].filter((z) => z.zone_type !== 'GREEN').sort((a) => (a.zone_type === 'RED' ? 1 : -1))
  return <>{ordered.map((z) => <Zone key={z.zone_id} zone={z} d={d} cityCenter={cityCenter} />)}</>
}

// ── Ceilings, altitude ruler, scale bar, north arrow ────────────────────

export function Ceilings({ d, opsCeilingM, legalCeilingM }: { d: Diorama; opsCeilingM: number; legalCeilingM: number }) {
  const H = d.tableHalf
  const planes = [
    { m: opsCeilingM, label: `AeroFleet ops ceiling · ${opsCeilingM} m`, color: C.accent, opacity: 0.035 },
    { m: legalCeilingM, label: `DGCA legal limit · ${legalCeilingM} m AGL`, color: C.bad, opacity: 0.03 },
  ]
  return (
    <>
      {planes.map((p) => (
        <group key={p.m} position={[0, d.y(p.m), 0]}>
          <mesh rotation={[-Math.PI / 2, 0, 0]} renderOrder={1}>
            <planeGeometry args={[H * 2, H * 2]} />
            <meshBasicMaterial color={p.color} transparent opacity={p.opacity} side={THREE.DoubleSide} depthWrite={false} />
          </mesh>
          <lineSegments>
            <edgesGeometry args={[new THREE.PlaneGeometry(H * 2, H * 2).rotateX(-Math.PI / 2)]} />
            <lineBasicMaterial color={p.color} transparent opacity={0.55} />
          </lineSegments>
          <Label position={[H - 0.01, 0.009, H]} text={p.label} color={p.color} size={0.0085} anchorX="right" />
        </group>
      ))}
    </>
  )
}

export function AltitudeRuler({ d }: { d: Diorama }) {
  const H = d.tableHalf
  const x = -H - 0.055, z = H
  const ticks = [0, 60, 80, 100, 120]
  return (
    <group position={[x, 0, z]}>
      {ALTITUDE_BANDS.map((b) => (
        <mesh key={b.name} position={[0, (d.y(b.floor) + d.y(b.ceiling)) / 2, 0]}>
          <boxGeometry args={[0.006, d.y(b.ceiling) - d.y(b.floor), 0.006]} />
          <meshBasicMaterial color={b.color} />
        </mesh>
      ))}
      <mesh position={[0, (d.y(100) + d.y(120)) / 2, 0]}>
        <boxGeometry args={[0.004, d.y(120) - d.y(100), 0.004]} />
        <meshBasicMaterial color={C.textFaint} />
      </mesh>
      {ticks.map((m) => (
        <group key={m} position={[0, d.y(m), 0]}>
          <mesh>
            <boxGeometry args={[0.018, 0.0012, 0.0012]} />
            <meshBasicMaterial color={C.text} />
          </mesh>
          <Label position={[-0.014, 0, 0]} text={`${m} m`} color={C.textDim} size={0.0072} anchorX="right" font={FONT.mono} />
        </group>
      ))}
      {ALTITUDE_BANDS.map((b) => (
        <Label key={`l${b.name}`} position={[0.014, (d.y(b.floor) + d.y(b.ceiling)) / 2, 0]} text={b.name}
          color={b.color} size={0.0072} anchorX="left" font={FONT.mono} />
      ))}
      <Label position={[0, -0.018, 0]} text={`vertical ×${d.vExag.toFixed(0)}`} color={C.textFaint} size={0.0068} font={FONT.mono} />
    </group>
  )
}

export function ScaleAndNorth({ d }: { d: Diorama }) {
  const H = d.tableHalf
  const barM = niceScaleBar(d.extentM)
  const barW = barM * d.scale
  const x0 = H - 0.04 - barW
  const z = H + 0.06
  return (
    <group>
      <group position={[x0, 0.002, z]}>
        <mesh position={[barW / 2, 0, 0]}>
          <boxGeometry args={[barW, 0.002, 0.004]} />
          <meshBasicMaterial color={C.text} />
        </mesh>
        {[0, barW].map((xx) => (
          <mesh key={xx} position={[xx, 0.004, 0]}>
            <boxGeometry args={[0.0015, 0.01, 0.004]} />
            <meshBasicMaterial color={C.text} />
          </mesh>
        ))}
        <Label position={[barW / 2, 0.016, 0]} text={fmtDistance(barM)} color={C.text} size={0.0085} font={FONT.mono} />
      </group>
      <group position={[0, 0.003, -H - 0.06]}>
        <mesh rotation={[-Math.PI / 2, 0, 0]}>
          <coneGeometry args={[0.012, 0.03, 3]} />
          <meshBasicMaterial color={C.accent} />
        </mesh>
        <Label position={[0, 0.02, 0]} text="N" color={C.accent} size={0.013} font={FONT.display} />
      </group>
    </group>
  )
}

export function Depots({ depots, d, cityCenter }: { depots: DepotDto[]; d: Diorama; cityCenter: [number, number] }) {
  return (
    <>
      {depots.filter((p) => p.lat != null && p.lon != null).map((p) => {
        const [e, n] = toLocal(p.lat as number, p.lon as number, cityCenter)
        if (!d.contains(e, n)) return null
        const [x, , z] = d.point(e, n)
        return (
          <group key={p.depot_id} position={[x, 0, z]}>
            <mesh position={[0, 0.002, 0]}>
              <cylinderGeometry args={[0.011, 0.011, 0.004, 6]} />
              <meshStandardMaterial color={C.depot} emissive={C.depot} emissiveIntensity={0.25} />
            </mesh>
            <Label position={[0, 0.016, 0]} text={p.name.replace('Micro-Depot', 'Depot')} color={C.depot} size={0.0075} />
          </group>
        )
      })}
    </>
  )
}
