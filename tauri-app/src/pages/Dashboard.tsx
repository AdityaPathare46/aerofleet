import React, { useEffect, useState, useCallback } from 'react'
import { useAppStore } from '../store/appStore'

interface FleetTwin {
  battery_consumed_wh: number
  distance_km: number
  deliveries_completed: number
  near_misses_resolved: number
  cbf_interventions: number
  fault_events: number
  health_score: number
}

export default function DashboardPage() {
  const { setActivePage, apiConnected, agentRoster, scenarioProgress, apiUrl } = useAppStore()
  const [twin, setTwin] = useState<FleetTwin | null>(null)
  const [fleetSize, setFleetSize] = useState<{ drones: number; depots: number } | null>(null)

  const passRate = scenarioProgress.total > 0
    ? ((scenarioProgress.passed / scenarioProgress.total) * 100).toFixed(1)
    : '0.0'

  // Static roster size — no live per-agent connectivity is tracked; the
  // council never runs synchronously, so there's nothing to poll for
  // "online" status (see docs/PATENT_NOVELTY.md Claim 1).
  const rosterSize = agentRoster.length

  const refresh = useCallback(async () => {
    try {
      const [t, drones, depots] = await Promise.all([
        fetch(`${apiUrl}/api/v1/fleet/twin`).then(r => r.json()),
        fetch(`${apiUrl}/api/v1/fleet/drones`).then(r => r.json()),
        fetch(`${apiUrl}/api/v1/fleet/depots`).then(r => r.json()),
      ])
      setTwin(t)
      setFleetSize({ drones: drones.length, depots: depots.length })
    } catch {
      // API not reachable yet — cards fall back to placeholders below.
    }
  }, [apiUrl])

  useEffect(() => { refresh() }, [refresh])

  return (
    <div style={{ padding: '0', overflow: 'auto', flex: 1 }}>
      <div className="page-header">
        <div>
          <div className="page-title">Ops Center</div>
          <div className="page-subtitle">AeroFleet · 11-agent council, CBF-gated dispatch, live over {fleetSize ? `${fleetSize.depots} depots / ${fleetSize.drones} drones` : 'the fleet'}</div>
        </div>
        <button id="btn-new-mission" className="btn btn--primary" onClick={() => setActivePage('mission')}>
          New Dispatch
        </button>
      </div>

      <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Stat cards */}
        <div className="grid-3" style={{ gridTemplateColumns: '1fr 1fr 1fr 1fr' }}>
          <StatCard
            label="Agent Roster"
            value={String(rosterSize)}
            color="blue"
            sublabel="11-agent council + 5 specialists (async, advisory-only)"
          />
          <StatCard
            label="API Link"
            value={apiConnected ? 'CONNECTED' : 'OFFLINE'}
            color={apiConnected ? 'green' : 'red'}
            sublabel="dispatch backend"
          />
          <StatCard
            label="Scenario Suite"
            value={`${passRate}%`}
            color={parseFloat(passRate) >= 90 ? 'green' : parseFloat(passRate) >= 60 ? 'amber' : 'red'}
            sublabel={`${scenarioProgress.passed}/${scenarioProgress.total || 7} passed`}
          />
          <StatCard
            label="Fleet Health"
            value={twin ? `${(twin.health_score * 100).toFixed(0)}%` : '—'}
            color={!twin ? 'blue' : twin.health_score >= 0.9 ? 'green' : twin.health_score >= 0.6 ? 'amber' : 'red'}
            sublabel={twin ? `${twin.deliveries_completed} deliveries logged` : 'awaiting telemetry'}
          />
        </div>

        {/* Live fleet telemetry */}
        {twin && (
          <div className="card">
            <div className="card__header">
              <span className="card__title">Fleet Digital Twin</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>live</span>
            </div>
            <div className="grid-3" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
              <MiniMetric label="Distance" value={`${twin.distance_km.toFixed(1)} km`} />
              <MiniMetric label="Battery Used" value={`${twin.battery_consumed_wh.toFixed(0)} Wh`} />
              <MiniMetric label="CBF Interventions" value={String(twin.cbf_interventions)} />
              <MiniMetric label="Near-Misses Resolved" value={String(twin.near_misses_resolved)} />
              <MiniMetric label="Fault Events" value={String(twin.fault_events)} />
            </div>
          </div>
        )}

        {/* Quick actions */}
        <div className="card">
          <div className="card__header">
            <span className="card__title">Console Shortcuts</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
            {[
              { label: 'Dispatch Console', desc: 'Configure and launch a new delivery order', page: 'mission' },
              { label: 'Council Room', desc: 'Browse async, post-hoc explanations of past decisions', page: 'council' },
              { label: 'Scenario Lab', desc: 'Run the drone-dispatch regression suite', page: 'scenarios' },
              { label: 'Airspace Map', desc: 'Live drones, depots & geofence over the city', page: 'trajectory' },
              { label: 'Depot Network', desc: 'Browse the micro-depot network', page: 'knowledge' },
            ].map(({ label, desc, page }) => (
              <button
                key={page}
                id={`quick-action-${page}`}
                onClick={() => setActivePage(page)}
                className="shortcut-tile"
              >
                <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '4px' }}>{label}</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Architecture badges */}
        <div className="card">
          <div className="card__header">
            <span className="card__title">Safety &amp; Compliance Stack</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>docs/PATENT_NOVELTY.md</span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {['CBF / ASIF Safety Gate', 'Airspace Pre-Screening', 'ACO Council Convergence', 'ReAct Provenance Trace',
              'Real OSM City Routing', '3D Altitude-Banded Geofence', 'MAD-BAD-SAD Governance', 'DGCA 2021 Compliance'].map(tag => (
              <span key={tag} className="tag-chip">{tag}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({
  label, value, color, sublabel
}: {
  label: string; value: string; color: string; sublabel: string
}) {
  const colorMap: Record<string, string> = {
    green: 'var(--status-green)',
    amber: 'var(--status-amber)',
    red: 'var(--status-red)',
    blue: 'var(--accent)',
  }
  return (
    <div className="card" style={{ borderLeft: `2px solid ${colorMap[color] || 'var(--border)'}` }}>
      <span className="card__title">{label}</span>
      <div style={{ marginTop: '12px' }}>
        <div style={{
          fontSize: '22px',
          fontWeight: '600',
          fontFamily: 'var(--font-mono)',
          color: colorMap[color] || 'var(--text-primary)',
        }}>{value}</div>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>{sublabel}</div>
      </div>
    </div>
  )
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span className="metric__label">{label}</span>
      <span style={{ fontSize: 15, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{value}</span>
    </div>
  )
}
