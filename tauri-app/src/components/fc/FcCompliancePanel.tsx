import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useAppStore } from '../../store/appStore'
import MotorDiagram, { MotorLayout, MotorLegend } from './MotorDiagram'

// ── Types (mirror aerofleet/api/routes/fc_compliance.py responses) ─────────

type CheckStatus = 'PASS' | 'WARN' | 'FAIL' | 'MANUAL' | 'UNKNOWN'
type Verdict = 'PASS' | 'WARN' | 'FAIL' | 'INCOMPLETE'

interface Candidate {
  source: 'mission_planner_forward' | 'usb'
  connection: string
  label: string
  confidence: string
  status: string
  detail: string
  usable: boolean
  udp_port: number | null
  device: string | null
  usb_id?: string
  product: string | null
}

interface DiscoveryResult {
  candidates: Candidate[]
  recommended: Candidate | null
  udp_ports_checked: number[]
  serial_ports_seen: number
  serial_scan_available: boolean
  notes: string[]
  summary: string
  mission_planner_help: string | null
}

interface Check {
  id: string
  category: string
  category_title: string
  title: string
  requirement: string
  status: CheckStatus
  evidence: Record<string, unknown>
  detail: string
  fix: string
  source: string
  reference: string
  kind: 'measured' | 'manual' | 'wizard'
  required: boolean
  resolved: boolean | null
  attestation?: { result: string; note?: string | null; by?: string; at?: string }
}

interface Report {
  verdict: Verdict
  counts: Record<CheckStatus, number>
  failed: { id: string; title: string }[]
  warnings: { id: string; title: string }[]
  unknown_required: { id: string; title: string }[]
  manual_pending: { id: string; title: string }[]
  categories: { key: string; title: string; counts: Record<CheckStatus, number>; check_ids: string[] }[]
  checks: Check[]
  snapshot_notes: string[]
  firmware: string | null
  params_received: number
  params_expected: number | null
}

interface MotorResult {
  letter: string
  motor_number: number
  position: string
  expected_direction: 'CW' | 'CCW'
  throttle_pct: number
  duration_s: number
  capped: boolean
  ack_result: string
  accepted: boolean
  esc_corroboration: { status: string; expected_esc: number[]; spun_esc: number[]; note: string; rpm_by_esc?: Record<string, number> }
  tested_by: string
  tested_at: string
  confirmation: { result: 'correct' | 'incorrect'; note?: string | null; by: string; at: string } | null
}

interface InspectionSummary {
  inspection_id: string
  status: 'PENDING' | 'RUNNING' | 'READY' | 'FAILED'
  progress: number
  stage: string | null
  verdict: Verdict | null
  source: string | null
  connection: string | null
  drone_id: string | null
  uin: string | null
  bench_mode: boolean | null
  requested_by: string | null
  firmware: string | null
  error: string | null
  created_at: string | null
  completed_at: string | null
}

interface InspectionDetail extends InspectionSummary {
  report: Report | null
  motor_tests: { layout?: string; results?: Record<string, MotorResult> }
  motor_layout: MotorLayout | null
  discovery: DiscoveryResult | null
}

// ── Helpers ────────────────────────────────────────────────────────────────

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('aerofleet_token') || ''
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...(init?.headers || {}) },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? '')
    throw new Error(detail || `${res.status} ${res.statusText}`)
  }
  return res.json()
}

const STATUS_TONE: Record<string, string> = {
  PASS: 'green', WARN: 'yellow', FAIL: 'red', MANUAL: 'grey', UNKNOWN: 'grey',
  INCOMPLETE: 'yellow',
}

const TD: React.CSSProperties = { padding: '8px 10px', verticalAlign: 'middle' }
const SMALL_BTN: React.CSSProperties = { padding: '4px 10px', fontSize: '12px' }

const SOURCE_LABEL: Record<string, string> = {
  mission_planner_forward: 'Mission Planner forward (UDP)',
  usb: 'Direct USB',
  manual: 'Manual connection',
}

function StatusChip({ status }: { status: string }) {
  const tone = STATUS_TONE[status] || 'grey'
  if (tone === 'grey') {
    return (
      <span className="verdict-badge" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>
        {status}
      </span>
    )
  }
  return <span className={`verdict-badge verdict-badge--${tone}`}>{status}</span>
}

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

function Evidence({ evidence }: { evidence: Record<string, unknown> }) {
  const entries = Object.entries(evidence || {})
  if (entries.length === 0) return null
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '6px' }}>
      {entries.map(([k, v]) => (
        <span key={k} className="tag-chip" title={formatValue(v)} style={{ maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {k}: {formatValue(v)}
        </span>
      ))}
    </div>
  )
}

const MP_STEPS = [
  'In Mission Planner, stay connected to the drone as usual.',
  'Press Ctrl-F and click "MAVLink" (or SETUP > Advanced > MAVLink Mirror).',
  'Choose "UDP Client" and tick "Write" (lets AeroFleet read parameters and run the motor test).',
  'Enter host 127.0.0.1 and port 14550 (use 14551 if 14550 is taken), then Connect.',
  'Back here, click Auto-detect. The setting is remembered only while Mission Planner is open.',
]

// ── Component ──────────────────────────────────────────────────────────────

export default function FcCompliancePanel() {
  const { apiUrl } = useAppStore()
  const base = `${apiUrl}/api/v1/hardware/fc`

  const [discovery, setDiscovery] = useState<DiscoveryResult | null>(null)
  const [discovering, setDiscovering] = useState(false)
  const [history, setHistory] = useState<InspectionSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<InspectionDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [hidePasses, setHidePasses] = useState(false)

  // Run-check form
  const [droneId, setDroneId] = useState('')
  const [uin, setUin] = useState('')
  const [weightKg, setWeightKg] = useState('')
  const [payloadKg, setPayloadKg] = useState('')
  const [benchMode, setBenchMode] = useState(false)
  const [connectionOverride, setConnectionOverride] = useState('')

  // Checklist notes, keyed by check id
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [savingCheck, setSavingCheck] = useState<string | null>(null)

  // Motor-test wizard
  const [propsModalOpen, setPropsModalOpen] = useState(false)
  const [propsConfirmed, setPropsConfirmed] = useState(false)
  const [modalProps, setModalProps] = useState(false)
  const [modalDisarmed, setModalDisarmed] = useState(false)
  const [modalClear, setModalClear] = useState(false)
  const [throttle, setThrottle] = useState(10)
  const [duration, setDuration] = useState(2)
  const [activeMotor, setActiveMotor] = useState<string | null>(null)
  const [spinning, setSpinning] = useState<string | null>(null)

  const loadHistory = useCallback(() => {
    api<InspectionSummary[]>(`${base}/inspections?limit=30`).then(setHistory).catch(() => {})
  }, [base])

  const loadDetail = useCallback((id: string) => {
    api<InspectionDetail>(`${base}/inspections/${id}`).then(setDetail).catch(e => setError(String(e.message || e)))
  }, [base])

  useEffect(() => { loadHistory() }, [loadHistory])

  useEffect(() => {
    if (!selectedId) return
    loadDetail(selectedId)
    // A new inspection means a new props-off confirmation.
    setPropsConfirmed(false)
    setActiveMotor(null)
  }, [selectedId, loadDetail])

  // Poll while the inspection is running.
  useEffect(() => {
    if (!detail || (detail.status !== 'PENDING' && detail.status !== 'RUNNING')) return
    const t = setInterval(() => {
      loadDetail(detail.inspection_id)
    }, 700)
    return () => clearInterval(t)
  }, [detail, loadDetail])

  useEffect(() => {
    if (detail && (detail.status === 'READY' || detail.status === 'FAILED')) loadHistory()
  }, [detail?.status, loadHistory])

  async function handleDiscover() {
    setDiscovering(true)
    setError(null)
    try {
      setDiscovery(await api<DiscoveryResult>(`${base}/discover?listen_s=2`))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setDiscovering(false)
    }
  }

  async function handleRun() {
    setStarting(true)
    setError(null)
    try {
      const body: Record<string, unknown> = {
        auto: !connectionOverride.trim(),
        connection: connectionOverride.trim() || null,
        drone_id: droneId.trim() || null,
        uin: uin.trim() || null,
        bench_mode: benchMode,
        payload_kg: payloadKg ? Number(payloadKg) : 0,
      }
      if (weightKg) body.weight_kg = Number(weightKg)
      const res = await api<{ inspection_id: string }>(`${base}/inspections`, { method: 'POST', body: JSON.stringify(body) })
      setSelectedId(res.inspection_id)
      setDetail(null)
      loadHistory()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setStarting(false)
    }
  }

  async function setChecklist(checkId: string, result: 'confirmed' | 'failed' | 'unchecked') {
    if (!detail) return
    setSavingCheck(checkId)
    setError(null)
    try {
      const updated = await api<InspectionDetail>(`${base}/inspections/${detail.inspection_id}/checklist`, {
        method: 'POST',
        body: JSON.stringify({ items: [{ check_id: checkId, result, note: notes[checkId] || null }] }),
      })
      setDetail(updated)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSavingCheck(null)
    }
  }

  async function spinMotor(letter: string) {
    if (!detail) return
    if (!propsConfirmed) {
      setActiveMotor(letter)
      setPropsModalOpen(true)
      return
    }
    setSpinning(letter)
    setActiveMotor(letter)
    setError(null)
    try {
      await api(`${base}/inspections/${detail.inspection_id}/motor-test`, {
        method: 'POST',
        body: JSON.stringify({ motor: letter, throttle_pct: throttle, duration_s: duration, props_removed_confirmed: true }),
      })
      loadDetail(detail.inspection_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSpinning(null)
    }
  }

  async function confirmMotor(letter: string, result: 'correct' | 'incorrect') {
    if (!detail) return
    setError(null)
    try {
      const updated = await api<InspectionDetail>(`${base}/inspections/${detail.inspection_id}/motor-test/${letter}/confirm`, {
        method: 'POST',
        body: JSON.stringify({ result }),
      })
      setDetail(updated)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  async function exportJson() {
    if (!detail) return
    try {
      const data = await api<unknown>(`${base}/inspections/${detail.inspection_id}/export`)
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${detail.inspection_id}.json`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const report = detail?.report || null
  const checksByCategory = useMemo(() => {
    if (!report) return []
    return report.categories.map(cat => ({
      ...cat,
      checks: report.checks.filter(c => c.category === cat.key && (!hidePasses || c.status !== 'PASS')),
    }))
  }, [report, hidePasses])
  const manualChecks = report?.checks.filter(c => c.kind === 'manual') || []
  const motorResults = detail?.motor_tests?.results || {}
  const layout = detail?.motor_layout || null
  const running = detail && (detail.status === 'PENDING' || detail.status === 'RUNNING')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {error && (
        <div className="card" style={{ borderColor: 'var(--status-red)' }}>
          <span style={{ color: 'var(--status-red)' }}>⚠ {error}</span>
        </div>
      )}

      {/* ── Connection ─────────────────────────────────────────────── */}
      <div className="card">
        <div className="card__header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="card__title">Flight controller connection</span>
          <button id="btn-fc-discover" className="btn btn--ghost" onClick={handleDiscover} disabled={discovering || !!running}>
            {discovering ? <><div className="spinner" style={{ width: 14, height: 14 }} /> Listening…</> : 'Auto-detect'}
          </button>
        </div>
        {!discovery && (
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            AeroFleet first listens for Mission Planner's forwarded MAVLink on UDP 14550/14551, then scans USB for a
            flight controller (ArduPilot, Pixhawk, Cube, Holybro, 3DR). Running a check auto-detects too.
          </div>
        )}
        {discovery && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ fontSize: '14px', fontWeight: 600, color: discovery.recommended ? 'var(--status-green)' : 'var(--status-red)' }}>
              {discovery.summary}
            </div>
            {discovery.recommended && (
              <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                Path: <strong>{SOURCE_LABEL[discovery.recommended.source]}</strong> · <span className="mono">{discovery.recommended.connection}</span>
              </div>
            )}
            {(discovery.candidates.length > 1 || !discovery.recommended) && discovery.candidates.length > 0 && (
              <table className="data-table">
                <thead><tr><th>Path</th><th>Device</th><th>Status</th><th>Detail</th></tr></thead>
                <tbody>
                  {discovery.candidates.map((c, i) => (
                    <tr key={i}>
                      <td>{SOURCE_LABEL[c.source]}</td>
                      <td className="mono">{c.device || `UDP ${c.udp_port}`}{c.usb_id ? ` (${c.usb_id})` : ''}</td>
                      <td><StatusChip status={c.usable ? 'PASS' : c.status === 'in_use' ? 'WARN' : 'UNKNOWN'} /> <span className="text-xs text-muted">{c.status}</span></td>
                      <td style={{ fontSize: '12px' }}>{c.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {discovery.notes.map((n, i) => <div key={i} style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{n}</div>)}
          </div>
        )}
        <details style={{ marginTop: '12px' }} open={!!discovery && !discovery.recommended}>
          <summary style={{ cursor: 'pointer', fontSize: '13px', color: 'var(--accent)' }}>
            Using Mission Planner? One-time MAVLink forwarding setup
          </summary>
          <ol style={{ margin: '8px 0 0', paddingLeft: '20px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {MP_STEPS.map((s, i) => <li key={i}>{s}</li>)}
          </ol>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '6px' }}>
            Why: Mission Planner holds the USB port, and only one program can open a COM port at a time.
          </div>
        </details>
      </div>

      {/* ── Run check ──────────────────────────────────────────────── */}
      <div className="card">
        <div className="card__header"><span className="card__title">Run compliance check</span></div>
        <div className="grid-3" style={{ gap: '12px' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Drone ID (fleet registry, optional)</label>
            <input className="form-input" value={droneId} onChange={e => setDroneId(e.target.value)} placeholder="e.g. PUN-D01-1" />
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Digital Sky UIN</label>
            <input className="form-input" value={uin} onChange={e => setUin(e.target.value)} placeholder="UIN from Digital Sky" />
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Airframe weight kg (blank = registry)</label>
            <input className="form-input" type="number" min={0} step={0.1} value={weightKg} onChange={e => setWeightKg(e.target.value)} />
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Payload kg</label>
            <input className="form-input" type="number" min={0} step={0.1} value={payloadKg} onChange={e => setPayloadKg(e.target.value)} />
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Connection override (optional)</label>
            <input className="form-input mono" value={connectionOverride} onChange={e => setConnectionOverride(e.target.value)} placeholder="auto-detect" />
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--text-secondary)' }}>
            <input type="checkbox" checked={benchMode} onChange={e => setBenchMode(e.target.checked)} />
            Indoor bench check (no GPS fix expected → WARN, not FAIL)
          </label>
        </div>
        <div style={{ display: 'flex', gap: '10px', marginTop: '16px', alignItems: 'center' }}>
          <button id="btn-fc-run" className="btn btn--primary" onClick={handleRun} disabled={starting || !!running}>
            {starting ? <div className="spinner" style={{ width: 14, height: 14 }} /> : 'Run check'}
          </button>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Read-only: parameters, sensors, battery, GPS, EKF, vibration and the autopilot's own pre-arm checks. Nothing is written to the drone.
          </span>
        </div>
      </div>

      {/* ── Progress ───────────────────────────────────────────────── */}
      {detail && running && (
        <div className="card">
          <div className="card__header" style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span className="card__title">Inspecting {detail.inspection_id}</span>
            <span className="mono text-xs">{detail.progress}%</span>
          </div>
          <div className="progress-bar"><div className="progress-bar__fill" style={{ width: `${detail.progress}%` }} /></div>
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '8px' }}>{detail.stage}</div>
        </div>
      )}
      {detail && detail.status === 'FAILED' && (
        <div className="card" style={{ borderColor: 'var(--status-red)' }}>
          <div className="card__header"><span className="card__title">Inspection {detail.inspection_id} could not run</span></div>
          <div style={{ fontSize: '13px', color: 'var(--status-red)', whiteSpace: 'pre-wrap' }}>{detail.error}</div>
        </div>
      )}

      {/* ── Report ─────────────────────────────────────────────────── */}
      {detail && report && (
        <>
          <div className="card" style={{ borderColor: report.verdict === 'FAIL' ? 'var(--status-red)' : report.verdict === 'PASS' ? 'var(--status-green)' : 'var(--status-amber)' }}>
            <div className="card__header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="card__title">Report {detail.inspection_id} · {SOURCE_LABEL[detail.source || ''] || detail.source} · firmware {report.firmware || 'unknown'}</span>
              <div style={{ display: 'flex', gap: '8px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  <input type="checkbox" checked={hidePasses} onChange={e => setHidePasses(e.target.checked)} /> Hide passes
                </label>
                <button className="btn btn--ghost" onClick={exportJson}>Export JSON</button>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '22px', fontWeight: 700 }}><StatusChip status={report.verdict} /></span>
              {(['FAIL', 'WARN', 'UNKNOWN', 'MANUAL', 'PASS'] as CheckStatus[]).map(s => (
                <span key={s} style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{report.counts[s]} {s}</span>
              ))}
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                {report.params_received}/{report.params_expected ?? '?'} parameters read
              </span>
            </div>
            {report.failed.length > 0 && (
              <div style={{ marginTop: '10px', fontSize: '13px', color: 'var(--status-red)' }}>
                Must fix: {report.failed.map(f => f.title).join(' · ')}
              </div>
            )}
            {report.manual_pending.length > 0 && (
              <div style={{ marginTop: '6px', fontSize: '13px', color: 'var(--text-secondary)' }}>
                Still to check by hand: {report.manual_pending.map(f => f.title).join(' · ')}
              </div>
            )}
            {report.unknown_required.length > 0 && (
              <div style={{ marginTop: '6px', fontSize: '13px', color: '#92700C' }}>
                Not measured: {report.unknown_required.map(f => f.title).join(' · ')}
              </div>
            )}
            {report.snapshot_notes.map((n, i) => <div key={i} style={{ marginTop: '6px', fontSize: '12px', color: 'var(--text-muted)' }}>{n}</div>)}
          </div>

          {checksByCategory.map(cat => (
            <div key={cat.key} className="card">
              <div className="card__header" style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="card__title">{cat.title}</span>
                <span style={{ display: 'flex', gap: '6px' }}>
                  {(['FAIL', 'WARN', 'UNKNOWN', 'MANUAL'] as CheckStatus[]).filter(s => cat.counts[s] > 0).map(s => (
                    <span key={s} className="text-xs text-muted">{cat.counts[s]} {s}</span>
                  ))}
                </span>
              </div>
              {cat.checks.length === 0 && <div className="text-sm text-muted">All passed.</div>}
              {cat.checks.map(c => (
                <div key={c.id} style={{ padding: '10px 0', borderTop: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', gap: '10px', alignItems: 'baseline' }}>
                    <StatusChip status={c.status} />
                    <span style={{ fontWeight: 600, fontSize: '14px' }}>{c.title}</span>
                    {c.status === 'MANUAL' && c.resolved && <span className="text-xs" style={{ color: 'var(--status-green)' }}>✓ confirmed</span>}
                    <span className="mono text-xs text-muted" style={{ marginLeft: 'auto' }}>{c.id}</span>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>Requirement: {c.requirement}</div>
                  {c.detail && <div style={{ fontSize: '13px', marginTop: '4px' }}>{c.detail}</div>}
                  <Evidence evidence={c.evidence} />
                  {c.status !== 'PASS' && <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '6px' }}>Fix: {c.fix}</div>}
                  <div style={{ fontSize: '11px', marginTop: '4px' }}>
                    <a href={c.source} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>Source</a>
                    {c.reference && <span className="text-muted"> · {c.reference}</span>}
                  </div>
                </div>
              ))}
            </div>
          ))}

          {/* ── Manual checklist ─────────────────────────────────── */}
          <div className="card">
            <div className="card__header"><span className="card__title">Manual checklist</span></div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px' }}>
              These can't be sensed over MAVLink. Your tick is recorded with your name as an attestation — it stays MANUAL, it doesn't become a measured PASS.
              Marking an item failed fails the report.
            </div>
            {manualChecks.map(c => (
              <div key={c.id} style={{ display: 'flex', gap: '12px', alignItems: 'center', padding: '8px 0', borderTop: '1px solid var(--border)', flexWrap: 'wrap' }}>
                <div style={{ flex: '1 1 320px' }}>
                  <div style={{ fontWeight: 600, fontSize: '13px' }}>{c.title} <span className="text-xs text-muted">· {c.category_title}</span></div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{c.requirement}</div>
                  {c.attestation && (
                    <div className="text-xs" style={{ color: c.attestation.result === 'failed' ? 'var(--status-red)' : 'var(--status-green)' }}>
                      {c.attestation.result} by {c.attestation.by} · {c.attestation.at?.replace('T', ' ').slice(0, 16)}{c.attestation.note ? ` — ${c.attestation.note}` : ''}
                    </div>
                  )}
                </div>
                <input className="form-input" style={{ flex: '0 1 200px' }} placeholder="Note (optional)" value={notes[c.id] || ''}
                  onChange={e => setNotes(n => ({ ...n, [c.id]: e.target.value }))} />
                <button className="btn btn--ghost" disabled={savingCheck === c.id} onClick={() => setChecklist(c.id, 'confirmed')}>✓ OK</button>
                <button className="btn btn--ghost" disabled={savingCheck === c.id} onClick={() => setChecklist(c.id, 'failed')} style={{ color: 'var(--status-red)' }}>✗ Failed</button>
                {c.attestation && <button className="btn btn--ghost" disabled={savingCheck === c.id} onClick={() => setChecklist(c.id, 'unchecked')}>Clear</button>}
              </div>
            ))}
          </div>

          {/* ── Motor test wizard ────────────────────────────────── */}
          <div className="card">
            <div className="card__header"><span className="card__title">Motor test (props off)</span></div>
            {!layout && (
              <div className="text-sm text-muted">
                No guided diagram for this frame (Quad X, Quad + and Hexa X are supported). Use Mission Planner's Motor Test and ArduPilot's motor diagrams.
              </div>
            )}
            {layout && (
              <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                <div>
                  <MotorDiagram
                    layout={layout}
                    active={activeMotor}
                    results={Object.fromEntries(Object.entries(motorResults).map(([k, r]) => [k, r.confirmation?.result ?? 'pending']))}
                  />
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textAlign: 'center' }}>
                    {layout.name} · <a href={layout.docs} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>ArduPilot motor diagrams</a>
                  </div>
                </div>
                <div style={{ flex: '1 1 380px', minWidth: 0 }}>
                  <MotorLegend />
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '8px 0' }}>
                    One motor at a time, max 15 % throttle for max 3 s (enforced by the server). Watch the drone: the
                    named motor must spin, in the direction shown. Then mark it correct or incorrect.
                    {propsConfirmed && <span style={{ color: 'var(--status-green)' }}> Props-off confirmed for this inspection.</span>}
                  </div>
                  <div style={{ display: 'flex', gap: '16px', alignItems: 'center', marginBottom: '8px', fontSize: '12px' }}>
                    <label>Throttle {throttle}%
                      <input type="range" min={5} max={15} step={1} value={throttle} onChange={e => setThrottle(Number(e.target.value))} style={{ marginLeft: 8 }} />
                    </label>
                    <label>Duration {duration}s
                      <input type="range" min={0.5} max={3} step={0.5} value={duration} onChange={e => setDuration(Number(e.target.value))} style={{ marginLeft: 8 }} />
                    </label>
                  </div>
                  <div style={{ overflowX: 'auto' }}>
                  <table className="data-table" style={{ fontSize: '12px' }}>
                    <thead><tr><th style={TD}>Motor</th><th style={TD}>Expected</th><th style={TD}>Spin</th><th style={TD}>ESC telemetry</th><th style={TD}>You saw</th></tr></thead>
                    <tbody>
                      {layout.motors.map(m => {
                        const r = motorResults[m.letter]
                        const esc = r?.esc_corroboration
                        return (
                          <tr key={m.letter} style={activeMotor === m.letter ? { background: 'var(--bg-hover)' } : undefined}>
                            <td style={{ ...TD, whiteSpace: 'nowrap' }} className="mono"><strong>{m.letter}</strong> · M{m.motor_number}</td>
                            <td style={TD}>{m.position}<br />{m.direction === 'CW' ? '↻ CW' : '↺ CCW'}</td>
                            <td style={TD}>
                              <button className="btn btn--ghost" style={SMALL_BTN} disabled={!!spinning} onClick={() => spinMotor(m.letter)}>
                                {spinning === m.letter ? <div className="spinner" style={{ width: 12, height: 12 }} /> : r ? 'Again' : 'Spin'}
                              </button>
                            </td>
                            <td style={TD} title={esc?.note}>
                              {esc ? (
                                <>
                                  <StatusChip status={esc.status === 'corroborated' ? 'PASS' : esc.status === 'mismatch' ? 'WARN' : 'UNKNOWN'} />
                                  <div className="text-xs" style={{ marginTop: 2 }}>
                                    {esc.status}{esc.spun_esc.length ? ` · ESC ${esc.spun_esc.join(', ')}` : ''}{r?.capped ? ' · capped' : ''}
                                  </div>
                                </>
                              ) : <span className="text-muted">—</span>}
                            </td>
                            <td style={TD}>
                              {r ? (
                                <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                  <button className="btn btn--ghost" onClick={() => confirmMotor(m.letter, 'correct')}
                                    style={{ ...SMALL_BTN, ...(r.confirmation?.result === 'correct' ? { color: 'var(--status-green)', borderColor: 'var(--status-green)' } : {}) }}>Correct</button>
                                  <button className="btn btn--ghost" onClick={() => confirmMotor(m.letter, 'incorrect')}
                                    style={{ ...SMALL_BTN, ...(r.confirmation?.result === 'incorrect' ? { color: 'var(--status-red)', borderColor: 'var(--status-red)' } : {}) }}>Incorrect</button>
                                </div>
                              ) : <span className="text-muted text-xs">spin first</span>}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '6px' }}>
                    Wrong direction: swap any two of that motor's three wires. Wrong position: fix the ESC signal wiring or SERVOn_FUNCTION.
                  </div>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* ── History ────────────────────────────────────────────────── */}
      <div className="card">
        <div className="card__header"><span className="card__title">Inspection history</span></div>
        {history.length === 0 && <div className="text-sm text-muted">No inspections yet.</div>}
        {history.length > 0 && (
          <table className="data-table">
            <thead><tr><th>Inspection</th><th>When</th><th>Drone / UIN</th><th>Path</th><th>Status</th><th>By</th></tr></thead>
            <tbody>
              {history.map(h => (
                <tr key={h.inspection_id} onClick={() => setSelectedId(h.inspection_id)} style={{ cursor: 'pointer', background: h.inspection_id === selectedId ? 'var(--bg-hover)' : undefined }}>
                  <td className="mono">{h.inspection_id}</td>
                  <td style={{ fontSize: '12px' }}>{h.created_at?.replace('T', ' ').slice(0, 16)}</td>
                  <td style={{ fontSize: '12px' }}>{h.drone_id || '—'} / {h.uin || '—'}</td>
                  <td style={{ fontSize: '12px' }}>{SOURCE_LABEL[h.source || ''] || '—'}</td>
                  <td>{h.status === 'READY' && h.verdict ? <StatusChip status={h.verdict} /> : <span className="text-xs text-muted">{h.status}</span>}</td>
                  <td style={{ fontSize: '12px' }}>{h.requested_by}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Props-off confirmation modal ───────────────────────────── */}
      {propsModalOpen && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(15, 23, 42, 0.55)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px',
        }}>
          <div className="card" style={{ width: '480px', maxWidth: '100%', borderColor: 'var(--status-red)' }} role="dialog" aria-modal="true">
            <div className="card__header"><span className="card__title" style={{ color: 'var(--status-red)' }}>Before spinning any motor</span></div>
            <p style={{ fontSize: '14px', color: 'var(--text-secondary)', lineHeight: 1.5, marginTop: 0 }}>
              A motor test spins a real motor. A propeller left on can cut, or the drone can lift or flip.
            </p>
            {[
              [modalProps, setModalProps, 'I have removed ALL propellers from this drone.'],
              [modalDisarmed, setModalDisarmed, 'The drone is disarmed and restrained on the bench.'],
              [modalClear, setModalClear, 'People, cables and loose objects are clear of every motor.'],
            ].map(([checked, set, label], i) => (
              <label key={i} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start', fontSize: '14px', margin: '10px 0' }}>
                <input type="checkbox" checked={checked as boolean} onChange={e => (set as (v: boolean) => void)(e.target.checked)} />
                <span>{label as string}</span>
              </label>
            ))}
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '16px' }}>
              <button className="btn btn--ghost" onClick={() => setPropsModalOpen(false)}>Cancel</button>
              <button
                id="btn-fc-props-confirm"
                className="btn btn--danger"
                disabled={!(modalProps && modalDisarmed && modalClear)}
                onClick={() => {
                  setPropsConfirmed(true)
                  setPropsModalOpen(false)
                  setModalProps(false); setModalDisarmed(false); setModalClear(false)
                }}
              >
                Props are off — enable motor test
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
