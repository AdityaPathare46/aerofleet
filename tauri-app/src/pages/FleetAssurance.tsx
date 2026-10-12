import { useCallback, useEffect, useRef, useState } from 'react'
import { useAppStore } from '../store/appStore'

// AeroFleet 2.0 — configuration drift from uploaded parameter files (no drone connected).
// An operator sets the fleet's approved baseline; anyone signed in uploads a drone's parameter
// file and sees what changed against the baseline and against that drone's previous upload.
// Every verdict comes from deterministic code: aerofleet/assurance/ and api/routes/assurance.py.

type Severity = 'CRITICAL' | 'HIGH' | 'TUNING' | 'INFO'
type Verdict = 'BLOCK' | 'REVIEW' | 'OK' | 'NO_REFERENCE'
interface Change { name: string; kind: 'changed' | 'added' | 'removed'; old: number | null; new: number | null; severity: Severity; approved: boolean }
interface Side { verdict: Verdict; counts: Record<Severity, number>; changes: Change[] }
interface Drift {
  drone_id: string; verdict: Verdict; decided_by: 'vs_baseline' | 'vs_previous' | null; param_count: number
  vs_baseline: Side | null; vs_previous: Side | null; filename: string | null; uploaded_at: string
  file?: { format: string; duplicates: string[]; rejected: { line: number; reason: string }[] }
}
interface FleetRow { drone_id: string; verdict: Verdict; counts: Record<Severity, number> | null; uploaded_at: string }
interface Fleet { has_baseline: boolean; drones: FleetRow[]; summary: Record<Verdict, number> }
interface Baseline { param_count: number; source: string | null; set_by: string; set_at: string; approved: Record<string, { value: number; by: string; note: string }> }
interface Check { id: string; title: string; status: string; detail: string; fix: string }
interface Episode { kind: 'off_route' | 'off_altitude' | 'in_no_fly_zone'; start_s: number; duration_s: number; max_m: number; lat: number; lon: number }
interface FlightRow { id: number; drone_id: string; verdict: 'CONFORMED' | 'DEVIATED'; log_name: string | null; uploaded_at: string; flight_s: number; max_off_route_m: number; episodes: number; manual_control: number; settings_changed_critical?: number }
interface Review {
  id: number; drone_id: string; verdict: 'CONFORMED' | 'DEVIATED'; plan_name: string | null; log_name: string | null
  report: {
    tolerances: { corridor_m: number; altitude_m: number; min_duration_s: number }
    horizontal_m: { max: number; p95: number; median: number }; vertical_m: { max: number }
    max_height_m: { flown: number; planned: number }; time_off_route_s: number; flight_s: number
    episodes: Episode[]; manual_control: { mode: string; start_s: number; duration_s: number }[]; notes: string[]
    log: { points: number; param_count: number; notes: string[] }
    settings_changed_in_flight?: { count: number; safety_critical: number; flight_limit: number; changes: { t_s: number; name: string; old: number; new: number; severity: Severity }[] }
  }
  drift?: Drift | null
}
interface Conflict { a: string; b: string; t_s: number; horizontal_m: number; vertical_m: number; duration_s: number }
interface Deconflicted {
  before: Conflict[]; after: Conflict[]; resolved: boolean; unresolved: string[]; note: string
  changes: { id: string; delay_s: number; new_altitude_m: number | null; old_altitude_m: number | null }[]
  schedule: { id: string; launch_at_s: number; cruise_altitude_m: number }[]
  rule: { h_sep_m: number; v_sep_m: number | null }; files: Record<string, string>
}
interface WindCase { energy_wh: number | null; flyable: boolean; margin_wh: number | null }
interface WindReport {
  verdict: 'PASS' | 'FAILS_AT_ALTITUDE' | 'FAIL'; cruise_height_m: number; usable_wh: number; hour_utc: string | null; wind_source: string
  wind: { at_10m: { speed_mps: number; from_deg: number }; at_cruise: { speed_mps: number; from_deg: number }; ratio: number | null; over_limit: boolean; limit_mps: number | null }
  still_air: WindCase; ground_wind: WindCase; cruise_wind: WindCase; assumptions: string
}
const WIND_VERDICT: Record<WindReport['verdict'], { tone: Verdict; label: string; meaning: string }> = {
  PASS: { tone: 'OK', label: 'Enough battery', meaning: 'The mission has enough energy on the wind forecast at its cruise height.' },
  FAILS_AT_ALTITUDE: { tone: 'BLOCK', label: 'Fails at cruise height', meaning: 'It passes on the ground-level wind but not on the stronger wind at cruise height — a ground check would miss this.' },
  FAIL: { tone: 'BLOCK', label: 'Not enough battery', meaning: 'It does not have enough energy even on the ground-level wind.' },
}
interface LedgerEntry { seq: number; kind: string; subject: string; entry_hash: string; created_at: string; created_by: string }
interface Ledger { public_key_pem: string; entries: LedgerEntry[] }
interface LedgerCheck { ok: boolean; entries: number; head: string | null; first_bad_seq: number | null; problem: string | null }
const KIND_LABEL: Record<string, string> = { baseline: 'Baseline set', approval: 'Change approved', drift: 'Settings checked', flight_review: 'Flight reviewed' }
const EPISODE_LABEL: Record<Episode['kind'], string> = { off_route: 'Off the planned route', off_altitude: 'Off the planned height', in_no_fly_zone: 'Inside a no-fly zone' }
const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`
interface Checks { verdict: string; counts: { total: number; evaluated: number; needs_live: number; manual: number; PASS: number; WARN: number; FAIL: number }; evaluated: Check[] }

const VERDICT: Record<Verdict, { color: string; bg: string; label: string; meaning: string }> = {
  BLOCK: { color: 'var(--status-red)', bg: 'var(--status-red-subtle)', label: 'Blocked', meaning: 'A safety-critical setting differs from the approved configuration.' },
  REVIEW: { color: '#92400E', bg: 'var(--status-amber-subtle)', label: 'Needs review', meaning: 'A flight-limit or airframe setting differs from the approved configuration.' },
  OK: { color: 'var(--status-green)', bg: 'var(--status-green-subtle)', label: 'OK', meaning: 'No unapproved safety-critical or flight-limit changes.' },
  NO_REFERENCE: { color: 'var(--text-secondary)', bg: 'var(--bg-subtle, #F1F5F9)', label: 'Nothing to compare', meaning: 'No baseline and no earlier upload yet, so drift cannot be judged.' },
}
const SEVERITY_LABEL: Record<Severity, string> = { CRITICAL: 'Safety-critical', HIGH: 'Flight limit', TUNING: 'Tuning', INFO: 'Other' }

function token(): Record<string, string> {
  const t = localStorage.getItem('aerofleet_token') || ''
  return t ? { Authorization: `Bearer ${t}` } : {}
}

function Pill({ verdict, label }: { verdict: Verdict; label?: string }) {
  const v = VERDICT[verdict]
  return <span style={{ background: v.bg, color: v.color, padding: '2px 10px', borderRadius: 999, fontSize: 12, fontWeight: 700, whiteSpace: 'nowrap' }}>{label ?? v.label}</span>
}

const fmt = (x: number | null) => (x === null ? '—' : String(Number(x.toFixed(6))))
// The backend stores UTC without a zone suffix; show it in the viewer's local time.
const when = (iso: string) => new Date(iso.endsWith('Z') ? iso : iso + 'Z').toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })

export default function FleetAssurancePage() {
  const { apiUrl } = useAppStore()
  const [fleet, setFleet] = useState('default')
  const [fleetDraft, setFleetDraft] = useState('default')   // applied on Enter or blur, not on every keystroke
  const epoch = useRef(0)                                    // discards replies that belong to a previous fleet
  const [droneId, setDroneId] = useState('')
  const [baseline, setBaseline] = useState<Baseline | null>(null)
  const [rows, setRows] = useState<Fleet | null>(null)
  const [drift, setDrift] = useState<Drift | null>(null)
  const [checks, setChecks] = useState<Checks | null>(null)
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const baselineFile = useRef<HTMLInputElement>(null)
  const droneFile = useRef<HTMLInputElement>(null)
  const planFile = useRef<HTMLInputElement>(null)
  const logFile = useRef<HTMLInputElement>(null)
  const [plan, setPlan] = useState<File | null>(null)
  const [flightLog, setFlightLog] = useState<File | null>(null)
  const [flights, setFlights] = useState<FlightRow[]>([])
  const [review, setReview] = useState<Review | null>(null)
  const missionFiles = useRef<HTMLInputElement>(null)
  const [missions, setMissions] = useState<File[]>([])
  const [layered, setLayered] = useState(false)
  const [plansResult, setPlansResult] = useState<Deconflicted | null>(null)
  const windFile = useRef<HTMLInputElement>(null)
  const [windPlan, setWindPlan] = useState<File | null>(null)
  const [payloadKg, setPayloadKg] = useState('1')
  const [usableWh, setUsableWh] = useState('')
  const [windLimit, setWindLimit] = useState('')
  const [windResult, setWindResult] = useState<WindReport | null>(null)
  const [ledger, setLedger] = useState<Ledger | null>(null)
  const [ledgerCheck, setLedgerCheck] = useState<LedgerCheck | null>(null)
  const base = `${apiUrl}/api/v1/assurance/fleets/${encodeURIComponent(fleet.trim() || 'default')}`

  const call = useCallback(async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const r = await fetch(base + path, { ...init, headers: { ...token(), ...(init?.headers || {}) } })
    if (r.status === 401) throw new Error('Sign in to use fleet assurance.')
    if (r.status === 403) throw new Error('Only an operator can set the baseline or approve a change.')
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`)
    return r.json()
  }, [base])

  const refresh = useCallback(async () => {
    const mine = epoch.current
    const [b, r, f] = await Promise.all([call<Baseline>('/baseline').catch(() => null), call<Fleet>('/drift').catch(() => null),
                                         call<FlightRow[]>('/flights').catch(() => [] as FlightRow[])])
    if (mine !== epoch.current) return
    setBaseline(b); setRows(r); setFlights(f)
  }, [call])

  const open = useCallback(async (id: string) => {
    setDrift(await call<Drift>(`/drones/${encodeURIComponent(id)}/drift`))
    setChecks(await call<Checks>(`/drones/${encodeURIComponent(id)}/checks`).catch(() => null))
  }, [call])

  useEffect(() => { epoch.current += 1; setBaseline(null); setRows(null); setFlights([]); setDrift(null); setChecks(null); setReview(null); refresh() }, [refresh])

  const act = async (fn: () => Promise<void>) => {
    setBusy(true); setError(null)
    try { await fn() } catch (e) { setError(e instanceof Error ? e.message : String(e)) } finally { setBusy(false) }
  }
  const upload = (path: string, file: File) => { const body = new FormData(); body.append('file', file); return call<Drift>(path, { method: 'POST', body }) }
  const onBaseline = (f?: File) => f && act(async () => { await upload('/baseline', f); await refresh(); if (drift) await open(drift.drone_id) })
  const onDrone = (f?: File) => f && act(async () => {
    const id = droneId.trim()
    if (!id) throw new Error('Enter the drone id first.')
    const d = await upload(`/drones/${encodeURIComponent(id)}/params`, f)
    setDrift(d); setChecks(await call<Checks>(`/drones/${encodeURIComponent(id)}/checks`).catch(() => null)); await refresh()
  })
  const approve = (c: Change) => act(async () => {
    if (note.trim().length < 3) throw new Error('Write a short reason for the approval first.')
    await call('/approvals', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: c.name, value: c.new, note: note.trim() }) })
    setNote(''); await refresh(); if (drift) await open(drift.drone_id)
  })

  const compare = () => act(async () => {
    const id = droneId.trim()
    if (!id) throw new Error('Enter the drone id first.')
    if (!plan || !flightLog) throw new Error('Choose both the mission file and the flight log.')
    const body = new FormData(); body.append('plan', plan); body.append('log', flightLog)
    const r = await call<Review>(`/drones/${encodeURIComponent(id)}/flights`, { method: 'POST', body })
    setReview(r); if (r.drift) setDrift(r.drift); setPlan(null); setFlightLog(null); await refresh()
  })
  const deconflict = () => act(async () => {
    if (missions.length < 2) throw new Error('Choose at least two mission files.')
    const body = new FormData()
    missions.forEach((f) => body.append('plans', f))
    body.append('options', JSON.stringify({ v_sep_m: layered ? 20 : null }))
    const r = await fetch(`${apiUrl}/api/v1/assurance/plans/deconflict`, { method: 'POST', headers: token(), body })
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`)
    setPlansResult(await r.json())
  })
  const download = (id: string, text: string, ext = '.waypoints') => {
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain' })); a.download = `${id}${ext}`; a.click()
    URL.revokeObjectURL(a.href)
  }
  const root = `${apiUrl}/api/v1/assurance`
  const plain = async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const r = await fetch(root + path, { ...init, headers: token() })
    if (r.status === 401) throw new Error('Sign in to use fleet assurance.')
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`)
    return r.json()
  }
  const checkWind = () => act(async () => {
    if (!windPlan) throw new Error('Choose the mission file first.')
    if (!(Number(usableWh) > 0)) throw new Error('Enter the battery energy available above the landing reserve, in Wh.')
    const body = new FormData(); body.append('plan', windPlan); body.append('payload_kg', payloadKg || '0'); body.append('usable_wh', usableWh)
    if (Number(windLimit) > 0) body.append('max_wind_mps', windLimit)
    setWindResult(await plain<WindReport>('/plans/wind-check', { method: 'POST', body }))
  })
  const loadLedger = useCallback(async () => {
    const t = localStorage.getItem('aerofleet_token') || ''
    const r = await fetch(`${apiUrl}/api/v1/assurance/ledger?limit=10`, { headers: t ? { Authorization: `Bearer ${t}` } : {} }).catch(() => null)
    setLedger(r && r.ok ? await r.json() : null)
  }, [apiUrl])
  useEffect(() => { loadLedger() }, [loadLedger, rows, flights])
  const verifyLedger = () => act(async () => { setLedgerCheck(await plain<LedgerCheck>('/ledger/verify')); await loadLedger() })
  const exportLedger = () => act(async () => {
    const all = await plain<Ledger>('/ledger?limit=1000')
    download('aerofleet-signed-record.json', JSON.stringify({ public_key_pem: all.public_key_pem, entries: [...all.entries].reverse() }, null, 2), '')
  })
  const openReview = (id: number) => act(async () => setReview(await call<Review>(`/flights/${id}`)))

  const side = drift ? (drift.vs_baseline ?? drift.vs_previous) : null
  const newSince = drift?.vs_baseline && drift.vs_previous ? new Set(drift.vs_previous.changes.map((c) => c.name)) : null
  const failed = checks?.evaluated.filter((c) => c.status !== 'PASS') ?? []

  return (
    <div style={{ display: 'grid', gap: 16, maxWidth: 1100 }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 22 }}>Fleet Assurance</h1>
        <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
          Upload a drone's parameter file to see which settings have drifted from the fleet's approved configuration. No drone needs to be connected.
        </div>
      </div>

      <div className="card" style={{ padding: 16, display: 'grid', gap: 12 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'end', flexWrap: 'wrap' }}>
          <label style={{ display: 'grid', gap: 4, fontSize: 12, color: 'var(--text-secondary)' }}>Fleet
            <input id="assurance-fleet" value={fleetDraft} onChange={(e) => setFleetDraft(e.target.value)} style={{ width: 160 }}
              onBlur={() => setFleet(fleetDraft.trim() || 'default')} onKeyDown={(e) => { if (e.key === 'Enter') setFleet(fleetDraft.trim() || 'default') }} />
          </label>
          <div style={{ fontSize: 13, flex: 1, minWidth: 240 }}>
            {baseline
              ? <><b>Approved baseline:</b> {baseline.param_count} settings from {baseline.source || 'an uploaded file'}, set by {baseline.set_by} on {when(baseline.set_at)}</>
              : <><b>No approved baseline yet.</b> An operator sets it from a known-good parameter file.</>}
          </div>
          <input ref={baselineFile} type="file" hidden onChange={(e) => { onBaseline(e.target.files?.[0]); e.target.value = '' }} />
          <button className="btn" id="btn-set-baseline" disabled={busy} onClick={() => baselineFile.current?.click()}>{baseline ? 'Replace baseline' : 'Set baseline'}</button>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'end', flexWrap: 'wrap', borderTop: '1px solid var(--border, #E2E8F0)', paddingTop: 12 }}>
          <label style={{ display: 'grid', gap: 4, fontSize: 12, color: 'var(--text-secondary)' }}>Drone id
            <input id="assurance-drone" value={droneId} onChange={(e) => setDroneId(e.target.value)} placeholder="e.g. AGRI-014" style={{ width: 160 }} />
          </label>
          <input ref={droneFile} type="file" hidden onChange={(e) => { onDrone(e.target.files?.[0]); e.target.value = '' }} />
          <button className="btn btn--primary" id="btn-upload-params" disabled={busy} onClick={() => droneFile.current?.click()}>Upload parameter file</button>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>.param, .parm or .params saved from Mission Planner, MAVProxy or QGroundControl</span>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', borderTop: '1px solid var(--border, #E2E8F0)', paddingTop: 12 }}>
          <b style={{ fontSize: 13 }}>Did it fly the plan?</b>
          <input ref={planFile} id="flight-plan-file" type="file" hidden onChange={(e) => { setPlan(e.target.files?.[0] ?? null); e.target.value = '' }} />
          <input ref={logFile} id="flight-log-file" type="file" hidden onChange={(e) => { setFlightLog(e.target.files?.[0] ?? null); e.target.value = '' }} />
          <button className="btn" disabled={busy} onClick={() => planFile.current?.click()}>{plan ? plan.name : 'Choose mission file'}</button>
          <button className="btn" disabled={busy} onClick={() => logFile.current?.click()}>{flightLog ? flightLog.name : 'Choose flight log'}</button>
          <button className="btn btn--primary" id="btn-compare-flight" disabled={busy || !plan || !flightLog} onClick={compare}>Compare</button>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>.waypoints mission and an ArduPilot .tlog or .bin log, for the drone id above</span>
        </div>
        {error && <div role="alert" style={{ color: 'var(--status-red)', fontSize: 13 }}>{error}</div>}
      </div>

      {rows && rows.drones.length > 0 && (
        <div className="card" style={{ padding: 16 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>
            Drones in this fleet · {rows.summary.BLOCK} blocked · {rows.summary.REVIEW} need review · {rows.summary.OK} OK
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}><th>Drone</th><th>Status</th><th>Safety-critical</th><th>Flight limit</th><th>Tuning</th><th>Uploaded</th><th /></tr></thead>
            <tbody>{rows.drones.map((d) => (
              <tr key={d.drone_id} style={{ borderTop: '1px solid var(--border, #E2E8F0)' }}>
                <td style={{ padding: '6px 0', fontWeight: 600 }}>{d.drone_id}</td><td><Pill verdict={d.verdict} /></td>
                <td>{d.counts?.CRITICAL ?? '—'}</td><td>{d.counts?.HIGH ?? '—'}</td><td>{d.counts?.TUNING ?? '—'}</td>
                <td>{when(d.uploaded_at)}</td>
                <td><button className="btn" onClick={() => act(() => open(d.drone_id))}>View</button></td>
              </tr>))}</tbody>
          </table>
        </div>
      )}

      {drift && (
        <div className="card" style={{ padding: 16, display: 'grid', gap: 12 }} id="drift-detail">
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700, fontSize: 16 }}>{drift.drone_id}</span><Pill verdict={drift.verdict} />
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{VERDICT[drift.verdict].meaning}</span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {drift.param_count} settings in {drift.filename || 'the uploaded file'} · compared with {drift.decided_by === 'vs_baseline' ? 'the approved baseline' : drift.decided_by === 'vs_previous' ? "this drone's previous upload (no baseline set)" : 'nothing yet'}
            {drift.file && drift.file.rejected.length > 0 && <span style={{ color: 'var(--status-red)' }}> · {drift.file.rejected.length} line(s) could not be read (first: line {drift.file.rejected[0].line}, {drift.file.rejected[0].reason})</span>}
          </div>
          {side && side.changes.length === 0 && <div style={{ fontSize: 13 }}>No differences.</div>}
          {side && side.changes.length > 0 && (
            <>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead><tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}><th>Setting</th><th>Kind</th><th>Approved value</th><th>On this drone</th><th /></tr></thead>
                <tbody>{side.changes.map((c) => (
                  <tr key={c.name} style={{ borderTop: '1px solid var(--border, #E2E8F0)' }}>
                    <td style={{ padding: '6px 0', fontFamily: 'var(--font-mono, monospace)', fontWeight: 600 }}>
                      {c.name}{newSince?.has(c.name) && <span title="Changed since this drone's previous upload" style={{ marginLeft: 8, fontSize: 11, color: 'var(--status-red)', fontFamily: 'inherit' }}>NEW</span>}
                    </td>
                    <td style={{ color: c.severity === 'CRITICAL' ? 'var(--status-red)' : c.severity === 'HIGH' ? '#92400E' : 'var(--text-secondary)', fontWeight: c.severity === 'CRITICAL' ? 700 : 400 }}>{SEVERITY_LABEL[c.severity]}</td>
                    <td>{fmt(c.old)}</td><td style={{ fontWeight: 600 }}>{c.kind === 'removed' ? 'missing' : fmt(c.new)}</td>
                    <td style={{ textAlign: 'right' }}>
                      {c.approved ? <span style={{ color: 'var(--status-green)', fontSize: 12, fontWeight: 600 }}>Approved</span>
                        : c.new !== null && baseline && (c.severity === 'CRITICAL' || c.severity === 'HIGH') && <button className="btn" disabled={busy} onClick={() => approve(c)}>Approve</button>}
                    </td>
                  </tr>))}</tbody>
              </table>
              {baseline && side.changes.some((c) => !c.approved && c.new !== null && (c.severity === 'CRITICAL' || c.severity === 'HIGH')) && (
                <label style={{ display: 'grid', gap: 4, fontSize: 12, color: 'var(--text-secondary)' }}>Reason for approving (operators only; recorded with your name)
                  <input id="approval-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Bench drone, no RC receiver fitted" />
                </label>
              )}
            </>
          )}
          {checks && (
            <div style={{ borderTop: '1px solid var(--border, #E2E8F0)', paddingTop: 12, fontSize: 13, display: 'grid', gap: 6 }}>
              <div><b>Compliance checks from this file:</b> {checks.counts.PASS} passed, {checks.counts.WARN} warnings, {checks.counts.FAIL} failed.
                <span style={{ color: 'var(--text-secondary)' }}> {checks.counts.needs_live} of {checks.counts.total} need a live inspection and {checks.counts.manual} are physical checks, so this is not a full inspection.</span></div>
              {failed.map((c) => (
                <div key={c.id}><span style={{ color: c.status === 'FAIL' ? 'var(--status-red)' : '#92400E', fontWeight: 700 }}>{c.status}</span> {c.title}{c.detail && ` — ${c.detail}`}{c.fix && <span style={{ color: 'var(--text-secondary)' }}> Fix: {c.fix}</span>}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {flights.length > 0 && (
        <div className="card" style={{ padding: 16 }} id="flight-list">
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Flight reviews · {flights.filter((f) => f.verdict === 'DEVIATED').length} deviated of {flights.length}</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}><th>Drone</th><th>Result</th><th>Flight time</th><th>Furthest off route</th><th>Excursions</th><th>Settings changed in flight</th><th>Reviewed</th><th /></tr></thead>
            <tbody>{flights.map((f) => (
              <tr key={f.id} style={{ borderTop: '1px solid var(--border, #E2E8F0)' }}>
                <td style={{ padding: '6px 0', fontWeight: 600 }}>{f.drone_id}</td>
                <td><Pill verdict={f.verdict === 'DEVIATED' ? 'BLOCK' : 'OK'} label={f.verdict === 'DEVIATED' ? 'Deviated' : 'Flew the plan'} /></td>
                <td>{clock(f.flight_s)}</td><td>{f.max_off_route_m} m</td><td>{f.episodes + f.manual_control}</td>
                <td style={{ color: f.settings_changed_critical ? 'var(--status-red)' : 'var(--text-muted)', fontWeight: f.settings_changed_critical ? 700 : 400 }}>{f.settings_changed_critical ? `${f.settings_changed_critical} safety-critical` : 'none'}</td><td>{when(f.uploaded_at)}</td>
                <td><button className="btn" onClick={() => openReview(f.id)}>View</button></td>
              </tr>))}</tbody>
          </table>
        </div>
      )}

      {review && (
        <div className="card" style={{ padding: 16, display: 'grid', gap: 10 }} id="flight-detail">
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700, fontSize: 16 }}>{review.drone_id} · flight review</span>
            <Pill verdict={review.verdict === 'DEVIATED' ? 'BLOCK' : 'OK'} label={review.verdict === 'DEVIATED' ? 'Deviated' : 'Flew the plan'} />
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{review.log_name} against {review.plan_name}</span>
          </div>
          <div style={{ fontSize: 13 }}>
            Flight time {clock(review.report.flight_s)} · furthest off route <b>{review.report.horizontal_m.max} m</b> (typical {review.report.horizontal_m.median} m) ·
            furthest off planned height <b>{review.report.vertical_m.max} m</b> · highest flown {review.report.max_height_m.flown} m against {review.report.max_height_m.planned} m planned
          </div>
          {review.report.episodes.length === 0 && review.report.manual_control.length === 0
            ? <div style={{ fontSize: 13 }}>No excursions and no manual takeovers.</div>
            : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead><tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}><th>What happened</th><th>Starting at</th><th>For</th><th>Worst</th><th>Where</th></tr></thead>
                <tbody>
                  {review.report.episodes.map((e, i) => (
                    <tr key={`e${i}`} style={{ borderTop: '1px solid var(--border, #E2E8F0)' }}>
                      <td style={{ padding: '6px 0', fontWeight: 600, color: 'var(--status-red)' }}>{EPISODE_LABEL[e.kind]}</td>
                      <td>{clock(e.start_s)}</td><td>{e.duration_s} s</td><td>{e.kind === 'in_no_fly_zone' ? '—' : `${e.max_m} m`}</td><td>{e.lat}, {e.lon}</td>
                    </tr>))}
                  {review.report.manual_control.map((m, i) => (
                    <tr key={`m${i}`} style={{ borderTop: '1px solid var(--border, #E2E8F0)' }}>
                      <td style={{ padding: '6px 0', fontWeight: 600, color: '#92400E' }}>Pilot took manual control ({m.mode})</td>
                      <td>{clock(m.start_s)}</td><td>{m.duration_s} s</td><td>—</td><td>—</td>
                    </tr>))}
                </tbody>
              </table>
            )}
          {review.report.settings_changed_in_flight && review.report.settings_changed_in_flight.count > 0 && (
            <div id="inflight-changes" style={{ display: 'grid', gap: 6 }}>
              <div style={{ fontSize: 13 }}>
                <b>Settings changed during this flight: {review.report.settings_changed_in_flight.count}</b>
                {review.report.settings_changed_in_flight.safety_critical > 0 && <span style={{ color: 'var(--status-red)', fontWeight: 700 }}> · {review.report.settings_changed_in_flight.safety_critical} safety-critical</span>}
                {review.report.settings_changed_in_flight.flight_limit > 0 && <span style={{ color: '#92400E' }}> · {review.report.settings_changed_in_flight.flight_limit} flight-limit</span>}
                <span style={{ color: 'var(--text-secondary)' }}> — a setting changed and put back before landing does not show in the final settings.</span>
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead><tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}><th>At</th><th>Setting</th><th>Kind</th><th>From</th><th>To</th></tr></thead>
                <tbody>{review.report.settings_changed_in_flight.changes.filter((c) => c.severity === 'CRITICAL' || c.severity === 'HIGH').slice(0, 30).map((c, i) => (
                  <tr key={i} style={{ borderTop: '1px solid var(--border, #E2E8F0)' }}>
                    <td style={{ padding: '6px 0' }}>{clock(c.t_s)}</td>
                    <td style={{ fontFamily: 'var(--font-mono, monospace)', fontWeight: 600 }}>{c.name}</td>
                    <td style={{ color: c.severity === 'CRITICAL' ? 'var(--status-red)' : '#92400E', fontWeight: c.severity === 'CRITICAL' ? 700 : 400 }}>{SEVERITY_LABEL[c.severity]}</td>
                    <td>{fmt(c.old)}</td><td style={{ fontWeight: 600 }}>{fmt(c.new)}</td>
                  </tr>))}</tbody>
              </table>
              {review.report.settings_changed_in_flight.changes.every((c) => c.severity !== 'CRITICAL' && c.severity !== 'HIGH') && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Only tuning and other minor settings changed.</div>
              )}
            </div>
          )}
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Counted as a deviation beyond {review.report.tolerances.corridor_m} m sideways or {review.report.tolerances.altitude_m} m in height for {review.report.tolerances.min_duration_s} s or more; these are this fleet's tolerances, not regulatory limits.
            {' '}{review.report.log.points} positions read from the log.{[...review.report.notes, ...review.report.log.notes].map((n) => ` ${n}.`)}
          </div>
        </div>
      )}

      <div className="card" style={{ padding: 16, display: 'grid', gap: 10 }} id="deconflict-card">
        <div>
          <div style={{ fontWeight: 600 }}>Will these missions conflict?</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Choose the mission files planned for the same period. Each file is one drone; the file name is its id.</div>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <input ref={missionFiles} id="deconflict-files" type="file" multiple hidden onChange={(e) => { setMissions([...(e.target.files ?? [])]); setPlansResult(null); e.target.value = '' }} />
          <button className="btn" disabled={busy} onClick={() => missionFiles.current?.click()}>{missions.length ? `${missions.length} mission files chosen` : 'Choose mission files'}</button>
          <label style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 13 }}>
            <input type="checkbox" id="deconflict-layered" checked={layered} onChange={(e) => setLayered(e.target.checked)} />
            Allow drones to pass at different heights (20 m apart)
          </label>
          <button className="btn btn--primary" id="btn-deconflict" disabled={busy || missions.length < 2} onClick={deconflict}>Check and fix</button>
        </div>
        {plansResult && (
          <div id="deconflict-result" style={{ display: 'grid', gap: 10 }}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', fontSize: 13 }}>
              <Pill verdict={plansResult.resolved ? 'OK' : 'BLOCK'} label={plansResult.resolved ? 'No conflicts left' : `${plansResult.unresolved.length} mission(s) still conflict`} />
              <span>{plansResult.before.length} conflict(s) found, {plansResult.after.length} left after {plansResult.changes.length} change(s).</span>
              {!plansResult.resolved && <span style={{ color: 'var(--status-red)' }}>Could not clear: {plansResult.unresolved.join(', ')}</span>}
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead><tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}><th>Mission</th><th>Launch at</th><th>Cruise height</th><th>Change</th><th /></tr></thead>
              <tbody>{plansResult.schedule.map((m) => {
                const c = plansResult.changes.find((x) => x.id === m.id)
                return (
                  <tr key={m.id} style={{ borderTop: '1px solid var(--border, #E2E8F0)' }}>
                    <td style={{ padding: '6px 0', fontWeight: 600 }}>{m.id}</td><td>+{clock(m.launch_at_s)}</td><td>{m.cruise_altitude_m} m</td>
                    <td style={{ color: c ? '#92400E' : 'var(--text-muted)' }}>{!c ? 'none' : c.new_altitude_m !== null ? `height ${c.old_altitude_m} m → ${c.new_altitude_m} m` : `launch delayed ${c.delay_s} s`}</td>
                    <td style={{ textAlign: 'right' }}><button className="btn" onClick={() => download(m.id, plansResult.files[m.id])}>Download</button></td>
                  </tr>)
              })}</tbody>
            </table>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              Rule: at least {plansResult.rule.h_sep_m} m apart sideways{plansResult.rule.v_sep_m ? ` or ${plansResult.rule.v_sep_m} m apart in height` : ', whatever the height'}. {plansResult.note} Delays are a launch schedule; the mission files are not changed for them.
            </div>
          </div>
        )}
      </div>

      <div className="card" style={{ padding: 16, display: 'grid', gap: 10 }} id="wind-card">
        <div>
          <div style={{ fontWeight: 600 }}>Is there enough battery for the wind at cruise height?</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Wind is usually stronger aloft than near the ground. This uses the forecast for the mission's start point.</div>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'end', flexWrap: 'wrap' }}>
          <input ref={windFile} id="wind-plan-file" type="file" hidden onChange={(e) => { setWindPlan(e.target.files?.[0] ?? null); setWindResult(null); e.target.value = '' }} />
          <button className="btn" disabled={busy} onClick={() => windFile.current?.click()}>{windPlan ? windPlan.name : 'Choose mission file'}</button>
          <label style={{ display: 'grid', gap: 4, fontSize: 12, color: 'var(--text-secondary)' }}>Payload (kg)
            <input id="wind-payload" value={payloadKg} onChange={(e) => setPayloadKg(e.target.value)} inputMode="decimal" style={{ width: 90 }} />
          </label>
          <label style={{ display: 'grid', gap: 4, fontSize: 12, color: 'var(--text-secondary)' }}>Battery above reserve (Wh)
            <input id="wind-usable" value={usableWh} onChange={(e) => setUsableWh(e.target.value)} inputMode="decimal" style={{ width: 130 }} />
          </label>
          <label style={{ display: 'grid', gap: 4, fontSize: 12, color: 'var(--text-secondary)' }}>Wind limit (m/s, optional)
            <input id="wind-limit" value={windLimit} onChange={(e) => setWindLimit(e.target.value)} inputMode="decimal" style={{ width: 130 }} />
          </label>
          <button className="btn btn--primary" id="btn-wind-check" disabled={busy || !windPlan} onClick={checkWind}>Check</button>
        </div>
        {windResult && (
          <div id="wind-result" style={{ display: 'grid', gap: 8, fontSize: 13 }}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <Pill verdict={WIND_VERDICT[windResult.verdict].tone} label={WIND_VERDICT[windResult.verdict].label} />
              <span style={{ color: 'var(--text-secondary)' }}>{WIND_VERDICT[windResult.verdict].meaning}</span>
            </div>
            <div>
              Wind at 10 m: <b>{windResult.wind.at_10m.speed_mps} m/s</b> · at {windResult.cruise_height_m} m cruise height: <b>{windResult.wind.at_cruise.speed_mps} m/s</b>
              {windResult.wind.ratio !== null && <> ({windResult.wind.ratio}× the ground wind)</>}
              {windResult.wind.over_limit && <span style={{ color: 'var(--status-red)' }}> · above the {windResult.wind.limit_mps} m/s limit</span>}
            </div>
            <table style={{ borderCollapse: 'collapse', maxWidth: 520 }}>
              <thead><tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}><th style={{ paddingRight: 24 }}>Wind used</th><th style={{ paddingRight: 24 }}>Energy needed</th><th>Left over</th></tr></thead>
              <tbody>{([['No wind', windResult.still_air], ['Ground-level wind', windResult.ground_wind], ['Wind at cruise height', windResult.cruise_wind]] as [string, WindCase][]).map(([name, c]) => (
                <tr key={name} style={{ borderTop: '1px solid var(--border, #E2E8F0)' }}>
                  <td style={{ padding: '6px 24px 6px 0' }}>{name}</td><td>{c.flyable ? `${c.energy_wh} Wh` : 'cannot make headway'}</td>
                  <td style={{ fontWeight: 600, color: c.margin_wh !== null && c.margin_wh >= 0 ? 'var(--status-green)' : 'var(--status-red)' }}>{c.margin_wh !== null ? `${c.margin_wh} Wh` : '—'}</td>
                </tr>))}</tbody>
            </table>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{windResult.wind_source}{windResult.hour_utc ? `, ${windResult.hour_utc} UTC` : ''}. {windResult.assumptions}</div>
          </div>
        )}
      </div>

      <div className="card" style={{ padding: 16, display: 'grid', gap: 10 }} id="ledger-card">
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 240 }}>
            <div style={{ fontWeight: 600 }}>Signed record</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Every baseline, approval, settings check and flight review is signed and linked to the one before, so later edits can be detected.</div>
          </div>
          <button className="btn" id="btn-ledger-verify" disabled={busy} onClick={verifyLedger}>Check the record</button>
          <button className="btn" id="btn-ledger-export" disabled={busy || !ledger?.entries.length} onClick={exportLedger}>Export for an auditor</button>
        </div>
        {ledgerCheck && (
          <div id="ledger-check" style={{ fontSize: 13, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <Pill verdict={ledgerCheck.ok ? 'OK' : 'BLOCK'} label={ledgerCheck.ok ? 'Record intact' : 'Record has been changed'} />
            <span>{ledgerCheck.ok ? `${ledgerCheck.entries} entries checked. Latest fingerprint ${ledgerCheck.head ? ledgerCheck.head.slice(0, 16) + '…' : 'none yet'}` : ledgerCheck.problem}</span>
          </div>
        )}
        {ledger && ledger.entries.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}><th>#</th><th>What</th><th>For</th><th>When</th><th>By</th><th>Fingerprint</th></tr></thead>
            <tbody>{ledger.entries.map((e) => (
              <tr key={e.seq} style={{ borderTop: '1px solid var(--border, #E2E8F0)' }}>
                <td style={{ padding: '6px 0' }}>{e.seq}</td><td>{KIND_LABEL[e.kind] ?? e.kind}</td><td>{e.subject}</td><td>{when(e.created_at)}</td><td>{e.created_by}</td>
                <td style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 12 }}>{e.entry_hash.slice(0, 12)}…</td>
              </tr>))}</tbody>
          </table>
        )}
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>This shows whether the record was altered afterwards. It does not prove the uploaded files were genuine.</div>
      </div>
    </div>
  )
}
