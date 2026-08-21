/** The distinct Ollama model tags the 16-agent roster actually needs —
 * deduplicated from appStore.ts's DEFAULT_AGENTS (which maps each agent to
 * one of these tags; several agents share a tag). Single source of truth
 * so Settings.tsx and SetupWizard.tsx can't drift out of sync with each
 * other or with the real roster.
 *
 * Only 4 tags, not 5: `mistral-large-3` was here until it was traced back
 * to aerofleet/agents/factory.py's DEFAULT_MODEL_MAP, whose own comment
 * (dated 2026-08-09) explains it isn't actually a locally-pullable Ollama
 * model — Ollama's `mistral-large-3` is a 675B-parameter *cloud-only* tag
 * (`mistral-large-3:675b-cloud`), not something any local GPU runs. The
 * backend already swapped its COMPLIANCE agent to `mistral-small3.2`
 * because of this; this list, appStore.ts's DEFAULT_AGENTS, and
 * AI_MODEL_SETUP_GUIDE.md had not been updated to match and were telling
 * people to `ollama pull` a tag that would never work. (The tag still
 * exists, legitimately, in aerofleet/agents/openrouter_agent.py's
 * OpenRouter translation table — that's a real, cloud-hosted model over
 * OpenRouter's API, a completely different code path from local Ollama.) */
export const ROSTER_MODEL_TAGS = [
  'llama4:scout',
  'mistral-small3.2',
  'gemma4:12b',
  'phi4-reasoning:plus',
] as const

export type RosterModelTag = (typeof ROSTER_MODEL_TAGS)[number]
