import React, { useCallback, useEffect, useState } from 'react'
import { useAppStore, AgentVerdict, ExplanationStatus } from '../store/appStore'

interface TranscriptEntry {
  role?: string
  name?: string
  text?: string
  verdict?: AgentVerdict
  color?: string
  model?: string
  phase?: number
  round?: number
}

interface OrderSummary {
  order_id: string
  status: string
  council_verdict: string | null
  council_explanation_status: ExplanationStatus
  priority: string
  payload_kg: number
  created_at: string
}

interface OrderDetail extends OrderSummary {
  council_transcript: TranscriptEntry[] | null
}

const ROUND_COLORS = ['var(--accent)', 'var(--info)', 'var(--status-amber)', 'var(--status-green)', 'var(--text-secondary)']

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('aerofleet_token') || ''
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export default function CouncilViewerPage() {
  const { apiUrl, setActivePage } = useAppStore()
  const [orders, setOrders] = useState<OrderSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<OrderDetail | null>(null)
  const [loading, setLoading] = useState(false)

  const loadOrders = useCallback(() => {
    fetch(`${apiUrl}/api/v1/orders/?limit=50`, { headers: authHeaders() })
      .then(r => r.json())
      .then((data: OrderSummary[]) => setOrders(Array.isArray(data) ? data : []))
      .catch(() => {})
  }, [apiUrl])

  useEffect(() => { loadOrders() }, [loadOrders])

  const loadDetail = useCallback((orderId: string) => {
    setLoading(true)
    fetch(`${apiUrl}/api/v1/orders/${orderId}`, { headers: authHeaders() })
      .then(r => r.json())
      .then((data: OrderDetail) => setDetail(data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [apiUrl])

  useEffect(() => {
    if (selectedId) loadDetail(selectedId)
  }, [selectedId, loadDetail])

  // Poll while anything is mid-flight — this is the only "live-ish"
  // behavior left, and it's a plain poll like every other page in this
  // app, not a dedicated stream.
  useEffect(() => {
    const anyPending = orders.some(o => o.council_explanation_status === 'PENDING' || o.council_explanation_status === 'RUNNING')
      || (detail && (detail.council_explanation_status === 'PENDING' || detail.council_explanation_status === 'RUNNING'))
    if (!anyPending) return
    const id = setInterval(() => {
      loadOrders()
      if (selectedId) loadDetail(selectedId)
    }, 3000)
    return () => clearInterval(id)
  }, [orders, detail, selectedId, loadOrders, loadDetail])

  const roundGroups = (detail?.council_transcript || []).reduce<Map<number, TranscriptEntry[]>>(
    (acc, msg) => {
      const r = msg.round || 0
      if (!acc.has(r)) acc.set(r, [])
      acc.get(r)!.push(msg)
      return acc
    },
    new Map()
  )

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* ── Order list ── */}
      <div style={{ width: 300, flexShrink: 0, borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div className="page-header" style={{ flexShrink: 0, padding: '20px 16px' }}>
          <div>
            <div className="page-title" style={{ fontSize: 16 }}>Council Room</div>
            <div className="page-subtitle" style={{ fontSize: 11 }}>
              Async, post-hoc explanations of already-final decisions
            </div>
          </div>
        </div>
        <div style={{ overflow: 'auto', flex: 1, padding: '8px' }}>
          {orders.length === 0 ? (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
              No orders yet.
              <div style={{ marginTop: 12 }}>
                <button className="btn btn--primary" onClick={() => setActivePage('mission')}>Design a Dispatch</button>
              </div>
            </div>
          ) : orders.map(o => (
            <button
              key={o.order_id}
              onClick={() => setSelectedId(o.order_id)}
              style={{
                display: 'block', width: '100%', textAlign: 'left', padding: '10px 12px', marginBottom: 4,
                background: selectedId === o.order_id ? 'var(--accent-subtle)' : 'transparent',
                border: `1px solid ${selectedId === o.order_id ? 'var(--border-active)' : 'transparent'}`,
                borderRadius: 'var(--radius-md)', cursor: 'pointer',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span style={{ fontSize: 12, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{o.order_id}</span>
                <span className={`verdict-badge verdict-badge--${o.council_verdict === 'APPROVED' ? 'green' : 'red'}`} style={{ fontSize: 9 }}>
                  {o.council_verdict ?? 'PENDING'}
                </span>
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                Explanation: {o.council_explanation_status}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* ── Detail / transcript ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {!selectedId ? (
          <EmptyState onDesign={() => setActivePage('mission')} />
        ) : loading && !detail ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div className="spinner" style={{ width: 20, height: 20 }} />
          </div>
        ) : detail ? (
          <>
            <div className="page-header" style={{ flexShrink: 0 }}>
              <div>
                <div className="page-title">{detail.order_id}</div>
                <div className="page-subtitle">
                  {detail.council_explanation_status === 'READY' && detail.council_transcript
                    ? `Explanation ready — ${detail.council_transcript.length} entries`
                    : `Explanation: ${detail.council_explanation_status}`}
                </div>
              </div>
            </div>

            <div style={{ flex: 1, overflow: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {(detail.council_explanation_status === 'PENDING' || detail.council_explanation_status === 'RUNNING') && (
                <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div className="spinner" style={{ width: 16, height: 16 }} />
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                    Council is generating an explanation in the background — this never affected the
                    decision itself, which was already final. Checking again every few seconds.
                  </span>
                </div>
              )}

              {detail.council_explanation_status === 'FAILED' && (
                <div className="card" style={{ borderColor: 'var(--status-red)' }}>
                  <span style={{ color: 'var(--status-red)' }}>⚠ Explanation generation failed — the dispatch decision itself is unaffected.</span>
                </div>
              )}

              {detail.council_explanation_status === 'NOT_REQUESTED' && (
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
                  No explanation requested for this order yet.
                </div>
              )}

              {detail.council_transcript && Array.from(roundGroups.entries()).map(([round, messages]) => (
                <div key={round}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                    <div style={{ height: '1px', flex: 1, background: ROUND_COLORS[round % ROUND_COLORS.length], opacity: 0.3 }} />
                    <span style={{
                      fontSize: '11px', fontWeight: 600, fontFamily: 'var(--font-mono)',
                      color: ROUND_COLORS[round % ROUND_COLORS.length], padding: '2px 10px',
                      border: `1px solid ${ROUND_COLORS[round % ROUND_COLORS.length]}`, borderRadius: 'var(--radius-sm)', opacity: 0.8,
                    }}>
                      {round === 0 ? 'PRE-SCREENING' : `ROUND ${round}`}
                    </span>
                    <div style={{ height: '1px', flex: 1, background: ROUND_COLORS[round % ROUND_COLORS.length], opacity: 0.3 }} />
                  </div>
                  {messages.map((msg, i) => (
                    <div key={i} className="agent-msg" style={{ marginBottom: '8px' }}>
                      <div className="agent-msg__header">
                        {msg.verdict && (
                          <span className={`verdict-badge verdict-badge--${msg.verdict.toLowerCase()}`}>{msg.verdict}</span>
                        )}
                        <span className="agent-msg__name">{msg.name}</span>
                        {msg.model && <span className="agent-msg__model">{msg.model}</span>}
                      </div>
                      <div className="agent-msg__text">{msg.text}</div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}

function EmptyState({ onDesign }: { onDesign: () => void }) {
  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      gap: '16px', color: 'var(--text-muted)', padding: '48px', textAlign: 'center',
    }}>
      <div className="section-marker" style={{ width: 3, height: 40, opacity: 0.5 }} />
      <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-secondary)' }}>
        Pick an order to browse
      </div>
      <div style={{ fontSize: '13px', maxWidth: '320px' }}>
        Every dispatch decision is made instantly, deterministically, before the council is ever
        involved. Select one from the list to see its decision and, if requested, the council's
        asynchronous explanation of it.
      </div>
      <button id="btn-go-design" className="btn btn--primary" onClick={onDesign}>
        Design a Dispatch
      </button>
    </div>
  )
}
