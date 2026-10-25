# AeroFleet: handoff for whoever continues (any AI assistant or person)

Last updated 25 October 2026. Read this whole file before changing anything. It replaces the need for any earlier
chat history. Older context files (`docs/aerofleet2/CONTEXT.md`, `docs/aerofleet2/MASTER_PLAN.md`) are still useful
background, but where they disagree with this file, this file is right.

---

## 1. What this project is, in one paragraph

**AeroFleet** is an open-source, ground-side assurance tool for PX4 and ArduPilot drone fleets, plus a research paper
built on a study of 479,547 public PX4 flight logs. The tool reads files an operator already has (parameter files,
mission files, flight logs); it contacts no aircraft and **calls no AI model in any decision**. The study found that
flight logs **cannot** tell whether a crash was the pilot's or the aircraft's fault, but drones that later crashed
were rougher (more vibration) on ordinary flights than matched drones. So the tool shows evidence and ranks drones;
it never names a crash cause. The paper's title: *"Evidence, not verdicts: what 479,547 public PX4 flight logs can and
cannot tell a drone fleet operator"*, targeted at **Reliability Engineering & System Safety** (Elsevier).

People: Dr. Nagesh Chougule (corresponding author, nkc.mech@coeptech.ac.in), Vibhav Ambardekar, Aditya Pathare
(main developer; this machine's user), Atharv Waghmare, Shreyash Pawar, Piyush Bhamare. Department of Mechanical
Engineering, COEP Technological University, Pune, India. Repo: https://github.com/AdityaPathare46/aerofleet (branch
`main`).

---

## 2. Rules that must not be broken

These come from the project owner. Keep to them.

1. **No AI/LLM in the product's decision path.** Checks are deterministic code. The old "AI council" and LLM review
   panel are research artefacts only (`aerofleet/assurance/review_panel.py`, `research/panel_eval/`).
2. **Every test is declared before it is run.** Write the hypothesis, data selection and pass mark into the script's
   docstring, **commit and push that first**, then run it, then report the result whatever it is. Negative results go
   into the paper and README. This is the paper's main methodological claim; breaking it breaks the paper.
3. **Never overclaim.** If something was only checked on a desktop, say so. If a result is post hoc, say so.
4. **Never commit**: `aerofleet/README.md`, `aerofleet/parse_results.py`, `aerofleet/results (1).jsonl`,
   `docs/SPACE_MISSION_ARCHITECT_README.md`, `research/aerofleet_midterm_review.pptx` (owner's untracked files),
   reference PDFs, forum post text, review spreadsheets (`research/px4_log_study/forum_review/`,
   `label_review/` are git-ignored), raw logs, secrets.
5. **Never put tokens or passwords in files or command lines.** The local test account is in `.env`
   (`AEROFLEET_DEV_TEST_*`); use it only on localhost. Do not copy the Cesium token anywhere.
6. **Ask before large downloads** (more than about 1 GB).
7. Commit messages end with a co-author line for the AI used (Claude used
   `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`).
8. Writing style the owner wants: plain, short, critical, data-backed. Rate work honestly.

**macOS/exFAT quirk:** the repo is on an exFAT drive, so macOS creates `._*` files inside `.git/objects/pack/`, and git
prints many `non-monotonic index` errors. They are harmless. Clean them after a commit/push with:
`find .git/objects/pack -name '._*' -size -5k -delete`

---

## 3. How to run everything

```bash
./start.sh            # sets up .venv + npm packages if missing, starts API (:8000) and app (:1420), opens browser
./start.sh api        # API only
.venv/bin/python -m pytest -q --no-cov tests/unit tests/integration     # full suite: 657 pass (about 3 min)
cd tauri-app && npx tsc --noEmit -p .                                   # typecheck the app
```

Sign in to the app (register a local test user, or use the `.env` test account), open **Fleet Assurance**.
API docs: http://localhost:8000/docs (assurance endpoints under `/api/v1/assurance`).

Paper build (needs `tectonic`):

```bash
cd docs/paper/latex && tectonic -X compile main.tex && tectonic -X compile cover_letter.tex
cp main.pdf ../submission/manuscript.pdf; cp cover_letter.pdf ../submission/
```

Word version (needs `pandoc` from Homebrew and `python-docx` in `.venv`): build the PDF with
`tectonic -X compile --keep-intermediates main.tex` (the converter reads table/figure/section numbers from
`main.aux`), then `.venv/bin/python docs/paper/make_docx.py` writes `docs/paper/submission/manuscript.docx`.
The LaTeX is the master copy; regenerate the Word file after every edit.

The Overleaf zip (`docs/paper/submission/latex_source_for_overleaf.zip`) must contain `main.tex`, `refs.bib`,
`cover_letter.tex`, `highlights.txt` and `figures/` with every figure `main.tex` includes. Rebuild it after edits.

---

## 4. Where things are

The repository was cleaned on 25 Oct 2026 (git tag `pre-cleanup-2026-10-25` holds everything that was removed;
large untracked leftovers were moved to `/Volumes/One Touch/AeroFleet_archive_2026-10-25/`, nothing deleted).

**Core (work here):**

| Path | What |
|---|---|
| `aerofleet/assurance/` | The product's logic: `params`, `drift`, `static_checks`, `flightlog` (ArduPilot + PX4 readers), `reconcile` (planned vs flown), `evidence` (timeline), `vibration` (fleet ranking), `deconflict` (+ `rehearsal()` for 3D), `wind`, `ledger` (signed record), `report_html`, `troubleshoot` (description search), `data/fault_cases.json` |
| `aerofleet/api/routes/assurance.py` | All assurance HTTP endpoints; `auth.py` sign-in; `vr.py` headset pairing |
| `tauri-app/src/pages/FleetAssurance.tsx` | Main screen: baseline/drift, flight review, troubleshooting card, deconflict + "Rehearse in 3D", wind check, signed record |
| `tauri-app/src/pages/VRSafetyView.tsx`, `src/components/vr/` | 3D tabletop: Flight replay (`Flight.tsx`), Mission rehearsal (`Rehearsal.tsx`), Live swarm (legacy, simulated). WebXR for the Quest browser |
| `unity/AeroFleetVR/` | Mirror of the Quest app scripts (compiles, never run on a headset) |
| `tools/verify_ledger.py` | Standalone verifier for the signed record |
| `research/px4_log_study/`, `research/results/` | Every study script (docstring = declaration) and every result; see `research/README.md` |
| `research/protocols/` | Declared future studies |
| `docs/paper/` | `latex/` (master: `main.tex`, `refs.bib`, cover letter, highlights), `figures/`, `submission/` (PDF, Word, Overleaf zip), `make_docx.py`, `critical_review.md` |
| `docs/background/` | Operator, regulation and accident research behind the use case |
| `tests/test_*assurance*`, `tests/integration/test_missions_compliance_api.py`, `test_vr_pairing_api.py` | Tests of the product |
| `config/`, `data/components.json`, `alembic/` | Runtime config defaults (the config loader reads `config/default.yaml`), component data, DB migrations |

**Legacy (the earlier AI dispatch product; kept only because the app/API still import it; do not extend):**
`aerofleet/` outside `assurance/`, `api/`, `data/`, `utils/` (agents, council, dispatch, safety, swarm, hardware, city,
fleet, ...), `scenario_engine/`, `agent_memory/`, app pages other than Fleet Assurance and VR (hidden behind Settings ▸
Show legacy screens), and the tests that cover them. Removing it fully is a separate refactor; ask the owner first.

**Outside the repo:**

| Path | What |
|---|---|
| `/Volumes/One Touch/AeroFleet_px4_data/` | Raw data, not in git: `dbinfo.json` (archive index), logs in `h/`, `within/`, `rough/`, `crash/`, `newer/`, `forum_logs/`, CSV selections, `forum_cache/` (thread JSON) |
| `/Volumes/One Touch/AeroFleet_reference_papers/` | Reference PDFs with a README index (copyrighted; never commit or upload) |
| `/Volumes/One Touch/AeroFleet_paper_package_2026-10-25.zip` | Everything for the paper in one zip (manuscript PDF/Word, LaTeX, references, supplementary) |
| `/Volumes/One Touch/AeroFleet_archive_2026-10-25/` | Untracked leftovers moved out during cleanup (old datasets 24 GB, old venv, caches) |

## 5. What the study found (numbers to keep consistent everywhere)

| Question | Result | File |
|---|---|---|
| Q1 settings differ crash vs normal? | No: protection disabled 51% vs 46%, p = 0.63 (exploratory contrast: pilot-caused 70% vs aircraft 41%, p = 0.052, BA 0.647, 43% missing defaults) | `summary.md` |
| Q2 pilot vs aircraft from logs? | No: rule BA 0.57 dev, **0.47 held-out**; logistic model Task B AUC 0.408 (full n=148, 95% bootstrap CI [0.288, 0.530], upper bound 0.510) and 0.466 (constant n=89 subset, CI [0.325, 0.607], upper bound 0.584); 1,000-permutation null mean 0.497, 95% detection threshold 0.660 (null interval 0.313-0.660, p = 0.509); observed model upper bounds (0.510-0.619) lie safely below 0.660 detection threshold; boosted stumps 0.430 -> 0.413, depth-3 trees 0.595 -> 0.553 (10s), 0.548 (30s); two-class expert validation on 43 downloadable logs (38 aircraft, 5 pilot) yielded **48.6% error rate** on decided cases (BA 0.381, 95% CI [0.20, 0.59], chance 0.50 not excluded; pilot recall 1 of 5, Wilson CI 3.7-71.0%; cross-tabulation: 9 uploader `crash_sw_hw` 100% agreement, 0 `crash_pilot` uploaded) | `holdout.md`, `pilot_vs_drone.md`, `leak_curve.md`, `forum_expert_labels.md` |
| Q3a crash window leakage | Model AUC 0.88 to 0.86 (constant-subset n=213: 0.895 to 0.868; duration alone yields AUC 0.662 at 0s and 0.634 at 10s, correlating with tilt $\rho=+0.47$ and stick deflection $\rho=+0.36$); paired tuning check firing fell 7/9 to 1/9 (unadjusted McNemar p = 0.03125, Bonferroni p ~ 0.16; other 4 checks had low baseline sensitivity <= 25%); within-drone model substantially attenuates separation to Group-CV AUC 0.580 [0.528, 0.633], mean pairwise AUC 0.605 (67 drones, 372 flights) | `leak_curve.md`, `test_flight_check*_settled.md`, `within_drone.md` |
| Q3b within same drone | No warning: vibration rank 0.48, p = 0.67 (61 drones; 95% CI upper bound 0.58 rules out effect of between-drone magnitude) | `within_drone.md` |
| Q3c between drones (the positive result) | Crashed drones rougher: **0.67, 95% CI 0.57-0.77, p = 0.0023, Holm 0.016** (60 sets); top-rank 33/60 (55.0%) vs Poisson-binomial null 40.3% (p = 0.0137; lift 1.37x over null rate, relative risk 3.58x over unflagged); Q3 flag 38/60 (63.3%, older 66.7%, newer 50.0%); matched-set PPV 0.96-1.04% (lift 1.40x, 96-104 insp./crash) across screenable multi-flight base rate (0.689%, 182/26,421) and fleet vehicle base rate (0.741%, 284/38,320); stratum-matched fleet-ref: top decile (10% flag) PPV 2.26-2.47% [1.48-3.33%] (relative risk 4.50x, lift 3.28-3.33x, 40.5-44.2 insp./crash), top quartile (25% flag) PPV 1.37-1.48% [1.01-1.88%] (relative risk 3.00x, lift 1.99-2.00x, 67.5-73.1 insp./crash) | `rough_drone.md` |
| Robustness (post hoc) | Held with same airframe, without crash-day flights, duration-adjusted; mainly older estimator metric (48 sets) | `sensitivity*.md` |
| Newer metric replication (declared) | **Inconclusive: independent 10 new cases 0.50 (p = 0.5760); pooled 19 sets 0.58, CI 0.39-0.76, p = 0.25**; design power at N=19 is 0.379 at 0.67, 0.118 at 0.58; 55 sets needed assuming discovery effect, 247 sets needed at true 0.58 due to winner's curse (exceeds archive capacity; partner fleets required) | `rough_drone_newer.md` |
| Q4 expert diagnoses | 148 real crash threads (settled labels): drone 94, pilot 9, both 2, unclear/no diagnosis 43; tuning/config most named (26/94); 43 downloadable logs (38 aircraft, 5 pilot); 37 aircraft logs with checkable categories in Table 7; rule wrong on 48.6% of decided cases (BA 0.381, 95% CI 0.20-0.59); pilot recall 1/5 (Wilson CI 3.7-71.0%); poster confirmed only 47/94 aircraft and 5/9 pilot diagnoses | `forum_expert_labels.md` |
| LLM panels | Fixed rule 45/60 right, 0 wrong; panels 6-38 wrong; one adversary flipped 45-56 of 60 | `research/panel_eval/` |
| Planned-vs-flown, injected deviations (declared) | Sideways >= 35 m found 90-98%, upward >= 20 m 92-98%; false alarms 9/40 (22%) on track-built plans, 0/40 with 5 s waypoints | `injection_reconcile*.md` |
| Planned-vs-flown, real missions (declared) | Only 6 distinct missions in archive; no deviation in mission mode; 2 reported = drone had left mission mode (RTL / pilot takeover). Too few for a rate | `real_mission_reconcile.md` |
| Description search, leave-one-out (declared) | Top-1 22% vs 27% base rate on 96 cases (settled; first recording 20% vs 32% on 90): criterion not met; product orders checklist by expert frequency | `troubleshoot_loo_settled.md` |
| Second coding of forum threads (declared) | Blind redo: kappa **0.81** conclusion (0.71-0.88), **0.73** cause (0.65-0.81), 0.79 confirmed; pass mark 0.60 met; 45 disagreements settled (13 labels changed); `forum_expert_labels.csv` now holds settled labels, first recording kept in `forum_expert_labels_first_recording.csv`. First attempt rejected (pasted quotes) | `forum_agreement.md`, `forum_disagreements_settled.csv` |

---

## 6. Current status (25 Oct 2026)

**Paper** (Round 6 peer review complete & Stage 4 Strategic & Conceptual Unification achieved, rating **9.4/10**; 44 pages, 7 figures, 10 tables, 36 references, abstract 197 words, zero placeholders, DOIs verified):
Unified research question: integrated Q1--Q4 as sub-tests under one falsifiable central question (*"what evidentiary value can flight logs carry for a drone fleet operator, once evaluation protocols guard against crash-window leakage and between-aircraft confounding?"*); elevated methodological contribution (*crash-window ablation + within-aircraft Group-CV protocol*, 77.8%->11.1% sensitivity, AUC 0.88->0.58) to lead contribution (i); defined *crash-window leakage* as a domain-specific phenomenon in Related Work (Methodology); calibrated Discussion to state diagnostic check findings are *consistent with* leakage; headline claim reframed (0.660 permutation null 95% threshold vs 0.510-0.584 model upper bounds); two-class expert validation calibrated with Wilson CI on pilot recall (1/5, ~4-62%) and bootstrap CI on balanced accuracy (0.381 [0.20, 0.59]); screenable base rate 0.689% evaluated; duration confound empirically tested (AUC 0.662 at 0s, 0.634 at 10s); full 40-digit SWHIDs integrated; figures widened with generous margins (Figure 1: 8.6 in, Figure 4: 5.6 in, Figure 5: 6.0 in).

**Product**: all features work locally and are tested; 657 tests pass; app typechecks. Internal rating 7/10.
Removed on 25 Oct: four old start scripts, and "Incident replay" (the earlier product's AI-council view) from the VR
view. "Live swarm" in the VR view is still from the earlier dispatch product (simulated drones).

---

## 7. Open work, in priority order

1. *(Done 25 Oct: Round 6 peer review complete: Stage 3 Flawless Execution achieved, rating 9.2/10; headline detection threshold reframed, two-class expert validation calibrated with CIs and reporting cross-tabulation, screenable base rate 0.689% evaluated, duration confound empirically tested with AUC 0.662 and feature correlations, lift 3.6x corrected, full 40-digit SWHIDs integrated, figures padded and re-exported, abstract kept <= 200 words.)*
2. **Before submission:** repository URL and archived DOI (make the GitHub repo public, create a Zenodo release) in
   the paper's Data availability section; confirm the journal quartile; fill CRediT roles if the submission form asks.
3. **Prospective test and user study:** declared in `research/protocols/prospective_and_user_study.md`. Needs a
   partner fleet (8+ drones, 6 months) and 12-16 participants with ethics approval. Do not run variants without
   updating the declaration first.
4. **Real-mission false-alarm rate:** needs a partner fleet's own `.waypoints` files and logs; run the review on them.
5. **Quest headset:** run the Unity app (`unity/AeroFleetVR`) and the WebXR page on a real Quest 3; see
   `docs/VR_QUEST3_GUIDE.md`. The paired app does not yet support mission rehearsal (the browser does).
6. **Product cleanup still possible:** the earlier product's code (dispatch agents, council, live swarm) remains in
   `aerofleet/` and the app; remove only with the owner's agreement.

---

## 8. How to make a change safely (checklist)

1. Read the relevant module and its tests first; match the surrounding style (short docstrings that say *why*).
2. For any new measurement: declare in the script docstring, commit and push, then run.
3. Run the tests for what you touched, then the full suite before committing.
4. If the result changes a number, update **all** places: `README.md`, `docs/paper/latex/main.tex` (abstract,
   results, Section 6, discussion, threats, conclusion), `highlights.txt` (each at most 85 characters),
   `docs/paper/critical_review.md`, and this file's section 5.
5. Rebuild the paper, check page 1 does not overflow (render it; long abstracts push into the footer), rebuild the
   submission folder and the Overleaf zip.
6. Commit with a clear message, push, clean the `._*` files.
