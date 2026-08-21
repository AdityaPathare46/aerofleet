import React, { useState, useEffect, useCallback } from 'react'
import { useAppStore, DispatchPlan, ExplanationStatus } from '../store/appStore'

interface CityDto { slug: string; name: string; center: [number, number] }
interface DepotDto { depot_id: string; name: string }

interface DispatchResult {
  order_id: string
  assigned_drone_id: string | null
  verdict: string
  candidate: Record<string, unknown>
  cbf_certificate: { passed: boolean; safety_margins: Record<string, number>; execution_time_ms: number }
  explanation_status: ExplanationStatus
}

const PRIORITIES = ['STANDARD', 'EXPRESS', 'MEDICAL']

const DEFAULT_DISPATCH: DispatchPlan = {
  city: 'pune',
  origin_depot_id: 'DEPOT-1',
  destination_lat: 18.53,
  destination_lon: 73.86,
  payload_kg: 1.5,
  priority: 'STANDARD',
  deadline_minutes: 30,
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('aerofleet_token') || ''
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export default function DispatchDesignerPage() {
  const { setActivePage, updateTelemetry, apiUrl } = useAppStore()
  const [form, setForm] = useState<DispatchPlan>(DEFAULT_DISPATCH)
  const [dispatching, setDispatching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [cities, setCities] = useState<CityDto[]>([])
  const [depots, setDepots] = useState<DepotDto[]>([])
  const [result, setResult] = useState<DispatchResult | null>(null)
  const [requestingExplanation, setRequestingExplanation] = useState(false)
  const [exportingWaypoints, setExportingWaypoints] = useState(false)

  function update<K extends keyof DispatchPlan>(key: K, value: DispatchPlan[K]) {
    setForm(f => ({ ...f, [key]: value }))
  }

  useEffect(() => {
    fetch(`${apiUrl}/api/v1/cities/`).then(r => r.json()).then(setCities).catch(() => {})
  }, [apiUrl])

  const loadDepots = useCallback((city: string) => {
    fetch(`${apiUrl}/api/v1/fleet/depots?city=${city}`)
      .then(r => r.json())
      .then((d: DepotDto[]) => {
        setDepots(d)
        if (d.length && !d.some(x => x.depot_id === form.origin_depot_id)) {
          update('origin_depot_id', d[0].depot_id)
        }
      })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiUrl])

  useEffect(() => { loadDepots(form.city || 'pune') }, [form.city, loadDepots])

  function handleCityChange(slug: string) {
    const cfg = cities.find(c => c.slug === slug)
    setForm(f => ({
      ...f,
      city: slug,
      destination_lat: cfg ? cfg.center[0] + 0.01 : f.destination_lat,
      destination_lon: cfg ? cfg.center[1] - 0.01 : f.destination_lon,
    }))
  }

  async function handleDispatch() {
    setDispatching(true)
    setError(null)
    setResult(null)

    try {
      // Order creation requires an auth token — see API_TEST_GUIDE.md for
      // the register/login flow. This demo call will 401 without one.
      const createRes = await fetch(`${apiUrl}/api/v1/orders/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(form),
      })
      if (!createRes.ok) throw new Error(`Order creation failed: ${createRes.status} ${createRes.statusText}`)
      const order = await createRes.json()

      // Dispatch is always deterministic and instant — no LLM call sits on
      // this path (see docs/PATENT_NOVELTY.md Claim 1). The result below
      // is the real, final decision, not a preview.
      const dispatchRes = await fetch(`${apiUrl}/api/v1/orders/${order.order_id}/dispatch`, {
        method: 'POST',
        headers: authHeaders(),
      })
      if (!dispatchRes.ok) throw new Error(`Dispatch failed: ${dispatchRes.status} ${dispatchRes.statusText}`)
      const dispatchResult: DispatchResult = await dispatchRes.json()
      setResult(dispatchResult)

      const margins = dispatchResult.cbf_certificate?.safety_margins || {}
      updateTelemetry({
        etaMinutes: typeof dispatchResult.candidate?.eta_minutes === 'number' ? dispatchResult.candidate.eta_minutes as number : null,
        batteryMarginWh: margins.battery_reserve_margin ?? null,
        linkMargin_db: margins.comms_link_margin ?? null,
        cbfPass: dispatchResult.cbf_certificate?.passed ?? null,
      })
    } catch (e) {
      console.error('Dispatch failed:', e)
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setDispatching(false)
    }
  }

  async function handleRequestExplanation() {
    if (!result) return
    setRequestingExplanation(true)
    try {
      const res = await fetch(`${apiUrl}/api/v1/orders/${result.order_id}/request-explanation`, {
        method: 'POST',
        headers: authHeaders(),
      })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      const body = await res.json()
      setResult(r => r ? { ...r, explanation_status: body.council_explanation_status } : r)
    } catch (e) {
      console.error('Failed to request explanation:', e)
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRequestingExplanation(false)
    }
  }

  /** Downloads the CBF-approved route as a standard QGC WPL 110 .waypoints
   * file — openable directly in ArduPilot Mission Planner or
   * QGroundControl's Flight Plan view. See
   * aerofleet/integrations/mission_planner.py for why this is a file
   * export rather than vendoring Mission Planner's own codebase in. Fetch
   * + Blob rather than a plain <a href> since the endpoint needs the
   * Bearer auth header, which a navigated link can't carry. */
  async function handleExportWaypoints() {
    if (!result) return
    setExportingWaypoints(true)
    try {
      const res = await fetch(`${apiUrl}/api/v1/orders/${result.order_id}/mission-planner-waypoints`, {
        headers: authHeaders(),
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => null)
        throw new Error(detail?.detail || `${res.status} ${res.statusText}`)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${result.order_id}.waypoints`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('Failed to export waypoints:', e)
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setExportingWaypoints(false)
    }
  }

  return (
    <div style={{ overflow: 'auto', flex: 1 }}>
      <div className="page-header">
        <div>
          <div className="page-title">Dispatch Console</div>
          <div className="page-subtitle">Configure a delivery order · Deterministic CBF-gated dispatch, always instant</div>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button id="btn-reset-dispatch" className="btn btn--ghost" onClick={() => { setForm(DEFAULT_DISPATCH); setResult(null) }}>
            Reset
          </button>
          <button
            id="btn-launch-council"
            className="btn btn--primary"
            onClick={handleDispatch}
            disabled={dispatching}
          >
            {dispatching ? <><div className="spinner" style={{ width: 14, height: 14 }} /> Dispatching...</> : 'Create & Dispatch Order'}
          </button>
        </div>
      </div>

      <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {error && (
          <div className="card" style={{ borderColor: 'var(--status-red)' }}>
            <span style={{ color: 'var(--status-red)' }}>⚠ {error}</span>
          </div>
        )}

        {result && (
          <div className="card" style={{ borderColor: result.verdict === 'APPROVED' ? 'var(--status-green)' : 'var(--status-red)' }}>
            <div className="card__header">
              <span className="card__title">Dispatch Decision — {result.order_id}</span>
              <span className={`verdict-badge verdict-badge--${result.verdict === 'APPROVED' ? 'green' : 'red'}`}>
                {result.verdict}
              </span>
            </div>
            <div className="grid-3">
              <div className="metric">
                <span className="metric__label">Assigned Drone</span>
                <span className="metric__value" style={{ fontSize: 15 }}>{result.assigned_drone_id ?? '—'}</span>
              </div>
              <div className="metric">
                <span className="metric__label">CBF Gate</span>
                <span className={`metric__value ${result.cbf_certificate.passed ? 'text-green' : 'text-red'}`} style={{ fontSize: 15 }}>
                  {result.cbf_certificate.passed ? 'PASSED' : 'REJECTED'}
                </span>
              </div>
              <div className="metric">
                <span className="metric__label">Gate Evaluation Time</span>
                <span className="metric__value" style={{ fontSize: 15 }}>
                  {result.cbf_certificate.execution_time_ms.toFixed(2)} ms
                </span>
              </div>
            </div>

            <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', maxWidth: '52ch' }}>
                This decision is already final — the council never influences it. Optionally ask the
                council to explain it in natural language; generated asynchronously, never blocking.
              </div>
              <div style={{ display: 'flex', gap: 10 }}>
                {result.verdict === 'APPROVED' && (
                  <button id="btn-export-waypoints" className="btn btn--ghost" onClick={handleExportWaypoints} disabled={exportingWaypoints} title="Download a QGC WPL 110 .waypoints file — open it in ArduPilot Mission Planner's Flight Plan tab">
                    {exportingWaypoints ? <><div className="spinner" style={{ width: 12, height: 12 }} /> Exporting...</> : 'Export for Mission Planner'}
                  </button>
                )}
                {result.explanation_status === 'NOT_REQUESTED' ? (
                  <button id="btn-request-explanation" className="btn btn--ghost" onClick={handleRequestExplanation} disabled={requestingExplanation}>
                    {requestingExplanation ? <><div className="spinner" style={{ width: 12, height: 12 }} /> Requesting...</> : 'Request Explanation'}
                  </button>
                ) : (
                  <button id="btn-view-explanation" className="btn btn--ghost" onClick={() => setActivePage('council')}>
                    View in Council Room ({result.explanation_status})
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Order Identity */}
        <Section title="Order Details">
          <div className="grid-3">
            <div className="form-group">
              <label className="form-label">City</label>
              <select id="input-city" className="form-select"
                value={form.city}
                onChange={e => handleCityChange(e.target.value)}>
                {cities.length === 0 && <option value="pune">Pune</option>}
                {cities.map(c => <option key={c.slug} value={c.slug}>{c.name}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Origin Depot</label>
              <select id="input-origin-depot" className="form-select"
                value={form.origin_depot_id}
                onChange={e => update('origin_depot_id', e.target.value)}>
                {depots.length === 0 && <option value={form.origin_depot_id}>{form.origin_depot_id}</option>}
                {depots.map(d => <option key={d.depot_id} value={d.depot_id}>{d.depot_id} — {d.name}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Priority</label>
              <select id="input-priority" className="form-select"
                value={form.priority}
                onChange={e => update('priority', e.target.value)}>
                {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
          </div>
        </Section>

        {/* Destination & Payload */}
        <Section title="Destination & Payload">
          <div className="grid-3">
            <NumericField id="input-dest-lat" label="Destination Latitude" value={form.destination_lat}
              onChange={v => update('destination_lat', v)} min={-90} max={90} step={0.0001} />
            <NumericField id="input-dest-lon" label="Destination Longitude" value={form.destination_lon}
              onChange={v => update('destination_lon', v)} min={-180} max={180} step={0.0001} />
            <NumericField id="input-payload" label="Payload (kg)" value={form.payload_kg}
              onChange={v => update('payload_kg', v)} min={0.1} max={10} step={0.1} />
          </div>
          <div className="grid-2" style={{ marginTop: '16px' }}>
            <NumericField id="input-deadline" label="Deadline (minutes)" value={form.deadline_minutes}
              onChange={v => update('deadline_minutes', v)} min={5} max={120} step={1} />
          </div>
        </Section>

        {/* Order JSON Preview */}
        <Section title="Order Specification (JSON)">
          <pre style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
            padding: '16px',
            fontSize: '12px',
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-secondary)',
            overflowX: 'auto',
            whiteSpace: 'pre-wrap',
            userSelect: 'text',
          }}>
            {JSON.stringify(form, null, 2)}
          </pre>
        </Section>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card">
      <div className="card__header"><span className="card__title">{title}</span></div>
      {children}
    </div>
  )
}

function NumericField({
  id, label, value, onChange, min, max, step,
}: {
  id: string; label: string; value: number; onChange: (v: number) => void; min: number; max: number; step?: number
}) {
  return (
    <div className="form-group">
      <label className="form-label">{label}</label>
      <input
        id={id}
        type="number"
        className="form-input"
        value={value}
        min={min}
        max={max}
        step={step ?? 1}
        onChange={e => onChange(Number(e.target.value))}
      />
    </div>
  )
}
