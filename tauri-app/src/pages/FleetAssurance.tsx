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

function Pill({ verdict }: { verdict: Verdict }) {
  const v = VERDICT[verdict]
  return <span style={{ background: v.bg, color: v.color, padding: '2px 10px', borderRadius: 999, fontSize: 12, fontWeight: 700, whiteSpace: 'nowrap' }}>{v.label}</span>
}

const fmt = (x: number | null) => (x === null ? '—' : String(Number(x.toFixed(6))))
// The backend stores UTC without a zone suffix; show it in the viewer's local time.
const when = (iso: string) => new Date(iso.endsWith('Z') ? iso : iso + 'Z').toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })

export default function FleetAssurancePage() {
  const { apiUrl } = useAppStore()
  const [fleet, setFleet] = useState('default')
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
  const base = `${apiUrl}/api/v1/assurance/fleets/${encodeURIComponent(fleet.trim() || 'default')}`

  const call = useCallback(async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const r = await fetch(base + path, { ...init, headers: { ...token(), ...(init?.headers || {}) } })
    if (r.status === 401) throw new Error('Sign in to use fleet assurance.')
    if (r.status === 403) throw new Error('Only an operator can set the baseline or approve a change.')
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`)
    return r.json()
  }, [base])

  const refresh = useCallback(async () => {
    setBaseline(await call<Baseline>('/baseline').catch(() => null))
    setRows(await call<Fleet>('/drift').catch(() => null))
  }, [call])

  const open = useCallback(async (id: string) => {
    setDrift(await call<Drift>(`/drones/${encodeURIComponent(id)}/drift`))
    setChecks(await call<Checks>(`/drones/${encodeURIComponent(id)}/checks`).catch(() => null))
  }, [call])

  useEffect(() => { setDrift(null); setChecks(null); refresh() }, [refresh])

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
            <input id="assurance-fleet" value={fleet} onChange={(e) => setFleet(e.target.value)} style={{ width: 160 }} />
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
    </div>
  )
}
