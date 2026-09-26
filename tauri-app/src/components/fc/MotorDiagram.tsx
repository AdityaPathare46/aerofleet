import React from 'react'

// Mirrors aerofleet/hardware/motor_layouts.py (MotorLayout.to_dict()),
// which is transcribed from ArduPilot's AP_MotorsMatrix.cpp (Copter-4.5).
export interface MotorPosition {
  motor_number: number
  angle_deg: number        // from the nose, + clockwise
  direction: 'CW' | 'CCW'  // propeller rotation seen from above
  test_order: number
  letter: string
  position: string
}

export interface MotorLayout {
  key: string
  name: string
  frame_class: number
  frame_type: number
  motor_count: number
  motors: MotorPosition[]
  source: string
  docs: string
}

// ArduPilot's own motor diagrams colour clockwise props green and
// counter-clockwise props blue — kept here so the picture matches theirs.
const CW_COLOR = '#16A34A'
const CCW_COLOR = '#2563EB'

interface Props {
  layout: MotorLayout
  active?: string | null
  results?: Record<string, 'correct' | 'incorrect' | 'pending' | undefined>
  size?: number
}

export default function MotorDiagram({ layout, active, results = {}, size = 260 }: Props) {
  const c = size / 2
  const armR = size * 0.34
  const motorR = size * 0.1

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={`${layout.name} motor order and spin direction, viewed from above`}
    >
      {/* Nose marker */}
      <polygon
        points={`${c},${size * 0.02} ${c - 8},${size * 0.1} ${c + 8},${size * 0.1}`}
        fill="var(--accent)"
      />
      <text x={c} y={size * 0.14} textAnchor="middle" fontSize="9" fill="var(--text-secondary)"
        fontFamily="var(--font-mono)" letterSpacing="0.1em">FRONT</text>

      {layout.motors.map(m => {
        const rad = (m.angle_deg * Math.PI) / 180
        const x = c + Math.sin(rad) * armR
        const y = c - Math.cos(rad) * armR
        return <line key={`arm-${m.letter}`} x1={c} y1={c} x2={x} y2={y} stroke="var(--border-hover)" strokeWidth={6} strokeLinecap="round" />
      })}
      <rect x={c - 18} y={c - 18} width={36} height={36} rx={6} fill="var(--bg-elevated)" stroke="var(--border-hover)" />

      {layout.motors.map(m => {
        const rad = (m.angle_deg * Math.PI) / 180
        const x = c + Math.sin(rad) * armR
        const y = c - Math.cos(rad) * armR
        const color = m.direction === 'CW' ? CW_COLOR : CCW_COLOR
        const state = results[m.letter]
        const isActive = active === m.letter
        const ring = state === 'correct' ? 'var(--status-green)'
          : state === 'incorrect' ? 'var(--status-red)'
          : isActive ? 'var(--accent)' : color
        return (
          <g key={m.letter}>
            <circle cx={x} cy={y} r={motorR + 5} fill="none" stroke={ring}
              strokeWidth={isActive || state ? 3 : 1.5} strokeDasharray={isActive && !state ? '4 3' : undefined} />
            <circle cx={x} cy={y} r={motorR} fill={color} fillOpacity={isActive ? 0.28 : 0.14} stroke={color} strokeWidth={1.5} />
            <text x={x} y={y + 1} textAnchor="middle" dominantBaseline="middle" fontSize={motorR * 0.95}
              fontWeight={700} fill="var(--text-primary)" fontFamily="var(--font-mono)">{m.letter}</text>
            <text x={x} y={y + motorR + 17} textAnchor="middle" fontSize="10" fill={color} fontFamily="var(--font-mono)">
              {m.direction === 'CW' ? '↻' : '↺'} {m.direction} · M{m.motor_number}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

export function MotorLegend() {
  return (
    <div style={{ display: 'flex', gap: '14px', fontSize: '11px', color: 'var(--text-secondary)', flexWrap: 'wrap' }}>
      <span><span style={{ color: CW_COLOR }}>● ↻ CW</span> clockwise prop</span>
      <span><span style={{ color: CCW_COLOR }}>● ↺ CCW</span> counter-clockwise prop</span>
      <span>Letter = test order (A, B, C… clockwise from the nose) · M = motor/output number · viewed from above</span>
    </div>
  )
}
