import React, { useEffect, useRef, useState, useCallback } from 'react'
import * as maplibregl from 'maplibre-gl'
import type { Map as MLMap } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useAppStore } from '../store/appStore'

// ── Types (mirrors aerofleet/api/schemas.py) ─────────────────────────────

interface DroneDto {
  drone_id: string
  lat: number | null
  lon: number | null
  soc: number
  state: string
  altitude_band_m: number
  home_depot_id: string | null
  link_mode?: 'SIMULATED' | 'LIVE'
}

interface DepotDto {
  depot_id: string
  name: string
  lat: number | null
  lon: number | null
  launch_pad_slots: number
  queued_drones: string[]
}

interface ZoneDto {
  zone_id: string
  zone_type: 'GREEN' | 'YELLOW' | 'RED'
  reason: string | null
  center_lat: number
  center_lon: number
  radius_m: number
}

interface CityDto {
  slug: string
  name: string
  center: [number, number]
  airport_name: string
  bounds_radius_km: number
}

interface CityInfo {
  city_name: string
  is_synthetic: boolean
  node_count: number
}

const STATE_COLORS: Record<string, string> = {
  IDLE: '#94A3B8',
  EN_ROUTE: '#0EA5E9',
  DELIVERING: '#16A34A',
  RETURNING: '#EAB308',
  CHARGING: '#8a6fb8',
  SWAPPING_BATTERY: '#8a6fb8',
  EMERGENCY_LANDING: '#DC2626',
  GROUNDED: '#DC2626',
}

const ZONE_COLORS: Record<string, string> = { RED: '#DC2626', YELLOW: '#EAB308', GREEN: '#16A34A' }

const ESRI_ATTRIBUTION =
  'Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community'

// ── Geometry helpers ──────────────────────────────────────────────────

function circlePolygon(lat: number, lon: number, radiusM: number, points = 48): GeoJSON.Position[] {
  const coords: GeoJSON.Position[] = []
  const latRad = (lat * Math.PI) / 180
  for (let i = 0; i <= points; i++) {
    const angle = (i / points) * 2 * Math.PI
    const dLat = (radiusM * Math.cos(angle)) / 111320
    const dLon = (radiusM * Math.sin(angle)) / (111320 * Math.cos(latRad))
    coords.push([lon + dLon, lat + dLat])
  }
  return coords
}

function squarePolygon(lat: number, lon: number, halfSideM = 12): GeoJSON.Position[] {
  const latRad = (lat * Math.PI) / 180
  const dLat = halfSideM / 111320
  const dLon = halfSideM / (111320 * Math.cos(latRad))
  return [
    [lon - dLon, lat - dLat], [lon + dLon, lat - dLat],
    [lon + dLon, lat + dLat], [lon - dLon, lat + dLat],
    [lon - dLon, lat - dLat],
  ]
}

/** Simple degree-offset bounding box around a city center — a UX pan/zoom
 * limit, not a precision calculation, so a flat-earth approximation is fine. */
function computeBounds(center: [number, number], radiusKm: number): maplibregl.LngLatBoundsLike {
  const [lat, lon] = center
  const latRad = (lat * Math.PI) / 180
  const dLat = (radiusKm * 1000) / 111320
  const dLon = (radiusKm * 1000) / (111320 * Math.cos(latRad))
  return [
    [lon - dLon, lat - dLat],
    [lon + dLon, lat + dLat],
  ]
}

// ── Page ──────────────────────────────────────────────────────────────

export default function FleetMapPage() {
  const { apiUrl } = useAppStore()
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MLMap | null>(null)
  const popupRef = useRef<maplibregl.Popup | null>(null)

  const [cities, setCities] = useState<CityDto[]>([])
  const [city, setCity] = useState('pune')
  const [drones, setDrones] = useState<DroneDto[]>([])
  const [depots, setDepots] = useState<DepotDto[]>([])
  const [zones, setZones] = useState<ZoneDto[]>([])
  const [cityInfo, setCityInfo] = useState<CityInfo | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [show3D, setShow3D] = useState(false)
  const [mapReady, setMapReady] = useState(false)

  // ── Init map once ──
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          satellite: {
            type: 'raster',
            tiles: [
              'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            ],
            tileSize: 256,
            attribution: ESRI_ATTRIBUTION,
            maxzoom: 19,
          },
        },
        layers: [{ id: 'satellite', type: 'raster', source: 'satellite' }],
      },
      center: [73.8567, 18.5204],
      zoom: 12.5,
      minZoom: 10,
      maxZoom: 18,
      pitch: 0,
      attributionControl: false,
      renderWorldCopies: false,
      // Default Pune bound, active from first paint — narrowed to the actual
      // selected city's own radius once /api/v1/cities/ resolves below.
      maxBounds: computeBounds([18.5204, 73.8567], 20.0),
    })
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right')
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right')
    map.on('load', () => setMapReady(true))
    mapRef.current = map
    popupRef.current = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12 })
    return () => { map.remove(); mapRef.current = null }
  }, [])

  // ── Fetch cities once ──
  useEffect(() => {
    fetch(`${apiUrl}/api/v1/cities/`).then(r => r.json()).then(setCities).catch(() => {})
  }, [apiUrl])

  // ── Fetch fleet data for the selected city ──
  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [d, dep, z, info] = await Promise.all([
        fetch(`${apiUrl}/api/v1/fleet/drones?city=${city}`).then(r => r.json()),
        fetch(`${apiUrl}/api/v1/fleet/depots?city=${city}`).then(r => r.json()),
        fetch(`${apiUrl}/api/v1/geofence/zones?city=${city}`).then(r => r.json()),
        fetch(`${apiUrl}/api/v1/routes/city-info?city=${city}`).then(r => r.json()),
      ])
      setDrones(d)
      setDepots(dep)
      setZones(z)
      setCityInfo(info)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [apiUrl, city])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 10000)
    return () => clearInterval(id)
  }, [refresh])

  // ── Fly to city on change ──
  useEffect(() => {
    const cfg = cities.find(c => c.slug === city)
    const map = mapRef.current
    if (!cfg || !map) return

    // Clear the bound during the flight so it doesn't clip the animation if
    // the destination city's own box doesn't yet cover the flight path, then
    // re-tighten to the new city's bound once the flight settles.
    map.setMaxBounds(undefined)
    map.flyTo({ center: [cfg.center[1], cfg.center[0]], zoom: 12.5, duration: 1200 })
    map.once('moveend', () => {
      map.setMaxBounds(computeBounds(cfg.center, cfg.bounds_radius_km))
    })
  }, [city, cities])

  // ── Render layers whenever data or the 3D toggle changes ──
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return

    const zonesFC: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: zones.map(z => ({
        type: 'Feature',
        properties: { zone_type: z.zone_type, reason: z.reason, color: ZONE_COLORS[z.zone_type] },
        geometry: { type: 'Polygon', coordinates: [circlePolygon(z.center_lat, z.center_lon, z.radius_m)] },
      })),
    }

    const depotsFC: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: depots.filter(d => d.lat != null && d.lon != null).map(d => ({
        type: 'Feature',
        properties: { depot_id: d.depot_id, name: d.name, queue: d.queued_drones.length },
        geometry: { type: 'Point', coordinates: [d.lon as number, d.lat as number] },
      })),
    }
    const depotTowersFC: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: depots.filter(d => d.lat != null && d.lon != null).map(d => ({
        type: 'Feature',
        properties: {},
        geometry: { type: 'Polygon', coordinates: [squarePolygon(d.lat as number, d.lon as number, 10)] },
      })),
    }

    const dronesFC: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: drones.filter(d => d.lat != null && d.lon != null).map(d => ({
        type: 'Feature',
        properties: {
          drone_id: d.drone_id, state: d.state, soc: d.soc, altitude_band_m: d.altitude_band_m,
          color: STATE_COLORS[d.state] || '#7c8288',
          live: d.link_mode === 'LIVE',
        },
        geometry: { type: 'Point', coordinates: [d.lon as number, d.lat as number] },
      })),
    }
    const droneTowersFC: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: drones.filter(d => d.lat != null && d.lon != null).map(d => ({
        type: 'Feature',
        properties: { height: Math.max(20, d.altitude_band_m), color: STATE_COLORS[d.state] || '#7c8288' },
        geometry: { type: 'Polygon', coordinates: [squarePolygon(d.lat as number, d.lon as number, 7)] },
      })),
    }

    const ensureSource = (id: string, data: GeoJSON.FeatureCollection) => {
      const src = map.getSource(id) as maplibregl.GeoJSONSource | undefined
      if (src) src.setData(data)
      else map.addSource(id, { type: 'geojson', data })
    }

    ensureSource('zones', zonesFC)
    ensureSource('depots', depotsFC)
    ensureSource('depot-towers', depotTowersFC)
    ensureSource('drones', dronesFC)
    ensureSource('drone-towers', droneTowersFC)

    if (!map.getLayer('zones-fill')) {
      map.addLayer({
        id: 'zones-fill', type: 'fill', source: 'zones',
        paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 0.22 },
      })
      // A thin, translucent line all but disappears against real satellite
      // photography (buildings, roads, vegetation all fight for the same
      // contrast) — a dark casing underneath the colored line is standard
      // cartography practice for exactly this: it guarantees the boundary
      // reads against *any* basemap content, not just plain colors.
      map.addLayer({
        id: 'zones-line-halo', type: 'line', source: 'zones',
        paint: {
          'line-color': '#0B1220',
          'line-width': ['match', ['get', 'zone_type'], 'RED', 5.5, 'YELLOW', 4.5, 3.5],
          'line-opacity': 0.55,
        },
      })
      map.addLayer({
        id: 'zones-line', type: 'line', source: 'zones',
        paint: {
          'line-color': ['get', 'color'],
          'line-width': ['match', ['get', 'zone_type'], 'RED', 3, 'YELLOW', 2.5, 2],
          'line-opacity': 1,
        },
      })
    }

    if (!map.getLayer('depots-fill')) {
      map.addLayer({
        id: 'depots-fill', type: 'circle', source: 'depots',
        paint: {
          'circle-radius': 6, 'circle-color': '#FFFFFF',
          'circle-stroke-width': 1.5, 'circle-stroke-color': '#1E293B',
        },
      })
    }

    if (!map.getLayer('drones-fill')) {
      map.addLayer({
        id: 'drones-fill', type: 'circle', source: 'drones',
        paint: {
          'circle-radius': 5, 'circle-color': ['get', 'color'],
          // LIVE drones (real MAVLink telemetry) get a thicker amber ring
          // so they read as distinct from simulated ones at a glance.
          'circle-stroke-width': ['case', ['get', 'live'], 2.5, 1],
          'circle-stroke-color': ['case', ['get', 'live'], '#244975', '#1E293B'],
        },
      })
    }

    if (!map.getLayer('depot-towers-fill')) {
      map.addLayer({
        id: 'depot-towers-fill', type: 'fill-extrusion', source: 'depot-towers',
        paint: { 'fill-extrusion-color': '#244975', 'fill-extrusion-height': 15, 'fill-extrusion-opacity': 0.85 },
        layout: { visibility: 'none' },
      })
    }

    if (!map.getLayer('drone-towers-fill')) {
      map.addLayer({
        id: 'drone-towers-fill', type: 'fill-extrusion', source: 'drone-towers',
        paint: {
          'fill-extrusion-color': ['get', 'color'],
          'fill-extrusion-height': ['get', 'height'],
          'fill-extrusion-opacity': 0.9,
        },
        layout: { visibility: 'none' },
      })
    }

    if (!map.getLayer('zones-extrusion')) {
      map.addLayer({
        id: 'zones-extrusion', type: 'fill-extrusion', source: 'zones',
        paint: { 'fill-extrusion-color': ['get', 'color'], 'fill-extrusion-height': 100, 'fill-extrusion-opacity': 0.12 },
        layout: { visibility: 'none' },
      })
    }

    // Popups
    const onDroneEnter = (e: maplibregl.MapLayerMouseEvent) => {
      map.getCanvas().style.cursor = 'pointer'
      const f = e.features?.[0]
      if (!f || !popupRef.current) return
      const p = f.properties as Record<string, unknown>
      popupRef.current
        .setLngLat((f.geometry as GeoJSON.Point).coordinates as [number, number])
        .setHTML(
          `<div class="map-popup"><strong>${p.drone_id}</strong><br/>${p.state} &middot; ${((p.soc as number) * 100).toFixed(0)}% SoC<br/>alt ${p.altitude_band_m}m</div>`
        )
        .addTo(map)
    }
    const onDepotEnter = (e: maplibregl.MapLayerMouseEvent) => {
      map.getCanvas().style.cursor = 'pointer'
      const f = e.features?.[0]
      if (!f || !popupRef.current) return
      const p = f.properties as Record<string, unknown>
      popupRef.current
        .setLngLat((f.geometry as GeoJSON.Point).coordinates as [number, number])
        .setHTML(`<div class="map-popup"><strong>${p.depot_id}</strong><br/>${p.name}<br/>queue ${p.queue}</div>`)
        .addTo(map)
    }
    const onLeave = () => { map.getCanvas().style.cursor = ''; popupRef.current?.remove() }

    map.on('mouseenter', 'drones-fill', onDroneEnter)
    map.on('mouseleave', 'drones-fill', onLeave)
    map.on('mouseenter', 'depots-fill', onDepotEnter)
    map.on('mouseleave', 'depots-fill', onLeave)

    return () => {
      map.off('mouseenter', 'drones-fill', onDroneEnter)
      map.off('mouseleave', 'drones-fill', onLeave)
      map.off('mouseenter', 'depots-fill', onDepotEnter)
      map.off('mouseleave', 'depots-fill', onLeave)
    }
  }, [drones, depots, zones, mapReady])

  // ── Toggle 3D ──
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return
    const vis = show3D ? 'visible' : 'none'
    for (const id of ['depot-towers-fill', 'drone-towers-fill', 'zones-extrusion']) {
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', vis)
    }
    for (const id of ['depots-fill', 'drones-fill']) {
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', show3D ? 'none' : 'visible')
    }
    map.easeTo({ pitch: show3D ? 55 : 0, duration: 500 })
  }, [show3D, mapReady])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="page-header" style={{ flexShrink: 0 }}>
        <div>
          <div className="page-title">Airspace Map</div>
          <div className="page-subtitle">
            {cityInfo ? `${cityInfo.city_name} · ${cityInfo.node_count} street-graph nodes${cityInfo.is_synthetic ? ' (synthetic fallback)' : ' (real OSM + satellite imagery)'}` : 'Live drones, depots & DGCA geofence'}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <select
            id="select-city"
            className="form-select"
            style={{ width: 140 }}
            value={city}
            onChange={e => setCity(e.target.value)}
          >
            {cities.length === 0 && <option value="pune">Pune</option>}
            {cities.map(c => <option key={c.slug} value={c.slug}>{c.name}</option>)}
          </select>
          <button
            id="btn-toggle-3d"
            className={`btn ${show3D ? 'btn--primary' : 'btn--ghost'}`}
            onClick={() => setShow3D(v => !v)}
          >
            {show3D ? '3D Corridors: ON' : '3D Corridors'}
          </button>
          <button id="btn-refresh-fleet" className="btn btn--ghost" onClick={refresh} disabled={loading}>
            {loading ? <div className="spinner" style={{ width: 14, height: 14 }} /> : '↻ Refresh'}
          </button>
        </div>
      </div>

      {/* Legend */}
      <div style={{
        padding: '8px 24px', display: 'flex', gap: '20px', flexWrap: 'wrap',
        background: 'var(--bg-deep)', borderBottom: '1px solid var(--border)', flexShrink: 0,
      }}>
        {Object.entries(STATE_COLORS).map(([state, color]) => (
          <div key={state} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text-muted)' }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
            {state.replace(/_/g, ' ')}
          </div>
        ))}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text-muted)' }}>
          <div style={{ width: 8, height: 8, background: ZONE_COLORS.RED, opacity: 0.6 }} /> Red Zone
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text-muted)' }}>
          <div style={{ width: 8, height: 8, background: ZONE_COLORS.YELLOW, opacity: 0.6 }} /> Yellow Zone
        </div>
        <div style={{ marginLeft: 'auto', fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          {drones.length} drones &middot; {depots.length} depots
        </div>
      </div>

      {error && (
        <div style={{ padding: '10px 24px', color: 'var(--status-red)', fontSize: 12, flexShrink: 0 }}>
          {error} — is the API running at {apiUrl}?
        </div>
      )}

      {/* Map */}
      <div style={{ flex: 1, position: 'relative', background: 'var(--bg-void)' }}>
        <div ref={mapContainer} id="fleet-map" style={{ position: 'absolute', inset: 0 }} />
      </div>
    </div>
  )
}
