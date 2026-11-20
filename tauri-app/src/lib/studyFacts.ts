// Every number the Overview page shows, with the exact text it comes from.
//
// `from.file` is a path from the repository root (or `main` / `supp` for the paper's main text and supplement),
// `from.text` a passage that must appear in it word for word. docs/paper/check_numbers.py checks every pair, so if the
// paper or a result changes, the check fails until this file is brought back in line. Keep the passages short and
// copy them exactly (LaTeX included); write each backslash twice.

export interface Source { file: string; text: string }

export interface Finding {
  id: string
  title: string                 // the finding in plain words
  big: string                   // the headline number
  bigLabel: string
  detail: string                // one or two sentences, no more than the source says
  bars?: { label: string; value: number; kind: 'result' | 'reference' }[]   // drawn on a 0..1 scale
  refLine?: { value: number; label: string }
  meaning: string               // what it means for an operator
  from: Source[]
}

export const STUDY = {
  logs: '479,547',
  crashLogs: '590',
  from: [{ file: 'main', text: '590 crash logs from a 479,547-flight PX4 archive' }] as Source[],
}

// The public PX4 Flight Review archive, from the whole index down to what the study used (paper Section 3, Fig. 1).
export interface ArchiveStep { id: string; big: string; count: number; label: string; note: string; from: Source[] }
export const ARCHIVE: ArchiveStep[] = [
  {
    id: 'index',
    big: '479,547', count: 479547, label: 'flight logs in the public archive',
    note: 'Every log uploaded to PX4 Flight Review, as indexed on 20 October 2026.',
    from: [{ file: 'main', text: 'index on 20 October 2026: 479,547 logs' }],
  },
  {
    id: 'real',
    big: '442,929', count: 442929, label: 'from real aircraft, not simulators',
    note: 'Flown by 38,320 distinct vehicles.',
    from: [{ file: 'main', text: 'of which 442,929 came from real hardware rather than simulation, from 38,320 distinct vehicle identifiers' }],
  },
  {
    id: 'normal',
    big: '21,112', count: 21112, label: 'real flights their pilots rated good or great',
    note: 'The pool that comparison flights were drawn from.',
    from: [{ file: 'main', text: 'Logs & 520 & 21,112' }],
  },
  {
    id: 'crash',
    big: '590', count: 590, label: 'logs rated a crash by the uploader',
    note: '402 blamed on the aircraft and 188 on the pilot, by the uploader; 520 from real aircraft.',
    from: [{ file: 'main', text: 'A total of 590 logs carry an uploader crash rating (402 aircraft-caused, 188 pilot-caused)' }],
  },
  {
    id: 'forum',
    big: '148', count: 148, label: 'crashes diagnosed by PX4 experts on the forum',
    note: 'An independent second opinion on what went wrong.',
    from: [{ file: 'main', text: 'Expert forum cases & 148 real crash threads' }],
  },
]
export const BASE_RATE = {
  big: '0.741%',
  text: 'Only 284 of the 38,320 vehicles have a crash-rated log from real hardware. When crashes are this rare, even an accurate alarm raises far more false alarms than true ones.',
  from: { file: 'supp', text: 'empirical vehicle crash base rate of 0.741\\% (284/38,320)' } as Source,
}

// The use case: agricultural drone service providers in India. Public facts, each with the page it comes from.
export interface WebSource { name: string; url: string }
export const USE_CASE: { big: string; label: string; text: string; source: WebSource }[] = [
  { big: '15,000', label: 'drones for women self-help groups',
    text: 'Namo Drone Didi (approved 29 November 2023, outlay Rs 1,261 crore) gives drones to 15,000 women self-help groups, which rent crop-spraying and nano-fertiliser flights to farmers.',
    source: { name: 'PIB, Ministry of Agriculture & Farmers Welfare', url: 'https://pib.gov.in/PressReleasePage.aspx?PRID=1980683' } },
  { big: '5 + 10 days', label: 'of training for each pilot',
    text: 'Pilots are trained for 5 days to fly, plus 10 days for applying nutrients and pesticides: new operators, not career pilots.',
    source: { name: 'PIB, Ministry of Agriculture & Farmers Welfare', url: 'https://pib.gov.in/PressReleasePage.aspx?PRID=1980683' } },
  { big: '7 days', label: 'to report spraying data',
    text: 'Under the crop-protection drone SOP, operators submit spray monitoring data to the Central Insecticide Board within seven days of spraying.',
    source: { name: 'Ministry of Agriculture SOP for drone pesticide application (2021)', url: 'https://pib.gov.in/PressReleasePage.aspx?PRID=1783937' } },
  { big: 'Mandatory', label: 'third-party insurance',
    text: 'The Drone Rules 2021 require third-party insurance for every drone above nano class, so after an accident someone will ask whose fault it was.',
    source: { name: 'Drone Rules 2021 (Digital Sky)', url: 'https://digitalsky.dgca.gov.in/assets/files/UasRules.pdf' } },
]
export const TOP_CAUSE = {
  big: '26 of 94',
  text: 'In our study, tuning or configuration was the cause PX4 experts named most often for aircraft-caused crashes, ahead of GPS, compass or estimator problems. Settings are the first thing AeroFleet checks.',
  from: [{ file: 'main', text: 'Tuning or configuration was the cause named most often (26 of 94' }] as Source[],
}

export const REGULATION: { where: string; rule: string; from: Source }[] = [
  { where: 'EU and UK', rule: 'Operators in the specific category keep records of operations, maintenance and personnel for at least three years.',
    from: { file: 'main', text: 'for at least three years' } },
  { where: 'India', rule: 'An accident must be reported within 48 hours.', from: { file: 'main', text: 'reported within 48 hours' } },
  { where: 'United States', rule: 'An accident must be reported within ten days.', from: { file: 'main', text: 'United States within ten days' } },
]

export const FINDINGS: Finding[] = [
  {
    id: 'blame',
    title: 'Logs cannot say whether the pilot or the aircraft caused a crash',
    big: '0.47', bigLabel: 'balanced accuracy on 112 held-out crashes',
    detail: 'A fixed rule, declared in advance with a pass mark of 0.70, scored at chance on crashes it had not seen. Trained models and a published log checker did no better.',
    bars: [{ label: 'Our rule', value: 0.47, kind: 'result' }, { label: 'Pass mark', value: 0.70, kind: 'reference' }],
    refLine: { value: 0.5, label: 'chance' },
    meaning: 'A tool that prints "pilot error" or "aircraft fault" from a log is guessing. AeroFleet shows the evidence and names no cause.',
    from: [{ file: 'main', text: 'A fixed rule reached 0.47 balanced accuracy on 112 held-out crashes (pass mark 0.70)' }],
  },
  {
    id: 'testing',
    title: 'Impressive accuracy can come from how a model is tested',
    big: '0.94 → 0.63', bigLabel: 'AUC of a published fault detector, once whole days were held out',
    detail: 'We re-implemented a published fault detector. It looked excellent when test windows were drawn at random, and fell much closer to chance when whole days were kept apart. Across 32 evaluation settings, crash-detection AUC moved by 0.21.',
    bars: [{ label: 'Random test windows', value: 0.94, kind: 'result' }, { label: 'Whole days held out', value: 0.63, kind: 'result' }],
    refLine: { value: 0.5, label: 'chance' },
    meaning: 'Ask how any diagnostic was tested before trusting its accuracy. The paper gives a ten-item checklist for exactly this.',
    from: [{ file: 'main', text: 'fell from AUC 0.94 to 0.63 once whole days were held out' }, { file: 'main', text: 'AUC fell by 0.21 [0.06, 0.34]' },
           { file: 'main', text: 'ten-item checklist' }],
  },
  {
    id: 'labels',
    title: 'Even "crash" labels in public archives are shaky',
    big: '7–50%', bigLabel: 'of crashes the usual tilt rule misses, depending on who judges',
    detail: 'Independent reviewers disagreed on whether a log even contains the crash, and pilot-rated logs show a crash-like tilt half as often as aircraft-rated ones.',
    meaning: 'Labels from uploaders cannot be the ground truth for an automatic verdict. AeroFleet never uses them.',
    from: [{ file: 'main', text: 'misses roughly 7--50\\% of crashes' }],
  },
  {
    id: 'own',
    title: 'No warning in a drone\'s own history',
    big: '0.48', bigLabel: 'rank of the crash flight against the drone\'s own earlier flights (0.50 = no difference)',
    detail: 'Across 61 drones, the flight that crashed vibrated no more than the same drone\'s earlier flights (p = 0.67).',
    bars: [{ label: 'Crash flight vs own earlier flights', value: 0.48, kind: 'result' }],
    refLine: { value: 0.5, label: 'no difference' },
    meaning: 'A per-flight "crash coming" alarm would not be supported. AeroFleet shows each flight against the drone\'s history as context, not as a warning.',
    from: [{ file: 'main', text: '$\\bar r=0.48$, 95\\% CI 0.38--0.58, $p=0.67$, 61 drones' }],
  },
  {
    id: 'rough',
    title: 'Rougher drones crashed more often, but not enough to screen on',
    big: '1.77×', bigLabel: 'lift of a top-10% vibration screen against 412 non-crash drones (interval 1.00 to 2.60)',
    detail: 'Drones that later crashed vibrated more than matched drones on ordinary flights (rank 0.67 over 60 sets), but the effect weakened under stricter tests, and as a screen it was not shown to beat random inspection.',
    bars: [{ label: 'Later-crashed vs matched drones', value: 0.67, kind: 'result' }],
    refLine: { value: 0.5, label: 'no difference' },
    meaning: 'Vibration is useful context for an inspector, so AeroFleet shows where each drone stands among comparable drones, without a pass/fail line.',
    from: [{ file: 'main', text: 'a top-decile threshold gave a lift of only $1.77\\times$ [1.00, 2.60]' },
           { file: 'main', text: 'rank 0.67; airframe-clustered $p=0.012$; site-weighted $p=0.076$' }],
  },
  {
    id: 'llm',
    title: 'AI review panels added errors',
    big: '97', bigLabel: 'real crash cases where no language-model panel beat a plain rule',
    detail: 'Small language models, alone or as a voting panel, did not beat a fixed rule, and one compromised reviewer moved most of the panel\'s verdicts.',
    meaning: 'Every number in AeroFleet comes from fixed, testable code. No AI model takes part in any decision.',
    from: [{ file: 'main', text: 'On 97 real crash logs' }, { file: 'main', text: 'no panel beat the rule either' }, { file: 'main', text: 'One compromised reviewer moved most panel verdicts' }],
  },
]

// What the tool itself was measured to do (research/results/px4_log_study/).
export const TOOL_TESTS: { what: string; result: string; from: Source }[] = [
  { what: 'Planned-versus-flown check, 40 real PX4 flights with a deviation injected',
    result: 'Found 36 of 40 sideways deviations of 35 m and 39 of 40 upward deviations of 20 m, with 0 false alarms on the 40 untouched flights (plans with a waypoint every 5 s).',
    from: { file: 'research/results/px4_log_study/injection_reconcile.md', text: '| Same, plan with a waypoint every 5 s instead of 10 s | **0/40 (0%)** | 36/40 (90%) | 38/40 (95%) | 39/40 (98%) |' } },
  { what: 'Same check, plans with a waypoint every 10 s',
    result: '9 of 40 untouched flights gave a false alarm: fast flights cutting the corners of plans built from the track.',
    from: { file: 'research/results/px4_log_study/injection_reconcile.md', text: '| **Whole-flight ordered alignment (now the default)** | 9/40 (22%)' } },
  { what: 'Describe-a-problem search, 96 expert-diagnosed crashes, each held out in turn',
    result: 'Its best guess matched the expert in 22% of cases, below the 27% of always guessing the most common cause. So the screen orders its checklist by how often experts found each cause, and says so.',
    from: { file: 'research/results/px4_log_study/troubleshoot_loo_settled.md', text: '| Top-1 baseline (most frequent cause) | 26 of 96 | 27% | 19-37% |' } },
]

export const NOT_YET: string[] = [
  'No operator has used AeroFleet on their own fleet yet. A prospective test with a partner fleet is declared but not run.',
  'There is no evidence yet that using it reduces crashes.',
  'The false-alarm rate on real missions is unknown: the public archive holds only 6 distinct missions with their plans.',
  'It has been checked on a desktop. The VR headset path has not been tested on a real headset.',
]
export const NOT_YET_FROM: Source[] = [
  { file: 'research/results/px4_log_study/real_mission_reconcile.md', text: 'Distinct missions: 6.' },
]
