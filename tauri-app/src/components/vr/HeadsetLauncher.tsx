import { useCallback, useEffect, useState } from 'react'
import { isTauri, tauriInvoke } from '../../lib/tauriBridge'

// "Connect the headset" for the desktop app: checks the PC-VR runtime (Quest Link / SteamVR via
// OpenXR) and launches the native AeroFleet VR viewer on the same backend, city, mode and
// incident — see src-tauri/src/vr_headset.rs. Only rendered inside the desktop app; in a plain
// browser the WebXR Enter VR / Enter MR buttons remain the path.

interface HeadsetStatus {
  platform: string
  openxr_runtime_path: string | null
  runtime_name: string | null
  quest_link_running: boolean
  steamvr_running: boolean
  viewer_path: string | null
  viewer_running: boolean
  ready: boolean
  hint: string
}

function Check({ ok, label, detail }: { ok: boolean; label: string; detail?: string }) {
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', fontSize: 13 }}>
      <span style={{ width: 10, height: 10, borderRadius: 5, flex: 'none', transform: 'translateY(1px)',
        background: ok ? 'var(--status-green)' : 'var(--status-amber, #F5A524)' }} />
      <span style={{ fontWeight: 600, minWidth: 150 }}>{label}</span>
      <span style={{ color: 'var(--text-secondary)', overflowWrap: 'anywhere' }}>{detail}</span>
    </div>
  )
}

export function HeadsetLauncher({ apiUrl, city, mode, incidentId }: {
  apiUrl: string; city: string; mode: 'live' | 'replay'; incidentId: string
}) {
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState<HeadsetStatus | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(() => {
    tauriInvoke<HeadsetStatus>('vr_headset_status').then(setStatus).catch((e) => setMessage(String(e)))
  }, [])

  useEffect(() => {
    if (!isTauri()) return
    refresh()
    const t = setInterval(refresh, 3000)
    return () => clearInterval(t)
  }, [refresh])

  if (!isTauri()) return null

  const launch = async () => {
    setBusy(true)
    setMessage(null)
    try {
      await tauriInvoke('launch_vr_viewer', {
        apiUrl, city, mode,
        incidentId: mode === 'replay' ? incidentId : null,
        token: localStorage.getItem('aerofleet_token'),
      })
      setMessage(`Launched — ${mode === 'live' ? 'live swarm' : 'incident replay'} for ${city} is loading in the headset.`)
      refresh()
    } catch (e) {
      setMessage(String(e))
    } finally {
      setBusy(false)
    }
  }

  const locate = async () => {
    const { open: pick } = await import('@tauri-apps/plugin-dialog')
    const picked = await pick({ title: 'Select AeroFleetVR.exe', filters: [{ name: 'AeroFleet VR viewer', extensions: ['exe'] }] })
    if (!picked || Array.isArray(picked)) return
    try {
      await tauriInvoke('set_vr_viewer_path', { path: picked })
      refresh()
    } catch (e) {
      setMessage(String(e))
    }
  }

  const label = status?.viewer_running ? 'In headset' : status?.ready ? 'Launch in headset' : 'Headset'
  return (
    <>
      <button className={`btn ${status?.ready ? 'btn--primary' : ''}`} id="btn-headset" onClick={() => setOpen((o) => !o)}
        title="Run this view in a Quest 3 over Quest Link / Air Link (native viewer)">
        {label} ▾
      </button>
      {open && (
        <div className="card" role="dialog" aria-label="Headset connection"
          style={{ position: 'absolute', right: 24, top: 76, zIndex: 20, width: 460, display: 'grid', gap: 10, padding: 16 }}>
          <div style={{ fontWeight: 700 }}>Headset (PC-VR)</div>
          {status && (
            <>
              <Check ok={status.platform === 'windows'} label="Windows PC" detail={status.platform} />
              <Check ok={!!status.openxr_runtime_path} label="OpenXR runtime" detail={status.runtime_name ?? 'none set'} />
              <Check ok={status.quest_link_running || status.steamvr_running} label="Headset service"
                detail={status.quest_link_running ? 'Quest Link running' : status.steamvr_running ? 'SteamVR running' : 'not running'} />
              <Check ok={!!status.viewer_path} label="AeroFleet VR viewer" detail={status.viewer_path ?? 'not found'} />
              <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{status.hint}</div>
            </>
          )}
          {message && <div style={{ fontSize: 13 }}>{message}</div>}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {status?.viewer_running
              ? <button className="btn" onClick={() => tauriInvoke('stop_vr_viewer').then(refresh)}>Stop viewer</button>
              : <button className="btn btn--primary" disabled={!status?.ready || busy} onClick={launch}>
                  Launch {mode === 'live' ? 'live swarm' : 'this incident'} in headset
                </button>}
            {status?.platform === 'windows' && <button className="btn" onClick={locate}>Locate viewer…</button>}
            <button className="btn" onClick={refresh}>Recheck</button>
          </div>
        </div>
      )}
    </>
  )
}
