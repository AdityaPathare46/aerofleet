import React, { useMemo } from 'react'
import { Line } from '@react-three/drei'
import { Diorama, fmtDistance, toLocal } from './geo'
import { Label } from './Tag'
import { C, FONT } from './theme'

// A reviewed flight on the table: the approved plan (dashed) against the flown track (green where it
// stayed within the fleet's tolerances, red during a deviation), the log's events pinned where they
// happened, and a playhead. Same data as GET /api/v1/vr/device/flight-review, so the headset app and
// this view show the same thing. No cause is named — the facts are laid out for a person to judge.

export interface FlightEvent { t_s: number; kind: string; level: 'warning' | 'notice' | 'info'; text: string; end_s?: number }
export interface FlightReplayDto {
  id: number; drone_id: string; fleet: string; verdict: 'CONFORMED' | 'DEVIATED'; plan_name: string | null; log_name: string | null
  replay: { home: [number, number]; planned: [number, number, number][]; flown: [number, number, number, number][] }
  episodes: { kind: string; start_s: number; duration_s: number; max_m?: number }[]
  timeline: FlightEvent[]
  tolerances: { corridor_m?: number; altitude_m?: number }
  flight_s: number
}

const LEVEL_COLOR = { warning: C.bad, notice: C.warn, info: C.textDim }

/** Centre on the flight's home and fit both the plan and the track onto the table. */
export function flightFrame(f: FlightReplayDto): { center: [number, number]; d: Diorama } {
  const center = f.replay.home
  const pts = [...f.replay.planned.map((p) => toLocal(p[0], p[1], center)), ...f.replay.flown.map((p) => toLocal(p[1], p[2], center))]
  const es = pts.map((p) => p[0]), ns = pts.map((p) => p[1])
  const minE = Math.min(...es), maxE = Math.max(...es), minN = Math.min(...ns), maxN = Math.max(...ns)
  const extent = Math.max(80, 0.6 * Math.max(maxE - minE, maxN - minN))
  return { center, d: new Diorama((minE + maxE) / 2, (minN + maxN) / 2, extent) }
}

/** Index of the last flown sample at or before t. */
export function sampleAt(f: FlightReplayDto, t: number): number {
  const fl = f.replay.flown
  let lo = 0, hi = fl.length - 1
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (fl[mid][0] <= t) lo = mid; else hi = mid - 1 }
  return lo
}

function inEpisode(f: FlightReplayDto, t: number): boolean {
  return f.episodes.some((e) => t >= e.start_s && t <= e.start_s + e.duration_s)
}

export function FlightGeometry({ f, d, center, t }: { f: FlightReplayDto; d: Diorama; center: [number, number]; t: number }) {
  const pt = (lat: number, lon: number, h: number) => { const [e, n] = toLocal(lat, lon, center); return d.point(e, n, Math.max(0, h)) }
  const planned = useMemo(() => f.replay.planned.map((p) => pt(p[0], p[1], p[2])), [f, d])  // eslint-disable-line react-hooks/exhaustive-deps
  const runs = useMemo(() => {
    const out: { bad: boolean; pts: [number, number, number][] }[] = []
    for (const s of f.replay.flown) {
      const bad = inEpisode(f, s[0]), p = pt(s[1], s[2], s[3])
      const last = out[out.length - 1]
      if (!last || last.bad !== bad) out.push({ bad, pts: last ? [last.pts[last.pts.length - 1], p] : [p] })
      else last.pts.push(p)
    }
    return out.filter((r) => r.pts.length > 1)
  }, [f, d])  // eslint-disable-line react-hooks/exhaustive-deps
  const shadow = useMemo(() => f.replay.flown.map((s) => { const [e, n] = toLocal(s[1], s[2], center); return d.point(e, n, 0) }), [f, d, center])
  const pins = useMemo(() => f.timeline.filter((e) => e.level !== 'info' && e.kind !== 'end').slice(0, 12).map((e) => {
    const s = f.replay.flown[sampleAt(f, e.t_s)]
    return { e, top: pt(s[1], s[2], s[3]), base: pt(s[1], s[2], 0) }
  }), [f, d])  // eslint-disable-line react-hooks/exhaustive-deps
  const now = f.replay.flown[sampleAt(f, t)]
  const head = pt(now[1], now[2], now[3])
  const homePt = pt(center[0], center[1], 0)

  return (
    <group>
      {planned.length > 1 && <Line points={planned} color={C.accent} lineWidth={2} dashed dashSize={0.012} gapSize={0.008} />}
      {shadow.length > 1 && <Line points={shadow} color={C.textFaint} lineWidth={1} transparent opacity={0.45} />}
      {runs.map((r, i) => <Line key={i} points={r.pts} color={r.bad ? C.bad : C.ok} lineWidth={r.bad ? 3.5 : 2.5} />)}
      {pins.map(({ e, top, base }, i) => (
        <group key={i}>
          <Line points={[base, top]} color={LEVEL_COLOR[e.level]} lineWidth={1} transparent opacity={0.7} />
          <mesh position={top}><sphereGeometry args={[0.005, 12, 12]} /><meshStandardMaterial color={LEVEL_COLOR[e.level]} emissive={LEVEL_COLOR[e.level]} emissiveIntensity={0.6} /></mesh>
          <Label position={[top[0], top[1] + 0.018 + (i % 3) * 0.012, top[2]]} text={`${clock(e.t_s)} ${e.text}`} color={LEVEL_COLOR[e.level]} size={0.0072} />
        </group>
      ))}
      <mesh position={homePt}><cylinderGeometry args={[0.01, 0.01, 0.002, 24]} /><meshStandardMaterial color={C.accent} /></mesh>
      <Label position={[homePt[0], homePt[1] + 0.014, homePt[2]]} text="HOME" color={C.accent} size={0.0072} font={FONT.mono} />
      <group position={head}>
        <mesh><sphereGeometry args={[0.009, 16, 16]} /><meshStandardMaterial color={C.text} emissive={inEpisode(f, now[0]) ? C.bad : C.ok} emissiveIntensity={0.8} /></mesh>
        <Label position={[0, 0.022, 0]} text={`${clock(now[0])} · ${Math.round(now[3])} m`} color={C.text} size={0.0085} font={FONT.mono} />
      </group>
      <Label position={[-d.tableHalf + 0.02, 0.004, d.tableHalf - 0.03]} anchorX="left" size={0.0068}
        text={`dashed = approved plan · green = flown within tolerance · red = deviation · table ${fmtDistance(2 * d.extentM)} across`} color={C.textDim} />
    </group>
  )
}

export function clock(s: number): string {
  const t = Math.max(0, Math.round(s))
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`
}

const mono = `'JetBrains Mono', ui-monospace, monospace`

/** Desktop overlay: verdict, play controls and the event list (click an event to jump there). */
export function FlightBoard({ f, t, setT, playing, setPlaying }: {
  f: FlightReplayDto; t: number; setT: (t: number) => void; playing: boolean; setPlaying: (p: boolean) => void
}) {
  const end = f.replay.flown[f.replay.flown.length - 1]?.[0] ?? 0
  const deviated = f.verdict === 'DEVIATED'
  return (
    <div style={{
      position: 'absolute', top: 12, left: 12, width: 360, maxHeight: 'calc(100% - 24px)', overflowY: 'auto',
      background: 'rgba(8, 17, 31, 0.9)', border: `1px solid ${C.panelEdge}`, borderRadius: 10, color: C.text,
      fontFamily: `'Space Grotesk', system-ui, sans-serif`, fontSize: 12, zIndex: 40, padding: '12px 14px', display: 'grid', gap: 10,
    }}>
      <div>
        <div style={{ fontWeight: 700, fontSize: 13, letterSpacing: 0.8, color: C.accent }}>FLIGHT REPLAY · {f.drone_id}</div>
        <div style={{ fontSize: 11, color: C.textDim, marginTop: 2 }}>{f.log_name} against {f.plan_name} · fleet {f.fleet}</div>
      </div>
      <div style={{ color: deviated ? C.bad : C.ok, fontWeight: 600 }}>
        {deviated ? `Deviated: ${f.episodes.length} stretch(es) outside ${f.tolerances.corridor_m ?? '?'} m sideways / ${f.tolerances.altitude_m ?? '?'} m height` : 'Flew the plan within tolerance'}
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <button className="btn" onClick={() => { if (t >= end) setT(0); setPlaying(!playing) }}>{playing ? 'Pause' : 'Play ×10'}</button>
        <input type="range" min={0} max={end} step={0.5} value={t} onChange={(e) => { setPlaying(false); setT(Number(e.target.value)) }} style={{ flex: 1 }} aria-label="Time in flight" />
        <span style={{ fontFamily: mono, fontVariantNumeric: 'tabular-nums' }}>{clock(t)}</span>
      </div>
      <div style={{ display: 'grid', gap: 3 }}>
        <div style={{ fontFamily: mono, fontSize: 9.5, letterSpacing: 0.8, color: C.textFaint, fontWeight: 700 }}>FROM THE LOG — NO CAUSE IS NAMED</div>
        {f.timeline.filter((e) => e.kind !== 'end').slice(0, 60).map((e, i) => (
          <button key={i} onClick={() => { setPlaying(false); setT(e.t_s) }}
            style={{ all: 'unset', cursor: 'pointer', display: 'flex', gap: 8, padding: '2px 0', color: LEVEL_COLOR[e.level] }}>
            <span style={{ fontFamily: mono, width: 38, flexShrink: 0, color: C.textDim }}>{clock(e.t_s)}</span><span>{e.text}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
