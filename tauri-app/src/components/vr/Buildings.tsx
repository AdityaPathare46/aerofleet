import { useEffect, useMemo } from 'react'
import * as THREE from 'three'
import { Diorama, toLocal } from './geo'
import type { BuildingsDto } from './types'

// The real city in 3D: OSM footprints extruded on the same vertical scale as the drones, so a
// cruise altitude reads directly against the towers under it. Heights tagged in OSM are light;
// untagged buildings sit at the stated assumed height and are dark — never mistaken for a survey.
// Same data and colours as the headset viewer (Unity BuildingsView).

const COLORS = {
  measured: { wall: '#5C7394', roof: '#A9BCD6' },
  assumed: { wall: '#1F2C40', roof: '#2D3D55' },
}

interface Layer { walls: number[]; roofs: number[] }

function buildLayers(data: BuildingsDto, d: Diorama, cityCenter: [number, number]) {
  const [offE, offN] = toLocal(data.center[0], data.center[1], cityCenter)
  const assumedIdx = data.sources.indexOf('assumed')
  const layers: Record<'measured' | 'assumed', Layer> = { measured: { walls: [], roofs: [] }, assumed: { walls: [], roofs: [] } }
  let drawn = 0, measured = 0
  for (const b of data.buildings) {
    const ring: THREE.Vector2[] = []
    let inside = true
    for (let i = 2; i + 1 < b.length; i += 2) {
      const e = b[i] + offE, n = b[i + 1] + offN
      if (!d.contains(e, n)) { inside = false; break }
      ring.push(new THREE.Vector2(d.x(e), d.z(n)))
    }
    if (!inside || ring.length < 3) continue
    const h = d.y(b[0] / 10)
    const layer = b[1] === assumedIdx ? layers.assumed : layers.measured
    for (let i = 0; i < ring.length; i++) {
      const a = ring[i], c = ring[(i + 1) % ring.length]
      layer.walls.push(a.x, 0, a.y, c.x, 0, c.y, c.x, h, c.y, a.x, 0, a.y, c.x, h, c.y, a.x, h, a.y)
    }
    for (const [i, j, k] of THREE.ShapeUtils.triangulateShape(ring, [])) {
      layer.roofs.push(ring[i].x, h, ring[i].y, ring[j].x, h, ring[j].y, ring[k].x, h, ring[k].y)
    }
    drawn++
    if (b[1] !== assumedIdx) measured++
  }
  return { layers, drawn, measured }
}

function geometry(positions: number[]): THREE.BufferGeometry {
  const g = new THREE.BufferGeometry()
  g.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  return g
}

export function Buildings({ data, d, cityCenter, onStats }: {
  data: BuildingsDto; d: Diorama; cityCenter: [number, number]
  onStats?: (drawn: number, measured: number) => void
}) {
  const built = useMemo(() => {
    const { layers, drawn, measured } = buildLayers(data, d, cityCenter)
    const meshes = (['assumed', 'measured'] as const).flatMap((kind) => [
      { key: `${kind}-w`, geom: geometry(layers[kind].walls), color: COLORS[kind].wall },
      { key: `${kind}-r`, geom: geometry(layers[kind].roofs), color: COLORS[kind].roof },
    ])
    return { meshes, drawn, measured }
  }, [data, d, cityCenter])

  useEffect(() => { onStats?.(built.drawn, built.measured) }, [built, onStats])
  useEffect(() => () => built.meshes.forEach((m) => m.geom.dispose()), [built])

  return (
    <group>
      {built.meshes.map((m) => (
        <mesh key={m.key} geometry={m.geom}>
          {/* flat shading derives face normals in the shader; double-sided so winding never hides a face */}
          <meshStandardMaterial color={m.color} flatShading side={THREE.DoubleSide} roughness={0.85} metalness={0.05} />
        </mesh>
      ))}
    </group>
  )
}
