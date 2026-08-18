import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, Html, Grid, Line } from '@react-three/drei'
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

// ── Types (mirrors GET /api/v1/incidents/ and /vr-scene) ────────────────

interface IncidentSummaryDto {
  incident_id: string
  city: string
  order_id: string
  trigger_type: string
  status: string
  created_at: string
}

interface VRSceneViolation {
  constraint_name: string
  violation_magnitude: number
  required_correction: number
}

interface VRSceneDto {
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
  violations: VRSceneViolation[]
  root_cause_summary: string | null
  systemic_factor_note: string | null
  recommended_action: string | null
}

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

const CONSTRAINT_LABELS: Record<string, string> = {
  min_separation: 'Separation from nearest drone',
  geofence_exclusion: 'DGCA Red Zone geofence',
  battery_reserve_margin: 'Battery reserve for return-to-home',
  altitude_ceiling: 'Assigned altitude ceiling',
  wind_limit: 'Wind speed envelope',
  payload_weight_limit: 'Payload capacity',
  noise_limit: 'Ground noise limit',
  collision_probability: 'Predicted conflict probability',
  comms_link_margin: 'Command/telemetry link margin',
  depot_capacity: 'Destination depot pad availability',
  weather_visibility: 'BVLOS visibility minimum',
}

/** Renders the FROZEN geometry of a single rejected dispatch — the exact
 * origin/destination coordinates and violated-constraint set the Incident
 * Forensics Council's LLM investigation itself reasoned over (frozen_context
 * in aerofleet/data/models/models.py), reconstructed spatially. This is the
 * feature the VR mode toggle exists for: an operator can stand inside the
 * actual rejection geometry and check it, in 3D, against the council's
 * narrative — rather than trusting the text report on faith. See
 * docs/PATENT_NOVELTY.md Claim 4. */
function IncidentGeometry({ scene, center }: { scene: VRSceneDto; center: [number, number] }) {
  const hasOrigin = scene.origin.lat != null && scene.origin.lon != null
  const hasDest = scene.position.lat != null && scene.position.lon != null
  if (!hasDest) return null

  const [dx, dz] = toLocalMeters(scene.position.lat as number, scene.position.lon as number, center[0], center[1])
  const altitude = scene.altitude_m ?? 40
  const maxAltitude = scene.max_altitude_m ?? ALTITUDE_CEILING_M
  const altViolation = scene.violations.find((v) => v.constraint_name === 'altitude_ceiling')
  const geofenceViolation = scene.violations.find((v) => v.constraint_name === 'geofence_exclusion')
  const separationViolation = scene.violations.find((v) => v.constraint_name === 'min_separation')

  const originPoint = hasOrigin
    ? toLocalMeters(scene.origin.lat as number, scene.origin.lon as number, center[0], center[1])
    : null

  return (
    <>
      {originPoint && (
        <>
          <Line
            points={[[originPoint[0], 2, originPoint[1]], [dx, altitude, dz]]}
            color="#7c8288"
            dashed
            dashScale={4}
            lineWidth={1.5}
          />
          <mesh position={[originPoint[0], 3, originPoint[1]]}>
            <cylinderGeometry args={[4, 4, 1.5, 16]} />
            <meshBasicMaterial color="#16A34A" />
          </mesh>
          <Html position={[originPoint[0], 14, originPoint[1]]} center distanceFactor={80} occlude={false}>
            <div style={{
              background: 'rgba(14,15,16,0.9)', border: '1px solid var(--border)', borderRadius: '4px',
              padding: '4px 8px', fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-muted)',
              whiteSpace: 'nowrap', pointerEvents: 'none',
            }}>
              origin depot
            </div>
          </Html>
        </>
      )}

      {/* Vertical rod from ground to the attempted cruise altitude at the
          rejection point — this is the actual number the altitude_ceiling
          constraint checked, not a re-derived approximation. */}
      <Line
        points={[[dx, 0, dz], [dx, altitude, dz]]}
        color={altViolation ? '#DC2626' : '#7c8288'}
        lineWidth={altViolation ? 3 : 1.5}
      />
      <mesh position={[dx, altitude, dz]}>
        <sphereGeometry args={[3, 16, 16]} />
        <meshBasicMaterial color={geofenceViolation ? '#DC2626' : '#EAB308'} />
      </mesh>

      {altViolation && (
        <mesh position={[dx, maxAltitude, dz]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[40, 44, 32]} />
          <meshBasicMaterial color="#DC2626" transparent opacity={0.6} side={THREE.DoubleSide} depthWrite={false} />
        </mesh>
      )}

      {separationViolation && <SeparationSphere radius={MIN_SEPARATION_M} color="#DC2626" />}

      <Html position={[dx, altitude + 20, dz]} center distanceFactor={80} occlude={false}>
        <div style={{
          background: 'rgba(14,15,16,0.94)', border: '1px solid var(--status-red)', borderRadius: '4px',
          padding: '8px 10px', fontFamily: 'var(--font-mono)', fontSize: '11px', color: '#e8e6e1',
          whiteSpace: 'nowrap', pointerEvents: 'none',
        }}>
          <div style={{ fontWeight: 700, color: 'var(--status-red)', marginBottom: '4px' }}>
            REJECTED{scene.drone_id ? ` · ${scene.drone_id}` : ''}
          </div>
          <div>attempted alt {altitude.toFixed(0)}m{maxAltitude ? ` / ceiling ${maxAltitude.toFixed(0)}m` : ''}</div>
        </div>
      </Html>
    </>
  )
}

/** Drones can be several km from the city center (Phase P allows up to a
 * ~20km bounds radius), so the camera starts wide enough to cover a
 * realistic flight envelope by default — the user pans/zooms/orbits from
 * there via OrbitControls, same "explore it yourself" pattern as the
 * existing 2D Airspace Map, rather than the view trying to auto-chase
 * whatever's currently flying.
 *
 * In Incident Replay, a single rejection's geometry sits wherever that
 * order's real destination was — often nowhere near the city-wide default
 * framing above, and easily just off in the dark with nothing to orbit
 * toward. `focus` re-centers the camera on the incident's own midpoint
 * whenever the selected incident changes, with a tighter offset than the
 * live wide-area default. */
function CameraFraming({ focus }: { focus: [number, number, number] }) {
  const controlsRef = useRef<any>(null)
  const { camera } = useThree()
  const isReplay = focus[0] !== 0 || focus[1] !== 0 || focus[2] !== 0

  useEffect(() => {
    const offset: [number, number, number] = isReplay ? [350, 260, 350] : [900, 700, 900]
    camera.position.set(focus[0] + offset[0], focus[1] + offset[1], focus[2] + offset[2])
    camera.lookAt(focus[0], focus[1], focus[2])
    if (controlsRef.current) {
      controlsRef.current.target.set(focus[0], focus[1], focus[2])
      controlsRef.current.update()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus[0], focus[1], focus[2]])

  return <OrbitControls ref={controlsRef} target={focus} />
}

function Scene({
  drones, zones, center, replayScene,
}: {
  drones: Record<string, LiveDrone>
  zones: ZoneDto[]
  center: [number, number]
  replayScene?: VRSceneDto | null
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

  const focusPoint = useMemo<[number, number, number]>(() => {
    if (!replayScene || replayScene.position.lat == null || replayScene.position.lon == null) return [0, 0, 0]
    const [dx, dz] = toLocalMeters(replayScene.position.lat, replayScene.position.lon, center[0], center[1])
    if (replayScene.origin.lat != null && replayScene.origin.lon != null) {
      const [ox, oz] = toLocalMeters(replayScene.origin.lat, replayScene.origin.lon, center[0], center[1])
      return [(dx + ox) / 2, 25, (dz + oz) / 2]
    }
    return [dx, 25, dz]
  }, [replayScene, center])

  return (
    <>
      <ambientLight intensity={0.6} />
      <directionalLight position={[100, 200, 100]} intensity={0.8} />

      <Grid args={[8000, 8000]} cellColor="#2a2c2e" sectionColor="#3a3c3e" fadeDistance={6000} infiniteGrid position={[0, -1, 0]} />
      <AltitudeCeiling span={8000} />

      {zones.map((z) => <GeofenceZone key={z.zone_id} zone={z} center={center} />)}

      {replayScene ? (
        <IncidentGeometry scene={replayScene} center={center} />
      ) : (
        Object.entries(drones).map(([id, d], i) => (
          <DroneMarker key={id} droneId={id} position={dronePositions[i]} drone={d} />
        ))
      )}

      <CameraFraming focus={focusPoint} />
    </>
  )
}

// ── Page ──────────────────────────────────────────────────────────────

const xrStore = createXRStore()

/** Floating HTML overlay (outside the Canvas — plain DOM, not drei's <Html>)
 * carrying the Incident Forensics Council's own text findings alongside the
 * 3D replay, so an operator can read the AI's claimed root cause right next
 * to the frozen geometry it's claiming happened, rather than having to
 * cross-reference a separate page from memory. */
function IncidentBriefingPanel({ scene }: { scene: VRSceneDto }) {
  return (
    <div style={{
      position: 'absolute', top: '16px', right: '16px', width: '320px', maxHeight: 'calc(100% - 32px)',
      overflowY: 'auto', background: 'rgba(14,15,16,0.94)', border: '1px solid var(--border)',
      borderRadius: '6px', padding: '14px 16px', fontFamily: 'var(--font-mono)', fontSize: '11px',
      color: '#e8e6e1', zIndex: 5,
    }}>
      <div style={{ fontWeight: 700, marginBottom: '2px' }}>{scene.incident_id}</div>
      <div style={{ color: 'var(--text-muted)', marginBottom: '10px' }}>
        {scene.trigger_type} &middot; investigation {scene.status}
      </div>

      <div style={{ fontWeight: 700, color: 'var(--status-red)', marginBottom: '4px' }}>Violated constraints</div>
      {scene.violations.length === 0 && <div style={{ color: 'var(--text-muted)', marginBottom: '10px' }}>none recorded</div>}
      {scene.violations.map((v) => (
        <div key={v.constraint_name} style={{ marginBottom: '8px' }}>
          <div>{CONSTRAINT_LABELS[v.constraint_name] || v.constraint_name}</div>
          <div style={{ color: 'var(--text-muted)' }}>
            margin breach {v.violation_magnitude.toFixed(2)} &middot; est. correction {v.required_correction.toFixed(1)}
          </div>
        </div>
      ))}

      {scene.root_cause_summary && (
        <>
          <div style={{ fontWeight: 700, marginTop: '10px', marginBottom: '4px' }}>Council's root cause</div>
          <div style={{ color: 'var(--text-muted)', marginBottom: '10px' }}>{scene.root_cause_summary}</div>
        </>
      )}

      {scene.recommended_action && (
        <>
          <div style={{ fontWeight: 700, marginBottom: '4px' }}>Recommended action</div>
          <div style={{ color: 'var(--text-muted)', marginBottom: '10px' }}>{scene.recommended_action}</div>
        </>
      )}

      <div style={{ borderTop: '1px solid var(--border)', marginTop: '10px', paddingTop: '10px', color: 'var(--text-muted)' }}>
        Walk the geometry above and confirm it actually matches this claim before trusting it —
        that check is the reason this view exists.
      </div>
    </div>
  )
}

export default function VRSafetyView() {
  const { apiUrl } = useAppStore()
  const [city, setCity] = useState('pune')
  const [cities, setCities] = useState<CityDto[]>([])
  const [margins, setMargins] = useState<LiveMarginsDto | null>(null)
  const [zones, setZones] = useState<ZoneDto[]>([])
  const [error, setError] = useState<string | null>(null)

  const [mode, setMode] = useState<'live' | 'replay'>('live')
  const [incidents, setIncidents] = useState<IncidentSummaryDto[]>([])
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>('')
  const [vrScene, setVrScene] = useState<VRSceneDto | null>(null)

  useEffect(() => {
    fetch(`${apiUrl}/api/v1/cities/`).then((r) => r.json()).then(setCities).catch(() => {})
  }, [apiUrl])

  useEffect(() => {
    fetch(`${apiUrl}/api/v1/geofence/zones?city=${city}`).then((r) => r.json()).then(setZones).catch(() => {})
  }, [apiUrl, city])

  useEffect(() => {
    if (mode !== 'live') return
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
  }, [apiUrl, city, mode])

  useEffect(() => {
    if (mode !== 'replay') return
    fetch(`${apiUrl}/api/v1/incidents/?city=${city}&trigger_type=CBF_REJECTION`, { headers: authHeaders() })
      .then((r) => {
        if (!r.ok) throw new Error(r.status === 401 ? 'Not signed in — incident history requires auth' : `HTTP ${r.status}`)
        return r.json()
      })
      .then((list: IncidentSummaryDto[]) => {
        setIncidents(list)
        setError(null)
        setSelectedIncidentId((prev) => (list.some((i) => i.incident_id === prev) ? prev : (list[0]?.incident_id || '')))
      })
      .catch((e) => { setIncidents([]); setError(String(e.message || e)) })
  }, [apiUrl, city, mode])

  useEffect(() => {
    if (mode !== 'replay' || !selectedIncidentId) { setVrScene(null); return }
    fetch(`${apiUrl}/api/v1/incidents/${selectedIncidentId}/vr-scene`, { headers: authHeaders() })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((d) => { setVrScene(d); setError(null) })
      .catch((e) => { setVrScene(null); setError(String(e.message || e)) })
  }, [apiUrl, selectedIncidentId, mode])

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
            {mode === 'live' ? (
              <>Live CBF constraint margins rendered in stereoscopic 3D — real depth cues for judging near-boundary separation that a flat screen collapses &middot; {droneCount} active flight{droneCount === 1 ? '' : 's'}</>
            ) : (
              <>Incident Replay — walk the frozen rejection geometry to verify the Forensics Council's narrative against the real numbers</>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ display: 'flex', gap: '4px' }}>
            <button className={`btn ${mode === 'live' ? 'btn--primary' : ''}`} onClick={() => setMode('live')}>Live</button>
            <button className={`btn ${mode === 'replay' ? 'btn--primary' : ''}`} onClick={() => setMode('replay')}>Incident Replay</button>
          </div>
          {mode === 'replay' && (
            <select
              className="form-select"
              value={selectedIncidentId}
              onChange={(e) => setSelectedIncidentId(e.target.value)}
            >
              {incidents.length === 0 && <option value="">No CBF-rejection incidents yet</option>}
              {incidents.map((i) => (
                <option key={i.incident_id} value={i.incident_id}>
                  {i.incident_id} &middot; {new Date(i.created_at).toLocaleString()}
                </option>
              ))}
            </select>
          )}
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

      {mode === 'live' && droneCount === 0 && (
        <div className="card" style={{ margin: '0 24px 12px' }}>
          <span style={{ color: 'var(--text-muted)' }}>
            No active flights right now — dispatch an order from the Dispatch Console to see live safety margins here.
            Geofence zones still render below.
          </span>
        </div>
      )}

      {mode === 'replay' && incidents.length === 0 && (
        <div className="card" style={{ margin: '0 24px 12px' }}>
          <span style={{ color: 'var(--text-muted)' }}>
            No CBF-rejection incidents recorded yet for {city} — dispatch an order into a red zone or over the
            altitude ceiling from the Dispatch Console to generate one.
          </span>
        </div>
      )}

      {mode === 'replay' && vrScene && vrScene.position.lat == null && (
        <div className="card" style={{ margin: '0 24px 12px', borderColor: 'var(--status-amber)' }}>
          <span style={{ color: 'var(--text-muted)' }}>
            This incident predates coordinate capture in frozen_context and has no geometry to replay —
            pick a more recent one, or dispatch a new rejected order.
          </span>
        </div>
      )}

      <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
        <Canvas camera={{ position: [900, 700, 900], fov: 55, near: 0.1, far: 40000 }} style={{ background: '#0e0f10' }}>
          <XR store={xrStore}>
            <Scene
              drones={mode === 'live' ? (margins?.drones || {}) : {}}
              zones={zones}
              center={center}
              replayScene={mode === 'replay' ? vrScene : null}
            />
          </XR>
        </Canvas>
        {mode === 'replay' && vrScene && vrScene.position.lat != null && <IncidentBriefingPanel scene={vrScene} />}
      </div>
    </div>
  )
}
