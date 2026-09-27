# What makes AeroFleet a publishable research contribution

This is the gap analysis: the official standards and methods a reviewer in UAS / UTM / safe-AI
will expect, where AeroFleet already stands, and the concrete work left. Standard numbers and
titles below are the ones I'm confident of; **check the exact clause text of every standard before
citing it**, since editions get revised.

## The claim the paper should make

> An LLM multi-agent council can be used in a safety-critical drone fleet **only** as an explanation
> layer bounded by a deterministic run-time-assurance gate; its causal claims are verified against
> the gate's own geometry before an operator sees them, and the VR tabletop is where that
> verification happens.

Everything below either substantiates that claim or makes it measurable.

## 1. Official frameworks to align with, by where AeroFleet stands

| standard / framework | what it is | AeroFleet today | to add |
|---|---|---|---|
| **ASTM F3269** (run-time assurance for complex functions) | bounding an untrusted complex function with a simple verified monitor and a recovery path | the CBF gate *is* an RTA monitor; the LLM council is the complex function | map the architecture to F3269's terms (monitor, safety-critical boundary, recovery). This is the strongest "official" anchor for the main claim |
| **ASTM F3548-21** (UTM USS interoperability) | strategic coordination via *operational intents*, conflict detection, conformance monitoring | 4D trajectories + 2-min conflict forecast (`fleet/conflict_forecast.py`) | express each flight as an F3548 operational intent (4D volumes with time bounds), report conflicts in its terms, add conformance monitoring (actual vs. intent) |
| **ASTM F3411-22a** (Remote ID) | broadcast/network identification | not implemented | emit Remote ID messages from simulated drones; state it in the regulatory domain |
| **JARUS SORA 2.5** | risk assessment: ground-risk class, air-risk class, SAIL, OSOs | not implemented | compute GRC/ARC/SAIL per mission from population density (ground risk) and zone/altitude (air risk); show it on the board and in the compliance report |
| **EUROCAE ED-269** (geographical zone data) | a standard format for UAS geo-zones | zones are circles in `city/restricted_sites.py` | import/export zones as ED-269 data; cite the source of each zone |
| **India: Drone Rules 2021** (G.S.R. 589(E)) + **Drone (Amendment) Rules 2022**, **Digital Sky**, **National UTM Policy Framework (MoCA, 2021)** | the governing regulation: UIN, remote pilot certificate, green/yellow/red zones, 400 ft AGL, NPNT | green/yellow/red zones, 120 m ceiling, UIN registry, FC compliance check (59 checks) | a clause-by-clause compliance matrix (rule → AeroFleet check → status); replace the hand-placed zones with Digital Sky airspace-map zones for Pune/Mumbai |
| **ICAO Doc 10019** (RPAS manual), **ISO 21384-3** (UAS operational procedures) | international operational framing | not referenced | cite them for operational procedures (pre-flight checks ⇒ the FC compliance check) |
| **ICAO ADREP / CICTT occurrence categories** | the standard taxonomy for aviation occurrences | own 7-factor taxonomy (`agents/incident_taxonomy.py`) | map each factor to CICTT categories so the forensics output is comparable with real occurrence reporting |
| **NIST AI RMF 1.0**, **EASA AI Concept Paper (Issue 2)** | governance and assurance of ML components in aviation | the LLM is kept off the decision path (architectural) | a short assurance case: hazards of the LLM layer, mitigations (gate, claim check, confidence not trusted), residual risk |

## 2. Evidence reviewers will ask for

| item | status | what's needed |
|---|---|---|
| Formal safety of the gate | done — `cbf_formal_safety.md` | keep the proofs scoped to what the gate checks |
| LLM evaluation at scale | done — 985 cases, macro-F1 0.468, diagnosed (`real_llm_results.md`) | the v2 experiment below, on **unseen** cases, with CIs and paired tests |
| A non-circular benchmark | **missing** | today every label is a function of the violated margins, so a constraint map solves it. Add cases whose cause is only visible in narrative telemetry (link RSSI dropouts, gust logs, battery-trend degradation) with no margin breach; that's where LLM reasoning is actually tested |
| Baselines | partial | evidence-blind baselines exist; add a rule-based baseline and a larger model (e.g. a 14B) to position the 3.8B result |
| Real-world validation | missing | **ArduPilot SITL** end to end (dispatch → MAVLink → flown path vs. planned 4D trajectory), then one **HIL** run on a real Pixhawk with the FC compliance check |
| User study (VR) | protocol only (`user_study_protocol.md`) | ethics/IRB approval; a within-subjects comparison of VR claim-check vs. 2-D report on error-detection rate and time; **NASA-TLX** and **SUS** questionnaires |
| Reproducibility | mostly (`reproducibility.md`) | archive code + data + results with a **DOI (Zenodo)**; a **datasheet** for the scenario dataset and a **model card** for the council configuration |
| Statistics | partial | pre-registered hypotheses, 95% CIs, paired tests (McNemar), multiple-comparison correction; the v2 harness below reports CIs and McNemar |

## 3. Improving phi4-mini from its 1,000-case errors — the protocol

Harness: `research/forensics_v2/` (strategy switches in `aerofleet/agents/forensics_strategy.py`).

- **No test leakage.** Few-shot examples come from the *original* manifest (training split). Evaluation
  uses a freshly generated plan (seed 20260927), stratified like the study, plus a **hard** variant
  in which every non-violated core margin is a near-miss (0.1–3 units from its limit).
- **Conditions, each adding one fix:**

| condition | fix | targets (measured in the 1,000-case study) |
|---|---|---|
| C0 | v1 prompt + regex extractor | reproduces the baseline |
| C1 | valid-JSON prompt, robust extractor, factor pinning | 82% of misses (parse), factor-name drift |
| C2 | + JSON-schema constrained decoding (reasoning inside the JSON) | parse failures at the decoding level |
| C3 | + constraint-ownership map | 61% of false alarms (cross-attribution) |
| C4 | + error-derived few-shot examples | 73% false-alarm rate on controls |

- **Reported per condition:** macro-F1 with a 95% bootstrap CI, parse-failure rate, cross-attribution
  false-positive rate, control false-alarm rate, a paired McNemar test against C0, and latency.
  Raw agent text is saved for every call, so a future parser change can be re-scored without
  re-running the model.
- **Honest caveat for the paper:** C3 gives the model the system's own constraint schema. On a
  benchmark whose labels come from that schema, C3/C4 will look very strong. That shows *grounding
  works*, not that the model reasons better; the non-circular benchmark (section 2) is what tests the
  latter.
- **After the prompt-level results:** optional LoRA fine-tuning of phi4-mini on the training split
  (MLX on Apple Silicon, or a free GPU notebook), evaluated on the same unseen sets, and confidence
  calibration (the study found ≥0.9-confidence claims are right only 51% of the time).

## 4. Suggested order

1. Run forensics v2 (C0–C4 on eval, C0/C4 on hard) and write up.
2. Build the non-circular benchmark slice; re-run C0 and C4.
3. ArduPilot SITL validation of the 4D trajectory + conflict forecast.
4. F3269 / F3548 / SORA mappings and the Drone Rules compliance matrix.
5. User study (after ethics approval).
6. Zenodo archive, datasheet, model card; manuscript for *Drones* (MDPI).
