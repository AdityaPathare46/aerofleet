import React from 'react'
import { useAppStore } from '../store/appStore'

/**
 * RightPanel — Live telemetry + agent roster sidebar.
 * Always visible on the right side of the app shell.
 */
export default function RightPanel() {
  const { telemetry, agentRoster } = useAppStore()

  return (
    <>
      {/* ── Live Telemetry ── */}
      <div className="card" style={{ flexShrink: 0 }}>
        <div className="card__header">
          <span className="card__title">Live Telemetry</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <TelemetryRow
            label="ETA"
            value={telemetry.etaMinutes}
            unit="min"
            max={60}
            color="blue"
          />
          <TelemetryRow
            label="Battery Margin"
            value={telemetry.batteryMarginWh}
            unit="Wh"
            max={500}
            color={telemetry.batteryMarginWh !== null && telemetry.batteryMarginWh < 0 ? 'red' : 'green'}
          />
          <TelemetryRow
            label="Delivery Cost"
            value={telemetry.costUsd}
            unit="USD"
            max={5}
            color="amber"
          />
          <TelemetryRow
            label="Peak Noise"
            value={telemetry.peakNoiseDb}
            unit="dB"
            max={90}
            color={telemetry.peakNoiseDb && telemetry.peakNoiseDb > 65 ? 'red' : 'blue'}
          />
          <TelemetryRow
            label="Link Margin"
            value={telemetry.linkMargin_db}
            unit="dB"
            max={30}
            color={telemetry.linkMargin_db && telemetry.linkMargin_db < 3 ? 'red' : 'green'}
          />
        </div>

        {/* Binary flags */}
        <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
          <FlagBadge label="CBF" pass={telemetry.cbfPass} />
          <FlagBadge label="DGCA" pass={telemetry.dgcaCompliant} />
        </div>
      </div>

      {/* ── Agent Roster ── */}
      <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div className="card__header">
          <span className="card__title">Agent Roster</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            {agentRoster.length} agents
          </span>
        </div>
        <div style={{ overflow: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {agentRoster.map((agent) => (
            <div
              key={agent.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '6px 8px',
                borderRadius: 6,
                background: agent.status === 'thinking' ? 'var(--accent-subtle)' : 'transparent',
                border: `1px solid ${agent.status === 'thinking' ? 'var(--border-active)' : 'transparent'}`,
                transition: 'all 150ms',
              }}
            >
              {/* Status dot */}
              <div style={{
                width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                background: agent.status === 'thinking' ? 'var(--status-amber)' :
                            agent.status === 'done'     ? 'var(--status-green)' :
                            agent.status === 'offline'  ? 'var(--text-muted)' :
                            'var(--bg-elevated)',
                boxShadow: agent.status === 'thinking' ? '0 0 4px var(--status-amber)' : 'none',
              }} />

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {agent.name}
                </div>
                <div style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {agent.model}
                </div>
              </div>

              {agent.lastVerdict && (
                <span className={`verdict-badge verdict-badge--${agent.lastVerdict.toLowerCase()}`}>
                  {agent.lastVerdict}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── Cost Estimate ── */}
      {telemetry.costUsd !== null && (
        <div className="card" style={{ flexShrink: 0 }}>
          <div className="card__title" style={{ marginBottom: 8 }}>Estimated Delivery Cost</div>
          <div className="metric metric--blue">
            <span className="metric__value">${telemetry.costUsd?.toFixed(2)}</span>
            <span className="metric__unit">USD</span>
          </div>
        </div>
      )}
    </>
  )
}

function TelemetryRow({
  label, value, unit, max, color
}: {
  label: string; value: number | null; unit: string; max: number; color: string
}) {
  const pct = value !== null ? Math.min((value / max) * 100, 100) : 0
  return (
    <div className="metric">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <span className="metric__label">{label}</span>
        <span className={`mono text-sm metric--${color}`} style={{ color: `var(--${color === 'blue' ? 'accent' : `status-${color}`})` }}>
          {value !== null ? value.toLocaleString() : '—'} <span className="text-muted" style={{ fontSize: 10 }}>{unit}</span>
        </span>
      </div>
      <div className="gauge-bar">
        <div
          className={`gauge-bar__fill gauge-bar__fill--${color === 'blue' ? '' : color}`}
          style={{ width: `${pct}%`, background: color === 'blue' ? 'var(--accent)' : undefined }}
        />
      </div>
    </div>
  )
}

function FlagBadge({ label, pass }: { label: string; pass: boolean | null }) {
  return (
    <div style={{
      flex: 1,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 4,
      padding: '4px 8px',
      borderRadius: 6,
      background: pass === null ? 'var(--bg-elevated)' : pass ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
      border: `1px solid ${pass === null ? 'var(--border)' : pass ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'}`,
      fontSize: 11,
      fontWeight: 600,
      color: pass === null ? 'var(--text-muted)' : pass ? 'var(--status-green)' : 'var(--status-red)',
      fontFamily: 'var(--font-mono)',
    }}>
      {pass === null ? '?' : pass ? '✓' : '✗'} {label}
    </div>
  )
}
