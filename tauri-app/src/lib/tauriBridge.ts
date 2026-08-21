/** Tauri's IPC bridge (window.__TAURI_INTERNALS__) only exists inside the
 * native app window, not a plain browser tab — these helpers no-op/throw
 * gracefully outside it so any page/component that touches native-only
 * commands (Ollama install/pull, first-run setup) degrades instead of
 * crashing when previewed in an ordinary browser. Shared by Settings.tsx
 * and SetupWizard.tsx so both talk to the same handful of Tauri commands
 * declared in src-tauri/src/ollama_installer.rs the same way. */

export function isTauri(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
}

export async function tauriInvoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  const { invoke } = await import('@tauri-apps/api/core')
  return invoke<T>(cmd, args)
}

export async function tauriListen(event: string, handler: (payload: any) => void): Promise<() => void> {
  const { listen } = await import('@tauri-apps/api/event')
  return listen(event, (e) => handler(e.payload))
}
