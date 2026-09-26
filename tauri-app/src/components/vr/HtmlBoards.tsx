import React, { useState } from 'react'
import { claimRows, claimVerdict, constraintRows, fleetKpis, legendNote } from './boardModel'
import { RANGE_OPTIONS_KM, ViewControls } from './Panels'
import { STATUS_COLOR } from './Swarm'
import { C } from './theme'
import type { LiveMarginsDto, VRSceneDto } from './types'

// Desktop counterparts of the in-world boards (Panels.tsx) — same view-model, rendered as
// crisp screen-space HTML over the 3D table.

const mono = `'JetBrains Mono', ui-monospace, monospace`
const ui = `'Space Grotesk', system-ui, sans-serif`

const shell: React.CSSProperties = {
  position: 'absolute', top: 12, left: 12, width: 318, maxHeight: 'calc(100% - 24px)', overflowY: 'auto',
  background: 'rgba(8, 17, 31, 0.9)', border: `1px solid ${C.panelEdge}`, borderRadius: 10,
  color: C.text, fontFamily: ui, fontSize: 12, zIndex: 40, boxShadow: '0 10px 30px rgba(0,0,0,0.45)',
  backdropFilter: 'blur(6px)',
}
const eyebrow: React.CSSProperties = { fontFamily: mono, fontSize: 9.5, letterSpacing: 0.8, color: C.textFaint, fontWeight: 700 }

function Chip({ text, color }: { text: string; color: string }) {
  return (
    <span style={{
      fontFamily: mono, fontSize: 9, fontWeight: 700, letterSpacing: 0.5, color, border: `1px solid ${color}`,
      background: `${color}22`, borderRadius: 4, padding: '0 4px', lineHeight: '15px', display: 'inline-block',
    }}>{text}</span>
  )
}

function Btn({ children, active, onClick, title }: { children: React.ReactNode; active?: boolean; onClick: () => void; title?: string }) {
  return (
    <button onClick={onClick} title={title} style={{
      fontFamily: ui, fontSize: 11, fontWeight: 600, padding: '4px 8px', borderRadius: 6, cursor: 'pointer',
      border: `1px solid ${active ? C.accent : C.panelEdge}`, background: active ? '#1F4A7C' : '#0F2038',
      color: active ? C.text : C.textDim,
    }}>{children}</button>
  )
}

function Header({ title, sub, open, setOpen }: { title: string; sub: string; open: boolean; setOpen: (v: boolean) => void }) {
  return (
    <div style={{ padding: '12px 14px 10px', borderBottom: open ? `1px solid ${C.panelEdge}55` : 'none', display: 'flex', alignItems: 'flex-start', gap: 8 }}>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 700, fontSize: 13, letterSpacing: 0.8, color: C.accent }}>{title}</div>
        <div style={{ fontSize: 11, color: C.textDim, marginTop: 2 }}>{sub}</div>
      </div>
      <button onClick={() => setOpen(!open)} title={open ? 'Collapse' : 'Expand'} style={{
        background: 'none', border: 'none', color: C.textDim, cursor: 'pointer', fontSize: 14, padding: 0,
      }}>{open ? '▾' : '▸'}</button>
    </div>
  )
}

export function LiveBoard({ data, cityName, ageS, vExag, controls }: {
  data: LiveMarginsDto | null; cityName: string; ageS: number | null; vExag: number; controls: ViewControls
}) {
  const [open, setOpen] = useState(true)
  const minSep = data?.constants.min_separation_m ?? 15
  return (
    <div style={shell}>
      <Header open={open} setOpen={setOpen} title="AIRSPACE SUPERVISION"
        sub={`${cityName} · ${data ? 'live CBF margins' : 'waiting for data'}${ageS != null ? ` · ${ageS.toFixed(1)} s ago` : ''}`} />
      {open && (
        <div style={{ padding: '10px 14px 12px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            {fleetKpis(data).map((k) => (
              <div key={k.key} style={{ background: '#0D1C31', border: '1px solid #1A3354', borderRadius: 7, padding: '6px 8px' }}>
                <div style={eyebrow}>{k.key}</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: k.color, lineHeight: 1.2, fontVariantNumeric: 'tabular-nums' }}>{k.value}</div>
                {k.sub && <div style={{ fontSize: 10, color: C.textFaint }}>{k.sub}</div>}
              </div>
            ))}
          </div>

          <div>
            <div style={{ ...eyebrow, marginBottom: 5 }}>FLEET WORST-CASE MARGIN · 11 CBF CONSTRAINTS</div>
            {constraintRows(data).map((r) => (
              <div key={r.name} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '2px 0' }}>
                <span style={{ flex: 1, color: r.live ? C.text : C.textDim }}>{r.label}</span>
                <span style={{ fontFamily: mono, fontSize: 11, color: r.color, fontVariantNumeric: 'tabular-nums' }}>{r.value}</span>
                <span style={{ width: 58, textAlign: 'right' }}><Chip text={r.live ? 'LIVE' : 'ASSUMED'} color={r.live ? C.accent : C.textFaint} /></span>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {([['ok', 'clear'], ['watch', 'watch band'], ['violation', 'CBF violation']] as const).map(([k, t]) => (
              <span key={k} style={{ display: 'flex', alignItems: 'center', gap: 5, color: C.textDim, fontSize: 11 }}>
                <span style={{ width: 9, height: 9, borderRadius: 5, background: STATUS_COLOR[k] }} />{t}
              </span>
            ))}
          </div>
          <div style={{ fontSize: 10.5, color: C.textFaint, lineHeight: 1.5 }}>{legendNote(minSep, vExag)}</div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, alignItems: 'center' }}>
            <span style={{ ...eyebrow, marginRight: 2 }}>RANGE</span>
            {RANGE_OPTIONS_KM.map((km) => (
              <Btn key={km} active={controls.rangeKm === km} onClick={() => controls.setRangeKm(km)}
                title={km < 4 ? 'Zoom in (centres on the selected drone, if any)' : 'Whole operating area'}>{km} km</Btn>
            ))}
            <Btn active={controls.detailAll} onClick={() => controls.setDetailAll(!controls.detailAll)}
              title="Show every drone's full data block, not just ones needing attention">
              {controls.detailAll ? 'Details: all' : 'Details: auto'}
            </Btn>
            <Btn onClick={() => controls.rotate(45)} title="Rotate table">⟲</Btn>
            <Btn onClick={() => controls.rotate(-45)} title="Rotate table">⟳</Btn>
          </div>
        </div>
      )}
    </div>
  )
}

export function ReplayBoard({ scene }: { scene: VRSceneDto }) {
  const [open, setOpen] = useState(true)
  const verdict = claimVerdict(scene)
  return (
    <div style={{ ...shell, width: 380 }}>
      <Header open={open} setOpen={setOpen} title="INCIDENT REPLAY · VERIFY THE AI"
        sub={`${scene.incident_id} · ${scene.trigger_type.replace('_', ' ')} · drone ${scene.drone_id ?? 'n/a'} · ${scene.status}`} />
      {open && (
        <div style={{ padding: '10px 14px 12px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{
            border: `1px solid ${verdict.color}`, background: `${verdict.color}1F`, color: verdict.color,
            borderRadius: 7, padding: '7px 9px', fontWeight: 600, lineHeight: 1.4,
          }}>{verdict.text}</div>

          <div>
            <div style={{ display: 'grid', gridTemplateColumns: '1.25fr 0.95fr 1.1fr auto', gap: '3px 8px', alignItems: 'center' }}>
              {['FACTOR', 'COUNCIL', 'GEOMETRY', 'CHECK'].map((h) => <span key={h} style={eyebrow}>{h}</span>)}
              {claimRows(scene).map((r) => (
                <React.Fragment key={r.factor}>
                  <span style={{ color: r.checkable ? C.text : C.textDim }}>{r.label}</span>
                  <span style={{ fontFamily: mono, fontSize: 10.5, color: C.textDim }}>{r.claim}</span>
                  <span style={{ fontSize: 11, color: r.evidenceHot ? C.bad : C.textFaint }}>{r.evidence}</span>
                  <span title={r.statusNote}><Chip text={r.status} color={r.statusColor} /></span>
                </React.Fragment>
              ))}
            </div>
          </div>

          <div>
            <div style={{ ...eyebrow, marginBottom: 3 }}>AI ROOT-CAUSE CLAIM</div>
            <div style={{ lineHeight: 1.5 }}>{scene.root_cause_summary ?? 'Investigation not complete — no narrative yet.'}</div>
          </div>
          {scene.recommended_action && (
            <div>
              <div style={{ ...eyebrow, marginBottom: 3 }}>RECOMMENDED ACTION</div>
              <div style={{ lineHeight: 1.5, color: C.textDim }}>{scene.recommended_action}</div>
            </div>
          )}
          <div style={{ fontSize: 10.5, color: C.textFaint }}>
            Checks are deterministic (violated CBF constraint → factor map), never AI-generated. Hover a check for what it means.
          </div>
        </div>
      )}
    </div>
  )
}
