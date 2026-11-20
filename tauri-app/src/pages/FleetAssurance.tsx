import { useCallback, useEffect, useRef, useState } from 'react'
import { useAppStore } from '../store/appStore'
import type { RehearsalDto } from '../components/vr/Rehearsal'
import SignInCard from '../components/SignInCard'

// AeroFleet 2.0 — configuration drift from uploaded parameter files (no drone connected).
// An operator sets the fleet's approved baseline; anyone signed in uploads a drone's parameter
// file and sees what changed against the baseline and against that drone's previous upload.
// Every verdict comes from deterministic code: aerofleet/assurance/ and api/routes/assurance.py.

type Severity = 'CRITICAL' | 'HIGH' | 'TUNING' | 'INFO'
type Verdict = 'BLOCK' | 'REVIEW' | 'OK' | 'NO_REFERENCE'
interface PublicSetting { same_value_pct: number; logs: number; most_common: string; most_common_pct: number; note: string }
interface Change { name: string; kind: 'changed' | 'added' | 'removed'; old: number | null; new: number | null; severity: Severity; approved: boolean; public?: PublicSetting | null }
// Where a value stands among public PX4 flights rated good or great (aerofleet/assurance/public_reference.py)
interface PublicVib { higher_than_pct: number; flights: number; vehicles: number; median: number; source: string; vehicle: string; note: string }
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
type FlightVerdict = 'CONFORMED' | 'DEVIATED' | 'LOG_ONLY'   // LOG_ONLY: a log reviewed with no mission file
interface FlightRow { id: number; drone_id: string; verdict: FlightVerdict; log_name: string | null; uploaded_at: string; flight_s: number; max_off_route_m: number | null; episodes: number; manual_control: number; settings_changed_critical?: number }
interface Review {
  id: number; drone_id: string; verdict: FlightVerdict; plan_name: string | null; log_name: string | null
  report: {
    tolerances: { corridor_m: number; altitude_m: number; min_duration_s: number } | null
    horizontal_m: { max: number; p95: number; median: number } | null; vertical_m: { max: number } | null
    max_height_m: { flown: number; planned: number | null }; time_off_route_s: number | null; flight_s: number
    vibration?: { p95: number; median: number; p95_whole_flight?: number; end_margin_s?: number; source: string; flown_at?: string } | null
    normal_flight?: { note: string; model?: string; targets: Record<string, { label: string; unit: string; observed: number; low: number; mid: number; high: number; position: 'below' | 'inside' | 'above'; times_mid: number | null }> } | null
    episodes: Episode[]; manual_control: { mode: string; start_s: number; duration_s: number }[]; notes: string[]
    log: { points: number; param_count: number; notes: string[] }
    settings_changed_in_flight?: { count: number; safety_critical: number; flight_limit: number; changes: { t_s: number; name: string; old: number; new: number; severity: Severity }[] }
    evidence_timeline?: TimelineEvent[]
    data_quality?: { position_rate_hz: number | null; longest_gap_s: number | null; gps_satellites_median: number | null; gps_hdop_median: number | null; gps_hdop_worst: number | null; height_reference: string; clock: string; note: string }
    around_episodes?: { episode: number; kind: Episode['kind']; start_s: number; summary: string }[]
  }
  drift?: Drift | null
  public_vibration?: PublicVib | null
}
// No drone is flagged: the study did not show a vibration threshold to beat random inspection, so only the position is shown.
interface VibrationRow { drone_id: string; source: string; flights: number; vibration_p95: number; rank: number; group_size: number; comparable: boolean; times_group_median: number | null; public?: PublicVib | null }
interface Vibration { drones: VibrationRow[]; evidence: string; note: string }
interface VibFlight { review_id: number; p95: number; when: string; ordered_by: 'gps_time' | 'upload_time'; log_name: string | null; public_pct?: number | null }
interface VibHistory {
  drone_id: string; source?: string; flights: VibFlight[]; evidence: string; order_note?: string; message: string | null
  latest_vs_own: { latest_p95: number; earlier_median: number; earlier_flights: number; higher_than: number; times_own_median: number | null } | null
  among_peers: VibrationRow | null
  latest_vs_public?: PublicVib | null
  maintenance?: MaintenanceItem[]; maintenance_actions?: string[]
}
interface BatchRow { file: string; drone_id: string | null; matched_by: string | null; review_id?: number; verdict?: string; flight_s?: number; warnings?: string[]; outside_expected?: string[]; error: string | null }
interface BatchResult { results: BatchRow[]; reviewed: number; not_reviewed: number }
interface MaintenanceItem {
  id: number; done_at: string; action: string; note: string | null; done_by: string
  effect: { flights_before: number; flights_after: number; summary: string; note: string
    measures: { label: string; unit: string; before: number; after: number; change_pct: number | null; flights_before: number; flights_after: number }[] }
}
interface CheckItem { cause: string; experts_found: string; mentioned: boolean; matched_words: string[]; checks: string[]; fixes: string[]; aerofleet_check: string }
interface SimilarCase { title: string; url: string; score: number; expert_conclusion: string; cause: string; who_diagnosed: string; poster_confirmed_fix: string; flight_review_logs: string[] }
interface Troubleshoot { checklist: CheckItem[]; similar_cases: SimilarCase[]; cases_searched: number; note: string; how_well_it_works: string; message?: string; this_drone_vibration?: Partial<VibrationRow> & { message?: string } }
const VIB_SOURCE: Record<string, string> = { ardupilot_vibe: 'ArduPilot VIBE (m/s²)', px4_imu: 'PX4 accel vibration metric', px4_estimator: 'PX4 estimator vibration (older firmware)' }
interface TimelineEvent { t_s: number; kind: 'mode' | 'setting' | 'battery' | 'gps' | 'sensor' | 'plan' | 'end'; level: 'warning' | 'notice' | 'info'; text: string }
const LEVEL_COLOR: Record<TimelineEvent['level'], string> = { warning: 'var(--status-red)', notice: '#92400E', info: 'var(--text-secondary)' }
interface Conflict { a: string; b: string; t_s: number; horizontal_m: number; vertical_m: number; duration_s: number }
interface Deconflicted {
  before: Conflict[]; after: Conflict[]; resolved: boolean; unresolved: string[]; note: string
  changes: { id: string; delay_s: number; new_altitude_m: number | null; old_altitude_m: number | null }[]
  schedule: { id: string; launch_at_s: number; cruise_altitude_m: number }[]
  rule: { h_sep_m: number; v_sep_m: number | null }; files: Record<string, string>
  rehearsal?: RehearsalDto
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
const KIND_LABEL: Record<string, string> = { baseline: 'Baseline set', approval: 'Change approved', drift: 'Settings checked', flight_review: 'Flight reviewed', deconflict: 'Missions checked for conflicts', airspace_check: 'Routes checked against airspace', maintenance: 'Maintenance recorded', wind_check: 'Wind checked' }
const EPISODE_LABEL: Record<Episode['kind'], string> = { off_route: 'Off the planned route', off_altitude: 'Off the planned height', in_no_fly_zone: 'Inside a no-fly zone' }
// rounds the total first: 299.9 s is 5:00, not 4:60
const clock = (s: number) => { const t = Math.max(0, Math.round(s)); return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}` }
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
const sig3 = (x: number) => (Math.abs(x) >= 1000 ? Math.round(x).toString() : Number(x.toPrecision(3)).toString())   // 3 significant figures
const when = (iso: string) => new Date(iso.endsWith('Z') ? iso : iso + 'Z').toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })

export default function FleetAssurancePage() {
  const { apiUrl, setVrFlight, setVrRehearsal, setActivePage } = useAppStore()
  const remembered = (() => { try { return localStorage.getItem('aerofleet_fleet') || 'default' } catch { return 'default' } })()
  const [fleet, setFleet] = useState(remembered)             // the last fleet opened on this computer
  const [fleetDraft, setFleetDraft] = useState(remembered)   // applied on Enter or blur, not on every keystroke
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
  const [vibration, setVibration] = useState<Vibration | null>(null)
  const [history, setHistory] = useState<VibHistory | null>(null)
  const batchFile = useRef<HTMLInputElement>(null)
  const [batch, setBatch] = useState<BatchResult | null>(null)
  const [mDate, setMDate] = useState(''); const [mAction, setMAction] = useState(''); const [mNote, setMNote] = useState('')
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
  const [symptom, setSymptom] = useState('')
  const [help, setHelp] = useState<Troubleshoot | null>(null)
  const [ledgerCheck, setLedgerCheck] = useState<LedgerCheck | null>(null)
  const [needsAuth, setNeedsAuth] = useState(false)      // the API answered 401: show the sign-in card instead of an empty page
  const base = `${apiUrl}/api/v1/assurance/fleets/${encodeURIComponent(fleet.trim() || 'default')}`
  useEffect(() => { try { localStorage.setItem('aerofleet_fleet', fleet.trim() || 'default') } catch { /* private window */ } }, [fleet])

  const call = useCallback(async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const r = await fetch(base + path, { ...init, headers: { ...token(), ...(init?.headers || {}) } })
    setNeedsAuth(r.status === 401)
    if (r.status === 401) throw new Error('Sign in to use fleet assurance.')
    if (r.status === 403) throw new Error('Only an operator can set the baseline or approve a change.')
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`)
    return r.json()
  }, [base])

  const refresh = useCallback(async () => {
    const mine = epoch.current
    const [b, r, f, v] = await Promise.all([call<Baseline>('/baseline').catch(() => null), call<Fleet>('/drift').catch(() => null),
                                         call<FlightRow[]>('/flights').catch(() => [] as FlightRow[]), call<Vibration>('/vibration').catch(() => null)])
    if (mine !== epoch.current) return
    setBaseline(b); setRows(r); setFlights(f); setVibration(v)
  }, [call])

  const open = useCallback(async (id: string) => {
    setDrift(await call<Drift>(`/drones/${encodeURIComponent(id)}/drift`))
    setChecks(await call<Checks>(`/drones/${encodeURIComponent(id)}/checks`).catch(() => null))
  }, [call])

  useEffect(() => { epoch.current += 1; setBaseline(null); setRows(null); setFlights([]); setVibration(null); setHistory(null); setDrift(null); setChecks(null); setReview(null); refresh() }, [refresh])

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
    if (!flightLog) throw new Error('Choose the flight log.')
    const body = new FormData(); if (plan) body.append('plan', plan); body.append('log', flightLog)   // the mission file is optional
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
  const askHelp = () => act(async () => {
    if (symptom.trim().length < 3) throw new Error('Describe what the drone did first.')
    const id = droneId.trim()
    const r = await fetch(`${root}/troubleshoot`, { method: 'POST', headers: { ...token(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ description: symptom.trim(), ...(id ? { fleet: fleet.trim() || 'default', drone_id: id } : {}) }) })
    if (r.status === 401) throw new Error('Sign in to use fleet assurance.')
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`)
    setHelp(await r.json())
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
  const printable = (id: number) => act(async () => {
    const r = await fetch(`${base}/flights/${id}/report`, { headers: token() })
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`)
    download(`flight-review-${id}`, await r.text(), '.html')
  })
  const addMaintenance = () => act(async () => {
    if (!history || !mDate || !mAction) throw new Error('Choose the date and what was done.')
    await call(`/drones/${encodeURIComponent(history.drone_id)}/maintenance`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ done_at: `${mDate}T12:00:00`, action: mAction, note: mNote.trim() }) })
    setMDate(''); setMAction(''); setMNote('')
    setHistory(await call<VibHistory>(`/drones/${encodeURIComponent(history.drone_id)}/vibration`))
  })
  const uploadBatch = (files: File[]) => act(async () => {
    if (!files.length) return
    const body = new FormData(); files.forEach((f) => body.append('logs', f))
    setBatch(await call<BatchResult>('/flights/batch', { method: 'POST', body })); await refresh()
  })
  const openHistory = (id: string) => act(async () => setHistory(await call<VibHistory>(`/drones/${encodeURIComponent(id)}/vibration`)))
  const openReview = (id: number) => act(async () => setReview(await call<Review>(`/flights/${id}`)))

  // Arriving from the readiness board with "open this drone's settings / this flight": open it and scroll to it once.
  useEffect(() => {
    let raw: string | null = null
    try { raw = localStorage.getItem('aerofleet_open'); localStorage.removeItem('aerofleet_open') } catch { return }
    if (!raw) return
    const req = JSON.parse(raw) as { kind: 'drift' | 'review' | 'history'; id: string | number }
    const show = (el: string) => setTimeout(() => document.getElementById(el)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 300)
    ;(async () => {
      if (req.kind === 'drift') { await open(String(req.id)); show('drift-detail') }
      else if (req.kind === 'history') { setHistory(await call<VibHistory>(`/drones/${encodeURIComponent(String(req.id))}/vibration`)); show('vibration-history') }
      else { setReview(await call<Review>(`/flights/${req.id}`)); show('flight-detail') }
    })().catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const side = drift ? (drift.vs_baseline ?? drift.vs_previous) : null
  const newSince = drift?.vs_baseline && drift.vs_previous ? new Set(drift.vs_previous.changes.map((c) => c.name)) : null
  const failed = checks?.evaluated.filter((c) => c.status !== 'PASS') ?? []

  return (
    <div style={{ display: 'grid', gap: 16, maxWidth: 1100 }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 22 }}>Fleet Assurance</h1>
        <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
          Checks a fleet from the files you already have: settings against the approved configuration, each flight's events in time order,
          and each drone's vibration against its own history and comparable drones. No drone needs to be connected, and no cause is named.
        </div>
      </div>

      {needsAuth && <SignInCard apiUrl={apiUrl} reason="Fleet assurance keeps a signed record of who checked what, so it needs a signed-in user." onSignedIn={() => { setNeedsAuth(false); refresh() }} />}

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
          <b style={{ fontSize: 13 }}>Review a flight</b>
          <input ref={planFile} id="flight-plan-file" type="file" hidden onChange={(e) => { setPlan(e.target.files?.[0] ?? null); e.target.value = '' }} />
          <input ref={logFile} id="flight-log-file" type="file" hidden onChange={(e) => { setFlightLog(e.target.files?.[0] ?? null); e.target.value = '' }} />
          <input ref={batchFile} id="batch-log-files" type="file" multiple hidden accept=".ulg,.bin,.tlog" onChange={(e) => { uploadBatch(Array.from(e.target.files ?? [])); e.target.value = '' }} />
          <button className="btn" disabled={busy} onClick={() => planFile.current?.click()}>{plan ? plan.name : 'Mission file (optional)'}</button>
          <button className="btn" disabled={busy} onClick={() => logFile.current?.click()}>{flightLog ? flightLog.name : 'Choose flight log'}</button>
          <button className="btn btn--primary" id="btn-compare-flight" disabled={busy || !flightLog} onClick={compare}>{plan ? 'Compare with plan' : 'Review log'}</button>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>A flight log (ArduPilot .tlog or .bin, PX4 .ulg) for the drone id above. Add the .waypoints mission to also check whether it flew the plan.</span>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', borderTop: '1px solid var(--border, #E2E8F0)', paddingTop: 12 }}>
          <b style={{ fontSize: 13 }}>Evening upload</b>
          <button className="btn btn--primary" id="btn-batch-upload" disabled={busy} onClick={() => batchFile.current?.click()}>Upload the day's logs</button>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Select all of today's logs at once. Each is matched to its drone by the flight controller's own id; the first time, name a file DRONEID_anything.ulg.</span>
        </div>
        {batch && (
          <div id="batch-results" style={{ display: 'grid', gap: 6 }}>
            <div style={{ fontSize: 13 }}><b>{batch.reviewed} reviewed</b>{batch.not_reviewed > 0 && <span style={{ color: 'var(--status-red)' }}> · {batch.not_reviewed} not reviewed</span>}</div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead><tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}><th>File</th><th>Drone</th><th>Matched by</th><th>Flight</th><th>Warnings</th><th>Outside expected</th><th /></tr></thead>
              <tbody>{batch.results.map((r) => (
                <tr key={r.file} style={{ borderTop: '1px solid var(--border, #E2E8F0)' }}>
                  <td style={{ padding: '5px 0', fontFamily: 'var(--font-mono, monospace)', fontSize: 12 }}>{r.file}</td>
                  <td style={{ fontWeight: 600 }}>{r.drone_id ?? '—'}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{r.matched_by ?? ''}</td>
                  {r.error ? <td colSpan={3} style={{ color: 'var(--status-red)' }}>{r.error}</td> : <>
                    <td>{r.flight_s != null ? clock(r.flight_s) : '—'}</td>
                    <td style={{ color: (r.warnings ?? []).length ? '#92400E' : 'var(--text-muted)' }}>{(r.warnings ?? []).length ? (r.warnings ?? []).join('; ') : 'none'}</td>
                    <td style={{ color: (r.outside_expected ?? []).length ? '#92400E' : 'var(--text-muted)' }}>{(r.outside_expected ?? []).length ? (r.outside_expected ?? []).join(', ') : 'none'}</td></>}
                  <td>{r.review_id != null && <button className="btn" style={{ padding: '2px 10px', fontSize: 12 }} onClick={() => openReview(r.review_id!)}>View</button>}</td>
                </tr>))}</tbody>
            </table>
          </div>)}
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
                <thead><tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}><th>Setting</th><th>Kind</th><th>{drift.vs_baseline ? 'Approved value' : 'Previous upload'}</th><th>On this drone</th><th title="How public PX4 flights rated good or great set this value">Public PX4 flights</th><th /></tr></thead>
                <tbody>{side.changes.map((c) => (
                  <tr key={c.name} style={{ borderTop: '1px solid var(--border, #E2E8F0)' }}>
                    <td style={{ padding: '6px 0', fontFamily: 'var(--font-mono, monospace)', fontWeight: 600 }}>
                      {c.name}{newSince?.has(c.name) && <span title="Changed since this drone's previous upload" style={{ marginLeft: 8, fontSize: 11, color: 'var(--status-red)', fontFamily: 'inherit' }}>NEW</span>}
                    </td>
                    <td style={{ color: c.severity === 'CRITICAL' ? 'var(--status-red)' : c.severity === 'HIGH' ? '#92400E' : 'var(--text-secondary)', fontWeight: c.severity === 'CRITICAL' ? 700 : 400 }}>{SEVERITY_LABEL[c.severity]}</td>
                    <td>{fmt(c.old)}</td><td style={{ fontWeight: 600 }}>{c.kind === 'removed' ? 'missing' : fmt(c.new)}</td>
                    <td style={{ fontSize: 12, color: 'var(--text-secondary)' }} title={c.public?.note}>
                      {c.public ? <><b style={{ color: c.public.same_value_pct < 10 ? 'var(--status-red)' : 'inherit' }}>{c.public.same_value_pct}%</b> use this value
                        {c.public.most_common !== fmt(c.new) && <> · most use {c.public.most_common} ({c.public.most_common_pct}%)</>}</> : '—'}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      {c.approved ? <span style={{ color: 'var(--status-green)', fontSize: 12, fontWeight: 600 }}>Approved</span>
                        : c.new !== null && baseline && (c.severity === 'CRITICAL' || c.severity === 'HIGH') && <button className="btn" disabled={busy} onClick={() => approve(c)}>Approve</button>}
                    </td>
                  </tr>))}</tbody>
              </table>
              {side.changes.find((c) => c.public)?.public && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{side.changes.find((c) => c.public)?.public?.note}</div>)}
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
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Flight reviews · latest {flights.length} · {flights.filter((f) => f.verdict === 'DEVIATED').length} deviated of {flights.filter((f) => f.verdict !== 'LOG_ONLY').length} compared with a plan</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}><th>Drone</th><th>Result</th><th>Flight time</th><th>Furthest off route</th><th>Excursions</th><th>Settings changed in flight</th><th>Reviewed</th><th /></tr></thead>
            <tbody>{flights.map((f) => (
              <tr key={f.id} style={{ borderTop: '1px solid var(--border, #E2E8F0)' }}>
                <td style={{ padding: '6px 0', fontWeight: 600 }}>{f.drone_id}</td>
                <td>{f.verdict === 'LOG_ONLY' ? <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Log only</span>
                  : <Pill verdict={f.verdict === 'DEVIATED' ? 'BLOCK' : 'OK'} label={f.verdict === 'DEVIATED' ? 'Deviated' : 'Flew the plan'} />}</td>
                <td>{clock(f.flight_s)}</td><td>{f.max_off_route_m == null ? '—' : `${f.max_off_route_m} m`}</td><td>{f.episodes + f.manual_control}</td>
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
            {review.verdict === 'LOG_ONLY' ? <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Log only · no plan to compare with</span>
              : <Pill verdict={review.verdict === 'DEVIATED' ? 'BLOCK' : 'OK'} label={review.verdict === 'DEVIATED' ? 'Deviated' : 'Flew the plan'} />}
            <span style={{ fontSize: 12, color: 'var(--text-muted)', flex: 1 }}>{review.log_name}{review.verdict === 'LOG_ONLY' ? '' : ` against ${review.plan_name}`}</span>
            <button className="btn" id="btn-printable-report" disabled={busy} onClick={() => printable(review.id)} title="A self-contained page; open it and print to PDF">Printable report</button>
            <button className="btn" id="btn-show-vr" onClick={() => { setVrFlight({ fleet: fleet.trim() || 'default', id: review.id }); setActivePage('vr') }}
              title="Replay this flight on the VR table: plan against flown track, with the log's events; a paired headset follows">Show on the VR table</button>
          </div>
          <div style={{ fontSize: 13 }}>
            Flight time {clock(review.report.flight_s)}
            {review.report.horizontal_m && review.report.vertical_m
              ? <> · furthest off route <b>{review.report.horizontal_m.max} m</b> (typical {review.report.horizontal_m.median} m) ·
                furthest off planned height <b>{review.report.vertical_m.max} m</b> · highest flown {review.report.max_height_m.flown} m against {review.report.max_height_m.planned} m planned</>
              : <> · highest flown {review.report.max_height_m.flown} m</>}
            {review.report.vibration && <> · vibration (95th pct.) <b>{fmt(review.report.vibration.p95)}</b>
              {review.report.vibration.end_margin_s ? ` with the last ${review.report.vibration.end_margin_s} s left out` : ''}
              {review.report.vibration.p95_whole_flight != null && review.report.vibration.p95_whole_flight !== review.report.vibration.p95 ? ` (whole flight ${fmt(review.report.vibration.p95_whole_flight)})` : ''}
              {review.public_vibration && <span title={review.public_vibration.note}>, <b>higher than {review.public_vibration.higher_than_pct}%</b> of {review.public_vibration.flights} public PX4 flights rated good or great</span>}</>}
          </div>
          {review.report.normal_flight && (
            <div id="normal-flight" style={{ display: 'grid', gap: 6, padding: 10, borderRadius: 8, background: 'var(--bg-secondary, #F8FAFC)' }}>
              <div style={{ fontSize: 13 }}><b>Compared with healthy flights of similar drones</b>
                <span style={{ color: 'var(--text-secondary)' }}> (learned model{review.report.normal_flight.model ? `: ${review.report.normal_flight.model}` : ''})</span></div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead><tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}><th>Measure</th><th>This flight</th><th title="In testing on drones the model had never seen, this range held about 90% of flights">Expected range (~90% of healthy flights)</th><th>Typical</th><th /></tr></thead>
                <tbody>{Object.entries(review.report.normal_flight.targets).map(([k, t]) => (
                  <tr key={k} style={{ borderTop: '1px solid var(--border, #E2E8F0)' }}>
                    <td style={{ padding: '5px 0' }}>{t.label} <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>({t.unit})</span></td>
                    <td style={{ fontWeight: 700 }}>{sig3(t.observed)}</td>
                    <td>{sig3(k === 'battery_drop_pct_per_min' ? Math.max(0, t.low) : t.low)} to {sig3(t.high)}</td><td>{sig3(t.mid)}</td>
                    <td style={{ fontWeight: 600, color: t.position === 'inside' ? 'var(--status-green)' : '#92400E' }}>
                      {t.position === 'inside' ? 'within range' : `${t.position} range${t.times_mid != null ? ` (${t.times_mid}x typical)` : ''}`}</td>
                  </tr>))}</tbody>
              </table>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{review.report.normal_flight.note}</div>
            </div>)}
          {review.report.episodes.length === 0 && review.report.manual_control.length === 0
            ? <div style={{ fontSize: 13 }}>{review.verdict === 'LOG_ONLY' ? 'No pilot-flown modes in the log.' : 'No excursions and no manual takeovers.'}</div>
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
                      <td style={{ padding: '6px 0', fontWeight: 600, color: '#92400E' }}>{review.verdict === 'LOG_ONLY' ? 'Pilot flew in' : 'Pilot took manual control'} ({m.mode})</td>
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
          {review.report.evidence_timeline && review.report.evidence_timeline.length > 1 && (
            <div id="evidence-timeline" style={{ display: 'grid', gap: 6 }}>
              <div style={{ fontSize: 13 }}><b>Timeline from the log</b>
                <span style={{ color: 'var(--text-secondary)' }}> — what happened and when. AeroFleet does not name a cause: on 590 public crash logs neither a fixed rule nor a trained model told pilot error from an aircraft fault better than chance, so that call is yours.</span>
              </div>
              {(review.report.around_episodes ?? []).map((a) => (
                <div key={a.episode} style={{ fontSize: 13, padding: '6px 10px', borderLeft: '3px solid var(--status-red)', background: 'var(--bg-secondary, #F8FAFC)' }}>
                  <b>{EPISODE_LABEL[a.kind]} at {clock(a.start_s)}</b> — around it: {a.summary}
                </div>))}
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead><tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}><th style={{ width: 70 }}>At</th><th>Event</th></tr></thead>
                <tbody>{review.report.evidence_timeline.slice(0, 200).map((ev, i) => (
                  <tr key={i} style={{ borderTop: '1px solid var(--border, #E2E8F0)' }}>
                    <td style={{ padding: '5px 0', fontVariantNumeric: 'tabular-nums' }}>{clock(ev.t_s)}</td>
                    <td style={{ color: LEVEL_COLOR[ev.level], fontWeight: ev.level === 'warning' ? 600 : 400 }}>{ev.text}</td>
                  </tr>))}</tbody>
              </table>
            </div>
          )}
          {review.report.data_quality && (
            <div id="data-quality" style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
              <b>Evidence quality:</b> positions {review.report.data_quality.position_rate_hz ?? '?'} per second (longest gap {review.report.data_quality.longest_gap_s ?? '?'} s)
              {' '}· GPS {review.report.data_quality.gps_satellites_median ?? '?'} satellites, HDOP {review.report.data_quality.gps_hdop_median ?? '?'} median / {review.report.data_quality.gps_hdop_worst ?? '?'} worst
              {' '}· height: {review.report.data_quality.height_reference} · times: {review.report.data_quality.clock}. {review.report.data_quality.note}
            </div>
          )}
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {review.report.tolerances && <>Counted as a deviation beyond {review.report.tolerances.corridor_m} m sideways or {review.report.tolerances.altitude_m} m in height for {review.report.tolerances.min_duration_s} s or more; these are this fleet's tolerances, not regulatory limits.</>}
            {' '}{review.report.log.points} positions read from the log.{[...review.report.notes, ...review.report.log.notes].map((n) => ` ${n}.`)}
          </div>
        </div>
      )}

      {vibration && vibration.drones.length > 0 && (
        <div className="card" style={{ padding: 16, display: 'grid', gap: 8 }} id="vibration-card">
          <div style={{ fontWeight: 600 }}>Vibration across the fleet</div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{vibration.evidence}</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}><th>Drone</th><th>Vibration (95th pct.)</th><th style={{ width: '24%' }} title="Share of public PX4 flights rated good or great, with the same measurement and kind of vehicle, that vibrated less">Against public PX4 flights</th><th>In this fleet</th><th>Measured as</th><th>Flights</th><th /></tr></thead>
            <tbody>{vibration.drones.map((d) => {
              return (
                <tr key={`${d.source}-${d.drone_id}`} style={{ borderTop: '1px solid var(--border, #E2E8F0)' }}>
                  <td style={{ padding: '6px 8px 6px 0', fontWeight: 600, whiteSpace: 'nowrap' }}>{d.drone_id}</td>
                  <td style={{ fontVariantNumeric: 'tabular-nums' }}>{fmt(d.vibration_p95)}</td>
                  <td style={{ paddingRight: 12 }}>{d.public
                    ? <div title={d.public.note} style={{ display: 'grid', gap: 2 }}>
                        <div style={{ height: 8, borderRadius: 4, background: 'var(--bg-secondary, #F1F5F9)', position: 'relative' }}>
                          <div style={{ width: `${Math.max(2, d.public.higher_than_pct)}%`, height: 8, borderRadius: 4, background: '#2a78d6' }} />
                          <div style={{ position: 'absolute', left: '50%', top: -2, height: 12, borderLeft: '2px dashed #94A3B8' }} title="public median" />
                        </div>
                        <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>higher than {d.public.higher_than_pct}% of {d.public.flights}</span>
                      </div>
                    : <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>no public reference for this measurement</span>}</td>
                  <td>{d.comparable ? <>{d.rank} of {d.group_size}{d.times_group_median != null ? ` · ${d.times_group_median}× median` : ''}</> : <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>fewer than 4 to compare</span>}</td>
                  <td style={{ color: 'var(--text-secondary)' }}>{VIB_SOURCE[d.source] ?? d.source}</td>
                  <td>{d.flights}</td>
                  <td><button className="btn" onClick={() => openHistory(d.drone_id)}>History</button></td>
                </tr>)})}</tbody>
          </table>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{vibration.note} The public column compares each drone with real PX4 flights from the public Flight Review archive that their pilots rated good or great (dashed line: their median); it works for a fleet of any size. {vibration.drones.find((d) => d.public)?.public?.note}</div>
        </div>
      )}

      {history && (
        <div className="card" style={{ padding: 16, display: 'grid', gap: 8 }} id="vibration-history">
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <span style={{ fontWeight: 600, flex: 1 }}>{history.drone_id} · vibration against its own earlier flights</span>
            <button className="btn" onClick={() => setHistory(null)}>Close</button>
          </div>
          {history.flights.length > 0 && (() => {
            const W = 640, H = 150, L = 62, B = 22, top = Math.max(...history.flights.map((f) => f.p95), history.latest_vs_public?.median ?? 0) * 1.1 || 1
            const x = (i: number) => L + (history.flights.length === 1 ? (W - L) / 2 : (i * (W - L - 12)) / (history.flights.length - 1))
            const y = (v: number) => H - B - (v / top) * (H - B - 8)
            const own = history.latest_vs_own?.earlier_median
            const pub = history.latest_vs_public?.median
            const day = (t: string) => { const d = new Date(t); return isNaN(d.getTime()) ? t.slice(0, 10) : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) }
            return (
              <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: 760 }} role="img" aria-label="Vibration of each flight in the order flown">
                <line x1={L} y1={H - B} x2={W} y2={H - B} stroke="#94A3B8" /><line x1={L} y1={8} x2={L} y2={H - B} stroke="#94A3B8" />
                <text x={L - 6} y={y(top / 1.1) + 4} fontSize="10" textAnchor="end" fill="#64748B">{fmt(top / 1.1)}</text>
                <text x={L - 6} y={H - B + 3} fontSize="10" textAnchor="end" fill="#64748B">0</text>
                {own != null && <><line x1={L} y1={y(own)} x2={W} y2={y(own)} stroke="#1baf7a" strokeDasharray="5 4" />
                  <text x={W - 4} y={y(own) - 4} fontSize="10" textAnchor="end" fill="#1baf7a">median of its earlier flights</text></>}
                {pub != null && <><line x1={L} y1={y(pub)} x2={W} y2={y(pub)} stroke="#94A3B8" strokeDasharray="2 3" />
                  <text x={(L + W) / 2} y={y(pub) - 4} fontSize="10" textAnchor="middle" fill="#64748B">median of public PX4 flights</text></>}
                {(history.maintenance ?? []).map((m) => {
                  const k = history.flights.filter((f) => new Date(f.when) < new Date(m.done_at + (m.done_at.endsWith('Z') ? '' : 'Z'))).length
                  const mx = k === 0 ? L : k >= history.flights.length ? W - 4 : (x(k - 1) + x(k)) / 2
                  return <g key={m.id}><line x1={mx} x2={mx} y1={8} y2={H - B} stroke="#7C3AED" strokeDasharray="4 3" />
                    <text x={mx + 3} y={18} fontSize="10" fill="#7C3AED">{m.action}</text></g>
                })}
                <polyline fill="none" stroke="#2a78d6" strokeWidth="1.5" points={history.flights.map((f, i) => `${x(i)},${y(f.p95)}`).join(' ')} />
                {history.flights.map((f, i) => (
                  <circle key={f.review_id} cx={x(i)} cy={y(f.p95)} r={i === history.flights.length - 1 ? 5 : 3.5} fill={i === history.flights.length - 1 ? '#eb6834' : '#2a78d6'}
                    style={{ cursor: 'pointer' }} onClick={() => openReview(f.review_id)}>
                    <title>{`${day(f.when)} · ${fmt(f.p95)} · ${f.log_name ?? ''} (click to open the review)`}</title></circle>))}
                <text x={L} y={H - 6} fontSize="10" fill="#64748B">{day(history.flights[0].when)}</text>
                <text x={W} y={H - 6} fontSize="10" textAnchor="end" fill="#64748B">{day(history.flights[history.flights.length - 1].when)} (newest, orange)</text>
              </svg>)
          })()}
          {history.latest_vs_own && (
            <div style={{ fontSize: 13 }}>
              Newest flight <b>{fmt(history.latest_vs_own.latest_p95)}</b>: higher than <b>{history.latest_vs_own.higher_than} of its {history.latest_vs_own.earlier_flights}</b> earlier flights
              {history.latest_vs_own.times_own_median != null ? ` (${history.latest_vs_own.times_own_median}× its own median of ${fmt(history.latest_vs_own.earlier_median)})` : ''}.
              {history.among_peers?.comparable ? ` Among comparable drones: ${history.among_peers.rank} of ${history.among_peers.group_size}.` : ''}
            </div>)}
          {history.latest_vs_public && (
            <div style={{ fontSize: 13 }} title={history.latest_vs_public.note}>
              Against public PX4 flights rated good or great ({history.latest_vs_public.flights} flights, {history.latest_vs_public.vehicles} vehicles): the newest flight is
              {' '}<b>higher than {history.latest_vs_public.higher_than_pct}%</b> of them.
            </div>)}
          {history.message && <div style={{ fontSize: 13 }}>{history.message}</div>}
          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{history.evidence}</div>
          {history.order_note && <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{history.order_note}</div>}
          <div id="maintenance-log" style={{ display: 'grid', gap: 8, borderTop: '1px solid var(--border, #E2E8F0)', paddingTop: 10 }}>
            <b style={{ fontSize: 13 }}>Maintenance logbook: did the fix work?</b>
            {(history.maintenance ?? []).length === 0 && <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Nothing recorded for this drone yet.</span>}
            {(history.maintenance ?? []).map((m) => (
              <div key={m.id} style={{ fontSize: 13, padding: '6px 10px', borderLeft: '3px solid #7C3AED', background: 'var(--bg-secondary, #F8FAFC)', display: 'grid', gap: 3 }}>
                <span><b>{m.action}</b> · {new Date(m.done_at + (m.done_at.endsWith('Z') ? '' : 'Z')).toLocaleDateString([], { dateStyle: 'medium' })} · by {m.done_by}{m.note ? ` · ${m.note}` : ''}</span>
                <span style={{ fontWeight: 600 }}>{m.effect.summary}</span>
                {m.effect.measures.map((x) => (
                  <span key={x.label} style={{ color: 'var(--text-secondary)' }}>{x.label}: {sig3(x.before)} → {sig3(x.after)} ({x.unit}; {x.flights_before} flights before, {x.flights_after} after)</span>))}
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{m.effect.note}</span>
              </div>))}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <input type="date" className="form-input" value={mDate} onChange={(e) => setMDate(e.target.value)} style={{ width: 150 }} aria-label="Date of the work" />
              <select className="form-select" value={mAction} onChange={(e) => setMAction(e.target.value)} style={{ width: 'auto' }} aria-label="What was done">
                <option value="">What was done…</option>
                {(history.maintenance_actions ?? []).map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
              <input className="form-input" placeholder="Note (optional)" value={mNote} onChange={(e) => setMNote(e.target.value)} maxLength={1000} style={{ flex: 1, minWidth: 160 }} />
              <button className="btn btn--primary" id="btn-add-maintenance" disabled={busy || !mDate || !mAction} onClick={addMaintenance}>Add to logbook</button>
            </div>
          </div>
        </div>
      )}

      <div className="card" style={{ padding: 16, display: 'grid', gap: 10 }} id="troubleshoot-card">
        <div>
          <div style={{ fontWeight: 600 }}>Something wrong with a drone? Describe it</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            You get a checklist in the order PX4 experts most often found each cause, with the causes your words mention marked, and
            the most similar past crash threads to read. It is not a diagnosis. Enter the drone id above to add its vibration.
          </div>
        </div>
        <textarea id="troubleshoot-text" rows={3} value={symptom} onChange={(e) => setSymptom(e.target.value)} maxLength={4000}
          placeholder="e.g. circles in position mode and drifts away; wobbles in hover after new propellers; flipped on take-off"
          style={{ width: '100%', fontFamily: 'inherit', fontSize: 13, padding: 8, borderRadius: 6, border: '1px solid var(--border, #E2E8F0)', background: 'transparent', color: 'inherit' }} />
        <div><button className="btn btn--primary" id="btn-troubleshoot" disabled={busy || symptom.trim().length < 3} onClick={askHelp}>Find similar cases</button></div>
        {help && (
          <div style={{ display: 'grid', gap: 10 }}>
            {help.message && <div style={{ fontSize: 13 }}>{help.message}</div>}
            {help.checklist.map((c, i) => (
              <details key={c.cause} open={c.mentioned} style={{ borderTop: i ? '1px solid var(--border, #E2E8F0)' : undefined, paddingTop: i ? 8 : 0 }}>
                <summary style={{ cursor: 'pointer', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 600 }}>{i + 1}. {c.cause}</span>
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>experts found it in {c.experts_found} crashes</span>
                  {c.mentioned && <Pill verdict="REVIEW" label={`you mentioned: ${c.matched_words.join(', ')}`} />}
                </summary>
                <div style={{ display: 'grid', gap: 4, marginTop: 4 }}>
                  <div style={{ fontSize: 13 }}><b>Check</b><ul style={{ margin: '2px 0 0 18px' }}>{c.checks.map((x) => <li key={x}>{x}</li>)}</ul></div>
                  <div style={{ fontSize: 13 }}><b>Usual fixes</b><ul style={{ margin: '2px 0 0 18px' }}>{c.fixes.map((x) => <li key={x}>{x}</li>)}</ul></div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>In AeroFleet: {c.aerofleet_check}.</div>
                </div>
              </details>))}
            {help.this_drone_vibration && (
              <div style={{ fontSize: 13 }}>
                <b>This drone's vibration:</b>{' '}
                {help.this_drone_vibration.message ?? `${fmt(help.this_drone_vibration.vibration_p95 ?? 0)}${help.this_drone_vibration.comparable ? `, ${help.this_drone_vibration.rank} of ${help.this_drone_vibration.group_size} among comparable drones` : ''} (context, not a prediction)`}
              </div>)}
            {help.similar_cases.length > 0 && (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead><tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}><th>Similar past case</th><th>Expert's cause</th><th>Diagnosed by</th><th>Fix confirmed</th></tr></thead>
                <tbody>{help.similar_cases.map((c) => (
                  <tr key={c.url} style={{ borderTop: '1px solid var(--border, #E2E8F0)' }}>
                    <td style={{ padding: '6px 0' }}><a href={c.url} target="_blank" rel="noreferrer">{c.title}</a></td>
                    <td>{c.cause}</td><td>{c.who_diagnosed}</td><td>{c.poster_confirmed_fix}</td>
                  </tr>))}</tbody>
              </table>)}
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{help.note} {help.how_well_it_works}</div>
          </div>
        )}
      </div>

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
              {plansResult.rehearsal && (
                <button className="btn" id="btn-rehearse-vr" title="Fly the missions on one clock on the VR table, as planned and as rescheduled"
                  onClick={() => { setVrRehearsal(plansResult.rehearsal ?? null); setActivePage('vr') }}>Rehearse in 3D</button>)}
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
