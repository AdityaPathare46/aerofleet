// Today's fleet: the morning readiness board. One row per drone: ready / check first / do not fly, with every reason and
// a button to the evidence. Rules only (aerofleet/assurance/readiness.py); vibration is shown as context, never judged.
import { useCallback, useEffect, useState } from 'react'
import { useAppStore } from '../store/appStore'
import SignInCard from '../components/SignInCard'
import { LANGS, LOCALE, REVIEWED, saveLang, savedLang, t, type Lang } from '../lib/readinessText'

type Status = 'READY' | 'CHECK_FIRST' | 'DO_NOT_FLY'
interface Reason { level: Status; text: string; where: 'settings' | 'flight' | 'register'; code?: string; args?: Record<string, unknown> }
interface Row {
  drone_id: string; status: Status; reasons: Reason[]; settings_verdict: string | null; settings_compared_with: string | null
  registration: { uin: string; status: string } | null
  last_flight: { review_id: number; flown_at: string; warnings: string[]; flight_s?: number; normal_flight?: string[]; pilot_notes?: string[] } | null
  vibration: { latest_vs_own: { higher_than: number; earlier_flights: number } | null; public: { higher_than_pct: number; flights: number } | null } | null
}
interface Board { fleet: string; drones: Row[]; counts: Record<Status, number>; vibration_note: string; rules: string }

const LOOK: Record<Status, { color: string; bg: string }> = {
  DO_NOT_FLY: { color: '#DC2626', bg: 'var(--status-red-subtle)' },
  CHECK_FIRST: { color: '#B45309', bg: 'var(--status-amber-subtle)' },
  READY: { color: '#16A34A', bg: 'var(--status-green-subtle)' },
}

function token(): Record<string, string> {
  try { const t = localStorage.getItem('aerofleet_token') || ''; return t ? { Authorization: `Bearer ${t}` } : {} } catch { return {} }
}
const day = (iso?: string, lang: Lang = 'en') => {
  if (!iso) return '—'
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z')
  return isNaN(d.getTime()) ? iso.slice(0, 10) : d.toLocaleDateString(LOCALE[lang], { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function ReadinessPage() {
  const { apiUrl, setActivePage } = useAppStore()
  const fleet = (() => { try { return localStorage.getItem('aerofleet_fleet') || 'default' } catch { return 'default' } })()
  const [board, setBoard] = useState<Board | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [needsAuth, setNeedsAuth] = useState(false)
  const [loading, setLoading] = useState(false)
  const [lang, setLang] = useState<Lang>(savedLang())
  const tr = (k: string, a?: Record<string, unknown>) => t(lang, k, a)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const r = await fetch(`${apiUrl}/api/v1/assurance/fleets/${encodeURIComponent(fleet)}/readiness`, { headers: token() })
      if (r.status === 401) { setNeedsAuth(true); return }
      setNeedsAuth(false)
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`)
      setBoard(await r.json())
    } catch (e) { setError((e as Error).message) } finally { setLoading(false) }
  }, [apiUrl, fleet])
  useEffect(() => { load() }, [load])

  const go = (row: Row, where: Reason['where']) => {
    if (where === 'register') { setActivePage('hardware'); return }
    try {
      localStorage.setItem('aerofleet_open', JSON.stringify(where === 'settings' ? { kind: 'drift', id: row.drone_id } : { kind: 'review', id: row.last_flight?.review_id }))
    } catch { /* private window */ }
    setActivePage('assurance')
  }

  return (
    <div style={{ display: 'grid', gap: 16, maxWidth: 1100 }} id="readiness" lang={lang}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'end', flexWrap: 'wrap' }}>
        <div style={{ flex: 1 }}>
          <h1 style={{ margin: 0, fontSize: 22 }}>{tr('title')}</h1>
          <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4, lineHeight: 1.5 }}>
            {tr('intro')} {tr('fleet')} <b>{fleet}</b> {tr('fleetHint')}.
          </div>
        </div>
        <div role="group" aria-label={tr('language')} style={{ display: 'flex', gap: 4 }}>
          {LANGS.map((l) => (
            <button key={l.id} className={`btn${lang === l.id ? ' btn--primary' : ''}`} aria-pressed={lang === l.id} lang={l.id}
              onClick={() => { setLang(l.id); saveLang(l.id) }} style={{ padding: '4px 10px' }}>{l.label}</button>))}
        </div>
        <button className="btn" disabled={loading} onClick={load}>{loading ? tr('checking') : tr('again')}</button>
      </div>
      {!REVIEWED[lang] && <div style={{ fontSize: 12, color: '#B45309' }} lang={lang}>{tr('unchecked')}</div>}
      {needsAuth && <SignInCard apiUrl={apiUrl} reason="The board reads this install's records, so it needs a signed-in user." onSignedIn={load} />}
      {error && <div role="alert" style={{ color: 'var(--status-red)' }}>{error}</div>}

      {board && <>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          {(['DO_NOT_FLY', 'CHECK_FIRST', 'READY'] as Status[]).map((s) => (
            <div key={s} className="card" style={{ padding: 16, borderTop: `4px solid ${LOOK[s].color}` }}>
              <div style={{ fontSize: 30, fontWeight: 700, color: LOOK[s].color }}>{board.counts[s]}</div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{tr(s)}</div>
            </div>))}
        </div>
        {board.drones.length === 0 && <div className="card" style={{ padding: 16 }}>{tr('empty')}</div>}
        {board.drones.map((d) => (
          <div key={d.drone_id} className="card" style={{ padding: 14, display: 'grid', gridTemplateColumns: 'minmax(130px, 170px) 1fr minmax(170px, 230px)', gap: 16, borderLeft: `5px solid ${LOOK[d.status].color}` }}>
            <div style={{ display: 'grid', gap: 6, alignContent: 'start' }}>
              <b style={{ fontSize: 16 }}>{d.drone_id}</b>
              <span style={{ justifySelf: 'start', fontSize: 12, fontWeight: 700, padding: '3px 10px', borderRadius: 999, color: LOOK[d.status].color, background: LOOK[d.status].bg }}>{tr(d.status)}</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{d.registration ? `UIN ${d.registration.uin}` : tr('noUin')}</span>
            </div>
            <div style={{ display: 'grid', gap: 6, alignContent: 'start' }}>
              {d.reasons.length === 0 && <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{tr('allClear')}</span>}
              {d.reasons.map((r, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'baseline', fontSize: 13 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 4, background: LOOK[r.level].color, flexShrink: 0, marginTop: 4 }} />
                  <span style={{ flex: 1 }} title={lang === 'en' ? undefined : r.text}>{r.code ? tr(r.code, r.args) : r.text}</span>
                  {(r.where !== 'flight' || d.last_flight) && <button className="btn" style={{ padding: '2px 10px', fontSize: 12 }} onClick={() => go(d, r.where)}>{tr(r.where)} →</button>}
                </div>))}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'grid', gap: 4, alignContent: 'start' }}>
              <span>{tr('lastFlight')}: <b>{day(d.last_flight?.flown_at, lang)}</b>{d.last_flight?.flight_s ? ` · ${Math.round(d.last_flight.flight_s / 60)} ${tr('min')}` : ''}</span>
              <span>{tr('settingsLine')}: {d.settings_verdict ? (d.settings_compared_with ? `${tr(d.settings_verdict)} (${tr(d.settings_compared_with === 'vs_baseline' ? 'vsBaseline' : 'vsPrevious')})` : tr(d.settings_verdict)) : tr('notChecked')}</span>
              {d.last_flight?.pilot_notes && d.last_flight.pilot_notes.length > 0 && (
                <span title="How the last flight was flown: shown for the pilot, never a reason on its own">{tr('pilotNote')}: {d.last_flight.pilot_notes.join('; ')}</span>)}
              {d.last_flight?.normal_flight && d.last_flight.normal_flight.length > 0 && (
                <span title="From the learned normal-flight model: context, never part of the verdict. Not trained on spraying drones (payload is not an input).">{tr('model')}: {d.last_flight.normal_flight.join('; ')}</span>)}
              {d.vibration && <span title={tr('vibNote')}>{tr('vibration')}: {d.vibration.latest_vs_own ? tr('vibOwn', { x: d.vibration.latest_vs_own.higher_than, y: d.vibration.latest_vs_own.earlier_flights }) : tr('fewFlights')}{d.vibration.public ? tr('vibPublic', { p: d.vibration.public.higher_than_pct }) : ''}</span>}
            </div>
          </div>))}
        <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6 }}><b>{tr('rulesTitle')}</b> {lang === 'en' ? board.rules : tr('rules')} {lang === 'en' ? board.vibration_note : tr('vibNote')}</div>
      </>}
    </div>
  )
}
