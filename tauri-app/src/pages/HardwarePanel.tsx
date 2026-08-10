import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useAppStore } from '../store/appStore'

// ── Types (mirrors aerofleet/api/schemas.py + hardware.py responses) ────────

interface DroneDto {
  drone_id: string
  home_depot_id: string | null
  state: string
  link_mode: 'SIMULATED' | 'LIVE'
  armed: boolean
  flight_mode: string
  last_telemetry_at: number | null
  // NOMINAL/DEGRADED/STORE_FORWARD/ISOLATED — see aerofleet/safety/d2d_mesh.py.
  // Only meaningful for LIVE drones; SIMULATED ones have no real link to degrade.
  d2d_link_state: 'NOMINAL' | 'DEGRADED' | 'STORE_FORWARD' | 'ISOLATED'
}

interface VehicleTelemetry {
  lat: number | null
  lon: number | null
  alt_m: number | null
  relative_alt_m: number | null
  heading_deg: number | null
  groundspeed_mps: number | null
  battery_voltage_v: number | null
  battery_remaining_pct: number | null
  armed: boolean
  flight_mode: string
  gps_fix_type: number
  satellites_visible: number
  system_status: string
  autopilot_type: string
  timestamp: number
}

interface LiveVehicleDto {
  drone_id: string
  connected: boolean
  telemetry: VehicleTelemetry | null
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('aerofleet_token') || ''
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const D2D_STATE_TONE: Record<string, string> = {
  DEGRADED: 'yellow',
  STORE_FORWARD: 'yellow',
  ISOLATED: 'red',
}

export default function HardwarePanel() {
  const { apiUrl } = useAppStore()
  const [drones, setDrones] = useState<DroneDto[]>([])
  const [liveVehicles, setLiveVehicles] = useState<Record<string, LiveVehicleDto>>({})
  const [city] = useState('pune')
  const [connectionStrings, setConnectionStrings] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [wsStatus, setWsStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected')
  const [stopArmed, setStopArmed] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const stopArmedTimer = useRef<number | null>(null)

  const loadDrones = useCallback(() => {
    fetch(`${apiUrl}/api/v1/fleet/drones?city=${city}`, { headers: authHeaders() })
      .then(r => r.json())
      .then(setDrones)
      .catch(() => {})
  }, [apiUrl, city])

  const loadLiveVehicles = useCallback(() => {
    fetch(`${apiUrl}/api/v1/hardware/vehicles`, { headers: authHeaders() })
      .then(r => r.json())
      .then((list: LiveVehicleDto[]) => {
        const byId: Record<string, LiveVehicleDto> = {}
        for (const v of list) byId[v.drone_id] = v
        setLiveVehicles(byId)
      })
      .catch(() => {})
  }, [apiUrl])

  useEffect(() => {
    loadDrones()
    loadLiveVehicles()
    const interval = setInterval(loadDrones, 4000)
    return () => clearInterval(interval)
  }, [loadDrones, loadLiveVehicles])

  // Live telemetry WebSocket — updates the vehicle readouts in real time
  // without waiting on the 4s drone-list poll above.
  useEffect(() => {
    const token = localStorage.getItem('aerofleet_token') || ''
    const wsUrl = apiUrl.replace(/^http/, 'ws') + '/api/v1/hardware/ws/telemetry'
      + (token ? `?token=${encodeURIComponent(token)}` : '')
    setWsStatus('connecting')
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => setWsStatus('connected')
    ws.onclose = () => setWsStatus('disconnected')
    ws.onerror = () => setWsStatus('disconnected')
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data)
        if (msg.type === 'telemetry.update' && msg.drone_id) {
          setLiveVehicles(prev => ({
            ...prev,
            [msg.drone_id]: {
              drone_id: msg.drone_id,
              connected: true,
              telemetry: msg as VehicleTelemetry,
            },
          }))
        }
      } catch {
        // ignore malformed frames
      }
    }

    return () => ws.close()
  }, [apiUrl])

  async function handleConnect(droneId: string) {
    const connectionString = connectionStrings[droneId]
    if (!connectionString) {
      setError('Enter a connection string first (e.g. udp:127.0.0.1:14550 or /dev/ttyACM0,57600).')
      return
    }
    setBusy(droneId)
    setError(null)
    try {
      const res = await fetch(`${apiUrl}/api/v1/hardware/vehicles/${droneId}/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ connection_string: connectionString, city }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `${res.status} ${res.statusText}`)
      }
      loadDrones()
      loadLiveVehicles()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  async function handleDisconnect(droneId: string) {
    setBusy(droneId)
    setError(null)
    try {
      await fetch(`${apiUrl}/api/v1/hardware/vehicles/${droneId}/connect`, {
        method: 'DELETE',
        headers: authHeaders(),
      })
      setLiveVehicles(prev => {
        const next = { ...prev }
        delete next[droneId]
        return next
      })
      loadDrones()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  async function handleArmDisarm(droneId: string, arm: boolean) {
    setBusy(droneId)
    setError(null)
    try {
      const res = await fetch(`${apiUrl}/api/v1/hardware/vehicles/${droneId}/${arm ? 'arm' : 'disarm'}`, {
        method: 'POST',
        headers: authHeaders(),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `${res.status} ${res.statusText}`)
      }
      loadDrones()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  function armStopConfirmation() {
    setStopArmed(true)
    if (stopArmedTimer.current) window.clearTimeout(stopArmedTimer.current)
    stopArmedTimer.current = window.setTimeout(() => setStopArmed(false), 5000)
  }

  async function handleEmergencyStopAll() {
    if (!stopArmed) {
      armStopConfirmation()
      return
    }
    setStopArmed(false)
    setBusy('__stop_all__')
    setError(null)
    try {
      const res = await fetch(`${apiUrl}/api/v1/hardware/emergency-stop-all`, {
        method: 'POST',
        headers: authHeaders(),
      })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      loadDrones()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  const liveDroneCount = drones.filter(d => d.link_mode === 'LIVE').length

  return (
    <div style={{ overflow: 'auto', flex: 1 }}>
      <div className="page-header">
        <div>
          <div className="page-title">Hardware</div>
          <div className="page-subtitle">MAVLink connections to real ArduPilot/PX4 vehicles &middot; {liveDroneCount} LIVE</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div className={`status-indicator status-indicator--${wsStatus === 'connected' ? 'online' : wsStatus === 'connecting' ? 'busy' : 'offline'}`}>
            <div className="status-indicator__dot" />
            <span>Telemetry {wsStatus}</span>
          </div>
          <button
            id="btn-emergency-stop-all"
            className="btn btn--danger"
            onClick={handleEmergencyStopAll}
            disabled={busy === '__stop_all__' || liveDroneCount === 0}
          >
            {busy === '__stop_all__'
              ? <><div className="spinner" style={{ width: 14, height: 14 }} /> Stopping...</>
              : stopArmed ? 'Confirm: RTL every LIVE drone now' : 'Emergency Stop All'}
          </button>
        </div>
      </div>

      <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {error && (
          <div className="card" style={{ borderColor: 'var(--status-red)' }}>
            <span style={{ color: 'var(--status-red)' }}>⚠ {error}</span>
          </div>
        )}

        <div className="card" style={{ borderColor: 'var(--status-amber)' }}>
          <span style={{ color: 'var(--status-amber)' }}>
            This connects to real flight-controller hardware. Standard UAV safety practice — a
            safety pilot with RC override, the flight controller's own configured failsafes, and
            flying within your DGCA-authorized category/VLOS — remains mandatory. This panel
            coordinates the fleet; it does not replace those safeguards.
          </span>
        </div>

        {drones.map(drone => {
          const live = liveVehicles[drone.drone_id]
          const t = live?.telemetry

          return (
            <div key={drone.drone_id} className="card">
              <div className="card__header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="card__title">
                  {drone.drone_id}
                  {drone.link_mode === 'LIVE' && (
                    <span className="verdict-badge verdict-badge--yellow" style={{ marginLeft: '10px' }}>LIVE</span>
                  )}
                  {drone.link_mode === 'LIVE' && drone.d2d_link_state !== 'NOMINAL' && (
                    <span
                      className={`verdict-badge verdict-badge--${D2D_STATE_TONE[drone.d2d_link_state]}`}
                      style={{ marginLeft: '6px' }}
                      title="Central-link health — see docs/D2D_MESH_RESEARCH_DESIGN.md"
                    >
                      D2D {drone.d2d_link_state}
                    </span>
                  )}
                </span>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{drone.home_depot_id}</span>
              </div>

              {drone.link_mode === 'SIMULATED' ? (
                <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end', padding: '4px 0' }}>
                  <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
                    <label className="form-label">Connection String</label>
                    <input
                      id={`input-conn-${drone.drone_id}`}
                      className="form-input"
                      placeholder="udp:127.0.0.1:14550 or /dev/ttyACM0,57600"
                      value={connectionStrings[drone.drone_id] || ''}
                      onChange={e => setConnectionStrings(s => ({ ...s, [drone.drone_id]: e.target.value }))}
                    />
                  </div>
                  <button
                    id={`btn-connect-${drone.drone_id}`}
                    className="btn btn--primary"
                    onClick={() => handleConnect(drone.drone_id)}
                    disabled={busy === drone.drone_id}
                  >
                    {busy === drone.drone_id ? <div className="spinner" style={{ width: 14, height: 14 }} /> : 'Connect'}
                  </button>
                </div>
              ) : (
                <div>
                  <div className="grid-3" style={{ marginTop: '8px' }}>
                    <Metric label="Armed" value={t?.armed ?? drone.armed ? 'ARMED' : 'safe'} tone={t?.armed ?? drone.armed ? 'red' : 'green'} />
                    <Metric label="Flight Mode" value={t?.flight_mode || drone.flight_mode || '—'} />
                    <Metric label="GPS" value={t ? `${t.satellites_visible} sats · fix ${t.gps_fix_type}` : '—'} />
                    <Metric label="Altitude" value={t?.relative_alt_m != null ? `${t.relative_alt_m.toFixed(1)} m` : '—'} />
                    <Metric label="Battery" value={t?.battery_remaining_pct != null ? `${t.battery_remaining_pct.toFixed(0)}%` : '—'}
                      tone={t?.battery_remaining_pct != null && t.battery_remaining_pct < 20 ? 'red' : undefined} />
                    <Metric label="Autopilot" value={t?.autopilot_type || '—'} />
                  </div>

                  <div style={{ display: 'flex', gap: '10px', marginTop: '16px' }}>
                    <button
                      id={`btn-arm-${drone.drone_id}`}
                      className="btn btn--ghost"
                      onClick={() => handleArmDisarm(drone.drone_id, !(t?.armed ?? drone.armed))}
                      disabled={busy === drone.drone_id}
                    >
                      {(t?.armed ?? drone.armed) ? 'Disarm' : 'Arm'}
                    </button>
                    <button
                      id={`btn-disconnect-${drone.drone_id}`}
                      className="btn btn--ghost"
                      onClick={() => handleDisconnect(drone.drone_id)}
                      disabled={busy === drone.drone_id}
                    >
                      Disconnect
                    </button>
                  </div>
                </div>
              )}
            </div>
          )
        })}

        {drones.length === 0 && (
          <div className="card"><span style={{ color: 'var(--text-muted)' }}>No drones registered for this city.</span></div>
        )}
      </div>
    </div>
  )
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: 'green' | 'amber' | 'red' }) {
  return (
    <div className={`metric${tone ? ` metric--${tone}` : ''}`}>
      <div className="metric__label">{label}</div>
      <div className="metric__value" style={{ fontSize: '16px' }}>{value}</div>
    </div>
  )
}
