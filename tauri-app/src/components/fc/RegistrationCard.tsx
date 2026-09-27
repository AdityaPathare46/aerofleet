import { useCallback, useEffect, useState } from 'react'

// A drone's DGCA Digital Sky registration (UIN) in AeroFleet's registry — what dispatch's regulatory
// check and the inspection's "UIN registered and verified" check read. AeroFleet can't query Digital
// Sky itself, so VERIFIED means an operator checked it there and says how (who/when are recorded).

interface Registration {
  drone_id: string
  uin: string | null
  status: 'NONE' | 'RECORDED' | 'VERIFIED'
  recorded_by?: string | null
  recorded_at?: string | null
  verified_by?: string | null
  verified_at?: string | null
  verification_note?: string | null
}

const TONE: Record<Registration['status'], string> = { NONE: 'red', RECORDED: 'yellow', VERIFIED: 'green' }
const MEANING: Record<Registration['status'], string> = {
  NONE: 'No UIN on file — dispatch flags this drone and the inspection fails the UIN check.',
  RECORDED: 'UIN on file but not yet verified on Digital Sky — the inspection shows a warning.',
  VERIFIED: 'Verified on Digital Sky by an operator — the inspection passes the UIN check.',
}

function headers(): Record<string, string> {
  const token = localStorage.getItem('aerofleet_token') || ''
  return { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }
}

export default function RegistrationCard({ apiUrl, droneId }: { apiUrl: string; droneId: string }) {
  const [reg, setReg] = useState<Registration | null>(null)
  const [uin, setUin] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const id = droneId.trim()
  const url = `${apiUrl}/api/v1/fleet/registrations/${encodeURIComponent(id)}`

  const load = useCallback(async () => {
    if (!id) { setReg(null); return }
    const r = await fetch(url, { headers: headers() })
    if (r.ok) { const body: Registration = await r.json(); setReg(body); setUin(body.uin ?? '') }
  }, [id, url])

  useEffect(() => {
    const t = setTimeout(() => { load().catch(() => setReg(null)) }, 300)
    return () => clearTimeout(t)
  }, [load])

  const send = async (method: string, path: string, body?: unknown) => {
    setBusy(true); setError(null)
    try {
      const r = await fetch(url + path, { method, headers: headers(), body: body ? JSON.stringify(body) : undefined })
      if (r.status === 403) throw new Error('Only an operator can change registrations.')
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`)
      setReg(await r.json())
      setNote('')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card">
      <div className="card__header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span className="card__title">Registration (Digital Sky UIN)</span>
        {reg && <span className={`verdict-badge verdict-badge--${TONE[reg.status]}`}>{reg.status}</span>}
      </div>
      {!id && <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Enter a drone ID below to see or record its UIN.</div>}
      {id && reg && (
        <div style={{ display: 'grid', gap: 12 }}>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            {MEANING[reg.status]}
            {reg.status === 'VERIFIED' && (
              <> Verified by {reg.verified_by} on {reg.verified_at?.slice(0, 10)}: “{reg.verification_note}”.</>
            )}
            {reg.status === 'RECORDED' && reg.recorded_by && <> Recorded by {reg.recorded_by} on {reg.recorded_at?.slice(0, 10)}.</>}
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div className="form-group" style={{ marginBottom: 0, minWidth: 220 }}>
              <label className="form-label">UIN for {id}</label>
              <input className="form-input mono" value={uin} onChange={(e) => setUin(e.target.value)} placeholder="as issued by Digital Sky" />
            </div>
            <button className="btn" disabled={busy || !uin.trim() || uin.trim().toUpperCase() === reg.uin}
              onClick={() => send('PUT', '', { uin })}>
              {reg.uin ? 'Change UIN' : 'Record UIN'}
            </button>
          </div>
          {reg.uin && reg.status !== 'VERIFIED' && (
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', flexWrap: 'wrap' }}>
              <div className="form-group" style={{ marginBottom: 0, flex: 1, minWidth: 260 }}>
                <label className="form-label">How you verified it on Digital Sky</label>
                <input className="form-input" value={note} onChange={(e) => setNote(e.target.value)}
                  placeholder="e.g. checked on digitalsky.dgca.gov.in, airframe serial matches" />
              </div>
              <button className="btn btn--primary" disabled={busy || note.trim().length < 3} onClick={() => send('POST', '/verify', { note })}>
                Mark verified
              </button>
            </div>
          )}
          {error && <div style={{ fontSize: 13, color: 'var(--status-red)' }}>{error}</div>}
        </div>
      )}
    </div>
  )
}
