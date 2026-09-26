import { useMemo, useState } from 'react'
import { Text } from '@react-three/drei'
import * as THREE from 'three'
import { claimRows, claimVerdict, constraintRows, fleetKpis, legendNote } from './boardModel'
import { STATUS_COLOR } from './Swarm'
import { C, FONT } from './theme'
import type { LiveMarginsDto, VRSceneDto } from './types'

// ── primitives ─────────────────────────────────────────────────────────

function roundedRect(w: number, h: number, r: number): THREE.ShapeGeometry {
  const s = new THREE.Shape()
  const x = -w / 2, y = -h / 2
  s.moveTo(x + r, y)
  s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r)
  s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h)
  s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r)
  s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y)
  return new THREE.ShapeGeometry(s, 6)
}

function Plate({ w, h, color = C.panel, opacity = 0.94, border = C.panelEdge, r = 0.012, z = 0 }: {
  w: number; h: number; color?: string; opacity?: number; border?: string | null; r?: number; z?: number
}) {
  const geo = useMemo(() => roundedRect(w, h, r), [w, h, r])
  const edge = useMemo(() => new THREE.EdgesGeometry(geo), [geo])
  return (
    <group position={[0, 0, z]}>
      <mesh geometry={geo}>
        <meshBasicMaterial color={color} transparent opacity={opacity} side={THREE.DoubleSide} />
      </mesh>
      {border && (
        <lineSegments geometry={edge} position={[0, 0, 0.0005]}>
          <lineBasicMaterial color={border} />
        </lineSegments>
      )}
    </group>
  )
}

function T({ x, y, text, size = 0.012, color = C.text, font = FONT.ui, anchorX = 'left', maxWidth, anchorY = 'top' }: {
  x: number; y: number; text: string; size?: number; color?: string; font?: string
  anchorX?: 'left' | 'center' | 'right'; maxWidth?: number; anchorY?: 'top' | 'middle'
}) {
  return (
    <Text position={[x, y, 0.002]} fontSize={size} color={color} font={font} anchorX={anchorX} anchorY={anchorY}
      maxWidth={maxWidth} lineHeight={1.35}>
      {text}
    </Text>
  )
}

export function Button3D({ x, y, w, label, active = false, onClick }: {
  x: number; y: number; w: number; label: string; active?: boolean; onClick: () => void
}) {
  const [hover, setHover] = useState(false)
  const h = 0.034
  return (
    <group position={[x + w / 2, y - h / 2, 0.003]}
      onClick={(e) => { e.stopPropagation(); onClick() }}
      onPointerOver={(e) => { e.stopPropagation(); setHover(true) }}
      onPointerOut={() => setHover(false)}>
      <Plate w={w} h={h} r={0.008} color={active ? '#1F4A7C' : hover ? '#16304F' : '#0F2038'}
        border={active ? C.accent : C.panelEdge} opacity={1} />
      <T x={0} y={0} text={label} size={0.0115} color={active ? C.text : C.textDim} anchorX="center" anchorY="middle"
        font={FONT.display} />
    </group>
  )
}

function Chip({ x, y, text, color }: { x: number; y: number; text: string; color: string }) {
  const w = text.length * 0.0095 * 0.6 + 0.012
  return (
    <group position={[x + w / 2, y - 0.009, 0.002]}>
      <Plate w={w} h={0.018} r={0.006} color={color} opacity={0.18} border={color} />
      <T x={0} y={0} text={text} size={0.0095} color={color} font={FONT.monoBold} anchorX="center" anchorY="middle" />
    </group>
  )
}

// ── Live: fleet supervision board ──────────────────────────────────────

export interface ViewControls {
  rangeKm: number
  setRangeKm: (km: number) => void
  detailAll: boolean
  setDetailAll: (v: boolean) => void
  rotate: (deg: number) => void
  inXR: boolean
  nudgeHeight: (dy: number) => void
}

export const RANGE_OPTIONS_KM = [1, 2, 4]

export function FleetPanel({ data, cityName, ageS, vExag, controls }: {
  data: LiveMarginsDto | null
  cityName: string
  ageS: number | null
  vExag: number
  controls: ViewControls
}) {
  const W = 1.0, Hh = 0.56
  const left = -W / 2 + 0.03, top = Hh / 2 - 0.026
  const minSep = data?.constants.min_separation_m ?? 15
  const tiles = fleetKpis(data)
  const rows = constraintRows(data)

  return (
    <group>
      <Plate w={W} h={Hh} />
      <T x={left} y={top} text="AIRSPACE SUPERVISION" size={0.021} color={C.accent} font={FONT.display} />
      <T x={left} y={top - 0.03} size={0.0115} color={C.textDim}
        text={`${cityName} · ${data ? 'live CBF margins' : 'waiting for data'}${ageS != null ? ` · updated ${ageS.toFixed(1)} s ago` : ''}`} />

      {tiles.map((t, i) => {
        const tw = 0.225, tx = left + i * (tw + 0.0117)
        return (
          <group key={t.key} position={[tx + tw / 2, top - 0.1, 0.001]}>
            <Plate w={tw} h={0.078} r={0.008} color="#0D1C31" opacity={1} border="#1A3354" />
            <T x={-tw / 2 + 0.012} y={0.03} text={t.key} size={0.0095} color={C.textFaint} font={FONT.monoBold} />
            <T x={-tw / 2 + 0.012} y={0.012} text={t.value} size={0.028} color={t.color} font={FONT.display} />
            {t.sub && <T x={tw / 2 - 0.012} y={-0.022} text={t.sub} size={0.0085} color={C.textFaint} anchorX="right" />}
          </group>
        )
      })}

      <T x={left} y={top - 0.16} text="FLEET WORST-CASE MARGIN PER CBF CONSTRAINT" size={0.0098} color={C.textFaint} font={FONT.monoBold} />
      {rows.map((r, i) => {
        const col = i < 6 ? 0 : 1
        const row = i < 6 ? i : i - 6
        const x = left + col * 0.47
        const y = top - 0.185 - row * 0.03
        return (
          <group key={r.name}>
            <T x={x} y={y} text={r.label} size={0.0112} color={r.live ? C.text : C.textDim} />
            <T x={x + 0.29} y={y} text={r.value} size={0.0112} color={r.color} font={FONT.mono} anchorX="right" />
            <Chip x={x + 0.305} y={y + 0.001} text={r.live ? 'LIVE' : 'ASSUMED'} color={r.live ? C.accent : C.textFaint} />
          </group>
        )
      })}

      {[
        { c: STATUS_COLOR.ok, t: 'all constraints clear' },
        { c: STATUS_COLOR.watch, t: 'within watch band' },
        { c: STATUS_COLOR.violation, t: 'CBF violation' },
      ].map((l, i) => (
        <group key={l.t} position={[left + i * 0.2, top - 0.385, 0.002]}>
          <mesh position={[0.006, -0.006, 0]}>
            <circleGeometry args={[0.006, 16]} />
            <meshBasicMaterial color={l.c} />
          </mesh>
          <T x={0.018} y={0} text={l.t} size={0.0098} color={C.textDim} />
        </group>
      ))}
      <T x={left} y={top - 0.408} size={0.0092} color={C.textFaint} maxWidth={W - 0.06} text={legendNote(minSep, vExag)} />

      <T x={left} y={top - 0.47} text="RANGE" size={0.0095} color={C.textFaint} font={FONT.monoBold} />
      {RANGE_OPTIONS_KM.map((km, i) => (
        <Button3D key={km} x={left + 0.06 + i * 0.075} y={top - 0.458} w={0.068} label={`${km} km`}
          active={controls.rangeKm === km} onClick={() => controls.setRangeKm(km)} />
      ))}
      <Button3D x={left + 0.3} y={top - 0.458} w={0.12} label={controls.detailAll ? 'Details: all' : 'Details: auto'}
        active={controls.detailAll} onClick={() => controls.setDetailAll(!controls.detailAll)} />
      <Button3D x={left + 0.43} y={top - 0.458} w={0.08} label="⟲ 45°" onClick={() => controls.rotate(45)} />
      <Button3D x={left + 0.52} y={top - 0.458} w={0.08} label="⟳ 45°" onClick={() => controls.rotate(-45)} />
      <Button3D x={left + 0.63} y={top - 0.458} w={0.1} label="Table ▲" onClick={() => controls.nudgeHeight(0.05)} />
      <Button3D x={left + 0.74} y={top - 0.458} w={0.1} label="Table ▼" onClick={() => controls.nudgeHeight(-0.05)} />
    </group>
  )
}

// ── Replay: council claims vs. geometry ────────────────────────────────

export function ClaimPanel({ scene, controls }: { scene: VRSceneDto; controls: ViewControls }) {
  const W = 1.0
  const rows = claimRows(scene)
  const Hh = 0.33 + rows.length * 0.031 + 0.2
  const left = -W / 2 + 0.03, top = Hh / 2 - 0.026
  const verdict = claimVerdict(scene)

  return (
    <group>
      <Plate w={W} h={Hh} />
      <T x={left} y={top} text="INCIDENT REPLAY · VERIFY THE AI" size={0.021} color={C.accent} font={FONT.display} />
      <T x={left} y={top - 0.03} size={0.0115} color={C.textDim}
        text={`${scene.incident_id} · ${scene.trigger_type.replace('_', ' ')} · drone ${scene.drone_id ?? 'n/a'} · investigation ${scene.status}`} />

      <group position={[0, top - 0.078, 0.001]}>
        <Plate w={W - 0.06} h={0.044} r={0.008} color={verdict.color} opacity={0.14} border={verdict.color} />
        <T x={0} y={0} text={verdict.text} size={0.0128} color={verdict.color} anchorX="center" anchorY="middle" font={FONT.display} />
      </group>

      <T x={left} y={top - 0.118} text="FACTOR" size={0.0092} color={C.textFaint} font={FONT.monoBold} />
      <T x={left + 0.25} y={top - 0.118} text="COUNCIL CLAIM" size={0.0092} color={C.textFaint} font={FONT.monoBold} />
      <T x={left + 0.46} y={top - 0.118} text="GEOMETRY EVIDENCE" size={0.0092} color={C.textFaint} font={FONT.monoBold} />
      <T x={left + 0.79} y={top - 0.118} text="CHECK" size={0.0092} color={C.textFaint} font={FONT.monoBold} />
      {rows.map((r, i) => {
        const y = top - 0.142 - i * 0.031
        return (
          <group key={r.factor}>
            <T x={left} y={y} text={r.label} size={0.0115} color={r.checkable ? C.text : C.textDim} />
            <T x={left + 0.25} y={y} text={r.claim} size={0.0112} color={C.textDim} font={FONT.mono} />
            <T x={left + 0.46} y={y} text={r.evidence} size={0.0108} color={r.evidenceHot ? C.bad : C.textFaint} maxWidth={0.32} />
            <Chip x={left + 0.79} y={y + 0.002} text={r.status} color={r.statusColor} />
          </group>
        )
      })}

      {(() => {
        const y0 = top - 0.16 - rows.length * 0.031
        return (
          <>
            <T x={left} y={y0} text="AI ROOT-CAUSE CLAIM" size={0.0092} color={C.textFaint} font={FONT.monoBold} />
            <T x={left} y={y0 - 0.018} size={0.0112} color={C.text} maxWidth={W - 0.06}
              text={scene.root_cause_summary ?? 'Investigation not complete — no narrative yet.'} />
            {scene.recommended_action && (
              <>
                <T x={left} y={y0 - 0.085} text="RECOMMENDED ACTION" size={0.0092} color={C.textFaint} font={FONT.monoBold} />
                <T x={left} y={y0 - 0.103} size={0.0112} color={C.textDim} maxWidth={W - 0.06} text={scene.recommended_action} />
              </>
            )}
            <Button3D x={left} y={-Hh / 2 + 0.05} w={0.08} label="⟲ 45°" onClick={() => controls.rotate(45)} />
            <Button3D x={left + 0.09} y={-Hh / 2 + 0.05} w={0.08} label="⟳ 45°" onClick={() => controls.rotate(-45)} />
            <Button3D x={left + 0.18} y={-Hh / 2 + 0.05} w={0.1} label="Table ▲" onClick={() => controls.nudgeHeight(0.05)} />
            <Button3D x={left + 0.29} y={-Hh / 2 + 0.05} w={0.1} label="Table ▼" onClick={() => controls.nudgeHeight(-0.05)} />
            <T x={W / 2 - 0.03} y={-Hh / 2 + 0.042} size={0.0088} color={C.textFaint} anchorX="right"
              text="Checks are deterministic (CBF margins → factor map), never AI-generated." />
          </>
        )
      })()}
    </group>
  )
}
