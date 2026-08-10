import React, { useCallback, useEffect, useState } from 'react'
import { useAppStore } from '../store/appStore'

interface PolicyProposal {
  id: number
  proposal_id: string
  city: string
  proposed_changes: Record<string, number>
  rationale: string | null
  status: string
  reviewed_by: string | null
  reviewed_at: string | null
  created_at: string
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('aerofleet_token') || ''
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const STATUS_BADGE: Record<string, string> = {
  PENDING_REVIEW: 'yellow',
  APPROVED: 'green',
  REJECTED: 'red',
}

export default function PolicyProposalsPage() {
  const { apiUrl } = useAppStore()
  const [proposals, setProposals] = useState<PolicyProposal[]>([])
  const [busyId, setBusyId] = useState<string | null>(null)
  const [triggering, setTriggering] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    fetch(`${apiUrl}/api/v1/policy/proposals`, { headers: authHeaders() })
      .then(r => r.json())
      .then((data: PolicyProposal[]) => setProposals(Array.isArray(data) ? data : []))
      .catch(() => {})
  }, [apiUrl])

  useEffect(() => { load() }, [load])

  async function decide(proposalId: string, action: 'approve' | 'reject') {
    setBusyId(proposalId)
    setError(null)
    try {
      const res = await fetch(`${apiUrl}/api/v1/policy/proposals/${proposalId}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({}),
      })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText} — operator permissions required`)
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusyId(null)
    }
  }

  async function triggerReview() {
    setTriggering(true)
    setError(null)
    try {
      const res = await fetch(`${apiUrl}/api/v1/policy/trigger-review`, { method: 'POST', headers: authHeaders() })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText} — operator permissions required`)
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setTriggering(false)
    }
  }

  const pending = proposals.filter(p => p.status === 'PENDING_REVIEW')
  const decided = proposals.filter(p => p.status !== 'PENDING_REVIEW')

  return (
    <div style={{ overflow: 'auto', flex: 1 }}>
      <div className="page-header">
        <div>
          <div className="page-title">Fleet Policy</div>
          <div className="page-subtitle">
            Council-drafted CBF threshold proposals · slow cadence · never takes effect without operator approval
          </div>
        </div>
        <button id="btn-trigger-review" className="btn btn--primary" onClick={triggerReview} disabled={triggering}>
          {triggering ? <><div className="spinner" style={{ width: 14, height: 14 }} /> Reviewing...</> : 'Trigger Review Now'}
        </button>
      </div>

      <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {error && (
          <div className="card" style={{ borderColor: 'var(--status-red)' }}>
            <span style={{ color: 'var(--status-red)' }}>⚠ {error}</span>
          </div>
        )}

        <Section title={`Pending Review (${pending.length})`}>
          {pending.length === 0 ? (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
              No proposals awaiting review right now. The council reviews fleet stats every few hours on its own
              (or trigger a review above) and only proposes a change when recent near-misses, CBF interventions,
              or faults actually support one.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {pending.map(p => (
                <ProposalCard
                  key={p.proposal_id}
                  proposal={p}
                  busy={busyId === p.proposal_id}
                  onApprove={() => decide(p.proposal_id, 'approve')}
                  onReject={() => decide(p.proposal_id, 'reject')}
                />
              ))}
            </div>
          )}
        </Section>

        {decided.length > 0 && (
          <Section title="History">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {decided.map(p => <ProposalCard key={p.proposal_id} proposal={p} busy={false} />)}
            </div>
          </Section>
        )}
      </div>
    </div>
  )
}

function ProposalCard({
  proposal, busy, onApprove, onReject,
}: {
  proposal: PolicyProposal
  busy: boolean
  onApprove?: () => void
  onReject?: () => void
}) {
  const changeEntries = Object.entries(proposal.proposed_changes || {})
  return (
    <div className="card">
      <div className="card__header">
        <span className="card__title">{proposal.proposal_id} — {proposal.city}</span>
        <span className={`verdict-badge verdict-badge--${STATUS_BADGE[proposal.status] || 'yellow'}`}>
          {proposal.status}
        </span>
      </div>

      {changeEntries.length > 0 && (
        <div className="grid-3" style={{ marginBottom: 12 }}>
          {changeEntries.map(([key, value]) => (
            <div className="metric" key={key}>
              <span className="metric__label">{key}</span>
              <span className="metric__value" style={{ fontSize: 15 }}>{value}</span>
            </div>
          ))}
        </div>
      )}

      {proposal.rationale && (
        <pre style={{
          background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)',
          padding: '12px', fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)',
          whiteSpace: 'pre-wrap', overflowX: 'auto', marginBottom: onApprove ? 12 : 0,
        }}>
          {proposal.rationale}
        </pre>
      )}

      {onApprove && onReject ? (
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button className="btn btn--danger" onClick={onReject} disabled={busy}>Reject</button>
          <button className="btn btn--primary" onClick={onApprove} disabled={busy}>
            {busy ? <><div className="spinner" style={{ width: 12, height: 12 }} /> Working...</> : 'Approve'}
          </button>
        </div>
      ) : (
        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {proposal.reviewed_by ? `${proposal.status === 'APPROVED' ? 'Approved' : 'Rejected'} by ${proposal.reviewed_by}` : ''}
        </div>
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {title}
      </div>
      {children}
    </div>
  )
}
