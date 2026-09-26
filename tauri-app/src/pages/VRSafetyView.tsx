import React, { Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { createXRStore, useXR, XR } from '@react-three/xr'
import { useAppStore } from '../store/appStore'
import SignInCard from '../components/SignInCard'
import { Diorama, toLocal } from '../components/vr/geo'
import { AltitudeRuler, Ceilings, Depots, ScaleAndNorth, Streets, Table, Zones } from '../components/vr/Airspace'
import { Buildings } from '../components/vr/Buildings'
import { HeadsetLauncher } from '../components/vr/HeadsetLauncher'
import { Swarm } from '../components/vr/Swarm'
import { ClaimPanel, FleetPanel, ViewControls } from '../components/vr/Panels'
import { ReplayGeometry, replayFrame } from '../components/vr/Replay'
import { LiveBoard, ReplayBoard } from '../components/vr/HtmlBoards'
import { UIMode } from '../components/vr/uiMode'
import { C } from '../components/vr/theme'
import type {
  BuildingsDto, CityDto, DepotDto, IncidentSummaryDto, LiveMarginsDto, RoadsDto, VRSceneDto, ZoneDto,
} from '../components/vr/types'

/*
 * VR Safety View — a world-in-miniature supervision table for the drone fleet.
 *
 * Why VR at all (docs/VR_RESEARCH_REFERENCES.md):
 *  1. Swarm separation is a 3D judgment. Two drones over the same street at different altitude
 *     bands are one dot on a 2D map; stereo depth + head parallax separates them.
 *  2. Incident Replay: the AI council's incident explanations need checking — on the 1,000-case
 *     benchmark its factor attribution scored macro-F1 0.47 — and the check is spatial: does the
 *     narrative match the rejection geometry? Every claim is tested against the CBF numbers here.
 *  3. A table-top miniature (Stoakley et al., CHI '95) gives the whole ops area at a glance and
 *     lets an operator walk around it — on a Quest 3 in mixed reality it sits on a real desk.
 */

const xrStore = createXRStore()

const TABLE_HALF = 0.7
const XR_TABLE_Z = -0.8

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('aerofleet_token') || ''
  return token ? { Authorization: `Bearer ${token}` } : {}
}

class AuthError extends Error {}

async function getJson<T>(url: string, auth = false): Promise<T> {
  const r = await fetch(url, { headers: auth ? authHeaders() : {} })
  if (r.status === 401) throw new AuthError('Not signed in')
  if (!r.ok) throw new Error(`HTTP ${r.status} from ${url.replace(/^https?:\/\/[^/]+/, '')}`)
  return r.json()
}

// ── 3D scene ─────────────────────────────────────────────────────────

function Room() {
  // Only in immersive VR: a floor for grounding. In MR the real room is the backdrop.
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]}>
        <circleGeometry args={[6, 64]} />
        <meshStandardMaterial color={C.floor} roughness={1} />
      </mesh>
      <gridHelper args={[12, 24, '#15263D', '#0E1B2E']} position={[0, 0.001, 0]} />
    </group>
  )
}

interface SceneProps {
  mode: 'live' | 'replay'
  live: LiveMarginsDto | null
  scene: VRSceneDto | null
  zones: ZoneDto[]
  depots: DepotDto[]
  roads: RoadsDto | null
  buildings: BuildingsDto | null
  onBuildingStats: (drawn: number, measured: number) => void
  cityCenter: [number, number]
  cityName: string
  diorama: Diorama
  selected: string | null
  setSelected: (id: string | null) => void
  controls: ViewControls
  rotationDeg: number
  tableHeight: number
  ageS: number | null
}

function SceneContent(p: SceneProps) {
  const xrMode = useXR((s) => s.mode)
  const inXR = xrMode != null
  const isAR = xrMode === 'immersive-ar'
  const legal = p.live?.constants.legal_ceiling_m ?? 120
  const ops = p.live?.constants.operational_ceiling_m ?? 100
  const controls = { ...p.controls, inXR }

  return (
    <UIMode.Provider value={{ inXR }}>
      {!isAR && <color attach="background" args={[C.void]} />}
      <ambientLight intensity={0.55} />
      <hemisphereLight args={['#9CC3FF', '#0A1220', 0.5]} />
      <directionalLight position={[1.5, 3, 2]} intensity={1.1} />

      {inXR && !isAR && <Room />}

      <group position={inXR ? [0, p.tableHeight, XR_TABLE_Z] : [0, 0, 0]}>
        <group rotation={[0, (p.rotationDeg * Math.PI) / 180, 0]}>
          <Table d={p.diorama} showPlinth={inXR && !isAR} />
          {p.roads && <Streets roads={p.roads} d={p.diorama} cityCenter={p.cityCenter} />}
          {p.buildings && p.controls.showBuildings && (
            <Buildings data={p.buildings} d={p.diorama} cityCenter={p.cityCenter} onStats={p.onBuildingStats} />
          )}
          <Zones zones={p.zones} d={p.diorama} cityCenter={p.cityCenter} />
          <Ceilings d={p.diorama} opsCeilingM={ops} legalCeilingM={legal} />
          <Depots depots={p.depots} d={p.diorama} cityCenter={p.cityCenter} />
          <AltitudeRuler d={p.diorama} />
          <ScaleAndNorth d={p.diorama} />
          {p.mode === 'live' && p.live && (
            <Swarm drones={p.live.drones} pairs={p.live.pairs} predicted={p.live.predicted_conflicts ?? []} constants={p.live.constants} d={p.diorama}
              cityCenter={p.cityCenter} selected={p.selected} detailAll={p.controls.detailAll}
              onSelect={(id) => p.setSelected(p.selected === id ? null : id)} />
          )}
          {p.mode === 'replay' && p.scene && <ReplayGeometry scene={p.scene} d={p.diorama} cityCenter={p.cityCenter} />}
        </group>

        {/* In a headset the boards are in-world (HTML can't render there); on desktop they're
            HTML overlays rendered by the page instead. */}
        {inXR && (
          <group position={[0, p.mode === 'live' ? 0.5 : 0.52, -TABLE_HALF - 0.18]} rotation={[-0.12, 0, 0]} scale={1.35}>
            {p.mode === 'live'
              ? <FleetPanel data={p.live} cityName={p.cityName} ageS={p.ageS} vExag={p.diorama.vExag} controls={controls} />
              : p.scene && <ClaimPanel scene={p.scene} controls={controls} />}
          </group>
        )}
      </group>

      {!inXR && (
        <OrbitControls makeDefault target={[0, 0.16, -0.22]} minDistance={0.45} maxDistance={3.2}
          maxPolarAngle={Math.PI * 0.47} enableDamping dampingFactor={0.08} zoomSpeed={1.4} />
      )}
    </UIMode.Provider>
  )
}

// ── page ─────────────────────────────────────────────────────────────

export default function VRSafetyView() {
  const { apiUrl } = useAppStore()
  const [city, setCity] = useState('pune')
  const [cities, setCities] = useState<CityDto[]>([])
  const [zones, setZones] = useState<ZoneDto[]>([])
  const [depots, setDepots] = useState<DepotDto[]>([])
  const [roads, setRoads] = useState<RoadsDto | null>(null)
  const [buildings, setBuildings] = useState<BuildingsDto | null>(null)
  const [showBuildings, setShowBuildings] = useState(true)
  const [buildingStats, setBuildingStats] = useState<{ drawn: number; measured: number } | null>(null)
  const onBuildingStats = useCallback((drawn: number, measured: number) => setBuildingStats({ drawn, measured }), [])
  const [live, setLive] = useState<LiveMarginsDto | null>(null)
  const [lastFetch, setLastFetch] = useState<number | null>(null)
  const [now, setNow] = useState(Date.now())
  const [error, setError] = useState<string | null>(null)
  const [needsAuth, setNeedsAuth] = useState(false)
  const [authNonce, setAuthNonce] = useState(0)

  const [mode, setMode] = useState<'live' | 'replay'>('live')
  const [incidents, setIncidents] = useState<IncidentSummaryDto[]>([])
  const [selectedIncidentId, setSelectedIncidentId] = useState('')
  const [scene, setScene] = useState<VRSceneDto | null>(null)

  const [rangeKm, setRangeKm] = useState(4)
  const [detailAll, setDetailAll] = useState(false)
  const [rotationDeg, setRotationDeg] = useState(0)
  const [tableHeight, setTableHeight] = useState(0.82)
  const [selected, setSelected] = useState<string | null>(null)
  const [focus, setFocus] = useState<[number, number]>([0, 0])
  const [xrSupport, setXrSupport] = useState<{ vr: boolean; ar: boolean }>({ vr: false, ar: false })

  const onAuthError = useCallback((e: unknown) => {
    if (e instanceof AuthError) { setNeedsAuth(true); return true }
    return false
  }, [])

  useEffect(() => {
    const xr = (navigator as Navigator & { xr?: { isSessionSupported: (m: string) => Promise<boolean> } }).xr
    if (!xr) return
    Promise.all([xr.isSessionSupported('immersive-vr'), xr.isSessionSupported('immersive-ar')])
      .then(([vr, ar]) => setXrSupport({ vr, ar })).catch(() => {})
  }, [])

  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(t) }, [])

  useEffect(() => { getJson<CityDto[]>(`${apiUrl}/api/v1/cities/`).then(setCities).catch(() => {}) }, [apiUrl])

  useEffect(() => {
    setRoads(null)
    getJson<ZoneDto[]>(`${apiUrl}/api/v1/geofence/zones?city=${city}`).then(setZones).catch(() => setZones([]))
    getJson<DepotDto[]>(`${apiUrl}/api/v1/fleet/depots?city=${city}`).then(setDepots).catch(() => setDepots([]))
    getJson<RoadsDto>(`${apiUrl}/api/v1/cities/${city}/roads`).then(setRoads).catch(() => {})
    setBuildings(null)
    setBuildingStats(null)
    getJson<BuildingsDto>(`${apiUrl}/api/v1/cities/${city}/buildings`).then((b) => setBuildings(b.available ? b : null)).catch(() => {})
  }, [apiUrl, city])

  useEffect(() => {
    if (mode !== 'live') return
    let cancelled = false
    const poll = () => getJson<LiveMarginsDto>(`${apiUrl}/api/v1/safety/live-margins?city=${city}`, true)
      .then((d) => { if (!cancelled) { setLive(d); setLastFetch(Date.now()); setError(null); setNeedsAuth(false) } })
      .catch((e) => { if (!cancelled && !onAuthError(e)) setError(String((e as Error).message || e)) })
    poll()
    const id = setInterval(poll, 1500)
    return () => { cancelled = true; clearInterval(id) }
  }, [apiUrl, city, mode, authNonce, onAuthError])

  useEffect(() => {
    if (mode !== 'replay') return
    getJson<IncidentSummaryDto[]>(`${apiUrl}/api/v1/incidents/?city=${city}&trigger_type=CBF_REJECTION`, true)
      .then((list) => {
        setIncidents(list)
        setError(null)
        setNeedsAuth(false)
        setSelectedIncidentId((prev) => (list.some((i) => i.incident_id === prev) ? prev : (list[0]?.incident_id || '')))
      })
      .catch((e) => { setIncidents([]); if (!onAuthError(e)) setError(String((e as Error).message || e)) })
  }, [apiUrl, city, mode, authNonce, onAuthError])

  useEffect(() => {
    if (mode !== 'replay' || !selectedIncidentId) { setScene(null); return }
    getJson<VRSceneDto>(`${apiUrl}/api/v1/incidents/${selectedIncidentId}/vr-scene`, true)
      .then((d) => { setScene(d); setError(null) })
      .catch((e) => { setScene(null); if (!onAuthError(e)) setError(String((e as Error).message || e)) })
  }, [apiUrl, selectedIncidentId, mode, authNonce, onAuthError])

  const cityCfg = cities.find((c) => c.slug === city)
  const cityCenter = useMemo<[number, number]>(() => cityCfg?.center ?? [18.5204, 73.8567], [cityCfg])
  const cityName = cityCfg?.name?.split(',')[0] ?? city

  // Zooming in to 1-2 km re-centres on the selected drone (a snapshot, so the table
  // doesn't swim every poll); the 4 km view always shows the whole operating area.
  const selectDrone = useCallback((id: string | null) => {
    setSelected(id)
    const drone = id && live?.drones[id]
    if (drone && rangeKm < 4) setFocus(toLocal(drone.lat, drone.lon, cityCenter))
  }, [live, rangeKm, cityCenter])

  const changeRange = useCallback((km: number) => {
    setRangeKm(km)
    const drone = selected && live?.drones[selected]
    setFocus(km < 4 && drone ? toLocal(drone.lat, drone.lon, cityCenter) : [0, 0])
  }, [selected, live, cityCenter])

  const diorama = useMemo(() => {
    const legal = live?.constants.legal_ceiling_m ?? 120
    if (mode === 'replay' && scene) {
      const f = replayFrame(scene, cityCenter)
      if (f) return new Diorama(f.east, f.north, f.extentM, TABLE_HALF, 0.32, legal)
    }
    return new Diorama(focus[0], focus[1], rangeKm * 1000, TABLE_HALF, 0.32, legal)
  }, [mode, scene, cityCenter, focus, rangeKm, live?.constants.legal_ceiling_m])

  const controls: ViewControls = {
    rangeKm, setRangeKm: changeRange, detailAll, setDetailAll,
    rotate: (deg) => setRotationDeg((r) => r + deg), inXR: false,
    nudgeHeight: (dy) => setTableHeight((h) => Math.min(1.3, Math.max(0.5, h + dy))),
    showBuildings, setShowBuildings,
    buildingNote: showBuildings && buildings && buildingStats
      ? ` · ${buildingStats.drawn.toLocaleString()} OSM buildings: ${buildingStats.measured.toLocaleString()} with a tagged height (light), `
        + `the rest drawn at an assumed ${buildings.assumed_height_m} m (dark)`
      : '',
  }

  const ageS = lastFetch ? (now - lastFetch) / 1000 : null
  const droneCount = live?.drone_count ?? 0
  const noXR = !xrSupport.vr && !xrSupport.ar

  return (
    <div style={{ overflow: 'hidden', flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
      <div className="page-header">
        <div>
          <div className="page-title">VR Safety View</div>
          <div className="page-subtitle">
            {mode === 'live'
              ? <>Walk-around tabletop of the live airspace — {droneCount} airborne · separation, altitude and battery for every drone, in stereo depth</>
              : <>Incident Replay — every AI council claim checked against the real rejection geometry</>}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: 4 }}>
            <button className={`btn ${mode === 'live' ? 'btn--primary' : ''}`} onClick={() => setMode('live')}>Live swarm</button>
            <button className={`btn ${mode === 'replay' ? 'btn--primary' : ''}`} onClick={() => setMode('replay')}>Incident replay</button>
          </div>
          {mode === 'replay' && (
            <select className="form-select" style={{ width: 'auto', maxWidth: 300 }} value={selectedIncidentId} onChange={(e) => setSelectedIncidentId(e.target.value)}>
              {incidents.length === 0 && <option value="">No CBF-rejection incidents yet</option>}
              {incidents.map((i) => (
                <option key={i.incident_id} value={i.incident_id}>{i.incident_id} · {new Date(i.created_at).toLocaleString()}</option>
              ))}
            </select>
          )}
          <select className="form-select" style={{ width: 'auto' }} value={city} onChange={(e) => { setCity(e.target.value); setSelected(null); setFocus([0, 0]) }}>
            {cities.length === 0 && <option value="pune">pune</option>}
            {cities.map((c) => <option key={c.slug} value={c.slug}>{c.name?.split(',')[0] ?? c.slug}</option>)}
          </select>
          <HeadsetLauncher apiUrl={apiUrl} city={city} mode={mode} incidentId={selectedIncidentId} />
          <button className="btn btn--primary" id="btn-enter-vr"
            title={xrSupport.vr ? 'Enter immersive VR' : 'No headset detected — open this page in the Quest 3 browser (see docs/VR_QUEST3_GUIDE.md)'}
            onClick={() => xrStore.enterVR().catch((e) => setError(`WebXR VR unavailable: ${e}`))}>
            Enter VR
          </button>
          <button className="btn" id="btn-enter-mr"
            title={xrSupport.ar ? 'Mixed reality: the table appears in your real room (Quest 3 passthrough)' : 'Mixed reality needs a passthrough headset such as Quest 3'}
            onClick={() => xrStore.enterAR().catch((e) => setError(`WebXR mixed reality unavailable: ${e}`))}>
            Enter MR
          </button>
        </div>
      </div>

      {needsAuth ? (
        <SignInCard apiUrl={apiUrl} reason="The live swarm feed and incident history need an authenticated session."
          onSignedIn={() => { setNeedsAuth(false); setAuthNonce((n) => n + 1) }} />
      ) : (
        <>
          {error && (
            <div className="card" style={{ margin: '0 24px 12px', borderColor: 'var(--status-red)' }}>
              <span style={{ color: 'var(--status-red)' }}>&#9888; {error}</span>
            </div>
          )}
          {mode === 'live' && live && droneCount === 0 && (
            <div className="card" style={{ margin: '0 24px 12px' }}>
              <span style={{ color: 'var(--text-secondary)' }}>
                No drones airborne in {cityName} — dispatch orders from the Dispatch Console (or run
                <code style={{ margin: '0 4px' }}>python tools/seed_demo_swarm.py</code>) to populate the swarm.
              </span>
            </div>
          )}
          {mode === 'replay' && incidents.length === 0 && (
            <div className="card" style={{ margin: '0 24px 12px' }}>
              <span style={{ color: 'var(--text-secondary)' }}>
                No CBF-rejection incidents recorded for {cityName} yet — a dispatch into a red zone or above the ceiling creates one.
              </span>
            </div>
          )}
          {mode === 'replay' && scene && scene.position.lat == null && (
            <div className="card" style={{ margin: '0 24px 12px', borderColor: 'var(--status-amber)' }}>
              <span style={{ color: 'var(--text-secondary)' }}>
                This incident predates coordinate capture and has no geometry to replay — pick a more recent one.
              </span>
            </div>
          )}

          <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
            <Canvas
              camera={{ position: [0, 1.12, 1.55], fov: 42, near: 0.01, far: 60 }}
              gl={{ antialias: true, alpha: true }}
              dpr={[1, 2]}
              style={{ background: C.void }}
            >
              <XR store={xrStore}>
                <Suspense fallback={null}>
                  <SceneContent
                    mode={mode} live={live} scene={scene} zones={zones} depots={depots} roads={roads}
                    buildings={buildings} onBuildingStats={onBuildingStats}
                    cityCenter={cityCenter} cityName={cityName} diorama={diorama} selected={selected}
                    setSelected={selectDrone} controls={controls} rotationDeg={rotationDeg}
                    tableHeight={tableHeight} ageS={ageS}
                  />
                </Suspense>
              </XR>
            </Canvas>
            {mode === 'live' && (
              <LiveBoard data={live} cityName={cityName} ageS={ageS} vExag={diorama.vExag} controls={controls} />
            )}
            {mode === 'replay' && scene && scene.position.lat != null && <ReplayBoard scene={scene} />}
            <div style={{
              position: 'absolute', right: 16, bottom: 14, textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 11,
              color: '#93A8C4', pointerEvents: 'none', lineHeight: 1.6,
            }}>
              drag to orbit · scroll to zoom · click a drone for its full data block
              {noXR && <><br />no WebXR headset detected — on a Quest 3, open this page in the Quest Browser (docs/VR_QUEST3_GUIDE.md)</>}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
