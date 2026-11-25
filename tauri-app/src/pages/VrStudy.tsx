// VR debrief study (research/vr_study/PROTOCOL.md): can a person tell whether a flight left its plan sideways, in
// height, or not at all, better on a 2D map with a height chart or on the 3D table in a headset?
// Both conditions show the same plan and flown track, with no warnings and no red highlights: only the view differs.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { createXRStore, useXR, XR } from '@react-three/xr'
import { useAppStore } from '../store/appStore'
import SignInCard from '../components/SignInCard'
import { toLocal } from '../components/vr/geo'
import { AltitudeRuler, ScaleAndNorth, Table } from '../components/vr/Airspace'
import { FlightGeometry, flightFrame, type FlightReplayDto } from '../components/vr/Flight'
import { Label } from '../components/vr/Tag'
import { UIMode } from '../components/vr/uiMode'
import { C } from '../components/vr/theme'

type Answer = 'none' | 'sideways' | 'height'
type Condition = '2d' | 'headset'
interface Trial { id: string; flight_s: number; answer?: Answer; replay: { home: [number, number]; planned: [number, number, number][]; flown: [number, number, number, number][] } }
interface Block { condition: Condition; set: string; practice: Trial[]; trials: Trial[] }
interface Plan { participant: string; group: number; blocks: Block[]; done: string[] }

const ANSWERS: { id: Answer; label: string }[] = [
  { id: 'none', label: 'Stayed on the plan' }, { id: 'sideways', label: 'Went off sideways' }, { id: 'height', label: 'Went off in height' }]
const PLAN_COLOR = '#2a78d6', FLOWN_COLOR = '#16A34A'
const xrStore = createXRStore()

function token(): Record<string, string> {
  try { const t = localStorage.getItem('aerofleet_token') || ''; return t ? { Authorization: `Bearer ${t}` } : {} } catch { return {} }
}
const asReplay = (t: Trial): FlightReplayDto => ({ id: 0, drone_id: '', fleet: '', verdict: 'CONFORMED', plan_name: null, log_name: null,
  replay: t.replay, episodes: [], timeline: [], tolerances: {}, flight_s: t.flight_s })

// ── 2D: top-down map and height chart ───────────────────────────────

function Map2D({ t }: { t: Trial }) {
  const c = t.replay.home
  const plan = t.replay.planned.map((p) => toLocal(p[0], p[1], c)), flown = t.replay.flown.map((p) => toLocal(p[1], p[2], c))
  const all = [...plan, ...flown], es = all.map((p) => p[0]), ns = all.map((p) => p[1])
  const minE = Math.min(...es), maxE = Math.max(...es), minN = Math.min(...ns), maxN = Math.max(...ns)
  const span = Math.max(80, maxE - minE, maxN - minN) * 1.1, cx = (minE + maxE) / 2, cy = (minN + maxN) / 2, S = 460
  const X = (e: number) => S / 2 + ((e - cx) / span) * S, Y = (n: number) => S / 2 - ((n - cy) / span) * S
  const path = (pts: [number, number][]) => pts.map((p, i) => `${i ? 'L' : 'M'}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(' ')
  const bar = [10, 20, 50, 100, 200, 500].find((m) => (m / span) * S > 60) ?? 500
  return (
    <svg viewBox={`0 0 ${S} ${S}`} style={{ width: '100%', maxWidth: S, background: '#F8FAFC', borderRadius: 8 }} role="img" aria-label="Top-down map">
      <path d={path(plan)} fill="none" stroke={PLAN_COLOR} strokeWidth={2} strokeDasharray="7 5" />
      <path d={path(flown)} fill="none" stroke={FLOWN_COLOR} strokeWidth={2} />
      <line x1={16} y1={S - 18} x2={16 + (bar / span) * S} y2={S - 18} stroke="#334155" strokeWidth={2} />
      <text x={16} y={S - 24} fontSize={11} fill="#334155">{bar} m</text>
      <text x={S - 22} y={24} fontSize={13} fill="#334155" textAnchor="middle">N ↑</text>
    </svg>
  )
}

function HeightChart({ t }: { t: Trial }) {
  // Height against the share of the route covered, plan and flight each measured along their own path, as mission
  // planners show a mission's height profile. No matching between the two is needed.
  const c = t.replay.home
  const profile = (pts: { xy: [number, number]; h: number }[]) => {
    let run = 0
    const out = pts.map((p, i) => { if (i) run += Math.hypot(p.xy[0] - pts[i - 1].xy[0], p.xy[1] - pts[i - 1].xy[1]); return { d: run, h: p.h } })
    return out.map((p) => ({ x: run > 0 ? p.d / run : 0, h: p.h }))
  }
  const plan = profile(t.replay.planned.map((p) => ({ xy: toLocal(p[0], p[1], c), h: p[2] })))
  const flown = profile(t.replay.flown.map((p) => ({ xy: toLocal(p[1], p[2], c), h: p[3] })))
  const W = 460, H = 180, L = 36, Bm = 22, hMax = Math.max(10, ...plan.map((r) => r.h), ...flown.map((r) => r.h)) * 1.1
  const X = (x: number) => L + x * (W - L - 8), Y = (h: number) => H - Bm - (h / hMax) * (H - Bm - 8)
  const line = (rows: { x: number; h: number }[]) => rows.map((r, i) => `${i ? 'L' : 'M'}${X(r.x).toFixed(1)},${Y(r.h).toFixed(1)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: W, background: '#F8FAFC', borderRadius: 8 }} role="img" aria-label="Height along the route">
      <line x1={L} y1={H - Bm} x2={W - 8} y2={H - Bm} stroke="#94A3B8" /><line x1={L} y1={8} x2={L} y2={H - Bm} stroke="#94A3B8" />
      <text x={L - 4} y={14} fontSize={10} textAnchor="end" fill="#64748B">{Math.round(hMax)} m</text>
      <text x={L - 4} y={H - Bm} fontSize={10} textAnchor="end" fill="#64748B">0</text>
      <text x={L} y={H - 6} fontSize={10} fill="#64748B">start</text>
      <text x={W - 8} y={H - 6} fontSize={10} textAnchor="end" fill="#64748B">end of route</text>
      <path d={line(plan)} fill="none" stroke={PLAN_COLOR} strokeWidth={2} strokeDasharray="7 5" />
      <path d={line(flown)} fill="none" stroke={FLOWN_COLOR} strokeWidth={2} />
    </svg>
  )
}

// ── headset: the 3D table with in-world answer buttons ───────────────

function AnswerButton({ x, label, onPick }: { x: number; label: string; onPick: () => void }) {
  const [hover, setHover] = useState(false)
  return (
    <group position={[x, 0, 0]}>
      <mesh onClick={onPick} onPointerOver={() => setHover(true)} onPointerOut={() => setHover(false)}>
        <boxGeometry args={[0.3, 0.09, 0.02]} />
        <meshStandardMaterial color={hover ? '#1D4ED8' : '#334155'} />
      </mesh>
      <Label position={[0, 0, 0.015]} text={label} color="#FFFFFF" size={0.018} />
    </group>
  )
}

function HeadsetScene({ trial, title, onAnswer, onReady }: { trial: Trial; title: string; onAnswer: (a: Answer) => void; onReady: () => void }) {
  const mode = useXR((s) => s.mode)
  const inXR = mode != null
  const f = useMemo(() => asReplay(trial), [trial])
  const { center, d } = useMemo(() => flightFrame(f), [f])
  useEffect(() => { if (inXR) onReady() }, [inXR, trial.id])  // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <UIMode.Provider value={{ inXR }}>
      <color attach="background" args={[C.void]} />
      <ambientLight intensity={0.6} /><directionalLight position={[1.5, 3, 2]} intensity={1.1} />
      <group position={inXR ? [0, 0.82, -0.8] : [0, 0, 0]}>
        <Table d={d} showPlinth={inXR} />
        <AltitudeRuler d={d} /><ScaleAndNorth d={d} />
        <FlightGeometry f={f} d={d} center={center} t={f.flight_s} neutral />
        {inXR && (
          <group position={[0, 0.42, -0.62]} rotation={[-0.15, 0, 0]}>
            <Label position={[0, 0.09, 0]} text={title} color="#E2E8F0" size={0.02} />
            {ANSWERS.map((a, i) => <AnswerButton key={a.id} x={(i - 1) * 0.34} label={a.label} onPick={() => onAnswer(a.id)} />)}
          </group>
        )}
      </group>
    </UIMode.Provider>
  )
}

// ── page ─────────────────────────────────────────────────────────────

export default function VrStudyPage() {
  const { apiUrl } = useAppStore()
  const base = `${apiUrl}/api/v1/vr-study`
  const [code, setCode] = useState('')
  const [consent, setConsent] = useState(false)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [blockIx, setBlockIx] = useState(0)
  const [phase, setPhase] = useState<'practice' | 'measured' | 'between' | 'preference' | 'finished'>('practice')
  const [ix, setIx] = useState(0)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [needsAuth, setNeedsAuth] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const shownAt = useRef<number | null>(null)

  const call = useCallback(async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const r = await fetch(`${base}${path}`, { ...init, headers: { ...token(), ...((init?.headers as Record<string, string>) || {}) } })
    if (r.status === 401) { setNeedsAuth(true); throw new Error('Sign in first.') }
    setNeedsAuth(false)
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`)
    return r.json()
  }, [base])

  const block = plan?.blocks[blockIx]
  const list = block ? (phase === 'practice' ? block.practice : block.trials) : []
  const trial = phase === 'practice' || phase === 'measured' ? list[ix] : undefined
  const cond = block?.condition
  const title = trial ? `${phase === 'practice' ? 'Practice' : 'Flight'} ${ix + 1} of ${list.length}` : ''

  const start = async () => {
    setError(null)
    try {
      const p = await call<Plan>(`/plan/${code.trim().toUpperCase()}`)
      // Resume: skip blocks and trials already answered.
      let b = 0
      while (b < p.blocks.length && p.blocks[b].trials.every((t) => p.done.includes(`${p.blocks[b].condition}|${t.id}`))) b++
      setPlan(p); setBlockIx(Math.min(b, p.blocks.length - 1))
      if (b >= p.blocks.length) { setPhase('preference'); return }
      const answered = p.blocks[b].trials.filter((t) => p.done.includes(`${p.blocks[b].condition}|${t.id}`)).length
      setPhase(answered ? 'measured' : 'practice'); setIx(answered)
    } catch (e) { setError((e as Error).message) }
  }

  useEffect(() => { if (cond === '2d' && trial) shownAt.current = performance.now() }, [cond, trial?.id])  // eslint-disable-line react-hooks/exhaustive-deps

  const answer = async (a: Answer) => {
    if (!plan || !block || !trial || feedback) return
    const ms = shownAt.current != null ? Math.round(performance.now() - shownAt.current) : null
    const practice = phase === 'practice'
    try {
      const r = await call<{ correct_answer?: Answer }>('/responses', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ participant: plan.participant, condition: practice ? `practice-${block.condition}` : block.condition,
          trial_id: trial.id, position: ix + 1, answer: a, ms }) })
      if (practice && r.correct_answer) {
        setFeedback(r.correct_answer === a ? 'Right.' : `Not quite: this one ${ANSWERS.find((x) => x.id === r.correct_answer)!.label.toLowerCase()}.`)
        setTimeout(() => { setFeedback(null); next() }, 1800)
        return
      }
    } catch (e) {
      if (!(e as Error).message.startsWith('Already answered')) { setError((e as Error).message); return }
    }
    next()
  }

  const next = () => {
    shownAt.current = null
    if (ix + 1 < list.length) { setIx(ix + 1); return }
    if (phase === 'practice') { setPhase('measured'); setIx(0); return }
    if (blockIx + 1 < (plan?.blocks.length ?? 0)) { setPhase('between'); return }
    setPhase('preference')
  }

  const prefer = async (p: '2d' | 'headset' | 'same') => {
    if (!plan) return
    try {
      await call('/responses', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ participant: plan.participant, condition: 'preference', trial_id: 'PREF', position: 0, answer: p }) })
    } catch (e) { if (!(e as Error).message.startsWith('Already answered')) { setError((e as Error).message); return } }
    setPhase('finished')
  }

  return (
    <div style={{ display: 'grid', gap: 14, maxWidth: 1000 }} id="vr-study">
      <div>
        <h1 style={{ margin: 0, fontSize: 22 }}>VR debrief study</h1>
        <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4, lineHeight: 1.5 }}>
          For the experimenter. Each flight shows its plan (dashed blue) and what was flown (green). The participant says
          whether the flight stayed on the plan, went off sideways or went off in height. Once on a 2D map with a height chart,
          once on the 3D table in the headset, with different flights. Protocol: <code>research/vr_study/PROTOCOL.md</code>.
        </div>
      </div>
      {needsAuth && <SignInCard apiUrl={apiUrl} reason="Answers are stored on this install's server." onSignedIn={() => setNeedsAuth(false)} />}
      {error && <div role="alert" style={{ color: 'var(--status-red)' }}>{error}</div>}

      {!plan && (
        <div className="card" style={{ padding: 16, display: 'grid', gap: 10, maxWidth: 520 }}>
          <label style={{ fontSize: 13 }}>Participant code <input className="form-input" value={code} onChange={(e) => setCode(e.target.value)} placeholder="P01" style={{ width: 90, marginLeft: 8 }} /></label>
          <label style={{ fontSize: 13, display: 'flex', gap: 8 }}><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            The participant has read and signed the consent sheet (paper copy kept by the experimenter).</label>
          <div><button className="btn btn--primary" disabled={!consent || !/^P\d{2}$/i.test(code.trim())} onClick={start}>Start or resume</button></div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No names are stored: only the code, the answers and the time each took.</div>
        </div>
      )}

      {plan && block && phase !== 'between' && phase !== 'preference' && phase !== 'finished' && trial && (
        <div className="card" style={{ padding: 16, display: 'grid', gap: 12 }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', fontSize: 13 }}>
            <b>{plan.participant}</b><span>· block {blockIx + 1} of 2 · {cond === '2d' ? '2D map and height chart' : 'Headset, 3D table'}</span>
            <span style={{ fontWeight: 700 }}>· {title}</span>
            {feedback && <span style={{ color: '#1D4ED8', fontWeight: 600 }}>{feedback}</span>}
          </div>
          {cond === '2d' ? <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 12, alignItems: 'start' }}>
              <div><div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>From above</div><Map2D t={trial} /></div>
              <div><div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Height along the route</div><HeightChart t={trial} /></div>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {ANSWERS.map((a) => <button key={a.id} className="btn btn--primary" disabled={!!feedback} onClick={() => answer(a.id)} style={{ padding: '10px 16px' }}>{a.label}</button>)}
            </div>
          </> : <>
            <div style={{ fontSize: 13 }}>The participant answers inside the headset with the controller. On this screen: open this page in the Quest browser, then <b>Enter VR</b>.</div>
            <div><button className="btn btn--primary" onClick={() => xrStore.enterVR().catch((e) => setError(`WebXR unavailable here: ${e}`))}>Enter VR</button></div>
            <div style={{ height: 420, borderRadius: 8, overflow: 'hidden' }}>
              <Canvas camera={{ position: [0, 1.0, 1.4], fov: 42, near: 0.01, far: 60 }}>
                <XR store={xrStore}>
                  <HeadsetScene trial={trial} title={feedback ?? title} onAnswer={answer} onReady={() => { shownAt.current = performance.now() }} />
                </XR>
              </Canvas>
            </div>
          </>}
        </div>
      )}

      {phase === 'between' && block && (
        <div className="card" style={{ padding: 16, display: 'grid', gap: 10 }}>
          <b>Block 1 done.</b>
          <div style={{ fontSize: 13 }}>Next: {plan!.blocks[blockIx + 1].condition === '2d' ? 'the 2D map and height chart on this screen' : 'the 3D table in the headset'}, with different flights. Three practice flights come first.</div>
          <div><button className="btn btn--primary" onClick={() => { setBlockIx(blockIx + 1); setPhase('practice'); setIx(0) }}>Start block 2</button></div>
        </div>
      )}
      {phase === 'preference' && (
        <div className="card" style={{ padding: 16, display: 'grid', gap: 10 }}>
          <b>Last question: which view made it easier to tell?</b>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn" onClick={() => prefer('2d')}>2D map and chart</button>
            <button className="btn" onClick={() => prefer('headset')}>3D table in the headset</button>
            <button className="btn" onClick={() => prefer('same')}>No difference</button>
          </div>
        </div>
      )}
      {phase === 'finished' && <div className="card" style={{ padding: 16 }}><b>Done. Thank you.</b> {plan?.participant}'s answers are stored. Results are only worked out after the last participant (<code>research/vr_study/analyse.py</code>).</div>}
    </div>
  )
}
