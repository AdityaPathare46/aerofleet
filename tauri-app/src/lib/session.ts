// Keeps the operator signed in while the app is in use.
//
// The backend issues a short-lived access token (1 h) and a refresh token (14 days). Every page
// reads the access token from localStorage per request, so renewing it here is enough: this module
// swaps in a fresh pair shortly before the access token expires, and again whenever the app regains
// focus (e.g. after the laptop slept). If the refresh token itself is gone or expired, nothing
// happens — the page asks the operator to sign in, as before.

const ACCESS_KEY = 'aerofleet_token'
const REFRESH_KEY = 'aerofleet_refresh_token'
const RENEW_WHEN_LEFT_S = 10 * 60
const CHECK_EVERY_MS = 60 * 1000

function read(key: string): string | null {
  try { return localStorage.getItem(key) } catch { return null }
}

function write(key: string, value: string | null) {
  try { if (value) localStorage.setItem(key, value); else localStorage.removeItem(key) } catch { /* storage unavailable */ }
}

/** Seconds until a JWT's `exp`, or null if it can't be read. */
export function secondsLeft(token: string | null): number | null {
  if (!token) return null
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return typeof payload.exp === 'number' ? payload.exp - Date.now() / 1000 : null
  } catch {
    return null
  }
}

export function storeTokens(tokens: { access_token: string; refresh_token?: string | null }) {
  write(ACCESS_KEY, tokens.access_token)
  if (tokens.refresh_token) write(REFRESH_KEY, tokens.refresh_token)
}

let inFlight: Promise<boolean> | null = null

/** Renew now if the access token is missing, expired or close to expiry. Resolves true if renewed. */
export function renewIfNeeded(apiUrl: string, force = false): Promise<boolean> {
  const left = secondsLeft(read(ACCESS_KEY))
  if (!force && left != null && left > RENEW_WHEN_LEFT_S) return Promise.resolve(false)
  const refresh = read(REFRESH_KEY)
  if (!refresh || (secondsLeft(refresh) ?? 0) <= 0) return Promise.resolve(false)
  if (inFlight) return inFlight
  inFlight = fetch(`${apiUrl}/api/v1/auth/refresh`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refresh }),
  })
    .then(async (r) => {
      if (r.status === 401) { write(REFRESH_KEY, null); return false }  // revoked/expired: sign in again
      if (!r.ok) return false                                             // backend busy: try next tick
      storeTokens(await r.json())
      return true
    })
    .catch(() => false)
    .finally(() => { inFlight = null })
  return inFlight
}

/** Start background renewal; returns a stop function. */
export function startSilentRenewal(apiUrl: string): () => void {
  const tick = () => { void renewIfNeeded(apiUrl) }
  tick()
  const timer = setInterval(tick, CHECK_EVERY_MS)
  const onVisible = () => { if (document.visibilityState === 'visible') tick() }
  window.addEventListener('focus', tick)
  document.addEventListener('visibilitychange', onVisible)
  return () => {
    clearInterval(timer)
    window.removeEventListener('focus', tick)
    document.removeEventListener('visibilitychange', onVisible)
  }
}

/**
 * Retry-once on 401 for every API call in the app: if the backend rejects the access token (it
 * expired while the laptop slept, say), renew with the refresh token and replay the request with
 * the new token. Installed once; pages keep using plain fetch().
 */
export function installAuthRetry(apiUrl: string): void {
  const w = window as Window & { __aerofleetAuthRetry?: boolean }
  if (w.__aerofleetAuthRetry) return
  w.__aerofleetAuthRetry = true
  const original = window.fetch.bind(window)
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const res = await original(input, init)
    if (res.status !== 401) return res
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    if (!url.startsWith(apiUrl) || url.includes('/api/v1/auth/')) return res
    const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined))
    if (!headers.get('Authorization')?.startsWith('Bearer ')) return res
    if (!(await renewIfNeeded(apiUrl, true))) return res
    headers.set('Authorization', `Bearer ${read(ACCESS_KEY)}`)
    return original(input instanceof Request ? new Request(input, { headers }) : input, { ...init, headers })
  }
}
