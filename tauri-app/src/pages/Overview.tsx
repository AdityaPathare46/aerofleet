// The opening page of a demonstration: what AeroFleet is for, what the study found, how the tool follows from it,
// what it has been measured to do, and what is not yet shown. Every number comes from src/lib/studyFacts.ts, which
// docs/paper/check_numbers.py checks against the paper and the result files.
import { useEffect, useState } from 'react'
import { useAppStore } from '../store/appStore'
import { FINDINGS, NOT_YET, REGULATION, STUDY, TOOL_TESTS, type Finding } from '../lib/studyFacts'

const BLUE = '#2a78d6', ORANGE = '#eb6834', GREEN = '#1baf7a'
const DEMO_FLEET = 'demo'

function token(): Record<string, string> {
  try { const t = localStorage.getItem('aerofleet_token') || ''; return t ? { Authorization: `Bearer ${t}` } : {} } catch { return {} }
}

/** Open Fleet Assurance on the demo fleet and scroll to one of its sections once it has loaded. */
function useGoTo() {
  const { setActivePage } = useAppStore()
  return (sectionId?: string) => {
    try { localStorage.setItem('aerofleet_fleet', DEMO_FLEET) } catch { /* private window */ }
    setActivePage('assurance')
    if (!sectionId) return
    let tries = 0
    const look = () => {
      const el = document.getElementById(sectionId)
      if (el) { el.scrollIntoView({ behavior: 'smooth', block: 'start' }); return }
      if (++tries < 40) setTimeout(look, 150)            // the section appears once the fleet's data has loaded
    }
    setTimeout(look, 150)
  }
}

function Bars({ f }: { f: Finding }) {
  if (!f.bars) return null
  const W = 300, row = 30, H = f.bars.length * row + 16, L = 0
  const x = (v: number) => L + v * (W - L)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: 360 }} role="img"
      aria-label={f.bars.map((b) => `${b.label} ${b.value}`).join(', ')}>
      {f.bars.map((b, i) => (
        <g key={b.label}>
          <text x={L} y={i * row + 10} fontSize="10" fill="#475569">{b.label} · <tspan fontWeight={700}>{b.value.toFixed(2)}</tspan></text>
          <rect x={L} y={i * row + 14} width={W} height={10} rx={3} fill="var(--bg-elevated)" />
          <rect x={L} y={i * row + 14} width={x(b.value) - L} height={10} rx={3} fill={b.kind === 'result' ? BLUE : '#94A3B8'} />
        </g>))}
      {f.refLine && <>
        <line x1={x(f.refLine.value)} x2={x(f.refLine.value)} y1={12} y2={f.bars.length * row} stroke={ORANGE} strokeWidth={2} strokeDasharray="3 2" />
        <text x={x(f.refLine.value)} y={H - 3} fontSize="10" textAnchor="middle" fill={ORANGE}>{f.refLine.label} ({f.refLine.value.toFixed(2)})</text>
      </>}
    </svg>
  )
}

const card: React.CSSProperties = { padding: 20, display: 'grid', gap: 12 }
const h2: React.CSSProperties = { margin: 0, fontSize: 18 }
const kicker: React.CSSProperties = { fontSize: 11, letterSpacing: 1, textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }
const grid = (min: number): React.CSSProperties => ({ display: 'grid', gap: 12, gridTemplateColumns: `repeat(auto-fit, minmax(${min}px, 1fr))` })

const HOW: { finding: string; does: string; section: string; button: string }[] = [
  { finding: 'Logs cannot assign blame', does: 'Each flight review lists the log\'s events in time order (mode changes, the pilot taking over, battery, GPS, what the autopilot reported about its sensors) with the quality of the evidence, and names no cause.', section: 'flight-list', button: 'Open a flight review' },
  { finding: 'No warning within a drone', does: 'Each drone\'s vibration flight by flight, in the order flown (GPS time, not upload date), with the newest flight against its own earlier ones, as context.', section: 'vibration-card', button: 'Open a drone\'s history' },
  { finding: 'Rough drones, weak screen', does: 'Each drone\'s position among drones with the same measurement, with no pass/fail line, and the study\'s evidence printed beside it. The last 10 s of each flight are left out so an impact cannot make a drone look rough.', section: 'vibration-card', button: 'Open the fleet view' },
  { finding: 'AI added errors; records are required', does: 'Fixed code only. Every baseline, approval, check and review is signed (Ed25519), chained and tied to the SHA-256 of the uploaded file, with a printable report and an export an auditor can verify without AeroFleet.', section: 'ledger-card', button: 'Check the signed record' },
]

const FLOW: { when: string; what: string[]; section: string }[] = [
  { when: 'Before a flight', what: ['Settings against the fleet\'s approved configuration: a disabled failsafe marks the drone Blocked', 'Missions planned for the same time checked for conflicts, with a proposed fix', 'Battery against the forecast wind at cruise height'], section: 'deconflict-card' },
  { when: 'After a flight', what: ['Upload the log, with the mission file if there is one', 'Events in time order, evidence quality, settings changed in flight', 'A signed, printable review'], section: 'flight-list' },
  { when: 'Over a fleet\'s life', what: ['Each drone\'s vibration against its own history', 'Its position among comparable drones', 'A tamper-evident record for the three-year retention rule'], section: 'vibration-card' },
  { when: 'When something goes wrong', what: ['Describe the problem in words', 'A checklist ordered by how often PX4 experts found each cause', 'The most similar past crash threads to read'], section: 'troubleshoot-card' },
]

const WHO: { who: string; gets: string }[] = [
  { who: 'Fleet operators', gets: 'One place for settings, flight reviews and records, without trusting an unproven verdict.' },
  { who: 'Maintenance engineers', gets: 'Which drone to look at first, with its own history beside the fleet\'s.' },
  { who: 'Investigators and insurers', gets: 'A time-ordered, signed account of what the log shows, and a clear statement of what it cannot show.' },
  { who: 'Regulators and tool builders', gets: 'A ten-item checklist for testing any log-based diagnostic before it is trusted.' },
]

export default function OverviewPage() {
  const { apiUrl } = useAppStore()
  const goTo = useGoTo()
  const [live, setLive] = useState<{ drones: number; flights: number; entries: number } | null>(null)

  useEffect(() => {        // live counts from this install's demo fleet; silently absent when signed out or empty
    const base = `${apiUrl}/api/v1/assurance`
    const get = (p: string) => fetch(base + p, { headers: token() }).then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    Promise.all([get(`/fleets/${DEMO_FLEET}/vibration`), get(`/fleets/${DEMO_FLEET}/flights?limit=200`), get('/ledger/head')])
      .then(([v, f, h]) => setLive({ drones: v.drones.length, flights: f.length, entries: h.seq }))
      .catch(() => setLive(null))
  }, [apiUrl])

  return (
    <div style={{ display: 'grid', gap: 16, maxWidth: 1100 }} id="overview">
      {/* 1. What it is */}
      <div className="card" style={{ ...card, padding: 28, background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent-dim) 100%)', color: '#fff', border: 'none' }}>
        <div style={{ ...kicker, color: 'rgba(255,255,255,0.75)' }}>AeroFleet 2.0 · open source · COEP Technological University</div>
        <h1 style={{ margin: 0, fontSize: 30, lineHeight: 1.15 }}>Evidence, not verdicts.</h1>
        <div style={{ fontSize: 16, maxWidth: 780, lineHeight: 1.5 }}>
          A ground-side assurance tool for PX4 and ArduPilot drone fleets. It checks settings, plans and flight logs an operator
          already has, keeps a signed record of every check, and shows what a log can support, built on a study of
          {' '}{STUDY.crashLogs} crash logs from a {STUDY.logs}-log public archive.
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 4 }}>
          <button className="btn" style={{ background: '#fff', color: 'var(--accent)', fontWeight: 700 }} onClick={() => goTo()}>Open the demo fleet</button>
          <button className="btn" style={{ background: 'transparent', color: '#fff', border: '1px solid rgba(255,255,255,0.6)' }}
            onClick={() => document.getElementById('overview-findings')?.scrollIntoView({ behavior: 'smooth' })}>What the study found</button>
        </div>
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', fontSize: 13, color: 'rgba(255,255,255,0.85)' }}>
          <span>Reads files only, never contacts the aircraft</span><span>No AI in any decision</span><span>Open source</span>
          {live && live.flights > 0 && <span style={{ fontWeight: 700, color: '#fff' }}>Live here: {live.drones} drones · {live.flights} real flights reviewed · {live.entries} signed record entries</span>}
        </div>
      </div>

      {/* 2. The problem */}
      <div className="card" style={card}>
        <div style={kicker}>The problem</div>
        <h2 style={h2}>Rules demand records, and tools promise verdicts that logs may not support</h2>
        <div style={grid(220)}>
          {REGULATION.map((r) => (
            <div key={r.where} style={{ padding: 12, borderRadius: 'var(--radius-md)', background: 'var(--bg-elevated)' }}>
              <div style={{ fontWeight: 700 }}>{r.where}</div><div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{r.rule}</div>
            </div>))}
        </div>
        <div style={{ fontSize: 14, lineHeight: 1.55 }}>
          When a drone crashes, the flight log is the richest record there is. Log viewers, fleet platforms and machine-learning and
          language-model prototypes promise to turn it into an answer: what failed, and whether the pilot or the aircraft was to
          blame. That answer can decide a warranty claim, an insurance payout or who is held responsible. <b>We tested whether
          real logs can carry that weight.</b>
        </div>
      </div>

      {/* 3. What the study found */}
      <div className="card" style={card} id="overview-findings">
        <div style={kicker}>What we found · {STUDY.crashLogs} crash logs · {STUDY.logs}-log PX4 archive · tests declared before they were run</div>
        <h2 style={h2}>Six findings, each with what it means for an operator</h2>
        <div style={grid(320)}>
          {FINDINGS.map((f) => (
            <div key={f.id} style={{ padding: 14, borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', display: 'grid', gap: 8, alignContent: 'start' }}>
              <div style={{ fontWeight: 700, fontSize: 15 }}>{f.title}</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 28, fontWeight: 700, color: 'var(--accent)', fontVariantNumeric: 'tabular-nums' }}>{f.big}</span>
                <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{f.bigLabel}</span>
              </div>
              <Bars f={f} />
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{f.detail}</div>
              <div style={{ fontSize: 13, lineHeight: 1.5, paddingLeft: 10, borderLeft: `3px solid ${GREEN}` }}><b>So:</b> {f.meaning}</div>
            </div>))}
        </div>
      </div>

      {/* 4. How the tool follows from the findings */}
      <div className="card" style={card}>
        <div style={kicker}>How AeroFleet answers it</div>
        <h2 style={h2}>Each design choice comes from a finding</h2>
        <div style={{ display: 'grid', gap: 10 }}>
          {HOW.map((h) => (
            <div key={h.finding} style={{ display: 'grid', gridTemplateColumns: 'minmax(150px, 210px) 1fr auto', gap: 14, alignItems: 'center', padding: '10px 0', borderTop: '1px solid var(--border)' }}>
              <div style={{ fontWeight: 700, fontSize: 14 }}>{h.finding}</div>
              <div style={{ fontSize: 13, lineHeight: 1.5 }}>{h.does}</div>
              <button className="btn" onClick={() => goTo(h.section)}>{h.button} →</button>
            </div>))}
        </div>
      </div>

      {/* 5. How an operator uses it */}
      <div className="card" style={card}>
        <div style={kicker}>How it is used</div>
        <h2 style={h2}>One workflow, before and after every flight</h2>
        <div style={grid(220)}>
          {FLOW.map((s, i) => (
            <button key={s.when} onClick={() => goTo(s.section)} className="card"
              style={{ textAlign: 'left', padding: 14, display: 'grid', gap: 6, alignContent: 'start', cursor: 'pointer', font: 'inherit', color: 'inherit' }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{ width: 24, height: 24, borderRadius: 12, background: 'var(--accent)', color: '#fff', display: 'grid', placeItems: 'center', fontSize: 12, fontWeight: 700 }}>{i + 1}</span>
                <b>{s.when}</b>
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, lineHeight: 1.5, color: 'var(--text-secondary)' }}>{s.what.map((w) => <li key={w}>{w}</li>)}</ul>
            </button>))}
        </div>
      </div>

      {/* 6. Benefits and evidence */}
      <div style={grid(420)}>
        <div className="card" style={card}>
          <div style={kicker}>Who benefits</div>
          <h2 style={h2}>Benefits and impact</h2>
          {WHO.map((w) => (
            <div key={w.who} style={{ fontSize: 13, lineHeight: 1.5 }}><b>{w.who}.</b> <span style={{ color: 'var(--text-secondary)' }}>{w.gets}</span></div>))}
          <div style={{ fontSize: 13, lineHeight: 1.5, padding: 12, borderRadius: 'var(--radius-md)', background: 'var(--status-green-subtle)' }}>
            <b>The wider impact:</b> it stops a log being used to blame a pilot or a manufacturer for something the log cannot show,
            and it gives anyone building such tools a way to test them honestly.
          </div>
        </div>
        <div className="card" style={card}>
          <div style={kicker}>What the tool was measured to do</div>
          <h2 style={h2}>Tested on real PX4 logs</h2>
          {TOOL_TESTS.map((t) => (
            <div key={t.what} style={{ fontSize: 13, lineHeight: 1.5 }}><b>{t.what}.</b> <span style={{ color: 'var(--text-secondary)' }}>{t.result}</span></div>))}
          <div style={{ fontSize: 13, lineHeight: 1.5, padding: 12, borderRadius: 'var(--radius-md)', background: 'var(--status-amber-subtle)' }}>
            <b>Not yet shown:</b>
            <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>{NOT_YET.map((n) => <li key={n}>{n}</li>)}</ul>
          </div>
        </div>
      </div>

      <div className="card" style={{ ...card, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}>
        <div style={{ fontSize: 14 }}><b>See it on real data.</b> <span style={{ color: 'var(--text-secondary)' }}>The demo fleet holds real public PX4 flights of eight airframes.</span></div>
        <button className="btn btn--primary" onClick={() => goTo()}>Open the demo fleet →</button>
      </div>
    </div>
  )
}
