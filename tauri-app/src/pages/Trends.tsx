// Fleet trends: the season view for a coordinator. Counts and medians over reviewed flights (aerofleet/assurance/trends.py).
import { useCallback, useEffect, useState } from 'react'
import { useAppStore } from '../store/appStore'
import SignInCard from '../components/SignInCard'
import FleetPicker, { SimulatedFleetBanner, initialFleet } from '../components/FleetPicker'

interface Period { period: string; flights: number; hours: number; warnings: number }
interface DroneTrend { drone_id: string; flights: number; hours: number; last_flown: string; warnings_per_flight: number; latest_vibration_vs_own_median: number | null; battery_vs_expected_median: number | null; flights_outside_expected: number; since_maintenance_flights?: number; since_maintenance_hours?: number; last_maintenance_action?: string | null }
interface Trends { flights: number; drone_count: number; hours: number; first: string; last: string; warnings_per_flight: number; share_outside_expected: number | null; scored_flights: number; period: 'week' | 'month'; periods: Period[]; drones: DroneTrend[]; note: string; message?: string }

const BLUE = '#2a78d6', ORANGE = '#eb6834'
function token(): Record<string, string> {
  try { const t = localStorage.getItem('aerofleet_token') || ''; return t ? { Authorization: `Bearer ${t}` } : {} } catch { return {} }
}
const day = (iso: string) => new Date(iso).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' })

function Tile({ big, label, sub }: { big: string; label: string; sub?: string }) {
  return (
    <div className="card" style={{ padding: 14, display: 'grid', gap: 2 }}>
      <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--accent)', fontVariantNumeric: 'tabular-nums' }}>{big}</div>
      <div style={{ fontSize: 13, fontWeight: 600 }}>{label}</div>
      {sub && <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{sub}</div>}
    </div>
  )
}

function Bars({ periods, period }: { periods: Period[]; period: string }) {
  const W = 760, H = 216, L = 36, B = 54, top = Math.max(1, ...periods.map((p) => p.flights))
  const bw = Math.min(64, Math.max(4, (W - L - 10) / Math.max(1, periods.length) - 6))
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%' }} role="img" aria-label={`Flights per ${period}`}>
      <line x1={L} y1={H - B} x2={W} y2={H - B} stroke="#94A3B8" />
      <text x={L - 6} y={14} fontSize="10" textAnchor="end" fill="#64748B">{top}</text>
      <text x={L - 6} y={H - B} fontSize="10" textAnchor="end" fill="#64748B">0</text>
      {periods.map((p, i) => {
        const x = L + 6 + i * (bw + 6), h = ((H - B - 10) * p.flights) / top
        return (
          <g key={p.period}>
            <rect x={x} y={H - B - h} width={bw} height={h} rx={3} fill={p.warnings > 0 ? ORANGE : BLUE}><title>{`${p.period}: ${p.flights} flights, ${p.hours} h, ${p.warnings} warnings`}</title></rect>
            <text x={x + bw / 2} y={H - B + 14} fontSize="9" textAnchor="end" fill="#64748B" transform={`rotate(-40 ${x + bw / 2} ${H - B + 14})`}>{p.period}</text>
          </g>)
      })}
    </svg>
  )
}

export default function TrendsPage() {
  const { apiUrl, setActivePage } = useAppStore()
  const [fleet, setFleet] = useState<string>(initialFleet())
  const [t, setT] = useState<Trends | null>(null)
  const [needsAuth, setNeedsAuth] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [from, setFrom] = useState(''); const [to, setTo] = useState('')

  const load = useCallback(async () => {
    setError(null)
    try {
      const r = await fetch(`${apiUrl}/api/v1/assurance/fleets/${encodeURIComponent(fleet)}/trends`, { headers: token() })
      if (r.status === 401) { setNeedsAuth(true); return }
      setNeedsAuth(false)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setT(await r.json())
    } catch (e) { setError((e as Error).message) }
  }, [apiUrl, fleet])
  useEffect(() => { load() }, [load])

  const download = async () => {
    setError(null)
    const q = new URLSearchParams(); if (from) q.set('start', from); if (to) q.set('end', to)
    const r = await fetch(`${apiUrl}/api/v1/assurance/fleets/${encodeURIComponent(fleet)}/operations-log?${q}`, { headers: token() })
    if (!r.ok) { setError(`Export failed (HTTP ${r.status})`); return }
    const url = URL.createObjectURL(await r.blob())
    const a = document.createElement('a'); a.href = url; a.download = `aerofleet-${fleet}-operations.csv`; a.click(); URL.revokeObjectURL(url)
  }

  const history = (id: string) => {
    try { localStorage.setItem('aerofleet_open', JSON.stringify({ kind: 'history', id })) } catch { /* private window */ }
    setActivePage('assurance')
  }

  return (
    <div style={{ display: 'grid', gap: 16, maxWidth: 1100 }} id="trends">
      <div style={{ display: 'flex', gap: 12, alignItems: 'end', flexWrap: 'wrap' }}>
        <div style={{ flex: 1 }}>
          <h1 style={{ margin: 0, fontSize: 22 }}>Fleet trends</h1>
          <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
            The season at a glance for fleet <b>{fleet}</b>: how much it flew, service intervals since last maintenance, how many warnings the logs showed, and which drones are
            drifting from what is expected of them.
          </div>
        </div>
        <FleetPicker apiUrl={apiUrl} fleet={fleet} onChange={setFleet} />
      </div>
      <SimulatedFleetBanner fleet={fleet} />
      {needsAuth && <SignInCard apiUrl={apiUrl} reason="Trends read this install's flight reviews." onSignedIn={load} />}
      {error && <div role="alert" style={{ color: 'var(--status-red)' }}>{error}</div>}
      {t && t.flights === 0 && <div className="card" style={{ padding: 16 }}>{t.message}</div>}
      {t && t.flights > 0 && <>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 12 }}>
          <Tile big={String(t.flights)} label="flights reviewed" sub={`${day(t.first)} to ${day(t.last)}`} />
          <Tile big={`${t.hours} h`} label="flight time" sub={`${t.drone_count} drones`} />
          <Tile big={String(t.warnings_per_flight)} label="warnings per flight" sub="from each log's timeline" />
          <Tile big={t.share_outside_expected != null ? `${Math.round(100 * t.share_outside_expected)}%` : '—'} label="flights outside expected range"
            sub={`learned model, ${t.scored_flights} flights scored; ~10% expected by chance`} />
        </div>
        <div className="card" style={{ padding: 16, display: 'grid', gap: 8 }}>
          <b style={{ fontSize: 14 }}>Flights per {t.period} <span style={{ fontWeight: 400, fontSize: 12, color: 'var(--text-muted)' }}>(orange: the {t.period} had warnings)</span></b>
          <Bars periods={t.periods} period={t.period} />
        </div>
        <div className="card" style={{ padding: 16, display: 'grid', gap: 8 }}>
          <b style={{ fontSize: 14 }}>Per drone</b>
          <style>{'#trends td, #trends th { padding: 6px 12px 6px 0; vertical-align: top; } #trends td:first-child { white-space: nowrap; }'}</style>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}>
              <th>Drone</th><th>Flights</th><th>Hours</th><th>Since maintenance</th><th>Last flown</th><th>Warnings / flight</th>
              <th title="Newest flight's vibration divided by the median of its earlier flights">Vibration, newest vs own</th>
              <th title="Median of battery drain divided by the learned model's typical value">Battery drain vs expected</th><th>Outside expected</th><th /></tr></thead>
            <tbody>{t.drones.map((d) => (
              <tr key={d.drone_id} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={{ padding: '6px 0', fontWeight: 600 }}>{d.drone_id}</td><td>{d.flights}</td><td>{d.hours}</td>
                <td title={d.last_maintenance_action ? `Last: ${d.last_maintenance_action}` : 'No maintenance recorded yet'}>
                  {d.since_maintenance_flights != null ? `${d.since_maintenance_flights} flt · ${d.since_maintenance_hours} h` : '—'}
                </td>
                <td>{day(d.last_flown)}</td>
                <td style={{ color: d.warnings_per_flight >= 1 ? '#B45309' : undefined }}>{d.warnings_per_flight}</td>
                <td>{d.latest_vibration_vs_own_median != null ? `${d.latest_vibration_vs_own_median}x` : '—'}</td>
                <td style={{ color: (d.battery_vs_expected_median ?? 0) > 1.5 ? '#B45309' : undefined }}>{d.battery_vs_expected_median != null ? `${d.battery_vs_expected_median}x` : '—'}</td>
                <td>{d.flights_outside_expected} of {d.flights}</td>
                <td><button className="btn" style={{ padding: '2px 10px', fontSize: 12 }} onClick={() => history(d.drone_id)}>History →</button></td>
              </tr>))}</tbody>
          </table>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{t.note}</div>
        </div>
        <div className="card" style={{ padding: 16, display: 'grid', gap: 8 }} id="operations-log">
          <b style={{ fontSize: 14 }}>Operations log (CSV)</b>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            One row per flight: date, drone and UIN, minutes, distance, the area of the outline flown (a field-size estimate, not the
            area sprayed), take-off point, maximum height, warnings, and the fingerprint of its signed review. The record a spray
            report is filled from; not the official reporting form.
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <label style={{ fontSize: 12 }}>From <input type="date" className="form-input" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
            <label style={{ fontSize: 12 }}>To <input type="date" className="form-input" value={to} onChange={(e) => setTo(e.target.value)} /></label>
            <button className="btn btn--primary" id="btn-ops-log" onClick={download}>Download CSV</button>
          </div>
        </div>
      </>}
    </div>
  )
}
