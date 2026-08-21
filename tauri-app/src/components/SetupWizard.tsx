import React, { useEffect, useRef, useState } from 'react'
import { useAppStore } from '../store/appStore'
import { ROSTER_MODEL_TAGS } from '../lib/rosterModels'
import { isTauri, tauriInvoke, tauriListen } from '../lib/tauriBridge'

interface OllamaStatus {
  installed: boolean
  running: boolean
  version: string | null
}

type ModelState = 'pending' | 'pulling' | 'done' | 'error'
type WizardPhase =
  | 'checking'      // querying status on mount, wizard not visible yet
  | 'hidden'        // nothing to do — Ollama + every roster model already present
  | 'welcome'       // needs setup, waiting for the user to click "Begin Setup"
  | 'installing'    // running install_ollama()
  | 'pulling'       // running pull_model() for each missing tag, in order
  | 'done'
  | 'fatal'         // install_ollama itself failed — nothing left to automate

/** First-run guided setup: on desktop-app launch, checks whether Ollama and
 * every roster model this app's 16 agents need are already present, and if
 * not, walks through installing Ollama and pulling each model ONE BY ONE,
 * automatically, from a single "Begin Setup" click — replacing the old
 * flow where a user had to find Settings > Local Ollama and press five
 * separate "Pull" buttons themselves. All the actual work (checksum-
 * verified download, silent install, `ollama pull`) already existed in
 * src-tauri/src/ollama_installer.rs; this component is the orchestration
 * and progress UI on top of it — no backend command surface changed.
 *
 * Never blocks the app: every phase has a visible way out ("Skip for now" /
 * "Continue anyway"), and a completed/skipped run is remembered
 * (setupWizardCompleted, persisted) so this doesn't reappear every launch.
 * Re-run anytime from Settings > Local Ollama > "Re-run guided setup". */
export default function SetupWizard() {
  const { setupWizardCompleted, setSetupWizardCompleted } = useAppStore()
  const [phase, setPhase] = useState<WizardPhase>('checking')
  const [ollamaStatus, setOllamaStatus] = useState<OllamaStatus | null>(null)
  const [installProgress, setInstallProgress] = useState<{ stage: string; percent: number | null } | null>(null)
  const [modelState, setModelState] = useState<Record<string, ModelState>>(
    () => Object.fromEntries(ROSTER_MODEL_TAGS.map((t) => [t, 'pending' as ModelState]))
  )
  const [error, setError] = useState<string | null>(null)
  const cancelledRef = useRef(false)

  useEffect(() => {
    cancelledRef.current = false
    return () => { cancelledRef.current = true }
  }, [])

  // Initial check — only ever runs the heavier "does this machine need
  // setup" query once per mount, and only inside the native app (a plain
  // browser tab has no Tauri IPC bridge to check against).
  useEffect(() => {
    if (setupWizardCompleted || !isTauri()) {
      setPhase('hidden')
      return
    }
    let unlistenInstall: (() => void) | undefined
    let unlistenPull: (() => void) | undefined
    tauriListen('install-progress', (p) => setInstallProgress(p)).then((fn) => (unlistenInstall = fn))
    tauriListen('pull-progress', (p: { model_tag: string; stage: string }) => {
      if (p.stage === 'complete') {
        setModelState((prev) => ({ ...prev, [p.model_tag]: 'done' }))
      }
    }).then((fn) => (unlistenPull = fn))

    ;(async () => {
      try {
        const status = await tauriInvoke<OllamaStatus>('check_ollama_status')
        if (cancelledRef.current) return
        setOllamaStatus(status)

        let present: string[] = []
        if (status.running) {
          try {
            const res = await fetch('http://localhost:11434/api/tags')
            const data = await res.json()
            present = (data.models || []).map((m: { name: string }) => m.name)
          } catch {
            // Ollama reported "running" but the local API didn't answer in
            // time — treat as "can't confirm any models yet", not a hard
            // error; the pulling phase below will just re-check per model.
          }
        }
        const missing = ROSTER_MODEL_TAGS.filter(
          (tag) => !present.some((p) => p.startsWith(tag.split(':')[0]))
        )
        setModelState((prev) => {
          const next = { ...prev }
          for (const tag of ROSTER_MODEL_TAGS) next[tag] = missing.includes(tag) ? 'pending' : 'done'
          return next
        })

        if (status.installed && status.running && missing.length === 0) {
          setPhase('hidden')
          setSetupWizardCompleted(true)
        } else {
          setPhase('welcome')
        }
      } catch {
        // No Tauri bridge reachable (shouldn't happen given the isTauri()
        // guard above, but degrade the same way if it does) — never block.
        if (!cancelledRef.current) setPhase('hidden')
      }
    })()

    return () => { unlistenInstall?.(); unlistenPull?.() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function runSetup() {
    setError(null)
    try {
      if (!ollamaStatus?.installed) {
        setPhase('installing')
        await tauriInvoke('install_ollama')
        const status = await tauriInvoke<OllamaStatus>('check_ollama_status')
        setOllamaStatus(status)
        if (!status.installed) {
          setError('Install finished but Ollama still isn’t detected — try again, or install it yourself from ollama.com.')
          setPhase('fatal')
          return
        }
      }

      setPhase('pulling')
      for (const tag of ROSTER_MODEL_TAGS) {
        if (modelState[tag] === 'done') continue
        setModelState((prev) => ({ ...prev, [tag]: 'pulling' }))
        try {
          await tauriInvoke('pull_model', { modelTag: tag })
          setModelState((prev) => ({ ...prev, [tag]: 'done' }))
        } catch (e) {
          setModelState((prev) => ({ ...prev, [tag]: 'error' }))
          setError(`${tag}: ${e instanceof Error ? e.message : String(e)}`)
          // Keep going — one model failing (e.g. a flaky download) shouldn't
          // stop the rest of the roster from being pulled.
        }
      }
      setPhase('done')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setPhase('fatal')
    }
  }

  function finish() {
    setSetupWizardCompleted(true)
    setPhase('hidden')
  }

  if (phase === 'checking' || phase === 'hidden') return null

  const allDone = ROSTER_MODEL_TAGS.every((t) => modelState[t] === 'done')

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(15, 23, 42, 0.55)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px',
    }}>
      <div className="card" style={{ width: '520px', maxWidth: '100%', maxHeight: '85vh', overflowY: 'auto' }}>
        <div className="card__header"><span className="card__title">Set up AeroFleet's local AI models</span></div>

        {phase === 'welcome' && (
          <>
            <p style={{ color: 'var(--text-secondary)', fontSize: '14px', lineHeight: 1.5 }}>
              AeroFleet's 16-agent council runs on {ROSTER_MODEL_TAGS.length} distinct local models via
              {' '}<span className="mono">Ollama</span>. This machine is missing some of them. This wizard
              will {!ollamaStatus?.installed && 'install Ollama and '}pull each missing model one at a time —
              no manual commands to copy or paste.
            </p>
            <ul style={{ margin: '12px 0', paddingLeft: '20px', color: 'var(--text-secondary)', fontSize: '13px' }}>
              {ROSTER_MODEL_TAGS.map((tag) => (
                <li key={tag} className="mono" style={{ opacity: modelState[tag] === 'done' ? 0.5 : 1 }}>
                  {tag} {modelState[tag] === 'done' && '✓ already present'}
                </li>
              ))}
            </ul>
            {!ollamaStatus?.installed && (
              <div style={{ color: 'var(--text-muted)', fontSize: '12px', marginBottom: '12px' }}>
                Ollama's own installer runs a per-user install (no admin/elevation prompt needed on
                Windows or macOS) — this wizard doesn't need to be run as Administrator.
              </div>
            )}
            <div style={{ display: 'flex', gap: '10px', marginTop: '16px' }}>
              <button id="btn-begin-setup" className="btn btn--primary" onClick={runSetup}>Begin Setup</button>
              <button className="btn btn--ghost" onClick={finish}>Skip for now</button>
            </div>
          </>
        )}

        {(phase === 'installing' || phase === 'pulling' || phase === 'done' || phase === 'fatal') && (
          <>
            {!ollamaStatus?.installed || phase === 'installing' ? (
              <StepRow
                label="Install Ollama"
                state={phase === 'installing' ? 'pulling' : 'done'}
                detail={installProgress ? `${installProgress.stage}${installProgress.percent != null ? ` — ${installProgress.percent.toFixed(0)}%` : ''}` : undefined}
              />
            ) : (
              <StepRow label="Ollama" state="done" detail="already installed" />
            )}

            {ROSTER_MODEL_TAGS.map((tag) => (
              <StepRow key={tag} label={tag} state={modelState[tag]} mono />
            ))}

            {error && (
              <div style={{ color: 'var(--status-red)', fontSize: '13px', marginTop: '10px' }}>&#9888; {error}</div>
            )}

            <div style={{ display: 'flex', gap: '10px', marginTop: '16px' }}>
              {phase === 'fatal' && (
                <button className="btn btn--primary" onClick={runSetup}>Retry</button>
              )}
              {phase === 'done' && (
                <button id="btn-setup-done" className="btn btn--primary" onClick={finish}>
                  {allDone ? 'Done — continue to AeroFleet' : 'Continue anyway'}
                </button>
              )}
              {(phase === 'installing' || phase === 'pulling') && (
                <button className="btn btn--ghost" onClick={finish}>Run in background / skip for now</button>
              )}
              {phase === 'fatal' && (
                <button className="btn btn--ghost" onClick={finish}>Skip for now</button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function StepRow({ label, state, detail, mono }: { label: string; state: ModelState | 'done'; detail?: string; mono?: boolean }) {
  const icon = state === 'done' ? '✓' : state === 'pulling' ? <span className="spinner" style={{ width: 12, height: 12, display: 'inline-block' }} /> : state === 'error' ? '✕' : '–'
  const color = state === 'done' ? 'var(--status-green)' : state === 'error' ? 'var(--status-red)' : state === 'pulling' ? 'var(--accent)' : 'var(--text-muted)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '6px 0', fontSize: '13px' }}>
      <span style={{ color, width: '16px', textAlign: 'center' }}>{icon}</span>
      <span className={mono ? 'mono' : undefined} style={{ color: 'var(--text-primary)' }}>{label}</span>
      {detail && <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>{detail}</span>}
    </div>
  )
}
