import React, { useState } from 'react'

/** Minimal sign-in / create-account card. Stores the JWT under the same
 * `aerofleet_token` key every page already reads, so signing in here unlocks
 * the rest of the app too. */
export default function SignInCard({ apiUrl, onSignedIn, reason }: {
  apiUrl: string
  onSignedIn: () => void
  reason?: string
}) {
  const [mode, setMode] = useState<'signin' | 'register'>('signin')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (mode === 'register') {
        const r = await fetch(`${apiUrl}/api/v1/auth/register`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, email, password }),
        })
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail?.toString?.() || `Registration failed (HTTP ${r.status})`)
      }
      const r = await fetch(`${apiUrl}/api/v1/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username, password }),
      })
      if (!r.ok) throw new Error(r.status === 401 ? 'Incorrect username or password' : `Sign-in failed (HTTP ${r.status})`)
      const { access_token } = await r.json()
      localStorage.setItem('aerofleet_token', access_token)
      onSignedIn()
    } catch (err) {
      setError(String((err as Error).message || err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card" style={{ maxWidth: 380, margin: '48px auto', padding: 24 }}>
      <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 4 }}>
        {mode === 'signin' ? 'Sign in to AeroFleet' : 'Create an AeroFleet account'}
      </div>
      <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 16 }}>
        {reason ?? 'Live fleet data requires an authenticated session.'}
      </div>
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <input className="form-input" placeholder="Username" autoComplete="username" value={username}
          onChange={(e) => setUsername(e.target.value)} required minLength={3} />
        {mode === 'register' && (
          <input className="form-input" placeholder="Email" type="email" autoComplete="email" value={email}
            onChange={(e) => setEmail(e.target.value)} required />
        )}
        <input className="form-input" placeholder="Password" type="password"
          autoComplete={mode === 'signin' ? 'current-password' : 'new-password'} value={password}
          onChange={(e) => setPassword(e.target.value)} required minLength={mode === 'register' ? 8 : 1} />
        {error && <div style={{ color: 'var(--status-red)', fontSize: 13 }}>{error}</div>}
        <button className="btn btn--primary" type="submit" disabled={busy}>
          {busy ? 'Working…' : mode === 'signin' ? 'Sign in' : 'Create account & sign in'}
        </button>
      </form>
      <button className="btn btn--ghost" style={{ marginTop: 10, width: '100%' }}
        onClick={() => { setMode(mode === 'signin' ? 'register' : 'signin'); setError(null) }}>
        {mode === 'signin' ? 'No account? Create one' : 'Have an account? Sign in'}
      </button>
    </div>
  )
}
