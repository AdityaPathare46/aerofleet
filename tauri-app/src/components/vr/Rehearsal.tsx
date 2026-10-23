import React, { useMemo } from 'react'
import { Line } from '@react-three/drei'
import { Diorama, fmtDistance, toLocal } from './geo'
import { Label } from './Tag'
import { C, FONT } from './theme'
import { clock } from './Flight'

// Missions rehearsed before anyone flies: every planned mission flown on one clock, as uploaded ("before")
// or as rescheduled by the deconfliction check ("after"), with each loss of separation marked where and
// when it happens. Same trajectories the check used (POST /api/v1/assurance/plans/deconflict, `rehearsal`):
// straight legs at the planned speeds, no wind. It shows the plan, not a prediction of the real flights.

export interface RehearsalTrack { id: string; launch_s: number; points: [number, number, number, number][] }
export interface RehearsalConflict { a: string; b: string; t_s: number; horizontal_m: number; vertical_m: number; duration_s: number; lat: number; lon: number; alt_m: number }
export interface RehearsalSide { tracks: RehearsalTrack[]; conflicts: RehearsalConflict[]; end_s: number }
export interface RehearsalDto { home: [number, number]; separation_m: number; before: RehearsalSide; after: RehearsalSide; note: string }

const PALETTE = ['#4FC3F7', '#FFB74D', '#BA68C8', '#81C784', '#F06292', '#FFD54F', '#4DB6AC', '#9575CD', '#A1887F', '#90A4AE']
export const trackColor = (i: number) => PALETTE[i % PALETTE.length]

export function rehearsalFrame(r: RehearsalDto): Diorama {
  const pts = [...r.before.tracks, ...r.after.tracks].flatMap((t) => t.points.map((p) => toLocal(p[1], p[2], r.home)))
  if (pts.length === 0) return new Diorama(0, 0, 200)
  const es = pts.map((p) => p[0]), ns = pts.map((p) => p[1])
  const minE = Math.min(...es), maxE = Math.max(...es), minN = Math.min(...ns), maxN = Math.max(...ns)
  return new Diorama((minE + maxE) / 2, (minN + maxN) / 2, Math.max(120, 0.6 * Math.max(maxE - minE, maxN - minN)))
}

/** Position at time t, or null while the drone is not airborne. */
function at(track: RehearsalTrack, t: number): [number, number, number] | null {
  const p = track.points
  if (p.length === 0 || t < p[0][0] || t > p[p.length - 1][0]) return null
  let lo = 0, hi = p.length - 1
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (p[mid][0] <= t) lo = mid; else hi = mid - 1 }
  const a = p[lo], b = p[Math.min(lo + 1, p.length - 1)]
  const w = b[0] > a[0] ? (t - a[0]) / (b[0] - a[0]) : 0
  return [a[1] + w * (b[1] - a[1]), a[2] + w * (b[2] - a[2]), a[3] + w * (b[3] - a[3])]
}

export function RehearsalGeometry({ r, side, d, t }: { r: RehearsalDto; side: 'before' | 'after'; d: Diorama; t: number }) {
  const s = r[side]
  const pt = (lat: number, lon: number, h: number) => { const [e, n] = toLocal(lat, lon, r.home); return d.point(e, n, Math.max(0, h)) }
  const paths = useMemo(() => s.tracks.map((tr) => tr.points.map((p) => pt(p[1], p[2], p[3]))), [s, d])  // eslint-disable-line react-hooks/exhaustive-deps
  const homePt = pt(r.home[0], r.home[1], 0)
  return (
    <group>
      {paths.map((ps, i) => ps.length > 1 && <Line key={s.tracks[i].id} points={ps} color={trackColor(i)} lineWidth={1.6} transparent opacity={0.55} />)}
      {s.tracks.map((tr, i) => {
        const now = at(tr, t)
        if (!now) return null
        const p = pt(now[0], now[1], now[2])
        return (
          <group key={tr.id} position={p}>
            <mesh><sphereGeometry args={[0.008, 14, 14]} /><meshStandardMaterial color={trackColor(i)} emissive={trackColor(i)} emissiveIntensity={0.6} /></mesh>
            <Label position={[0, 0.018, 0]} text={`${tr.id} · ${Math.round(now[2])} m`} color={C.text} size={0.0075} font={FONT.mono} />
          </group>
        )
      })}
      {s.conflicts.map((c, i) => {
        const p = pt(c.lat, c.lon, c.alt_m)
        const live = t >= c.t_s - c.duration_s && t <= c.t_s + c.duration_s
        return (
          <group key={i} position={p}>
            <mesh><sphereGeometry args={[live ? 0.02 : 0.012, 18, 18]} /><meshStandardMaterial color={C.bad} transparent opacity={live ? 0.55 : 0.3} emissive={C.bad} emissiveIntensity={live ? 0.9 : 0.3} /></mesh>
            <Label position={[0, 0.03 + (i % 4) * 0.02, 0]} text={`${clock(c.t_s)} ${c.a}–${c.b} ${c.horizontal_m} m apart`} color={C.bad} size={0.0072} font={FONT.mono} />
          </group>
        )
      })}
      <mesh position={homePt}><cylinderGeometry args={[0.01, 0.01, 0.002, 24]} /><meshStandardMaterial color={C.accent} /></mesh>
      <Label position={[-d.tableHalf + 0.02, 0.004, d.tableHalf - 0.03]} anchorX="left" size={0.0068}
        text={`planned missions on one clock · red = closer than ${r.separation_m} m · straight legs, no wind · table ${fmtDistance(2 * d.extentM)} across`} color={C.textDim} />
    </group>
  )
}

const mono = `'JetBrains Mono', ui-monospace, monospace`

/** Desktop overlay: before/after switch, play controls and the list of conflicts (click one to jump there). */
export function RehearsalBoard({ r, side, setSide, t, setT, playing, setPlaying }: {
  r: RehearsalDto; side: 'before' | 'after'; setSide: (s: 'before' | 'after') => void
  t: number; setT: (t: number) => void; playing: boolean; setPlaying: (p: boolean) => void
}) {
  const s = r[side]
  return (
    <div style={{
      position: 'absolute', top: 12, left: 12, width: 360, maxHeight: 'calc(100% - 24px)', overflowY: 'auto',
      background: 'rgba(8, 17, 31, 0.9)', border: `1px solid ${C.panelEdge}`, borderRadius: 10, color: C.text,
      fontFamily: `'Space Grotesk', system-ui, sans-serif`, fontSize: 12, zIndex: 40, padding: '12px 14px', display: 'grid', gap: 10,
    }}>
      <div>
        <div style={{ fontWeight: 700, fontSize: 13, letterSpacing: 0.8, color: C.accent }}>MISSION REHEARSAL · {s.tracks.length} drones</div>
        <div style={{ fontSize: 11, color: C.textDim, marginTop: 2 }}>{r.note}</div>
      </div>
      <div style={{ display: 'flex', gap: 4 }}>
        <button className={`btn ${side === 'before' ? 'btn--primary' : ''}`} onClick={() => { setSide('before'); setT(0) }}>As planned ({r.before.conflicts.length} conflicts)</button>
        <button className={`btn ${side === 'after' ? 'btn--primary' : ''}`} onClick={() => { setSide('after'); setT(0) }}>Rescheduled ({r.after.conflicts.length})</button>
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <button className="btn" onClick={() => { if (t >= s.end_s) setT(0); setPlaying(!playing) }}>{playing ? 'Pause' : 'Play ×10'}</button>
        <input type="range" min={0} max={s.end_s} step={1} value={t} onChange={(e) => { setPlaying(false); setT(Number(e.target.value)) }} style={{ flex: 1 }} aria-label="Mission time" />
        <span style={{ fontFamily: mono, fontVariantNumeric: 'tabular-nums' }}>{clock(t)}</span>
      </div>
      <div style={{ display: 'grid', gap: 3 }}>
        {s.tracks.map((tr, i) => (
          <div key={tr.id} style={{ display: 'flex', gap: 8 }}>
            <span style={{ width: 10, height: 10, borderRadius: 5, background: trackColor(i), marginTop: 3 }} />
            <span>{tr.id}</span><span style={{ color: C.textDim, fontFamily: mono }}>launch {clock(tr.launch_s)}</span>
          </div>))}
      </div>
      <div style={{ display: 'grid', gap: 3 }}>
        <div style={{ fontFamily: mono, fontSize: 9.5, letterSpacing: 0.8, color: C.textFaint, fontWeight: 700 }}>LOSS OF SEPARATION</div>
        {s.conflicts.length === 0 && <span style={{ color: C.ok }}>None: every pair stays at least {r.separation_m} m apart.</span>}
        {s.conflicts.map((c, i) => (
          <button key={i} onClick={() => { setPlaying(false); setT(Math.max(0, c.t_s - 5)) }}
            style={{ all: 'unset', cursor: 'pointer', display: 'flex', gap: 8, padding: '2px 0', color: C.bad }}>
            <span style={{ fontFamily: mono, width: 38, flexShrink: 0, color: C.textDim }}>{clock(c.t_s)}</span>
            <span>{c.a} and {c.b}: {c.horizontal_m} m apart for {c.duration_s} s</span>
          </button>))}
      </div>
    </div>
  )
}
