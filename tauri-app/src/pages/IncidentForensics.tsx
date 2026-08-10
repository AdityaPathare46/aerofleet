import React, { useCallback, useEffect, useState } from 'react'
import { useAppStore } from '../store/appStore'

interface ContributingFactor {
  factor: string
  contributed: 'CONTRIBUTED' | 'NOT_CONTRIBUTED' | 'UNCERTAIN'
  confidence?: number
  evidence?: string
}

interface TranscriptEntry {
  phase: number
  agent_id: string
  name: string
  model: string
  text: string
}

interface IncidentSummary {
  id: number
  incident_id: string
  city: string
  order_id: string | null
  trigger_type: string
  status: string
  root_cause_summary: string | null
  created_at: string
}

interface IncidentDetail extends IncidentSummary {
  trigger_detail: Record<string, unknown>
  frozen_context: Record<string, unknown>
  contributing_factors: ContributingFactor[] | null
  systemic_factor_note: string | null
  recommended_action: string | null
  recommended_policy_change: Record<string, number> | null
  regulatory_reportable: boolean | null
  regulatory_citation: string | null
  investigation_transcript: TranscriptEntry[] | null
  promoted_policy_proposal_id: string | null
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('aerofleet_token') || ''
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const CONTRIBUTION_TONE: Record<string, string> = {
  CONTRIBUTED: 'red',
  NOT_CONTRIBUTED: 'green',
  UNCERTAIN: 'yellow',
}

const STATUS_TONE: Record<string, string> = {
  PENDING: 'yellow',
  INVESTIGATING: 'yellow',
  READY: 'green',
  FAILED: 'red',
}

export default function IncidentForensicsPage() {
  const { apiUrl, setActivePage } = useAppStore()
  const [incidents, setIncidents] = useState<IncidentSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<IncidentDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [promoting, setPromoting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadIncidents = useCallback(() => {
    fetch(`${apiUrl}/api/v1/incidents/`, { headers: authHeaders() })
      .then(r => r.json())
      .then((data: IncidentSummary[]) => setIncidents(Array.isArray(data) ? data : []))
      .catch(() => {})
  }, [apiUrl])

  useEffect(() => { loadIncidents() }, [loadIncidents])

  const loadDetail = useCallback((incidentId: string) => {
    setLoading(true)
    fetch(`${apiUrl}/api/v1/incidents/${incidentId}`, { headers: authHeaders() })
      .then(r => r.json())
      .then((data: IncidentDetail) => setDetail(data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [apiUrl])

  useEffect(() => {
    if (selectedId) loadDetail(selectedId)
  }, [selectedId, loadDetail])

  // Poll while anything is mid-investigation — auto-triggered incidents
  // need this even more than the council explanation viewer does, since
  // nobody clicked a button to start them.
  useEffect(() => {
    const anyPending = incidents.some(i => i.status === 'PENDING' || i.status === 'INVESTIGATING')
      || (detail && (detail.status === 'PENDING' || detail.status === 'INVESTIGATING'))
    if (!anyPending) return
    const id = setInterval(() => {
      loadIncidents()
      if (selectedId) loadDetail(selectedId)
    }, 3000)
    return () => clearInterval(id)
  }, [incidents, detail, selectedId, loadIncidents, loadDetail])

  async function handlePromote() {
    if (!detail) return
    setPromoting(true)
    setError(null)
    try {
      const res = await fetch(`${apiUrl}/api/v1/incidents/${detail.incident_id}/promote-to-policy-proposal`, {
        method: 'POST', headers: authHeaders(),
      })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText} — operator permissions required`)
      const updated: IncidentDetail = await res.json()
      setDetail(updated)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setPromoting(false)
    }
  }

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* ── Incident list ── */}
      <div style={{ width: 320, flexShrink: 0, borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div className="page-header" style={{ flexShrink: 0, padding: '20px 16px' }}>
          <div>
            <div className="page-title" style={{ fontSize: 16 }}>Incident Forensics</div>
            <div className="page-subtitle" style={{ fontSize: 11 }}>
              Auto-triggered multi-agent root-cause investigation
            </div>
          </div>
        </div>
        <div style={{ overflow: 'auto', flex: 1, padding: '8px' }}>
          {incidents.length === 0 ? (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
              No incidents yet. This is a good thing — nothing here means the CBF gate hasn't had
              to reject a dispatch. This page only ever fills itself in; there's no "create" button.
            </div>
          ) : incidents.map(inc => (
            <button
              key={inc.incident_id}
              onClick={() => setSelectedId(inc.incident_id)}
              style={{
                display: 'block', width: '100%', textAlign: 'left', padding: '10px 12px', marginBottom: 4,
                background: selectedId === inc.incident_id ? 'var(--accent-subtle)' : 'transparent',
                border: `1px solid ${selectedId === inc.incident_id ? 'var(--border-active)' : 'transparent'}`,
                borderRadius: 'var(--radius-md)', cursor: 'pointer',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span style={{ fontSize: 12, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                  {inc.incident_id}
                </span>
                <span className={`verdict-badge verdict-badge--${STATUS_TONE[inc.status] || 'yellow'}`} style={{ fontSize: 9 }}>
                  {inc.status}
                </span>
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                {inc.trigger_type} {inc.order_id ? `· ${inc.order_id}` : ''}
              </div>
              {inc.root_cause_summary && (
                <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4 }}>
                  {inc.root_cause_summary.slice(0, 80)}
                </div>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* ── Detail ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {!selectedId ? (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, color: 'var(--text-muted)', padding: 48, textAlign: 'center' }}>
            <div className="section-marker" style={{ width: 3, height: 40, opacity: 0.5 }} />
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-secondary)' }}>Pick an incident to investigate</div>
            <div style={{ fontSize: 13, maxWidth: 420 }}>
              Every incident here was auto-triggered by a real CBF rejection — nobody asked for it.
              Each of 7 domain-expert agents independently assessed whether their domain
              contributed, citing the actual frozen numbers from that moment, before a synthesis
              agent combined their findings into one report.
            </div>
            <button className="btn btn--primary" onClick={() => setActivePage('mission')}>Go to Dispatch Console</button>
          </div>
        ) : loading && !detail ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div className="spinner" style={{ width: 20, height: 20 }} />
          </div>
        ) : detail ? (
          <>
            <div className="page-header" style={{ flexShrink: 0 }}>
              <div>
                <div className="page-title">{detail.incident_id}</div>
                <div className="page-subtitle">
                  {detail.trigger_type} {detail.order_id ? `on ${detail.order_id}` : ''} · {detail.city}
                </div>
              </div>
              <span className={`verdict-badge verdict-badge--${STATUS_TONE[detail.status] || 'yellow'}`}>
                {detail.status}
              </span>
            </div>

            <div style={{ flex: 1, overflow: 'auto', padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
              {error && (
                <div className="card" style={{ borderColor: 'var(--status-red)' }}>
                  <span style={{ color: 'var(--status-red)' }}>⚠ {error}</span>
                </div>
              )}

              {(detail.status === 'PENDING' || detail.status === 'INVESTIGATING') && (
                <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div className="spinner" style={{ width: 16, height: 16 }} />
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                    7 domain agents investigating in the background — this never blocked the
                    dispatch decision, which was already final. Checking again every few seconds.
                  </span>
                </div>
              )}

              {detail.status === 'READY' && (
                <div className="card">
                  <div className="card__header"><span className="card__title">Root Cause</span></div>
                  <p style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6 }}>{detail.root_cause_summary}</p>

                  {detail.systemic_factor_note && (
                    <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 8 }}>
                      <strong>Systemic factor:</strong> {detail.systemic_factor_note}
                    </p>
                  )}
                  {detail.recommended_action && (
                    <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 8 }}>
                      <strong>Recommended action:</strong> {detail.recommended_action}
                    </p>
                  )}

                  {detail.recommended_policy_change && (
                    <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                        Proposed: <code>{JSON.stringify(detail.recommended_policy_change)}</code> — never applied
                        automatically; promoting sends it to the same operator-approval queue as
                        every other policy change.
                      </div>
                      {detail.promoted_policy_proposal_id ? (
                        <button className="btn btn--ghost" onClick={() => setActivePage('policy')}>
                          View in Fleet Policy ({detail.promoted_policy_proposal_id})
                        </button>
                      ) : (
                        <button className="btn btn--primary" onClick={handlePromote} disabled={promoting}>
                          {promoting ? <><div className="spinner" style={{ width: 12, height: 12 }} /> Promoting...</> : 'Promote to Policy Proposal'}
                        </button>
                      )}
                    </div>
                  )}

                  {detail.regulatory_citation && (
                    <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)', fontSize: 11, color: 'var(--text-muted)' }}>
                      <strong>Regulatory:</strong> {detail.regulatory_reportable ? 'Reportable' : 'Not reportable'} — {detail.regulatory_citation}
                    </div>
                  )}
                </div>
              )}

              {detail.contributing_factors && detail.contributing_factors.length > 0 && (
                <div className="card">
                  <div className="card__header"><span className="card__title">Contributing-Factor Assessments (Tier 2)</span></div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {detail.contributing_factors.map((f, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '8px 0', borderBottom: i < detail.contributing_factors!.length - 1 ? '1px solid var(--border)' : 'none' }}>
                        <span className={`verdict-badge verdict-badge--${CONTRIBUTION_TONE[f.contributed] || 'yellow'}`} style={{ flexShrink: 0 }}>
                          {f.contributed}
                        </span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                            {f.factor} {f.confidence != null && <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>({(f.confidence * 100).toFixed(0)}% confidence)</span>}
                          </div>
                          {f.evidence && <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{f.evidence}</div>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {detail.investigation_transcript && detail.investigation_transcript.length > 0 && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Full Transcript
                  </div>
                  {detail.investigation_transcript.map((msg, i) => (
                    <div key={i} className="agent-msg" style={{ marginBottom: 8 }}>
                      <div className="agent-msg__header">
                        <span className="agent-msg__name">{msg.name}</span>
                        <span className="agent-msg__model">{msg.model}</span>
                      </div>
                      <div className="agent-msg__text">{msg.text}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
