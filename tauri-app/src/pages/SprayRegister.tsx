// Spray register: the crop-protection SOP's Spray Monitoring Form (Annexure-I) for each spraying flight, and the
// seven-day deadline to submit it. The log fills what it can; fixed checks cite the SOP (aerofleet/assurance/spray_form.py).
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAppStore } from '../store/appStore'
import SignInCard from '../components/SignInCard'
import FleetPicker, { SimulatedFleetBanner, initialFleet } from '../components/FleetPicker'

type State = 'OVERDUE' | 'DUE_SOON' | 'DRAFT' | 'READY' | 'SUBMITTED'
interface AreaEst { moved_m: number; spacing_m: number; hectares: number; acres: number; note: string }
interface Row { review_id: number; drone_id: string; uin: string | null; log_name: string | null; date: string | null; location: string | null
  product: string | null; area?: AreaEst | null; state: State; due: string | null; days_left: number | null; missing: number; problems: number
  submitted_on: string | null; submitted_late_by: number | null; not_spray: boolean }
interface Register { fleet: string; as_of: string; deadline_days: number; source: string; counts: Record<State, number>; total_acres?: number; total_hectares?: number; rows: Row[]; not_spray: Row[]; latest_flight: string | null }
interface Field { code: string; label: string; section: string; kind: 'text' | 'number' | 'date' | 'datetime' | 'choice' | 'multi' | 'yesno'; options: string[] | null; required: boolean }
interface Check { level: 'missing' | 'problem' | 'note'; code: string; text: string; rule: string }
type Val = string | number | string[] | null
interface Form { review_id: number; drone_id: string; uin: string | null; log_name: string | null; values: Record<string, Val>; sources: Record<string, string>
  log: Record<string, unknown>; area?: AreaEst | null; checks: Check[]; status: Row & { state: State }; submitted_on: string | null; submitted_via: string | null; updated_by: string | null; updated_at: string | null }

const LOOK: Record<State, { label: string; color: string; bg: string }> = {
  OVERDUE: { label: 'Overdue', color: '#DC2626', bg: 'var(--status-red-subtle)' },
  DUE_SOON: { label: 'Due soon, incomplete', color: '#B45309', bg: 'var(--status-amber-subtle)' },
  DRAFT: { label: 'Incomplete', color: '#475569', bg: 'var(--bg-elevated, #F1F5F9)' },
  READY: { label: 'Complete, not sent', color: '#1D4ED8', bg: '#DBEAFE' },
  SUBMITTED: { label: 'Submitted', color: '#16A34A', bg: 'var(--status-green-subtle)' },
}
const SRC: Record<string, string> = { log: 'from the log', 'upload time': 'upload time', 'previous form': "this drone's last form", logbook: 'maintenance logbook', drone: 'drone', entered: 'entered' }

function token(): Record<string, string> {
  try { const t = localStorage.getItem('aerofleet_token') || ''; return t ? { Authorization: `Bearer ${t}` } : {} } catch { return {} }
}
const today = () => new Date().toISOString().slice(0, 10)
const show = (d: string | null) => d ? new Date(d + 'T00:00:00Z').toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }) : '—'

function Badge({ s }: { s: State }) {
  return <span style={{ fontSize: 12, fontWeight: 700, color: LOOK[s].color, background: LOOK[s].bg, borderRadius: 6, padding: '2px 8px', whiteSpace: 'nowrap' }}>{LOOK[s].label}</span>
}

function Input({ f, v, set, disabled }: { f: Field; v: Val; set: (v: Val) => void; disabled: boolean }) {
  const common = { className: 'form-input', disabled, style: { width: '100%' } as const, id: `sf-${f.code}` }
  if (f.kind === 'choice' || f.kind === 'yesno') {
    const opts = f.kind === 'yesno' ? ['Yes', 'No'] : f.options || []
    return <select {...common} value={(v as string) ?? ''} onChange={(e) => set(e.target.value || null)}><option value="">—</option>{opts.map((o) => <option key={o}>{o}</option>)}</select>
  }
  if (f.kind === 'multi') {
    const cur = (v as string[]) || []
    return <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>{(f.options || []).map((o) => (
      <label key={o} style={{ fontSize: 12, display: 'flex', gap: 4, alignItems: 'center' }}>
        <input type="checkbox" disabled={disabled} checked={cur.includes(o)} onChange={(e) => set(e.target.checked ? [...cur, o] : cur.filter((x) => x !== o))} />{o}</label>))}</div>
  }
  const type = f.kind === 'number' ? 'number' : f.kind === 'date' ? 'date' : f.kind === 'datetime' ? 'datetime-local' : 'text'
  return <input {...common} type={type} step={f.kind === 'number' ? 'any' : undefined} value={v == null ? '' : String(v)}
    onChange={(e) => set(e.target.value === '' ? null : f.kind === 'number' ? Number(e.target.value) : e.target.value)} />
}

export default function SprayRegisterPage() {
  const { apiUrl } = useAppStore()
  const [fleet, setFleet] = useState<string>(initialFleet())
  const base = `${apiUrl}/api/v1/assurance`
  const [asOf, setAsOf] = useState(today())
  const [reg, setReg] = useState<Register | null>(null)
  const [fields, setFields] = useState<Field[]>([])
  const [form, setForm] = useState<Form | null>(null)
  const [edit, setEdit] = useState<Record<string, Val>>({})
  const [picked, setPicked] = useState<number[]>([])
  const [sentOn, setSentOn] = useState(today()); const [via, setVia] = useState('')
  const [needsAuth, setNeedsAuth] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [showAside, setShowAside] = useState(false)

  const call = useCallback(async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const r = await fetch(`${base}${path}`, { ...init, headers: { ...token(), ...(init?.headers || {}) } })
    if (r.status === 401) { setNeedsAuth(true); throw new Error('Sign in to see the spray register.') }
    setNeedsAuth(false)
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`)
    return (r.headers.get('content-type') || '').includes('json') ? r.json() : (r.text() as unknown as T)
  }, [base])
  const act = async (fn: () => Promise<void>) => { setBusy(true); setError(null); try { await fn() } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }
  const fl = `/fleets/${encodeURIComponent(fleet)}`
  const openId = form?.review_id
  useEffect(() => { if (openId) document.getElementById('spray-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }, [openId])

  const load = useCallback(() => act(async () => {
    const [r, f] = await Promise.all([call<Register>(`${fl}/spray-register?as_of=${asOf}`), fields.length ? Promise.resolve(null) : call<{ fields: Field[] }>('/spray-form/fields')])
    setReg(r); if (f) setFields(f.fields)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [call, fl, asOf])
  useEffect(() => { load() }, [load])

  const open = (id: number) => act(async () => { setForm(await call<Form>(`${fl}/spray-forms/${id}?as_of=${asOf}`)); setEdit({}) })
  const values = useMemo(() => ({ ...(form?.values || {}), ...edit }), [form, edit])
  const save = () => act(async () => {
    if (!form) return
    setForm(await call<Form>(`${fl}/spray-forms/${form.review_id}?as_of=${asOf}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ values: edit }) }))
    setEdit({}); setReg(await call<Register>(`${fl}/spray-register?as_of=${asOf}`))
  })
  const setAside = (id: number, notSpray: boolean) => act(async () => {
    await call(`${fl}/spray-forms/${id}/not-spray`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ not_spray: notSpray }) })
    setForm(null); setReg(await call<Register>(`${fl}/spray-register?as_of=${asOf}`))
  })
  const submitted = () => act(async () => {
    if (!form) return
    if (Object.keys(edit).length) throw new Error('Save the form first.')
    setForm(await call<Form>(`${fl}/spray-forms/${form.review_id}/submitted`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ submitted_on: sentOn, via }) }))
    setReg(await call<Register>(`${fl}/spray-register?as_of=${asOf}`))
  })
  const print = (ids: number[]) => act(async () => {
    const html = await call<string>(`${fl}/spray-forms-print?ids=${ids.join(',')}`)
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([html], { type: 'text/html' }))
    a.download = `spray-monitoring-form-${ids.join('-')}.html`; a.click()
  })
  const csv = () => act(async () => {
    const text = await call<string>(`${fl}/spray-register.csv`)
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type: 'text/csv' })); a.download = `aerofleet-${fleet}-spray-register.csv`; a.click()
  })

  const sections = useMemo(() => {
    const out: [string, Field[]][] = []
    fields.forEach((f) => { const last = out[out.length - 1]; if (last && last[0] === f.section) last[1].push(f); else out.push([f.section, [f]]) })
    return out
  }, [fields])
  const locked = !!form?.submitted_on
  const byCode = (code: string) => (form?.checks || []).filter((c) => c.code === code && c.level !== 'missing')
  const stale = reg?.latest_flight && reg.latest_flight < new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10)

  return (
    <div style={{ display: 'grid', gap: 16, maxWidth: 1150 }} id="spray">
      <div style={{ display: 'flex', gap: 12, alignItems: 'end', flexWrap: 'wrap' }}>
        <div style={{ flex: 1 }}>
          <h1 style={{ margin: 0, fontSize: 22 }}>Spray register</h1>
          <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4, lineHeight: 1.5 }}>
            The crop-protection SOP asks the operator to submit a <b>Spray Monitoring Form</b> within <b>seven days</b> of spraying
            pesticide by drone. Each reviewed flight of fleet <b>{fleet}</b> gets that form, with what the flight log can tell
            already filled in, the days left, and fixed checks that quote the SOP. AeroFleet does not send the form; it records
            when and how you sent it.
          </div>
        </div>
        <FleetPicker apiUrl={apiUrl} fleet={fleet} onChange={(next) => { setFleet(next); setForm(null); setPicked([]) }} />
      </div>
      <SimulatedFleetBanner fleet={fleet} />
      {needsAuth && <SignInCard apiUrl={apiUrl} reason="The spray register reads this install's flight reviews." onSignedIn={load} />}
      {error && <div role="alert" style={{ color: 'var(--status-red)' }}>{error}</div>}

      {reg && <>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', fontSize: 13 }}>
          <label>Days counted as of <input type="date" className="form-input" value={asOf} onChange={(e) => setAsOf(e.target.value || today())} /></label>
          {stale && reg.latest_flight && <button className="btn" onClick={() => setAsOf(reg.latest_flight!)}>As of the last spraying flight ({show(reg.latest_flight)})</button>}
          {stale && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>The demo flights are from public logs flown years ago, so counted from today every form is overdue.</span>}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10 }}>
          {(Object.keys(LOOK) as State[]).map((s) => (
            <div key={s} className="card" style={{ padding: 12, borderLeft: `4px solid ${LOOK[s].color}` }}>
              <div style={{ fontSize: 24, fontWeight: 700, color: LOOK[s].color }}>{reg.counts[s] ?? 0}</div>
              <div style={{ fontSize: 12, fontWeight: 600 }}>{LOOK[s].label}</div>
            </div>))}
          {(reg.total_acres ?? 0) > 0 && (
            <div className="card" style={{ padding: 12, borderLeft: '4px solid var(--accent)' }} title="Geometric estimate from moving airborne distance × track spacing (5-13); no flow sensor">
              <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--accent)' }}>{reg.total_acres} ac</div>
              <div style={{ fontSize: 12, fontWeight: 600 }}>Est. swath ({reg.total_hectares} ha)</div>
            </div>)}
        </div>

        <div className="card" style={{ padding: 16, display: 'grid', gap: 8 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <b style={{ fontSize: 14, flex: 1 }}>Spraying flights ({reg.rows.length})</b>
            <button className="btn" disabled={!picked.length || busy} onClick={() => print(picked)} id="btn-print-forms">Print form for {picked.length || 'selected'} (max 6)</button>
            <button className="btn" disabled={busy} onClick={csv}>Download register (CSV)</button>
          </div>
          {reg.rows.length === 0 && <div style={{ fontSize: 13 }}>No reviewed flights yet. Upload flight logs in Fleet Assurance; each appears here.</div>}
          <style>{'#spray td, #spray th { padding: 6px 10px 6px 0; vertical-align: top; text-align: left }'}</style>
          {reg.rows.length > 0 && <div style={{ overflowX: 'auto' }}><table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ color: 'var(--text-secondary)' }}><th /><th>Sprayed</th><th>Drone</th><th>Location</th><th>Product</th><th>Est. area</th><th>Status</th><th>Due</th><th>Empty fields</th><th>Problems</th><th /></tr></thead>
            <tbody>{reg.rows.map((r) => (
              <tr key={r.review_id} style={{ borderTop: '1px solid var(--border)', background: form?.review_id === r.review_id ? 'var(--bg-elevated, #F8FAFC)' : undefined }}>
                <td><input type="checkbox" aria-label={`Select flight ${r.review_id}`} checked={picked.includes(r.review_id)}
                  onChange={(e) => setPicked(e.target.checked ? [...picked, r.review_id].slice(-6) : picked.filter((x) => x !== r.review_id))} /></td>
                <td style={{ whiteSpace: 'nowrap' }}>{show(r.date)}</td><td style={{ fontWeight: 600, whiteSpace: 'nowrap' }}>{r.drone_id}</td>
                <td>{r.location || '—'}</td><td>{r.product || '—'}</td>
                <td style={{ whiteSpace: 'nowrap' }} title={r.area?.note}>{r.area ? `${r.area.acres} ac (${r.area.hectares} ha)` : '—'}</td>
                <td><Badge s={r.state} /></td>
                <td style={{ whiteSpace: 'nowrap' }}>{show(r.due)}<div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  {r.state === 'SUBMITTED' ? `sent ${show(r.submitted_on)}${r.submitted_late_by ? `, ${r.submitted_late_by} d late` : ''}`
                    : r.days_left == null ? '' : r.days_left < 0 ? `${-r.days_left} days overdue` : `${r.days_left} days left`}</div></td>
                <td>{r.missing || '—'}</td><td style={{ color: r.problems ? '#DC2626' : undefined }}>{r.problems || '—'}</td>
                <td><button className="btn" style={{ padding: '2px 10px', fontSize: 12 }} onClick={() => open(r.review_id)}>Form →</button></td>
              </tr>))}</tbody>
          </table></div>}
          {reg.not_spray.length > 0 && <div style={{ fontSize: 12 }}>
            <button className="btn" style={{ fontSize: 12, padding: '2px 8px' }} onClick={() => setShowAside(!showAside)}>{showAside ? 'Hide' : 'Show'} {reg.not_spray.length} flights marked as not spraying</button>
            {showAside && <ul>{reg.not_spray.map((r) => <li key={r.review_id}>{show(r.date)} · {r.drone_id} · flight #{r.review_id}{' '}
              <button className="btn" style={{ fontSize: 11, padding: '0 6px' }} onClick={() => setAside(r.review_id, false)}>Put back</button></li>)}</ul>}
          </div>}
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Form and deadline: {reg.source}. Due date = spraying date + {reg.deadline_days} days, in UTC.</div>
        </div>
      </>}

      {form && <div className="card" style={{ padding: 16, display: 'grid', gap: 12 }} id="spray-form">
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <b style={{ fontSize: 15, flex: 1 }}>Spray Monitoring Form · {form.drone_id} · flight #{form.review_id} {form.log_name ? `(${form.log_name})` : ''}</b>
          <Badge s={form.status.state} />
          <button className="btn" onClick={() => setForm(null)}>Close</button>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
          UIN {form.uin || <b style={{ color: '#DC2626' }}>none on record</b>} · due {show(form.status.due)}
          {form.updated_by && <> · last saved by {form.updated_by}, signed into the record</>}
          {typeof form.log.direction_strength === 'number' && <> · {Math.round(100 * (form.log.direction_strength as number))}% of the distance flown lies along one axis</>}
          {form.area && <> · <span title={form.area.note}>est. swath area <b>{form.area.acres} acres ({form.area.hectares} ha)</b> from {form.area.moved_m} m × {form.area.spacing_m} m</span></>}
        </div>
        {form.checks.filter((c) => c.level !== 'missing').length > 0 && <div style={{ display: 'grid', gap: 4 }}>
          {form.checks.filter((c) => c.level !== 'missing').map((c, i) => (
            <div key={i} style={{ fontSize: 13, padding: '6px 10px', borderRadius: 6, background: c.level === 'problem' ? 'var(--status-red-subtle)' : 'var(--bg-elevated, #F1F5F9)' }}>
              <b style={{ color: c.level === 'problem' ? '#DC2626' : undefined }}>{c.level === 'problem' ? 'Problem' : 'Note'}:</b> {c.text}
              <span style={{ color: 'var(--text-muted)', fontSize: 11 }}> · {c.rule}</span></div>))}
        </div>}
        {sections.map(([sec, fs]) => (
          <fieldset key={sec} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: '8px 12px' }}>
            <legend style={{ fontSize: 13, fontWeight: 700, padding: '0 6px' }}>{sec}</legend>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '8px 16px' }}>
              {fs.map((f) => {
                const v = values[f.code] ?? null
                const empty = v == null || v === '' || (Array.isArray(v) && !v.length)
                const src = f.code in edit ? 'entered' : form.sources[f.code]
                return (
                  <div key={f.code} style={{ display: 'grid', gap: 3 }}>
                    <label htmlFor={`sf-${f.code}`} style={{ fontSize: 12 }}>
                      <span style={{ color: 'var(--text-muted)' }}>{f.code}</span> {f.label}{f.required && empty ? <span style={{ color: '#B45309' }}> *</span> : null}
                      {src && <span style={{ marginLeft: 6, fontSize: 10, color: src === 'log' ? '#1D4ED8' : 'var(--text-muted)', border: '1px solid currentColor', borderRadius: 4, padding: '0 4px' }}>{SRC[src] || src}</span>}
                    </label>
                    <Input f={f} v={v} disabled={locked} set={(nv) => setEdit({ ...edit, [f.code]: nv })} />
                    {byCode(f.code).map((c, i) => <div key={i} style={{ fontSize: 11, color: c.level === 'problem' ? '#DC2626' : 'var(--text-muted)' }}>{c.text}</div>)}
                    {f.code === '5-7' && <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>The log gives height above the take-off point, not above the crop.</div>}
                  </div>)
              })}
            </div>
          </fieldset>))}
        {!locked ? <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <button className="btn btn--primary" disabled={busy || !Object.keys(edit).length} onClick={save} id="btn-save-form">Save and sign</button>
          <button className="btn" disabled={busy} onClick={() => print([form.review_id])}>Print this form</button>
          <button className="btn" disabled={busy} onClick={() => setAside(form.review_id, true)} title="A test, survey or training flight; the mark is signed">Not a spray flight</button>
          <span style={{ flex: 1 }} />
          <label style={{ fontSize: 12 }}>Sent on <input type="date" className="form-input" value={sentOn} max={today()} onChange={(e) => setSentOn(e.target.value)} /></label>
          <input className="form-input" placeholder="How: email to …, or the portal" value={via} onChange={(e) => setVia(e.target.value)} style={{ minWidth: 200 }} />
          <button className="btn" disabled={busy || !via.trim() || form.status.missing > 0} onClick={submitted}
            title={form.status.missing ? `${form.status.missing} fields still empty` : 'Record that you sent it'}>Record as submitted</button>
        </div> : <div style={{ fontSize: 13 }}>Submitted on <b>{show(form.submitted_on)}</b> via {form.submitted_via}. The submitted version is frozen and signed.
          {' '}<button className="btn" onClick={() => print([form.review_id])}>Print</button></div>}
        {form.status.missing > 0 && <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{form.status.missing} required fields are still empty (marked *).</div>}
      </div>}
    </div>
  )
}
