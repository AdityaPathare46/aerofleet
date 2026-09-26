import { useCallback, useEffect, useRef, useState } from 'react'
import { isTauri, tauriInvoke } from '../../lib/tauriBridge'

// "View this in VR": pairs a headset with this desktop and keeps it following the view.
//
//   Quest 3 on Wi-Fi (Windows or Mac) — opening a session makes the backend announce this computer
//   on the local network; the AeroFleet VR app on the headset finds it and asks to connect; both
//   screens show the same 4-digit code and the operator allows it here.
//   This PC over Quest Link (Windows) — the desktop launches the native viewer itself.
//
// While paired, every change to the view here (city, live/replay, incident, selected drone, range)
// is pushed to the headset. See aerofleet/api/routes/vr.py and aerofleet/vr/.

export interface VrScenario {
  city: string
  mode: 'live' | 'replay'
  incident_id: string | null
  selected_drone: string | null
  range_km: number
  detail_all: boolean
  show_buildings: boolean
}

interface PendingRequest { request_id: string; device_name: string; confirm_code: string; client_ip: string; age_s: number }
interface DeviceInfo {
  name: string; via: 'wifi' | 'local'; online: boolean; last_seen_s: number
  status: { mode?: string; city?: string; incident_id?: string | null; in_headset?: boolean }
}
interface SessionView {
  session_id: string; scenario_version: number; device: DeviceInfo | null; pending_requests: PendingRequest[]
  host: string; addresses: string[]; gateway_port: number; network: 'on' | 'off'; gateway_running: boolean
}
interface HeadsetStatus {
  platform: string; runtime_name: string | null; quest_link_running: boolean; steamvr_running: boolean
  viewer_path: string | null; viewer_running: boolean; ready: boolean; hint: string
}

const SHOWN_KEY = 'aerofleet_vr_prompt_shown'

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('aerofleet_token') || ''
  return token ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
}

function Dot({ color }: { color: string }) {
  return <span style={{ width: 9, height: 9, borderRadius: 5, background: color, display: 'inline-block', flex: 'none' }} />
}

export function VrConnect({ apiUrl, scenario, signedIn }: { apiUrl: string; scenario: VrScenario; signedIn: boolean }) {
  const [open, setOpen] = useState(false)
  const [session, setSession] = useState<SessionView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pcvr, setPcvr] = useState<HeadsetStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const lastPushed = useRef<string>('')

  const call = useCallback(async <T,>(method: string, path: string, body?: unknown): Promise<T> => {
    const r = await fetch(`${apiUrl}/api/v1/vr${path}`, { method, headers: authHeaders(), body: body ? JSON.stringify(body) : undefined })
    if (r.status === 401) throw new Error('Your AeroFleet sign-in has expired — sign in again, then connect the headset.')
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`)
    return r.json()
  }, [apiUrl])

  // First visit to the VR view in this app session: offer the headset.
  useEffect(() => {
    if (!signedIn) return
    let shown = false
    try { shown = sessionStorage.getItem(SHOWN_KEY) === '1'; sessionStorage.setItem(SHOWN_KEY, '1') } catch { /* private mode */ }
    if (!shown) setOpen(true)
  }, [signedIn])

  // Resume a session that's already open (e.g. after navigating away and back).
  useEffect(() => {
    if (!signedIn) return
    call<SessionView>('GET', '/session').then(setSession).catch(() => setSession(null))
  }, [call, signedIn])

  // While a session is open: poll it (this also keeps it alive), surface pair requests.
  useEffect(() => {
    if (!session) return
    const t = setInterval(() => {
      call<SessionView>('GET', '/session')
        .then((s) => { setSession(s); if (s.pending_requests.length) setOpen(true) })
        .catch(() => setSession(null))
    }, 1500)
    return () => clearInterval(t)
  }, [session?.session_id, call]) // eslint-disable-line react-hooks/exhaustive-deps

  // Push the view to the headset whenever it changes.
  useEffect(() => {
    if (!session) return
    const key = JSON.stringify(scenario)
    if (key === lastPushed.current) return
    lastPushed.current = key
    call('PUT', '/session/scenario', scenario).catch(() => { lastPushed.current = '' })
  }, [scenario, session, call])

  useEffect(() => {
    if (!open || !isTauri()) return
    const refresh = () => tauriInvoke<HeadsetStatus>('vr_headset_status').then(setPcvr).catch(() => setPcvr(null))
    refresh()
    const t = setInterval(refresh, 3000)
    return () => clearInterval(t)
  }, [open])

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError(null)
    try { await fn() } catch (e) { setError(e instanceof Error ? e.message : String(e)) } finally { setBusy(false) }
  }
  const startSession = () => act(async () => { lastPushed.current = ''; setSession(await call<SessionView>('POST', '/session')) })
  const endSession = () => act(async () => { await call('DELETE', '/session'); setSession(null) })
  const decide = (id: string, d: 'approve' | 'deny') => act(async () => { await call('POST', `/session/requests/${id}/${d}`); setSession(await call('GET', '/session')) })
  const disconnect = () => act(async () => { await call('POST', '/session/device/disconnect'); setSession(await call('GET', '/session')) })
  const launchPcvr = () => act(async () => {
    const s = session ?? await call<SessionView>('POST', '/session')
    setSession(s)
    const { token, gateway_url } = await call<{ token: string; gateway_url: string }>('POST', '/session/local-device', {})
    await tauriInvoke('launch_vr_viewer', {
      apiUrl: gateway_url, city: scenario.city, mode: scenario.mode,
      incidentId: scenario.mode === 'replay' ? scenario.incident_id : null, token,
    })
  })

  const device = session?.device
  const chip = !session ? { color: 'var(--text-muted)', text: 'Connect headset' }
    : device?.online ? { color: 'var(--status-green)', text: `${device.name} connected` }
      : session.pending_requests.length ? { color: 'var(--status-amber)', text: 'Headset waiting for approval' }
        : { color: 'var(--status-amber)', text: 'Waiting for headset…' }

  return (
    <>
      <button className="btn" id="btn-vr-connect" onClick={() => setOpen((o) => !o)} title="View this in a VR headset"
        style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Dot color={chip.color} />{chip.text}
      </button>
      {open && (
        <div role="dialog" aria-label="View this in VR" onClick={() => setOpen(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(8, 14, 24, 0.45)', zIndex: 50, display: 'grid', placeItems: 'center' }}>
          <div className="card" onClick={(e) => e.stopPropagation()}
            style={{ width: 'min(560px, calc(100vw - 32px))', padding: 22, display: 'grid', gap: 16, maxHeight: '90vh', overflowY: 'auto' }}>
            <div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>View this in VR</div>
              <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
                Connect the AeroFleet VR app and it shows exactly what you're looking at here — city, live swarm or incident, selected drone — and follows as you change it.
              </div>
            </div>

            {!signedIn && <div style={{ fontSize: 13 }}>Sign in first — the headset uses your session.</div>}

            {signedIn && (
              <section style={{ display: 'grid', gap: 10 }}>
                <div style={{ fontWeight: 600 }}>Quest 3 on Wi-Fi <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>· Windows or Mac</span></div>
                {!session && (
                  <>
                    <ol style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: 'var(--text-secondary)', display: 'grid', gap: 4 }}>
                      <li>Put the headset on the same Wi-Fi as this computer.</li>
                      <li>Click <b>Connect a headset</b>, then open <b>AeroFleet VR</b> on the Quest.</li>
                      <li>It finds this computer by itself; allow it here when the codes match.</li>
                    </ol>
                    <div><button className="btn btn--primary" disabled={busy} onClick={startSession}>Connect a headset</button></div>
                  </>
                )}
                {session && !device && session.pending_requests.length === 0 && (
                  <div style={{ fontSize: 13, display: 'grid', gap: 4 }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}><Dot color="var(--status-amber)" /><b>Waiting for the headset…</b></div>
                    <div style={{ color: 'var(--text-secondary)' }}>
                      Open AeroFleet VR on the Quest. This computer is announcing itself as <b>{session.host}</b>
                      {session.addresses.length > 0 && <> ({session.addresses.join(', ')})</>}.
                    </div>
                    {session.network === 'off' && <div style={{ color: 'var(--status-red)' }}>Network access is disabled on this backend (AEROFLEET_VR_NETWORK=off).</div>}
                  </div>
                )}
                {session?.pending_requests.map((r) => (
                  <div key={r.request_id} className="card" style={{ padding: 12, display: 'grid', gap: 8, borderColor: 'var(--status-amber)' }}>
                    <div style={{ fontSize: 13 }}><b>{r.device_name}</b> ({r.client_ip}) wants to connect.</div>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
                      <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Does the headset show this code?</span>
                      <span style={{ fontSize: 26, fontWeight: 700, letterSpacing: 6, fontVariantNumeric: 'tabular-nums' }}>{r.confirm_code}</span>
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button className="btn btn--primary" disabled={busy} onClick={() => decide(r.request_id, 'approve')}>Allow</button>
                      <button className="btn" disabled={busy} onClick={() => decide(r.request_id, 'deny')}>Deny</button>
                    </div>
                  </div>
                ))}
                {device && (
                  <div style={{ fontSize: 13, display: 'grid', gap: 6 }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <Dot color={device.online ? 'var(--status-green)' : 'var(--status-amber)'} />
                      <b>{device.name}</b> {device.via === 'local' ? 'on this PC (Quest Link)' : 'over Wi-Fi'} ·{' '}
                      {device.online ? 'connected' : `last seen ${Math.round(device.last_seen_s)} s ago`}
                    </div>
                    {device.status.mode && (
                      <div style={{ color: 'var(--text-secondary)' }}>
                        Showing {device.status.mode === 'replay' ? `incident ${device.status.incident_id ?? ''}` : 'the live swarm'} · {device.status.city}
                        {device.status.in_headset === false && ' (running without a headset)'}
                      </div>
                    )}
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button className="btn" disabled={busy} onClick={disconnect}>Disconnect headset</button>
                    </div>
                  </div>
                )}
                {session && <div><button className="btn" disabled={busy} onClick={endSession}>End VR session</button></div>}
              </section>
            )}

            {signedIn && isTauri() && (
              <section style={{ display: 'grid', gap: 8, borderTop: '1px solid var(--border, rgba(0,0,0,0.08))', paddingTop: 14 }}>
                <div style={{ fontWeight: 600 }}>This PC over Quest Link <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>· Windows</span></div>
                {pcvr && <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{pcvr.hint}</div>}
                <div>
                  <button className="btn" disabled={busy || !pcvr?.ready || pcvr.viewer_running} onClick={launchPcvr}>
                    {pcvr?.viewer_running ? 'Running in the headset' : 'Launch on this PC'}
                  </button>
                </div>
              </section>
            )}

            {error && <div style={{ fontSize: 13, color: 'var(--status-red)' }}>{error}</div>}
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button className="btn" onClick={() => setOpen(false)}>{session ? 'Close' : 'Continue on this screen'}</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
