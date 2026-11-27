// Pre-flight route check: planned missions drawn over the airspace zones, each checked for red and yellow zones, the
// 120 m height limit and conflicts with the other missions. Backed by POST /api/v1/assurance/plans/airspace
// (aerofleet/assurance/airspace_check.py). The zones are approximations, not Digital Sky, and the page says so.
import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import type { Map as MLMap } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useAppStore } from '../store/appStore'
import SignInCard from '../components/SignInCard'

interface ZoneDto { zone_id: string; zone_type: 'GREEN' | 'YELLOW' | 'RED'; reason: string | null; center_lat: number; center_lon: number; radius_m: number }
interface CityDto { slug: string; name: string; center: [number, number]; airport_name: string; bounds_radius_km: number }
type Verdict = 'CLEAR' | 'NEEDS_PERMISSION' | 'NOT_PERMITTED' | 'UNCHECKED'
interface Finding { kind: 'zone' | 'ceiling'; color?: 'RED' | 'YELLOW'; zone?: string; max_m?: number; at_m: number; until_m?: number; lat: number; lon: number }
interface MissionResult { id: string; verdict: Verdict; length_m: number; max_height_m: number; findings: Finding[]; path: [number, number, number][]; city: string | null; summary: string }
interface Conflict { a: string; b: string; t_s: number; horizontal_m: number; vertical_m: number; duration_s: number }
interface CheckResult { missions: MissionResult[]; conflicts: Conflict[]; counts: Record<Verdict, number>; note: string; conflict_note: string; ledger_seq: number }

const VERDICT: Record<Verdict, { label: string; color: string; bg: string }> = {
  NOT_PERMITTED: { label: 'Not permitted', color: '#DC2626', bg: 'var(--status-red-subtle)' },
  NEEDS_PERMISSION: { label: 'Needs ATC permission', color: '#B45309', bg: 'var(--status-amber-subtle)' },
  UNCHECKED: { label: 'Not checked', color: '#64748B', bg: 'var(--bg-elevated)' },
  CLEAR: { label: 'Clear', color: '#16A34A', bg: 'var(--status-green-subtle)' },
}
const ZONE_COLORS: Record<string, string> = { RED: '#DC2626', YELLOW: '#EAB308', GREEN: '#16A34A' }
const ESRI = 'Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community'
const DEMO = ['SPRAY-FIELD-A', 'SPRAY-FIELD-B', 'SPRAY-NEAR-AIRPORT', 'SPRAY-NEAR-CANTONMENT', 'CROP-MAP-150M']

function circle(lat: number, lon: number, r: number, n = 64): GeoJSON.Position[] {
  const out: GeoJSON.Position[] = []
  for (let i = 0; i <= n; i++) {
    const a = (i / n) * 2 * Math.PI
    out.push([lon + (r * Math.sin(a)) / (111320 * Math.cos((lat * Math.PI) / 180)), lat + (r * Math.cos(a)) / 111320])
  }
  return out
}
function token(): Record<string, string> {
  try { const t = localStorage.getItem('aerofleet_token') || ''; return t ? { Authorization: `Bearer ${t}` } : {} } catch { return {} }
}
const km = (m: number) => (m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${m} m`)

export default function RouteCheckPage() {
  const { apiUrl } = useAppStore()
  const box = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MLMap | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const [ready, setReady] = useState(false)
  const [cities, setCities] = useState<CityDto[]>([])
  const [city, setCity] = useState('pune')
  const [zones, setZones] = useState<ZoneDto[]>([])
  const [result, setResult] = useState<CheckResult | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [needsAuth, setNeedsAuth] = useState(false)

  useEffect(() => {
    if (!box.current || mapRef.current) return
    const map = new maplibregl.Map({
      container: box.current,
      style: { version: 8, sources: { sat: { type: 'raster', tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'], tileSize: 256, attribution: ESRI, maxzoom: 19 } },
        layers: [{ id: 'sat', type: 'raster', source: 'sat' }] },
      center: [73.8567, 18.5204], zoom: 10.6, attributionControl: false,
      canvasContextAttributes: { preserveDrawingBuffer: true },   // so the map can be printed or captured for a report
    })
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right')
    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    map.on('load', () => setReady(true))
    mapRef.current = map
    // the grid gives the map its size only after the first layout, so redraw whenever the box changes size
    const watch = new ResizeObserver(() => map.resize())
    watch.observe(box.current)
    return () => { watch.disconnect(); map.remove(); mapRef.current = null }
  }, [])

  useEffect(() => { fetch(`${apiUrl}/api/v1/cities/`).then((r) => r.json()).then(setCities).catch(() => {}) }, [apiUrl])
  useEffect(() => {
    fetch(`${apiUrl}/api/v1/geofence/zones?city=${city}`).then((r) => r.json()).then(setZones).catch(() => setZones([]))
    const c = cities.find((x) => x.slug === city)
    if (c && mapRef.current && !result) mapRef.current.flyTo({ center: [c.center[1], c.center[0]], zoom: 10.6 })
  }, [apiUrl, city, cities]) // eslint-disable-line react-hooks/exhaustive-deps

  // draw zones, routes and findings
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    const set = (id: string, data: GeoJSON.FeatureCollection) => {
      const src = map.getSource(id) as maplibregl.GeoJSONSource | undefined
      if (src) src.setData(data); else map.addSource(id, { type: 'geojson', data })
    }
    set('zones', { type: 'FeatureCollection', features: zones.filter((z) => z.zone_type !== 'GREEN').map((z) => ({
      type: 'Feature', properties: { color: ZONE_COLORS[z.zone_type], kind: z.zone_type, name: (z.reason || z.zone_id).split(' — ')[0] },
      geometry: { type: 'Polygon', coordinates: [circle(z.center_lat, z.center_lon, z.radius_m)] } })) })
    const missions = result?.missions ?? []
    set('routes', { type: 'FeatureCollection', features: missions.map((m) => ({
      type: 'Feature', properties: { id: m.id, color: VERDICT[m.verdict].color, sel: m.id === selected ? 1 : 0 },
      geometry: { type: 'LineString', coordinates: m.path.map(([la, lo]) => [lo, la]) } })) })
    set('ends', { type: 'FeatureCollection', features: missions.flatMap((m) => [
      { type: 'Feature' as const, properties: { label: m.id, color: VERDICT[m.verdict].color }, geometry: { type: 'Point' as const, coordinates: [m.path[0][1], m.path[0][0]] } }]) })
    set('findings', { type: 'FeatureCollection', features: missions.flatMap((m) => m.findings.map((f) => ({
      type: 'Feature' as const, properties: { color: f.kind === 'ceiling' ? '#7C3AED' : ZONE_COLORS[f.color ?? 'RED'] },
      geometry: { type: 'Point' as const, coordinates: [f.lon, f.lat] } }))) })
    if (!map.getLayer('zones-fill')) {
      map.addLayer({ id: 'zones-fill', type: 'fill', source: 'zones', paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 0.16 } })
      map.addLayer({ id: 'zones-line', type: 'line', source: 'zones', paint: { 'line-color': ['get', 'color'], 'line-width': 2.5 } })
      map.addLayer({ id: 'zones-label', type: 'symbol', source: 'zones', layout: { 'text-field': ['get', 'name'], 'text-size': 11, 'symbol-placement': 'line', 'text-allow-overlap': false },
        paint: { 'text-color': '#fff', 'text-halo-color': '#0B1220', 'text-halo-width': 1.5 } })
      map.addLayer({ id: 'routes-halo', type: 'line', source: 'routes', paint: { 'line-color': '#0B1220', 'line-width': ['+', 6, ['*', 3, ['get', 'sel']]], 'line-opacity': 0.7 } })
      map.addLayer({ id: 'routes-line', type: 'line', source: 'routes', paint: { 'line-color': ['get', 'color'], 'line-width': ['+', 3.5, ['*', 2, ['get', 'sel']]] } })
      map.addLayer({ id: 'findings-pt', type: 'circle', source: 'findings', paint: { 'circle-radius': 6, 'circle-color': ['get', 'color'], 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } })
      map.addLayer({ id: 'ends-label', type: 'symbol', source: 'ends', layout: { 'text-field': ['get', 'label'], 'text-size': 12, 'text-offset': [0, 1.2], 'text-anchor': 'top' },
        paint: { 'text-color': '#fff', 'text-halo-color': '#0B1220', 'text-halo-width': 2 } })
    }
  }, [zones, result, selected, ready])

  const fit = (ms: MissionResult[]) => {
    const map = mapRef.current
    if (!map || !ms.length) return
    const b = new maplibregl.LngLatBounds()
    ms.forEach((m) => m.path.forEach(([la, lo]) => b.extend([lo, la])))
    map.fitBounds(b, { padding: 70, maxZoom: 14, duration: 800 })
  }

  const run = async (files: File[]) => {
    if (!files.length) return
    setBusy(true); setError(null)
    try {
      const body = new FormData()
      files.forEach((f) => body.append('plans', f))
      const r = await fetch(`${apiUrl}/api/v1/assurance/plans/airspace`, { method: 'POST', headers: token(), body })
      if (r.status === 401) { setNeedsAuth(true); return }
      setNeedsAuth(false)
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`)
      const out: CheckResult = await r.json()
      setResult(out); setSelected(null)
      const c = out.missions.find((m) => m.city)?.city
      if (c && cities.some((x) => x.slug === c)) setCity(c)
      fit(out.missions)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  const demo = async () => {
    const files = await Promise.all(DEMO.map(async (id) => new File([await (await fetch(`/demo/route_check/${id}.waypoints`)).text()], `${id}.waypoints`)))
    run(files)
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 400px) 1fr', height: '100%', minHeight: 600 }} id="route-check">
      <div style={{ overflow: 'auto', padding: 16, display: 'grid', gap: 12, alignContent: 'start', borderRight: '1px solid var(--border)' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 20 }}>Route check</h1>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.5 }}>
            Before flying: does each planned route stay out of red and yellow airspace and under the 120 m limit, and does it
            cross another planned flight? Load the mission files (.waypoints) planned for the same period.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <input ref={fileRef} type="file" accept=".waypoints,.txt" multiple hidden onChange={(e) => { run(Array.from(e.target.files ?? [])); e.target.value = '' }} />
          <button className="btn btn--primary" id="btn-route-files" disabled={busy} onClick={() => fileRef.current?.click()}>{busy ? 'Checking…' : 'Choose mission files'}</button>
          <button className="btn" id="btn-route-demo" disabled={busy} onClick={demo}>Try 5 demo jobs</button>
          <select className="form-select" value={city} onChange={(e) => setCity(e.target.value)} style={{ width: 110 }} title="Airspace shown on the map">
            {(cities.length ? cities : [{ slug: 'pune', name: 'Pune' } as CityDto]).map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
          </select>
        </div>
        {needsAuth && <SignInCard apiUrl={apiUrl} reason="Each check is signed into the record with your name." onSignedIn={() => setNeedsAuth(false)} />}
        {error && <div role="alert" style={{ color: 'var(--status-red)', fontSize: 13 }}>{error}</div>}

        {result && <>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {(['NOT_PERMITTED', 'NEEDS_PERMISSION', 'CLEAR', 'UNCHECKED'] as Verdict[]).filter((v) => result.counts[v]).map((v) => (
              <span key={v} style={{ fontSize: 12, fontWeight: 700, padding: '3px 8px', borderRadius: 999, color: VERDICT[v].color, background: VERDICT[v].bg }}>{result.counts[v]} {VERDICT[v].label.replace(/^\w/, (c) => c.toLowerCase())}</span>))}
            {result.conflicts.length > 0 && <span style={{ fontSize: 12, fontWeight: 700, padding: '3px 8px', borderRadius: 999, color: '#B45309', background: 'var(--status-amber-subtle)' }}>{result.conflicts.length} conflict{result.conflicts.length > 1 ? 's' : ''}</span>}
          </div>
          {result.missions.map((m) => (
            <button key={m.id} onClick={() => { setSelected(m.id); fit([m]) }} className="card"
              style={{ textAlign: 'left', padding: 12, display: 'grid', gap: 4, cursor: 'pointer', font: 'inherit', color: 'inherit', borderLeft: `4px solid ${VERDICT[m.verdict].color}`, outline: m.id === selected ? '2px solid var(--accent)' : undefined }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <b style={{ flex: 1 }}>{m.id}</b>
                <span style={{ fontSize: 12, fontWeight: 700, color: VERDICT[m.verdict].color }}>{VERDICT[m.verdict].label}</span>
              </div>
              <div style={{ fontSize: 13, lineHeight: 1.45 }}>{m.summary}</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{km(m.length_m)} route · highest {m.max_height_m} m{m.city ? ` · ${m.city}` : ''}</div>
            </button>))}
          {result.conflicts.length > 0 && (
            <div className="card" style={{ padding: 12, display: 'grid', gap: 4, borderLeft: '4px solid #B45309' }}>
              <b>Planned flights that cross</b>
              {result.conflicts.map((c, i) => (
                <div key={i} style={{ fontSize: 13 }}><b>{c.a}</b> and <b>{c.b}</b>: {c.horizontal_m} m apart, {c.vertical_m} m in height, {Math.round(c.t_s)} s after launch</div>))}
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{result.conflict_note} Fleet Assurance ▸ "Will these missions conflict?" proposes a fix.</div>
            </div>)}
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, padding: 10, borderRadius: 'var(--radius-md)', background: 'var(--status-amber-subtle)' }}>
            {result.note} Signed into the record as entry #{result.ledger_seq}.
          </div>
        </>}
        {!result && (
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            <b>Legend.</b> <span style={{ color: '#DC2626' }}>Red zone</span>: no flying without central government permission.{' '}
            <span style={{ color: '#B45309' }}>Yellow zone</span>: air traffic control permission needed. Full local zones are
            loaded for Pune and Mumbai; across the rest of India, 36 major civil airport perimeters (Drone Rules 2021 5 km / 12 km
            circles) are checked automatically and routes outside them return <i>Not checked</i> until verified on the official Digital Sky map.
          </div>)}
      </div>
      <div style={{ position: 'relative', background: 'var(--bg-void)' }}>
        <div ref={box} id="route-map" style={{ position: 'absolute', inset: 0 }} />
      </div>
    </div>
  )
}
