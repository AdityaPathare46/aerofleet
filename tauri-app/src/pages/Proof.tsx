// "Show me": answers to the hardest questions, run live. Recomputes the paper's headline results from the committed
// data (with the commits that declared each test), attacks a copy of the signed record, and lists what the tool was
// measured to do. Backed by aerofleet/evidence.py and POST /api/v1/assurance/ledger/tamper-demo.
import { useState } from 'react'
import { useAppStore } from '../store/appStore'
import SignInCard from '../components/SignInCard'

interface Commit { commit: string; date?: string; subject?: string }
interface Claim {
  id: string; claim: string; paper: string; recomputed: number | null; ci: number[] | null; n: number | null; p: number | null
  detail: string; stored: boolean; ms: number; matches_paper: boolean; declared: Commit; result_commit: Commit
  declared_before_result: boolean; script: string; data: string; pass_mark: string
}
interface Attack { attack: string; change: string; caught: boolean; problem: string }
interface TamperResult { attacks: Attack[]; all_caught: boolean; record_untouched: { ok: boolean; entries: number }; note: string }

const GREEN = '#16A34A', RED = '#DC2626'
const card: React.CSSProperties = { padding: 20, display: 'grid', gap: 12 }
const kicker: React.CSSProperties = { fontSize: 11, letterSpacing: 1, textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }
const mono: React.CSSProperties = { fontFamily: 'var(--font-mono, monospace)', fontSize: 12 }

function token(): Record<string, string> {
  try { const t = localStorage.getItem('aerofleet_token') || ''; return t ? { Authorization: `Bearer ${t}` } : {} } catch { return {} }
}
const day = (iso?: string) => (iso ? new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '?')
function gap(a?: string, b?: string) {
  if (!a || !b) return ''
  const min = Math.round((new Date(b).getTime() - new Date(a).getTime()) / 60000)
  return min < 120 ? `${min} min later` : min < 2880 ? `${Math.round(min / 60)} h later` : `${Math.round(min / 1440)} days later`
}

const TESTS: { name: string; what: string }[] = [
  { name: 'No AI in the decision path', what: 'Follows every import from the product code and fails if it can reach an AI agent, the language-model panel or any ML library (tests/unit/test_no_ai_in_decision_path.py).' },
  { name: 'Paper numbers stay true', what: 'docs/paper/check_numbers.py checks 29 key numbers across the paper, supplement, cover letter and highlights against the result files, and every number on the Overview page against its source.' },
  { name: 'Results recompute', what: 'The four claims above are recomputed in a test, compared with the paper\'s text, and the declaration is checked to predate the result (tests/unit/test_evidence.py).' },
  { name: 'Damaged files', what: 'Empty files, random bytes, a mission file renamed as a log and a log cut off mid-flight all get a clear message, never a crash.' },
  { name: 'Tampering', what: 'Every attack on this page is also an automated test.' },
]
const MEASURED: { what: string; value: string; source: string }[] = [
  { what: 'Review speed, 36 real PX4 logs of 0.9 to 92.8 MB', value: 'median 0.23 s; the 92.8 MB (28 min) flight in 2.44 s', source: 'docs/measurements/review_speed.md' },
  { what: 'Planned-versus-flown check, deviations injected into 40 real flights', value: '36/40 sideways (35 m) and 39/40 upward (20 m) found; 0/40 false alarms with 5 s waypoints', source: 'research/results/px4_log_study/injection_reconcile.md' },
  { what: 'Describe-a-problem search, 96 expert-diagnosed crashes held out', value: 'best guess right 22%, below the 27% of guessing the most common cause; so it is not used as a diagnosis', source: 'research/results/px4_log_study/troubleshoot_loo_settled.md' },
]

export default function ProofPage() {
  const { apiUrl, setActivePage } = useAppStore()
  const [claims, setClaims] = useState<Claim[] | null>(null)
  const [tamper, setTamper] = useState<TamperResult | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [took, setTook] = useState<number | null>(null)
  const [needsAuth, setNeedsAuth] = useState(false)

  const recompute = async () => {
    setBusy('claims'); setError(null)
    const t0 = performance.now()
    try {
      const r = await fetch(`${apiUrl}/api/v1/evidence/claims`)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setClaims(await r.json()); setTook(Math.round(performance.now() - t0))
    } catch (e) { setError(`Could not recompute: ${(e as Error).message}. Is the API running?`) } finally { setBusy(null) }
  }
  const attack = async () => {
    setBusy('tamper'); setError(null)
    try {
      const r = await fetch(`${apiUrl}/api/v1/assurance/ledger/tamper-demo`, { method: 'POST', headers: token() })
      if (r.status === 401) { setNeedsAuth(true); return }
      setNeedsAuth(false)
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`)
      setTamper(await r.json())
    } catch (e) { setError((e as Error).message) } finally { setBusy(null) }
  }

  return (
    <div style={{ display: 'grid', gap: 16, maxWidth: 1100 }} id="proof">
      <div>
        <h1 style={{ margin: 0, fontSize: 22 }}>Proof</h1>
        <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
          Don't take our word for it: each check below runs now, on this computer, from the files in the repository.
        </div>
      </div>
      {error && <div role="alert" className="card" style={{ padding: 12, color: RED }}>{error}</div>}

      {/* 1. Results */}
      <div className="card" style={card} id="proof-claims">
        <div style={kicker}>1 · The paper's results, recomputed now</div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn--primary" id="btn-recompute" disabled={busy !== null} onClick={recompute}>{busy === 'claims' ? 'Recomputing…' : claims ? 'Recompute again' : 'Recompute the results'}</button>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            Reads the committed result files, redoes the arithmetic of the study's scripts and compares with the paper. Git shows
            when each test (hypothesis and pass mark) was committed, and when its result was.
          </span>
          {claims && took != null && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>done in {took} ms</span>}
        </div>
        {claims && claims.map((c) => (
          <div key={c.id} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: 14, display: 'grid', gap: 8 }}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
              <b style={{ fontSize: 15, flex: 1 }}>{c.claim}</b>
              <span style={{ fontWeight: 700, color: c.matches_paper ? GREEN : RED }}>{c.matches_paper ? '✓ matches the paper' : '✗ differs from the paper'}</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10, fontSize: 13 }}>
              <div><div style={kicker}>The paper says</div>{c.paper}</div>
              <div><div style={kicker}>{c.stored ? 'Read from the stored result' : 'Recomputed now'}</div>
                <span style={{ fontSize: 22, fontWeight: 700, color: 'var(--accent)' }}>{c.recomputed}</span>
                {c.ci && <span style={{ color: 'var(--text-secondary)' }}> [{c.ci.join(', ')}]</span>}
                {c.p != null && <span style={{ color: 'var(--text-secondary)' }}> · p = {c.p < 0.01 ? c.p.toFixed(4) : c.p.toFixed(2)}</span>}
                {c.n != null && <span style={{ color: 'var(--text-secondary)' }}> · n = {c.n}</span>}
                <span style={{ color: 'var(--text-muted)', fontSize: 11 }}> ({c.ms} ms)</span></div>
              <div><div style={kicker}>Pass mark</div>{c.pass_mark}</div>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{c.detail}</div>
            <div style={{ fontSize: 12, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <span style={{ color: c.declared_before_result ? GREEN : RED, fontWeight: 700 }}>{c.declared_before_result ? '✓ declared before the result' : '? order not shown'}</span>
              <span>Declared <span style={mono}>{c.declared.commit}</span> {day(c.declared.date)}</span>
              <span>→ result <span style={mono}>{c.result_commit.commit}</span> {day(c.result_commit.date)} ({gap(c.declared.date, c.result_commit.date)})</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Script <span style={mono}>{c.script}</span> · data <span style={mono}>{c.data}</span></div>
          </div>))}
      </div>

      {/* 2. Tampering */}
      <div className="card" style={card} id="proof-tamper">
        <div style={kicker}>2 · Try to tamper with the signed record</div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn--primary" id="btn-tamper" disabled={busy !== null} onClick={attack}>{busy === 'tamper' ? 'Attacking a copy…' : 'Run five attacks on a copy'}</button>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Each attack edits a copy of the record in memory; the real record is checked afterwards and is not changed.</span>
        </div>
        {needsAuth && <SignInCard apiUrl={apiUrl} reason="The attacks run on a copy of this install's signed record, so they need a signed-in user."
          onSignedIn={() => { setNeedsAuth(false); attack() }} />}
        {tamper && <>
          {tamper.attacks.map((a) => (
            <div key={a.attack} style={{ display: 'grid', gridTemplateColumns: '28px 1fr', gap: 8, fontSize: 13, padding: '8px 0', borderTop: '1px solid var(--border)' }}>
              <span style={{ fontSize: 18, color: a.caught ? GREEN : RED }}>{a.caught ? '✓' : '✗'}</span>
              <div><b>{a.attack}</b> <span style={{ color: 'var(--text-secondary)' }}>({a.change})</span>
                <div style={{ color: a.caught ? GREEN : RED }}>{a.caught ? 'Caught: ' : 'Not caught: '}{a.problem}</div></div>
            </div>))}
          <div style={{ fontSize: 13, padding: 10, borderRadius: 'var(--radius-md)', background: tamper.all_caught ? 'var(--status-green-subtle)' : 'var(--status-red-subtle)' }}>
            <b>{tamper.all_caught ? `All ${tamper.attacks.length} attacks caught.` : 'An attack was not caught.'}</b> The real record ({tamper.record_untouched.entries} entries) still checks
            {tamper.record_untouched.ok ? ' intact' : ' with a problem (see Fleet Assurance ▸ Signed record)'}. <span style={{ color: 'var(--text-secondary)' }}>{tamper.note}</span>
          </div>
        </>}
      </div>

      {/* 3. Measured */}
      <div className="card" style={card}>
        <div style={kicker}>3 · What the tool was measured to do</div>
        {MEASURED.map((m) => (
          <div key={m.what} style={{ fontSize: 13, display: 'grid', gap: 2 }}>
            <b>{m.what}</b><span>{m.value}</span><span style={{ ...mono, fontSize: 11, color: 'var(--text-muted)' }}>{m.source}</span>
          </div>))}
      </div>

      {/* 4. Automated checks */}
      <div className="card" style={card}>
        <div style={kicker}>4 · Checked automatically on every change</div>
        {TESTS.map((t) => <div key={t.name} style={{ fontSize: 13 }}><b>{t.name}.</b> <span style={{ color: 'var(--text-secondary)' }}>{t.what}</span></div>)}
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Run them all: <span style={mono}>python -m pytest -q --no-cov tests/unit tests/integration</span></div>
        <div><button className="btn" onClick={() => setActivePage('overview')}>Back to the Overview</button></div>
      </div>
    </div>
  )
}
