import React, { useEffect, useState, useCallback } from 'react'
import { useAppStore } from '../store/appStore'

interface Depot {
  depot_id: string
  name: string
  node: number | null
  launch_pad_slots: number
  battery_swap_slots: number
  queued_drones: string[]
}

interface Drone {
  drone_id: string
  home_depot_id: string | null
  state: string
  soc: number
}

export default function KnowledgeBasePage() {
  const { apiUrl } = useAppStore()
  const [depots, setDepots] = useState<Depot[]>([])
  const [drones, setDrones] = useState<Drone[]>([])
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Depot | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const [d, dr] = await Promise.all([
        fetch(`${apiUrl}/api/v1/fleet/depots`).then(r => r.json()),
        fetch(`${apiUrl}/api/v1/fleet/drones`).then(r => r.json()),
      ])
      setDepots(d)
      setDrones(dr)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [apiUrl])

  useEffect(() => { refresh() }, [refresh])

  const filtered = depots.filter(d =>
    !search ||
    d.name.toLowerCase().includes(search.toLowerCase()) ||
    d.depot_id.toLowerCase().includes(search.toLowerCase())
  )

  const dronesFor = (depotId: string) => drones.filter(d => d.home_depot_id === depotId)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div className="page-header" style={{ flexShrink: 0 }}>
        <div>
          <div className="page-title">Depot Network</div>
          <div className="page-subtitle">Micro-depot network · Launch pads · Battery-swap stations</div>
        </div>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          {depots.length} depots · {drones.length} drones
        </div>
      </div>

      {/* Filters */}
      <div style={{
        padding: '12px 24px', background: 'var(--bg-deep)', borderBottom: '1px solid var(--border)',
        display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap', flexShrink: 0,
      }}>
        <input
          id="knowledge-search"
          className="form-input"
          placeholder="Search depots..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ width: '240px' }}
        />
        <button id="btn-refresh-depots" className="btn btn--ghost" onClick={refresh}>↻ Refresh</button>
        {error && <span style={{ color: 'var(--status-red)', fontSize: 12 }}>⚠ {error} — is the API running at {apiUrl}?</span>}
      </div>

      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: selected ? '1fr 380px' : '1fr', overflow: 'hidden' }}>
        {/* Depot list */}
        <div style={{ overflow: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Depot</th>
                <th>Graph Node</th>
                <th>Launch Pads</th>
                <th>Swap Slots</th>
                <th>Drones Assigned</th>
                <th>Queue</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(d => (
                <tr
                  key={d.depot_id}
                  id={`depot-row-${d.depot_id}`}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setSelected(d === selected ? null : d)}
                >
                  <td style={{ color: 'var(--accent)' }}>{d.depot_id}</td>
                  <td style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{d.name}</td>
                  <td>{d.node ?? '—'}</td>
                  <td>{d.launch_pad_slots}</td>
                  <td>{d.battery_swap_slots}</td>
                  <td>{dronesFor(d.depot_id).length}</td>
                  <td>
                    <span className={`verdict-badge verdict-badge--${d.queued_drones.length > 0 ? 'yellow' : 'green'}`}>
                      {d.queued_drones.length}
                    </span>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 20 }}>No depots loaded</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Detail panel */}
        {selected && (
          <div style={{ borderLeft: '1px solid var(--border)', padding: '20px', overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>{selected.name}</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{selected.depot_id}</div>
              </div>
              <button id="btn-close-detail" className="btn btn--ghost" onClick={() => setSelected(null)}>✕</button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              {[
                ['Graph Node', String(selected.node ?? '—')],
                ['Launch Pads', String(selected.launch_pad_slots)],
                ['Swap Slots', String(selected.battery_swap_slots)],
                ['Queued', String(selected.queued_drones.length)],
              ].map(([label, value]) => (
                <div key={label} className="metric">
                  <span className="metric__label">{label}</span>
                  <span style={{ fontSize: '14px', fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{value}</span>
                </div>
              ))}
            </div>

            <div>
              <div className="metric__label" style={{ marginBottom: '8px' }}>Assigned Drones</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {dronesFor(selected.depot_id).map(d => (
                  <div key={d.drone_id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontFamily: 'var(--font-mono)' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>{d.drone_id}</span>
                    <span style={{ color: 'var(--text-muted)' }}>{d.state} · {(d.soc * 100).toFixed(0)}%</span>
                  </div>
                ))}
                {dronesFor(selected.depot_id).length === 0 && (
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>No drones assigned</span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
