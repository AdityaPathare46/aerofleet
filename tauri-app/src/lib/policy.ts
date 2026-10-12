import { useEffect, useState } from 'react'

// AeroFleet 2.0 presents itself as a ground-side assurance tool. Screens from the earlier AI-dispatch
// product (the agent council and the live telemetry / agent roster side panel) are hidden unless the
// user turns them back on in Settings; the backend separately refuses to command real aircraft unless
// AEROFLEET_LIVE_CONTROL is on (GET /api/v1/assurance/policy).

const KEY = 'aerofleet_show_legacy'
const EVENT = 'aerofleet-legacy-changed'

export function legacyVisible(): boolean {
  try { return localStorage.getItem(KEY) === '1' } catch { return false }
}

export function setLegacyVisible(on: boolean) {
  try { if (on) localStorage.setItem(KEY, '1'); else localStorage.removeItem(KEY) } catch { /* storage unavailable */ }
  window.dispatchEvent(new Event(EVENT))
}

export function useLegacyVisible(): boolean {
  const [on, setOn] = useState(legacyVisible())
  useEffect(() => {
    const update = () => setOn(legacyVisible())
    window.addEventListener(EVENT, update)
    return () => window.removeEventListener(EVENT, update)
  }, [])
  return on
}

/** true / false once known; null while loading or signed out. */
export function useLiveControl(apiUrl: string): boolean | null {
  const [live, setLive] = useState<boolean | null>(null)
  useEffect(() => {
    let cancelled = false
    const token = localStorage.getItem('aerofleet_token') || ''
    fetch(`${apiUrl}/api/v1/assurance/policy`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((r) => (r.ok ? r.json() : null))
      .then((p) => { if (!cancelled) setLive(p ? !!p.live_control : null) })
      .catch(() => { if (!cancelled) setLive(null) })
    return () => { cancelled = true }
  }, [apiUrl])
  return live
}
