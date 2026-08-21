import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// ──────────────────────────────────────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────────────────────────────────────

export type AgentVerdict = 'GREEN' | 'YELLOW' | 'RED'
export type SystemStatus = 'idle' | 'running' | 'complete' | 'error'

export interface AgentStatus {
  id: string
  name: string
  domain: string
  model: string
  status: 'idle' | 'thinking' | 'done' | 'offline'
  lastVerdict?: AgentVerdict
  lastMessage?: string
}

export interface Telemetry {
  etaMinutes: number | null
  batteryMarginWh: number | null
  costUsd: number | null
  peakNoiseDb: number | null
  linkMargin_db: number | null
  cbfPass: boolean | null
  dgcaCompliant: boolean | null
}

export interface ScenarioResult {
  scenarioId: string
  scenarioName: string
  passed: boolean
  passCount: number
  totalCount: number
  attempt: number
  failedMetrics: string[]
}

export interface DispatchPlan {
  city: string
  origin_depot_id: string
  destination_lat: number
  destination_lon: number
  payload_kg: number
  priority: string
  deadline_minutes: number
  [key: string]: unknown
}

export type ExplanationStatus = 'NOT_REQUESTED' | 'PENDING' | 'RUNNING' | 'READY' | 'FAILED'

// ──────────────────────────────────────────────────────────────────────────────
// Store
// ──────────────────────────────────────────────────────────────────────────────

interface AppState {
  // Navigation
  activePage: string
  setActivePage: (page: string) => void

  // API Connection
  apiUrl: string
  setApiUrl: (url: string) => void
  apiConnected: boolean
  setApiConnected: (v: boolean) => void

  // LLM connection mode — non-secret display state only, persisted across
  // restarts; the actual settings (host, API key) live server-side via
  // aerofleet.agents.runtime_settings, not here.
  llmConnectionMode: 'local_ollama' | 'tailscale_ollama' | 'openrouter'
  setLlmConnectionMode: (mode: AppState['llmConnectionMode']) => void

  // Whether the first-run local-model Setup Wizard has been completed (or
  // explicitly dismissed) on this machine — persisted so it doesn't
  // reappear on every launch once Ollama + the roster models are in place.
  // See components/SetupWizard.tsx.
  setupWizardCompleted: boolean
  setSetupWizardCompleted: (v: boolean) => void

  // Static agent roster (who's configured, which model) — display only.
  // No live per-agent status exists: the council never runs synchronously
  // as part of a request, so there's nothing to "watch" in real time
  // (see docs/PATENT_NOVELTY.md Claim 1 and aerofleet/agents/
  // explanation_worker.py). An agent's actual output, when requested,
  // shows up asynchronously per-order — see CouncilViewer.tsx.
  agentRoster: AgentStatus[]

  // Telemetry from the most recently completed dispatch decision —
  // populated directly from POST /orders/{id}/dispatch's response
  // (instant; no LLM wait), not from any live stream.
  telemetry: Telemetry
  updateTelemetry: (t: Partial<Telemetry>) => void

  // Scenario Engine
  scenarioStatus: SystemStatus
  scenarioResults: ScenarioResult[]
  scenarioProgress: { total: number; passed: number; failed: number; current?: string }
  appendScenarioResult: (r: ScenarioResult) => void
  setScenarioProgress: (p: AppState['scenarioProgress']) => void
}

// Default 11-agent core roster + 5 trigger-based specialists
const DEFAULT_AGENTS: AgentStatus[] = [
  { id: 'DISPATCHER', name: 'Fleet Dispatcher', domain: 'dispatch', model: 'llama4:scout', status: 'idle' },
  { id: 'ROUTE', name: 'Route Planner', domain: 'route', model: 'mistral-small3.2', status: 'idle' },
  { id: 'BATTERY', name: 'Battery & Power Engineer', domain: 'battery', model: 'phi4-reasoning:plus', status: 'idle' },
  { id: 'AIRSPACE_SAFETY', name: 'Airspace Safety Officer', domain: 'safety', model: 'llama4:scout', status: 'idle' },
  { id: 'WEATHER', name: 'Weather Agent', domain: 'weather', model: 'gemma4:12b', status: 'idle' },
  { id: 'COMMS', name: 'Comms / RF Link Agent', domain: 'comms', model: 'mistral-small3.2', status: 'idle' },
  { id: 'COST', name: 'Cost Economist', domain: 'cost', model: 'phi4-reasoning:plus', status: 'idle' },
  { id: 'OPS', name: 'Ops Scheduler', domain: 'operations', model: 'gemma4:12b', status: 'idle' },
  { id: 'COMPLIANCE', name: 'DGCA Compliance Advisor', domain: 'compliance', model: 'mistral-small3.2', status: 'idle' },
  { id: 'AI_VALIDATOR', name: 'Autonomy Validator', domain: 'validation', model: 'llama4:scout', status: 'idle' },
  { id: 'PAYLOAD', name: 'Payload / Delivery Specialist', domain: 'payload', model: 'phi4-reasoning:plus', status: 'idle' },
  { id: 'conflict_avoidance', name: 'Conflict Avoidance Planner', domain: 'conflict_avoidance', model: 'llama4:scout', status: 'idle' },
  { id: 'battery_swap', name: 'Battery Swap Planner', domain: 'battery_swap_planning', model: 'phi4-reasoning:plus', status: 'idle' },
  { id: 'ai_governance', name: 'AI Governance Validator', domain: 'governance_legal', model: 'llama4:scout', status: 'idle' },
  { id: 'cyber_security', name: 'Cyber Security Auditor', domain: 'cybersecurity', model: 'llama4:scout', status: 'idle' },
  { id: 'edge_compute', name: 'Edge Compute Feasibility Agent', domain: 'edge_compute', model: 'phi4-reasoning:plus', status: 'idle' },
]

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
  // Navigation
  activePage: 'dashboard',
  setActivePage: (page) => set({ activePage: page }),

  // API
  apiUrl: 'http://localhost:8000',
  setApiUrl: (url) => set({ apiUrl: url }),
  apiConnected: false,
  setApiConnected: (v) => set({ apiConnected: v }),

  // LLM connection mode (display only — see note on the field above)
  llmConnectionMode: 'local_ollama',
  setLlmConnectionMode: (mode) => set({ llmConnectionMode: mode }),

  // Setup Wizard
  setupWizardCompleted: false,
  setSetupWizardCompleted: (v) => set({ setupWizardCompleted: v }),

  // Agent roster (static)
  agentRoster: DEFAULT_AGENTS,

  // Telemetry
  telemetry: {
    etaMinutes: null, batteryMarginWh: null, costUsd: null,
    peakNoiseDb: null, linkMargin_db: null, cbfPass: null,
    dgcaCompliant: null,
  },
  updateTelemetry: (t) => set((s) => ({ telemetry: { ...s.telemetry, ...t } })),

  // Scenarios
  scenarioStatus: 'idle',
  scenarioResults: [],
  scenarioProgress: { total: 0, passed: 0, failed: 0 },
  appendScenarioResult: (r) =>
    set((s) => ({ scenarioResults: [...s.scenarioResults, r] })),
  setScenarioProgress: (p) => set({ scenarioProgress: p }),
    }),
    {
      name: 'aerofleet-settings',
      // Only persist small, non-secret display state — everything else
      // (debate messages, agent roster, scenario results) stays ephemeral
      // and resets to defaults on reload, same as before this change.
      partialize: (s) => ({
        apiUrl: s.apiUrl,
        llmConnectionMode: s.llmConnectionMode,
        setupWizardCompleted: s.setupWizardCompleted,
      }),
    }
  )
)
