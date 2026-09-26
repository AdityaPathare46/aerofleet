import { useMemo } from 'react'
import { Billboard, Html, Text } from '@react-three/drei'
import * as THREE from 'three'
import { C, FONT, MONO_ADVANCE } from './theme'
import { useInXR } from './uiMode'

export interface TagRow {
  label?: string          // dim, fixed-width left column (e.g. "ALT")
  value: string           // bright value text
  color?: string
  bar?: { frac: number; color: string; mark?: number }  // 0..1 fill, optional limit tick at `mark` (0..1)
}

// Labels are always drawn on top (like an ATC data block) — a swarm display that lets a
// zone volume or another drone hide a callsign is unreadable.
function overlayMaterial() {
  return new THREE.MeshBasicMaterial({ depthTest: false, depthWrite: false, transparent: true, toneMapped: false })
}

const LABEL_COL = 5
const BAR_CHARS = 9

interface TagProps {
  position: [number, number, number]
  title: string
  titleColor?: string
  rows?: TagRow[]
  size?: number
  accent?: string
  anchor?: 'bottom' | 'center'
  onClick?: () => void
}

export function Tag(props: TagProps) {
  return useInXR() ? <WorldTag {...props} /> : <HtmlTag {...props} />
}

// ── desktop: screen-space HTML data block ─────────────────────────────

const htmlFont = `'JetBrains Mono', ui-monospace, monospace`

function HtmlTag({ position, title, titleColor = C.text, rows = [], accent, anchor = 'bottom', onClick }: TagProps) {
  const compact = rows.length === 0
  return (
    <Html position={position} zIndexRange={[compact ? 10 : 30, 0]} style={{ pointerEvents: 'none' }}>
      <div
        onClick={onClick}
        style={{
          transform: anchor === 'bottom' ? 'translate(-50%, calc(-100% - 4px))' : 'translate(-50%, -50%)',
          pointerEvents: onClick ? 'auto' : 'none', cursor: onClick ? 'pointer' : 'default',
          background: 'rgba(8, 17, 31, 0.92)', border: `1px solid ${C.panelEdge}`,
          borderLeft: `3px solid ${accent ?? C.panelEdge}`, borderRadius: 5,
          padding: compact ? '1px 6px' : '6px 8px 5px', fontFamily: htmlFont, fontSize: compact ? 10 : 11,
          lineHeight: 1.45, color: C.text, whiteSpace: 'nowrap', boxShadow: '0 4px 14px rgba(0,0,0,0.45)',
          userSelect: 'none',
        }}
      >
        <div style={{ color: titleColor, fontWeight: 700, letterSpacing: 0.2 }}>{title}</div>
        {rows.map((r, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {r.label && <span style={{ color: C.textFaint, width: 30, fontSize: 9.5, letterSpacing: 0.6 }}>{r.label}</span>}
            <span style={{ color: r.color ?? C.text, minWidth: r.bar ? 118 : undefined }}>{r.value}</span>
            {r.bar && <HtmlBar {...r.bar} />}
          </div>
        ))}
      </div>
    </Html>
  )
}

function HtmlBar({ frac, color, mark }: { frac: number; color: string; mark?: number }) {
  const f = Math.max(0, Math.min(1, frac))
  return (
    <span style={{ position: 'relative', display: 'inline-block', width: 64, height: 6, background: C.bezel, borderRadius: 2 }}>
      <span style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${f * 100}%`, background: color, borderRadius: 2 }} />
      {mark !== undefined && (
        <span style={{
          position: 'absolute', left: `calc(${Math.max(0, Math.min(1, mark)) * 100}% - 1px)`, top: -2, width: 2, height: 10,
          background: C.text,
        }} />
      )}
    </span>
  )
}

// ── headset: in-world billboarded plate ───────────────────────────────

function WorldTag({
  position, title, titleColor = C.text, rows = [], size = 0.0085, accent, anchor = 'bottom', onClick,
}: TagProps) {
  const textMat = useMemo(overlayMaterial, [])
  const plateMat = useMemo(() => new THREE.MeshBasicMaterial({
    color: C.panel, transparent: true, opacity: 0.9, depthTest: false, depthWrite: false,
  }), [])

  const lineH = size * 1.45
  const pad = size * 0.8
  const hasBars = rows.some((r) => r.bar)
  const rowChars = rows.map((r) => (r.label ? LABEL_COL + 1 : 0) + r.value.length)
  const textChars = Math.max(title.length, ...rowChars, 1)
  const barW = hasBars ? BAR_CHARS * size * MONO_ADVANCE : 0
  const width = textChars * size * MONO_ADVANCE + (hasBars ? barW + size : 0) + pad * 2
  const height = lineH * (1 + rows.length) + pad * 1.4
  const offsetY = anchor === 'bottom' ? height / 2 : 0
  const left = -width / 2 + pad
  const top = height / 2 - pad * 0.7

  return (
    <Billboard position={position} renderOrder={20}>
      <group position={[0, offsetY, 0]} onClick={onClick}>
        <mesh material={plateMat} renderOrder={20}>
          <planeGeometry args={[width, height]} />
        </mesh>
        {accent && (
          <mesh position={[-width / 2 + size * 0.18, 0, 0.0001]} renderOrder={21}>
            <planeGeometry args={[size * 0.36, height]} />
            <meshBasicMaterial color={accent} depthTest={false} depthWrite={false} />
          </mesh>
        )}
        <Text
          font={FONT.monoBold} fontSize={size} color={titleColor} anchorX="left" anchorY="top"
          position={[left, top, 0.0002]} material={textMat} renderOrder={22}
        >
          {title}
        </Text>
        {rows.map((r, i) => {
          const y = top - lineH * (i + 1)
          const valueX = left + (r.label ? (LABEL_COL + 1) * size * MONO_ADVANCE : 0)
          const barX = left + textChars * size * MONO_ADVANCE + size
          return (
            <group key={i}>
              {r.label && (
                <Text font={FONT.mono} fontSize={size * 0.86} color={C.textFaint} anchorX="left" anchorY="top"
                  position={[left, y - size * 0.06, 0.0002]} material={textMat} renderOrder={22}>
                  {r.label}
                </Text>
              )}
              <Text font={FONT.mono} fontSize={size} color={r.color ?? C.text} anchorX="left" anchorY="top"
                position={[valueX, y, 0.0002]} material={textMat} renderOrder={22}>
                {r.value}
              </Text>
              {r.bar && <MiniBar x={barX} y={y - size * 0.5} width={barW} height={size * 0.62} {...r.bar} />}
            </group>
          )
        })}
      </group>
    </Billboard>
  )
}

function MiniBar({ x, y, width, height, frac, color, mark }: {
  x: number; y: number; width: number; height: number; frac: number; color: string; mark?: number
}) {
  const f = Math.max(0, Math.min(1, frac))
  return (
    <group position={[x, y, 0.0003]}>
      <mesh position={[width / 2, 0, 0]} renderOrder={21}>
        <planeGeometry args={[width, height]} />
        <meshBasicMaterial color={C.bezel} depthTest={false} depthWrite={false} />
      </mesh>
      {f > 0 && (
        <mesh position={[(width * f) / 2, 0, 0.0001]} renderOrder={22}>
          <planeGeometry args={[width * f, height]} />
          <meshBasicMaterial color={color} depthTest={false} depthWrite={false} />
        </mesh>
      )}
      {mark !== undefined && (
        <mesh position={[width * Math.max(0, Math.min(1, mark)), 0, 0.0002]} renderOrder={23}>
          <planeGeometry args={[height * 0.18, height * 1.6]} />
          <meshBasicMaterial color={C.text} depthTest={false} depthWrite={false} />
        </mesh>
      )}
    </group>
  )
}

interface LabelProps {
  position: [number, number, number]
  text: string
  color?: string
  size?: number
  font?: string
  anchorX?: 'left' | 'center' | 'right'
  billboard?: boolean
  rotation?: [number, number, number]
  weight?: number
}

/** Single-line label (zone names, ceiling names, axis ticks) — in-world in a headset,
 * screen-space HTML on desktop. */
export function Label(props: LabelProps) {
  return useInXR() ? <WorldLabel {...props} /> : <HtmlLabel {...props} />
}

function HtmlLabel({ position, text, color = C.textDim, size = 0.009, font, anchorX = 'center', weight }: LabelProps) {
  const isMono = font === FONT.mono || font === FONT.monoBold
  const isDisplay = font === FONT.display
  const tx = anchorX === 'center' ? '-50%' : anchorX === 'right' ? '-100%' : '0%'
  return (
    <Html position={position} zIndexRange={[5, 0]} style={{ pointerEvents: 'none' }}>
      <div style={{
        transform: `translate(${tx}, -50%)`, whiteSpace: 'nowrap', color,
        fontFamily: isMono ? htmlFont : `'Space Grotesk', system-ui, sans-serif`,
        fontWeight: weight ?? (isDisplay ? 600 : 500), fontSize: Math.round(9 + (size - 0.0068) * 900),
        letterSpacing: isDisplay ? 0.4 : 0.1,
        textShadow: `0 0 3px ${C.void}, 0 0 6px ${C.void}, 0 1px 2px ${C.void}`, userSelect: 'none',
      }}>
        {text}
      </div>
    </Html>
  )
}

function WorldLabel({
  position, text, color = C.textDim, size = 0.009, font = FONT.ui, anchorX = 'center', billboard = true, rotation,
}: LabelProps) {
  const mat = useMemo(overlayMaterial, [])
  const node = (
    <Text font={font} fontSize={size * 1.2} color={color} anchorX={anchorX} anchorY="middle" material={mat}
      renderOrder={18} outlineWidth={size * 0.14} outlineColor={C.void} rotation={billboard ? undefined : rotation}
      position={billboard ? undefined : position}>
      {text}
    </Text>
  )
  return billboard ? <Billboard position={position}>{node}</Billboard> : node
}
