import React, { useCallback, useEffect, useState } from 'react'
import { useAppStore } from '../store/appStore'

// ── Types ─────────────────────────────────────────────────────────────

type ConnectionMode = 'local_ollama' | 'tailscale_ollama' | 'openrouter'

interface LLMSettingsDto {
  mode: ConnectionMode
  ollama_host: string
  tailscale_host: string | null
  has_openrouter_key: boolean
  use_mock: boolean
}

interface OllamaStatus {
  installed: boolean
  running: boolean
  version: string | null
}

// Mirrors aerofleet/agents/factory.py's DEFAULT_MODEL_MAP roster — the
// same 5 distinct tags across all 11+5 agents (Phase Q).
const ROSTER_MODELS = [
  'llama4:scout',
  'mistral-small3.2',
  'mistral-small3.2',
  'gemma4:12b',
  'phi4-reasoning:plus',
]

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('aerofleet_token') || ''
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/** Tauri's IPC bridge (window.__TAURI_INTERNALS__) only exists inside the
 * native app window, not a plain browser tab — these helpers no-op/throw
 * gracefully outside it so the Local Ollama tab degrades instead of
 * crashing when previewed in an ordinary browser. */
async function tauriInvoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  const { invoke } = await import('@tauri-apps/api/core')
  return invoke<T>(cmd, args)
}

async function tauriListen(event: string, handler: (payload: any) => void): Promise<() => void> {
  const { listen } = await import('@tauri-apps/api/event')
  return listen(event, (e) => handler(e.payload))
}

export default function SettingsPage() {
  const { apiUrl, llmConnectionMode, setLlmConnectionMode } = useAppStore()

  const [activeTab, setActiveTab] = useState<ConnectionMode>(llmConnectionMode)
  const [current, setCurrent] = useState<LLMSettingsDto | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  // Local Ollama tab state
  const [ollamaStatus, setOllamaStatus] = useState<OllamaStatus | null>(null)
  const [installedModels, setInstalledModels] = useState<string[]>([])
  const [installProgress, setInstallProgress] = useState<{ stage: string; percent: number | null } | null>(null)
  const [pullProgress, setPullProgress] = useState<Record<string, string>>({})
  const [linuxCommand, setLinuxCommand] = useState<string | null>(null)
  const [tauriAvailable, setTauriAvailable] = useState(true)

  // Tailscale tab state
  const [tailscaleHost, setTailscaleHost] = useState('')

  // API tab state
  const [openrouterKey, setOpenrouterKey] = useState('')

  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)

  const loadCurrent = useCallback(() => {
    fetch(`${apiUrl}/api/v1/settings/llm`, { headers: authHeaders() })
      .then((r) => r.json())
      .then((d: LLMSettingsDto) => {
        setCurrent(d)
        setLlmConnectionMode(d.mode)
        if (d.tailscale_host) setTailscaleHost(d.tailscale_host)
      })
      .catch(() => {})
  }, [apiUrl, setLlmConnectionMode])

  useEffect(() => { loadCurrent() }, [loadCurrent])

  const refreshOllamaStatus = useCallback(async () => {
    try {
      const status = await tauriInvoke<OllamaStatus>('check_ollama_status')
      setOllamaStatus(status)
      setTauriAvailable(true)
    } catch {
      setTauriAvailable(false)
    }
  }, [])

  const refreshInstalledModels = useCallback(() => {
    fetch(`${apiUrl}/api/v1/settings/llm/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ mode: 'local_ollama', ollama_host: 'http://localhost:11434' }),
    })
      .then((r) => r.json())
      .then((d) => setInstalledModels(d.models || []))
      .catch(() => {})
  }, [apiUrl])

  useEffect(() => {
    if (activeTab !== 'local_ollama') return
    refreshOllamaStatus()
    refreshInstalledModels()
    tauriInvoke<string>('get_linux_install_command').then(setLinuxCommand).catch(() => {})

    let unlistenInstall: (() => void) | undefined
    let unlistenPull: (() => void) | undefined
    tauriListen('install-progress', (p) => setInstallProgress(p)).then((fn) => (unlistenInstall = fn))
    tauriListen('pull-progress', (p: { model_tag: string; stage: string }) =>
      setPullProgress((prev) => ({ ...prev, [p.model_tag]: p.stage }))
    ).then((fn) => (unlistenPull = fn))

    return () => {
      unlistenInstall?.()
      unlistenPull?.()
    }
  }, [activeTab, refreshOllamaStatus, refreshInstalledModels])

  async function handleInstallOllama() {
    setBusy('install')
    setError(null)
    setInstallProgress(null)
    try {
      await tauriInvoke('install_ollama')
      await refreshOllamaStatus()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  async function handlePullModel(tag: string) {
    setBusy(`pull-${tag}`)
    setError(null)
    try {
      await tauriInvoke('pull_model', { modelTag: tag })
      refreshInstalledModels()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  async function handleSave(mode: ConnectionMode) {
    setBusy('save')
    setError(null)
    try {
      const body: Record<string, unknown> = { mode }
      if (mode === 'local_ollama') body.ollama_host = 'http://localhost:11434'
      if (mode === 'tailscale_ollama') body.tailscale_host = tailscaleHost
      if (mode === 'openrouter' && openrouterKey) body.openrouter_api_key = openrouterKey

      const res = await fetch(`${apiUrl}/api/v1/settings/llm`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      const updated: LLMSettingsDto = await res.json()
      setCurrent(updated)
      setLlmConnectionMode(updated.mode)
      setOpenrouterKey('')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  async function handleTest(mode: ConnectionMode) {
    setBusy('test')
    setError(null)
    setTestResult(null)
    try {
      const body: Record<string, unknown> = { mode }
      if (mode === 'local_ollama') body.ollama_host = 'http://localhost:11434'
      if (mode === 'tailscale_ollama') body.tailscale_host = tailscaleHost
      if (mode === 'openrouter') body.openrouter_api_key = openrouterKey

      const res = await fetch(`${apiUrl}/api/v1/settings/llm/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(body),
      })
      const d = await res.json()
      setTestResult({
        ok: d.ok,
        message: d.ok ? `Connected — ${(d.models || []).length} models visible.` : d.error,
      })
    } catch (e) {
      setTestResult({ ok: false, message: e instanceof Error ? e.message : String(e) })
    } finally {
      setBusy(null)
    }
  }

  const missingModels = ROSTER_MODELS.filter(
    (m) => !installedModels.some((im) => im.startsWith(m.split(':')[0]))
  )

  return (
    <div style={{ overflow: 'auto', flex: 1 }}>
      <div className="page-header">
        <div>
          <div className="page-title">Settings</div>
          <div className="page-subtitle">
            LLM connection &middot; currently{' '}
            <span className="text-accent">{current?.mode || llmConnectionMode}</span>
          </div>
        </div>
      </div>

      <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {error && (
          <div className="card" style={{ borderColor: 'var(--status-red)' }}>
            <span style={{ color: 'var(--status-red)' }}>&#9888; {error}</span>
          </div>
        )}

        <div className="tabs">
          <button className={`tab ${activeTab === 'local_ollama' ? 'active' : ''}`} onClick={() => setActiveTab('local_ollama')}>
            Local Ollama
          </button>
          <button className={`tab ${activeTab === 'tailscale_ollama' ? 'active' : ''}`} onClick={() => setActiveTab('tailscale_ollama')}>
            Tailscale
          </button>
          <button className={`tab ${activeTab === 'openrouter' ? 'active' : ''}`} onClick={() => setActiveTab('openrouter')}>
            API (OpenRouter)
          </button>
        </div>

        {activeTab === 'local_ollama' && (
          <div className="card">
            <div className="card__header"><span className="card__title">Local Ollama</span></div>

            {!tauriAvailable ? (
              <div style={{ color: 'var(--text-muted)' }}>
                Install/pull automation only runs inside the native desktop app.
              </div>
            ) : (
              <>
                <div className="grid-3" style={{ marginBottom: '16px' }}>
                  <Metric label="Installed" value={ollamaStatus?.installed ? 'yes' : 'no'} tone={ollamaStatus?.installed ? 'green' : 'red'} />
                  <Metric label="Running" value={ollamaStatus?.running ? 'yes' : 'no'} tone={ollamaStatus?.running ? 'green' : 'amber'} />
                  <Metric label="Version" value={ollamaStatus?.version || '—'} />
                </div>

                {!ollamaStatus?.installed && (
                  <div style={{ marginBottom: '16px' }}>
                    <button
                      id="btn-install-ollama"
                      className="btn btn--primary"
                      onClick={handleInstallOllama}
                      disabled={busy === 'install'}
                    >
                      {busy === 'install' ? <><div className="spinner" style={{ width: 14, height: 14 }} /> Installing...</> : 'Install Ollama'}
                    </button>
                    {installProgress && (
                      <div style={{ marginTop: '10px' }}>
                        <div className="text-sm text-muted">{installProgress.stage}</div>
                        {installProgress.percent != null && (
                          <div className="progress-bar" style={{ marginTop: '4px' }}>
                            <div className="progress-bar__fill" style={{ width: `${installProgress.percent}%` }} />
                          </div>
                        )}
                      </div>
                    )}
                    {linuxCommand && (
                      <div style={{ marginTop: '12px' }}>
                        <div className="text-sm text-muted" style={{ marginBottom: '6px' }}>
                          On Linux, install automation isn't run for you (see below) — copy and run this yourself:
                        </div>
                        <pre style={{
                          background: 'var(--bg-surface)', border: '1px solid var(--border)',
                          borderRadius: 'var(--radius-md)', padding: '10px 12px', fontSize: '12px',
                          fontFamily: 'var(--font-mono)', overflowX: 'auto',
                        }}>{linuxCommand}</pre>
                      </div>
                    )}
                  </div>
                )}

                <div className="card__header" style={{ paddingLeft: 0 }}><span className="card__title">Roster Models</span></div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {ROSTER_MODELS.map((tag) => {
                    const present = installedModels.some((im) => im.startsWith(tag.split(':')[0]))
                    const stage = pullProgress[tag]
                    return (
                      <div key={tag} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span className="mono text-sm">{tag}</span>
                        {present ? (
                          <span className="verdict-badge verdict-badge--green">present</span>
                        ) : (
                          <button
                            id={`btn-pull-${tag.replace(/[^a-zA-Z0-9]/g, '-')}`}
                            className="btn btn--ghost"
                            onClick={() => handlePullModel(tag)}
                            disabled={busy === `pull-${tag}` || !ollamaStatus?.installed}
                          >
                            {busy === `pull-${tag}` ? 'Pulling...' : stage === 'complete' ? 'Done' : 'Pull'}
                          </button>
                        )}
                      </div>
                    )
                  })}
                </div>
                {missingModels.length > 0 && (
                  <div className="text-sm text-muted" style={{ marginTop: '10px' }}>
                    {missingModels.length} of {ROSTER_MODELS.length} roster models missing.
                  </div>
                )}
              </>
            )}

            <div style={{ marginTop: '20px' }}>
              <button className="btn btn--primary" onClick={() => handleSave('local_ollama')} disabled={busy === 'save'}>
                {busy === 'save' ? 'Saving...' : 'Use Local Ollama'}
              </button>
            </div>
          </div>
        )}

        {activeTab === 'tailscale_ollama' && (
          <div className="card">
            <div className="card__header"><span className="card__title">Tailscale</span></div>
            <div className="form-group">
              <label className="form-label">Ollama Host (Tailscale IP)</label>
              <input
                id="input-tailscale-host"
                className="form-input"
                placeholder="http://100.x.x.x:11434"
                value={tailscaleHost}
                onChange={(e) => setTailscaleHost(e.target.value)}
              />
            </div>
            <div style={{ display: 'flex', gap: '10px', marginTop: '12px' }}>
              <button className="btn btn--ghost" onClick={() => handleTest('tailscale_ollama')} disabled={busy === 'test' || !tailscaleHost}>
                {busy === 'test' ? 'Testing...' : 'Test Connection'}
              </button>
              <button className="btn btn--primary" onClick={() => handleSave('tailscale_ollama')} disabled={busy === 'save' || !tailscaleHost}>
                {busy === 'save' ? 'Saving...' : 'Use Tailscale'}
              </button>
            </div>
          </div>
        )}

        {activeTab === 'openrouter' && (
          <div className="card">
            <div className="card__header"><span className="card__title">API (OpenRouter)</span></div>
            <div className="form-group">
              <label className="form-label">
                OpenRouter API Key {current?.has_openrouter_key && <span className="text-muted">(one already saved)</span>}
              </label>
              <input
                id="input-openrouter-key"
                className="form-input"
                type="password"
                placeholder="sk-or-..."
                value={openrouterKey}
                onChange={(e) => setOpenrouterKey(e.target.value)}
                autoComplete="off"
              />
            </div>
            <div style={{ display: 'flex', gap: '10px', marginTop: '12px' }}>
              <button className="btn btn--ghost" onClick={() => handleTest('openrouter')} disabled={busy === 'test' || !openrouterKey}>
                {busy === 'test' ? 'Testing...' : 'Test Connection'}
              </button>
              <button className="btn btn--primary" onClick={() => handleSave('openrouter')} disabled={busy === 'save' || !openrouterKey}>
                {busy === 'save' ? 'Saving...' : 'Use OpenRouter'}
              </button>
            </div>
          </div>
        )}

        {testResult && (
          <div className="card" style={{ borderColor: testResult.ok ? 'var(--status-green)' : 'var(--status-red)' }}>
            <span style={{ color: testResult.ok ? 'var(--status-green)' : 'var(--status-red)' }}>
              {testResult.ok ? '✓' : '✕'} {testResult.message}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: 'green' | 'amber' | 'red' }) {
  return (
    <div className={`metric${tone ? ` metric--${tone}` : ''}`}>
      <div className="metric__label">{label}</div>
      <div className="metric__value" style={{ fontSize: '16px' }}>{value}</div>
    </div>
  )
}
