import React, { Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { createXRStore, useXR, XR } from '@react-three/xr'
import { useAppStore } from '../store/appStore'
import SignInCard from '../components/SignInCard'
import { Diorama, toLocal } from '../components/vr/geo'
import { AltitudeRuler, Ceilings, Depots, ScaleAndNorth, Streets, Table, Zones } from '../components/vr/Airspace'
import { Buildings } from '../components/vr/Buildings'
import { VrConnect, type VrScenario } from '../components/vr/VrConnect'
import { Swarm } from '../components/vr/Swarm'
import { FleetPanel, ViewControls } from '../components/vr/Panels'
import { LiveBoard } from '../components/vr/HtmlBoards'
import { FlightBoard, FlightGeometry, flightFrame, type FlightReplayDto } from '../components/vr/Flight'
import { RehearsalBoard, RehearsalGeometry, rehearsalFrame, type RehearsalDto } from '../components/vr/Rehearsal'
import { UIMode } from '../components/vr/uiMode'
import { C } from '../components/vr/theme'
import type {
  BuildingsDto, CityDto, DepotDto, LiveMarginsDto, RoadsDto, ZoneDto,
} from '../components/vr/types'

/*
 * VR Safety View — a world-in-miniature supervision table for the drone fleet.
 *
 * Why VR at all (docs/VR_RESEARCH_REFERENCES.md):
 *  1. Swarm separation is a 3D judgment. Two drones over the same street at different altitude
 *     bands are one dot on a 2D map; stereo depth + head parallax separates them.
 *  2. A reviewed flight or a set of planned missions is spatial too: deviations and losses of
 *     separation are easiest to judge where and when they happen (flight replay, mission rehearsal).
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

type Mode = 'live' | 'flight' | 'rehearsal'

interface SceneProps {
  mode: Mode
  flight: FlightReplayDto | null
  flightCenter: [number, number]
  flightT: number
  rehearsal: RehearsalDto | null
  rehearsalSide: 'before' | 'after'
  live: LiveMarginsDto | null
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
  const cityLayers = p.mode === 'live'   // a flight or a rehearsal can be anywhere, not around the city centre

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
          {/* City layers are drawn around the city centre; a reviewed flight can be anywhere, so they are left off. */}
          {cityLayers && p.roads && <Streets roads={p.roads} d={p.diorama} cityCenter={p.cityCenter} />}
          {cityLayers && p.buildings && p.controls.showBuildings && (
            <Buildings data={p.buildings} d={p.diorama} cityCenter={p.cityCenter} onStats={p.onBuildingStats} />
          )}
          {cityLayers && <Zones zones={p.zones} d={p.diorama} cityCenter={p.cityCenter} />}
          <Ceilings d={p.diorama} opsCeilingM={ops} legalCeilingM={legal} />
          {cityLayers && <Depots depots={p.depots} d={p.diorama} cityCenter={p.cityCenter} />}
          <AltitudeRuler d={p.diorama} />
          <ScaleAndNorth d={p.diorama} />
          {p.mode === 'live' && p.live && (
            <Swarm drones={p.live.drones} pairs={p.live.pairs} predicted={p.live.predicted_conflicts ?? []} constants={p.live.constants} d={p.diorama}
              cityCenter={p.cityCenter} selected={p.selected} detailAll={p.controls.detailAll}
              onSelect={(id) => p.setSelected(p.selected === id ? null : id)} />
          )}
          {p.mode === 'flight' && p.flight && <FlightGeometry f={p.flight} d={p.diorama} center={p.flightCenter} t={p.flightT} />}
          {p.mode === 'rehearsal' && p.rehearsal && <RehearsalGeometry r={p.rehearsal} side={p.rehearsalSide} d={p.diorama} t={p.flightT} />}
        </group>

        {/* In a headset the boards are in-world (HTML can't render there); on desktop they're
            HTML overlays rendered by the page instead. */}
        {inXR && cityLayers && (
          <group position={[0, 0.5, -TABLE_HALF - 0.18]} rotation={[-0.12, 0, 0]} scale={1.35}>
            <FleetPanel data={p.live} cityName={p.cityName} ageS={p.ageS} vExag={p.diorama.vExag} controls={controls} />
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
  const { apiUrl, vrFlight, vrRehearsal } = useAppStore()
  const [rehearsalSide, setRehearsalSide] = useState<'before' | 'after'>('before')
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

  const [mode, setMode] = useState<Mode>(vrRehearsal ? 'rehearsal' : vrFlight ? 'flight' : 'live')
  const [flight, setFlight] = useState<FlightReplayDto | null>(null)
  const [flightT, setFlightT] = useState(0)
  const [playing, setPlaying] = useState(false)

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
    if (mode !== 'flight' || !vrFlight) { setFlight(null); return }
    getJson<{ id: number; drone_id: string; fleet: string; verdict: FlightReplayDto['verdict']; plan_name: string | null; log_name: string | null
      report: { replay?: FlightReplayDto['replay']; episodes: FlightReplayDto['episodes']; evidence_timeline?: FlightReplayDto['timeline']
        tolerances: FlightReplayDto['tolerances']; flight_s: number } }>(
      `${apiUrl}/api/v1/assurance/fleets/${encodeURIComponent(vrFlight.fleet)}/flights/${vrFlight.id}`, true)
      .then((r) => {
        if (!r.report.replay) { setFlight(null); setError('This flight review was made before replays were stored — upload the flight again to replay it.'); return }
        setFlight({ id: r.id, drone_id: r.drone_id, fleet: r.fleet, verdict: r.verdict, plan_name: r.plan_name, log_name: r.log_name,
          replay: r.report.replay, episodes: r.report.episodes, timeline: r.report.evidence_timeline ?? [], tolerances: r.report.tolerances, flight_s: r.report.flight_s })
        setFlightT(0); setPlaying(false); setError(null)
      })
      .catch((e) => { setFlight(null); if (!onAuthError(e)) setError(String((e as Error).message || e)) })
  }, [apiUrl, mode, vrFlight, authNonce, onAuthError])

  useEffect(() => {
    if (!playing) return
    const end = mode === 'rehearsal' ? vrRehearsal?.[rehearsalSide].end_s ?? 0 : flight?.replay.flown[flight.replay.flown.length - 1]?.[0] ?? 0
    const id = setInterval(() => setFlightT((t) => { if (t + 2 >= end) { setPlaying(false); return end } return t + 2 }), 200)   // ×10
    return () => clearInterval(id)
  }, [playing, flight, mode, vrRehearsal, rehearsalSide])

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
    if (mode === 'flight' && flight) return flightFrame(flight).d
    if (mode === 'rehearsal' && vrRehearsal) return rehearsalFrame(vrRehearsal)
    return new Diorama(focus[0], focus[1], rangeKm * 1000, TABLE_HALF, 0.32, legal)
  }, [mode, flight, vrRehearsal, focus, rangeKm, live?.constants.legal_ceiling_m])
  const flightCenter = useMemo<[number, number]>(() => flight?.replay.home ?? [0, 0], [flight])

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

  const vrScenario = useMemo<VrScenario>(() => ({
    // the paired Quest app has no rehearsal mode yet; it stays on the live view while the browser rehearses
    city, mode: mode === 'rehearsal' ? 'live' : mode, incident_id: null, selected_drone: selected,
    range_km: rangeKm, detail_all: detailAll, show_buildings: showBuildings,
    ...(mode === 'flight' && vrFlight ? { flight_review_id: vrFlight.id } : {}),
  }), [city, mode, selected, rangeKm, detailAll, showBuildings, vrFlight])

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
              : mode === 'flight'
                ? <>Flight replay — the approved plan against what was flown, with the log's events where they happened</>
                : <>Mission rehearsal — the planned missions flown on one clock before anyone flies, with every loss of separation marked</>}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: 4 }}>
            <button className={`btn ${mode === 'live' ? 'btn--primary' : ''}`} onClick={() => setMode('live')}>Live swarm</button>
            <button className={`btn ${mode === 'flight' ? 'btn--primary' : ''}`} id="btn-flight-replay" disabled={!vrFlight}
              title={vrFlight ? `Flight review #${vrFlight.id} (fleet ${vrFlight.fleet})` : 'Open a flight review in Fleet Assurance and choose "Show on the VR table"'}
              onClick={() => setMode('flight')}>Flight replay</button>
            <button className={`btn ${mode === 'rehearsal' ? 'btn--primary' : ''}`} id="btn-rehearsal" disabled={!vrRehearsal}
              title={vrRehearsal ? 'The missions last checked for conflicts' : 'Check missions for conflicts in Fleet Assurance and choose "Rehearse in 3D"'}
              onClick={() => { setMode('rehearsal'); setFlightT(0); setPlaying(false) }}>Mission rehearsal</button>
          </div>
          {mode !== 'flight' && mode !== 'rehearsal' && <select className="form-select" style={{ width: 'auto' }} value={city} onChange={(e) => { setCity(e.target.value); setSelected(null); setFocus([0, 0]) }}>
            {cities.length === 0 && <option value="pune">pune</option>}
            {cities.map((c) => <option key={c.slug} value={c.slug}>{c.name?.split(',')[0] ?? c.slug}</option>)}
          </select>}
          <VrConnect apiUrl={apiUrl} scenario={vrScenario} signedIn={!needsAuth && (lastFetch != null || flight != null)} />
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
        <SignInCard apiUrl={apiUrl} reason="The live swarm feed and flight reviews need an authenticated session."
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
                    mode={mode} flight={flight} flightCenter={flightCenter} flightT={flightT} rehearsal={vrRehearsal} rehearsalSide={rehearsalSide} live={live} zones={zones} depots={depots} roads={roads}
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
            {mode === 'flight' && flight && <FlightBoard f={flight} t={flightT} setT={setFlightT} playing={playing} setPlaying={setPlaying} />}
            {mode === 'rehearsal' && vrRehearsal && <RehearsalBoard r={vrRehearsal} side={rehearsalSide} setSide={setRehearsalSide} t={flightT} setT={setFlightT} playing={playing} setPlaying={setPlaying} />}
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
