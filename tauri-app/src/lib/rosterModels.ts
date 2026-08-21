/** The distinct Ollama model tags the 16-agent roster actually needs —
 * deduplicated from appStore.ts's DEFAULT_AGENTS (which maps each agent to
 * one of these 5 tags; several agents share a tag). Single source of truth
 * so Settings.tsx and SetupWizard.tsx can't drift out of sync with each
 * other or with the real roster — a prior version of Settings.tsx hardcoded
 * its own copy that listed 'mistral-small3.2' twice and never listed
 * 'mistral-large-3' at all, so the DGCA Compliance Advisor agent's model
 * was never offered for install. */
export const ROSTER_MODEL_TAGS = [
  'llama4:scout',
  'mistral-small3.2',
  'mistral-large-3',
  'gemma4:12b',
  'phi4-reasoning:plus',
] as const

export type RosterModelTag = (typeof ROSTER_MODEL_TAGS)[number]
