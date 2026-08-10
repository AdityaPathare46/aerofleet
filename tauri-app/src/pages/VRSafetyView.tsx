import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Html, Grid } from '@react-three/drei'
import { createXRStore, XR } from '@react-three/xr'
import * as THREE from 'three'
import { useAppStore } from '../store/appStore'

// ── Types (mirrors GET /api/v1/safety/live-margins) ─────────────────────

interface SafetyMargins {
  min_separation: number
  geofence_exclusion: number
  battery_reserve_margin: number
  altitude_ceiling: number
  wind_limit: number
  payload_weight_limit: number
  noise_limit: number
  collision_probability: number
  comms_link_margin: number
  depot_capacity: number
  weather_visibility: number
}

interface LiveDrone {
  lat: number
  lon: number
  link_mode: 'SIMULATED' | 'LIVE'
  safety_margins: SafetyMargins
  passed: boolean
}

interface LiveMarginsDto {
  city: string
  drone_count: number
  drones: Record<string, LiveDrone>
  fleet_worst_case: SafetyMargins
}

interface ZoneDto {
  zone_id: string
  zone_type: 'GREEN' | 'YELLOW' | 'RED'
  center_lat: number
  center_lon: number
  radius_m: number
}

interface AltitudeBandDto { name: string; floor_m: number; ceiling_m: number }
interface CityDto { slug: string; center: [number, number] }

const ZONE_COLORS: Record<string, string> = { RED: '#DC2626', YELLOW: '#EAB308', GREEN: '#16A34A' }
const MIN_SEPARATION_M = 15.0
const ALTITUDE_CEILING_M = 100.0

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('aerofleet_token') || ''
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/** Flat-earth local East/North projection relative to a city center —
 * matches the degree-per-meter approximation already used in
 * TrajectoryViewer.tsx's circlePolygon/squarePolygon helpers. Good enough
 * at city scale; genuine WebXR units are metres, so this keeps a drone's
 * on-screen separation spatially meaningful. */
function toLocalMeters(lat: number, lon: number, centerLat: number, centerLon: number): [number, number] {
  const latRad = (centerLat * Math.PI) / 180
  const north = (lat - centerLat) * 111320
  const east = (lon - centerLon) * 111320 * Math.cos(latRad)
  return [east, north]
}

function marginColor(margin: number, warnAt = 5, dangerAt = 0): string {
  if (margin <= dangerAt) return '#DC2626'
  if (margin <= warnAt) return '#EAB308'
  return '#16A34A'
}

// ── 3D content ────────────────────────────────────────────────────────

function GeofenceZone({ zone, center }: { zone: ZoneDto; center: [number, number] }) {
  const [x, z] = toLocalMeters(zone.center_lat, zone.center_lon, center[0], center[1])
  const color = ZONE_COLORS[zone.zone_type] || '#7c8288'
  return (
    <mesh position={[x, ALTITUDE_CEILING_M / 2, z]}>
      <cylinderGeometry args={[zone.radius_m, zone.radius_m, ALTITUDE_CEILING_M, 32, 1, true]} />
      <meshBasicMaterial color={color} transparent opacity={0.12} side={THREE.DoubleSide} depthWrite={false} />
    </mesh>
  )
}

function AltitudeCeiling({ span }: { span: number }) {
  return (
    <mesh position={[0, ALTITUDE_CEILING_M, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[span, span]} />
      <meshBasicMaterial color="#0D9488" transparent opacity={0.05} side={THREE.DoubleSide} depthWrite={false} />
    </mesh>
  )
}

function SeparationSphere({ radius, color }: { radius: number; color: string }) {
  return (
    <mesh>
      <sphereGeometry args={[radius, 24, 24]} />
      <meshBasicMaterial color={color} transparent opacity={0.18} depthWrite={false} />
    </mesh>
  )
}

function BatteryGauge({ marginWh, maxWh = 500 }: { marginWh: number; maxWh?: number }) {
  const frac = Math.max(0, Math.min(1, marginWh / maxWh))
  const height = 20
  const color = marginColor(marginWh, 50, 0)
  return (
    <group position={[0, 12, 0]}>
      <mesh position={[0, height / 2, 0]}>
        <boxGeometry args={[1.5, height, 1.5]} />
        <meshBasicMaterial color="#2a2c2e" transparent opacity={0.4} />
      </mesh>
      <mesh position={[0, (height * frac) / 2, 0]}>
        <boxGeometry args={[1.8, Math.max(0.3, height * frac), 1.8]} />
        <meshBasicMaterial color={color} />
      </mesh>
    </group>
  )
}

function DroneMarker({
  droneId, position, drone,
}: {
  droneId: string
  position: [number, number, number]
  drone: LiveDrone
}) {
  const meshRef = useRef<THREE.Mesh>(null)
  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.position.y = position[1] + Math.sin(state.clock.elapsedTime * 1.5) * 0.6
    }
  })

  const m = drone.safety_margins
  const sepColor = marginColor(m.min_separation, 10, 0)
  const bodyColor = drone.passed ? '#16A34A' : '#DC2626'

  return (
    <group position={position}>
      <mesh ref={meshRef}>
        <boxGeometry args={[1.2, 0.4, 1.2]} />
        <meshStandardMaterial color={bodyColor} />
      </mesh>
      <SeparationSphere radius={MIN_SEPARATION_M} color={sepColor} />
      <BatteryGauge marginWh={m.battery_reserve_margin} />

      <Html position={[0, 28, 0]} center distanceFactor={80} occlude={false}>
        <div style={{
          background: 'rgba(14,15,16,0.9)', border: '1px solid var(--border)',
          borderRadius: '4px', padding: '8px 10px', fontFamily: 'var(--font-mono)',
          fontSize: '11px', color: '#e8e6e1', whiteSpace: 'nowrap', pointerEvents: 'none',
        }}>
          <div style={{ fontWeight: 700, marginBottom: '4px' }}>{droneId}</div>
          <div>sep {m.min_separation.toFixed(0)}m &middot; alt {m.altitude_ceiling.toFixed(0)}m &middot; batt {m.battery_reserve_margin.toFixed(0)}Wh</div>
          <div style={{ color: 'var(--text-muted)' }}>
            wind {m.wind_limit.toFixed(1)} &middot; noise {m.noise_limit.toFixed(0)} &middot; link {m.comms_link_margin.toFixed(1)}dB &middot; vis {m.weather_visibility.toFixed(0)}m
          </div>
        </div>
      </Html>
    </group>
  )
}

/** Drones can be several km from the city center (Phase P allows up to a
 * ~20km bounds radius), so the camera starts wide enough to cover a
 * realistic flight envelope by default — the user pans/zooms/orbits from
 * there via OrbitControls, same "explore it yourself" pattern as the
 * existing 2D Airspace Map, rather than the view trying to auto-chase
 * whatever's currently flying. */
function CameraFraming() {
  return <OrbitControls target={[0, 0, 0]} />
}

function Scene({
  drones, zones, center,
}: {
  drones: Record<string, LiveDrone>
  zones: ZoneDto[]
  center: [number, number]
}) {
  const dronePositions = useMemo<[number, number, number][]>(
    () =>
      Object.values(drones).map((d) => {
        const [x, z] = toLocalMeters(d.lat, d.lon, center[0], center[1])
        const y = d.safety_margins.altitude_ceiling > 0 ? ALTITUDE_CEILING_M - d.safety_margins.altitude_ceiling : 40
        return [x, y, z]
      }),
    [drones, center]
  )

  return (
    <>
      <ambientLight intensity={0.6} />
      <directionalLight position={[100, 200, 100]} intensity={0.8} />

      <Grid args={[8000, 8000]} cellColor="#2a2c2e" sectionColor="#3a3c3e" fadeDistance={6000} infiniteGrid position={[0, -1, 0]} />
      <AltitudeCeiling span={8000} />

      {zones.map((z) => <GeofenceZone key={z.zone_id} zone={z} center={center} />)}

      {Object.entries(drones).map(([id, d], i) => (
        <DroneMarker key={id} droneId={id} position={dronePositions[i]} drone={d} />
      ))}

      <CameraFraming />
    </>
  )
}

// ── Page ──────────────────────────────────────────────────────────────

const xrStore = createXRStore()

export default function VRSafetyView() {
  const { apiUrl } = useAppStore()
  const [city, setCity] = useState('pune')
  const [cities, setCities] = useState<CityDto[]>([])
  const [margins, setMargins] = useState<LiveMarginsDto | null>(null)
  const [zones, setZones] = useState<ZoneDto[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${apiUrl}/api/v1/cities/`).then((r) => r.json()).then(setCities).catch(() => {})
  }, [apiUrl])

  useEffect(() => {
    fetch(`${apiUrl}/api/v1/geofence/zones?city=${city}`).then((r) => r.json()).then(setZones).catch(() => {})
  }, [apiUrl, city])

  useEffect(() => {
    let cancelled = false
    const poll = () => {
      fetch(`${apiUrl}/api/v1/safety/live-margins?city=${city}`, { headers: authHeaders() })
        .then((r) => r.json())
        .then((d) => { if (!cancelled) { setMargins(d); setError(null) } })
        .catch((e) => { if (!cancelled) setError(String(e)) })
    }
    poll()
    const id = setInterval(poll, 1500)
    return () => { cancelled = true; clearInterval(id) }
  }, [apiUrl, city])

  const center = useMemo<[number, number]>(() => {
    const cfg = cities.find((c) => c.slug === city)
    return cfg ? cfg.center : [18.5204, 73.8567]
  }, [cities, city])

  const droneCount = margins?.drone_count ?? 0

  return (
    <div style={{ overflow: 'hidden', flex: 1, display: 'flex', flexDirection: 'column' }}>
      <div className="page-header">
        <div>
          <div className="page-title">VR Safety View</div>
          <div className="page-subtitle">
            Live CBF constraint margins rendered spatially &middot; {droneCount} active flight{droneCount === 1 ? '' : 's'}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <select className="form-select" value={city} onChange={(e) => setCity(e.target.value)}>
            {cities.length === 0 && <option value="pune">Pune</option>}
            {cities.map((c) => <option key={c.slug} value={c.slug}>{c.slug}</option>)}
          </select>
          <button
            id="btn-enter-vr"
            className="btn btn--primary"
            onClick={() => xrStore.enterVR().catch((e) => setError(`WebXR unavailable: ${e}`))}
          >
            Enter VR
          </button>
        </div>
      </div>

      {error && (
        <div className="card" style={{ margin: '0 24px 12px', borderColor: 'var(--status-red)' }}>
          <span style={{ color: 'var(--status-red)' }}>&#9888; {error}</span>
        </div>
      )}

      {droneCount === 0 && (
        <div className="card" style={{ margin: '0 24px 12px' }}>
          <span style={{ color: 'var(--text-muted)' }}>
            No active flights right now — dispatch an order from the Dispatch Console to see live safety margins here.
            Geofence zones still render below.
          </span>
        </div>
      )}

      <div style={{ flex: 1, minHeight: 0 }}>
        <Canvas camera={{ position: [900, 700, 900], fov: 55, near: 0.1, far: 40000 }} style={{ background: '#0e0f10' }}>
          <XR store={xrStore}>
            <Scene drones={margins?.drones || {}} zones={zones} center={center} />
          </XR>
        </Canvas>
      </div>
    </div>
  )
}
