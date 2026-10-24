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

The Overleaf zip (`docs/paper/submission/latex_source_for_overleaf.zip`) must contain `main.tex`, `refs.bib`,
`cover_letter.tex`, `highlights.txt` and `figures/` with every figure `main.tex` includes. Rebuild it after edits.

---

## 4. Where things are

| Path | What |
|---|---|
| `aerofleet/assurance/` | The product's logic: `params`, `drift`, `static_checks`, `flightlog` (ArduPilot + PX4 readers), `reconcile` (planned vs flown), `evidence` (timeline), `vibration` (fleet ranking), `deconflict` (+ `rehearsal()` for 3D), `wind`, `ledger` (signed record), `report_html`, `troubleshoot` (description search), `data/fault_cases.json` |
| `aerofleet/api/routes/assurance.py` | All assurance HTTP endpoints |
| `tauri-app/src/pages/FleetAssurance.tsx` | Main screen: baseline/drift, flight review, troubleshooting card, deconflict + "Rehearse in 3D", wind check, signed record |
| `tauri-app/src/pages/VRSafetyView.tsx`, `src/components/vr/` | 3D tabletop: Live swarm (earlier product), Flight replay (`Flight.tsx`), Mission rehearsal (`Rehearsal.tsx`). WebXR for Quest browser |
| `unity/AeroFleetVR/` | Mirror of the Quest app scripts (Unity project lives on another drive; compiles, never run on a headset) |
| `tools/verify_ledger.py` | Standalone verifier for the signed record |
| `research/px4_log_study/` | Every study script; each docstring is its declaration |
| `research/results/px4_log_study/` | Every result (markdown + jsonl) |
| `research/protocols/prospective_and_user_study.md` | Declared future studies |
| `docs/paper/latex/` | `main.tex`, `refs.bib`, `cover_letter.tex`, `highlights.txt` |
| `docs/paper/submission/` | Built PDF, cover letter, highlights, Overleaf zip |
| `docs/paper/critical_review.md` | All internal review rounds and ratings |
| `/Volumes/One Touch/AeroFleet_px4_data/` | Raw data, not in git: `dbinfo.json` (archive index), log folders `h/`, `within/`, `rough/`, `crash/`, `newer/`, CSV selections, `forum_cache/` (thread JSON) |
| `/Volumes/One Touch/AeroFleet_reference_papers/` | Reference PDFs with a README index (not in git) |

---

## 5. What the study found (numbers to keep consistent everywhere)

| Question | Result | File |
|---|---|---|
| Q1 settings differ crash vs normal? | No: protection disabled 51% vs 46%, p = 0.63 | `summary.md` |
| Q2 pilot vs aircraft from logs? | No: rule BA 0.57 dev, **0.47 held-out**; model 0.42-0.52 at all cut-offs | `holdout.md`, `pilot_vs_drone.md`, `leak_curve.md` |
| Q3a crash window leakage | Model AUC 0.88 to 0.86 (no model-level leak); single tuning check 13/15 to 2/10 without last 10 s | `leak_curve.md`, `test_flight_check*.md` |
| Q3b within same drone | No warning: vibration rank 0.48, p = 0.67 (61 drones) | `within_drone.md` |
| Q3c between drones (the positive result) | Crashed drones rougher: **0.67, 95% CI 0.57-0.77, p = 0.0023, Holm 0.016** (60 sets) | `rough_drone.md` |
| Robustness (post hoc) | Held with same airframe, without crash-day flights, duration-adjusted; mainly older estimator metric (48 sets) | `sensitivity*.md` |
| Newer metric replication (declared) | **Not confirmed: 0.58, CI 0.39-0.76, p = 0.25, 19 sets**; archive has no more cases | `rough_drone_newer.md` |
| Q4 expert diagnoses | 148 real crash threads: drone 88, pilot 9, both 2, unclear/no diagnosis 49; tuning/config most named (29/88) | `forum_expert_labels.md` |
| LLM panels | Fixed rule 45/60 right, 0 wrong; panels 6-38 wrong; one adversary flipped 45-56 of 60 | `research/panel_eval/` |
| Planned-vs-flown, injected deviations (declared) | Sideways >= 35 m found 90-98%, upward >= 20 m 92-98%; false alarms 9/40 (22%) on track-built plans, 0/40 with 5 s waypoints | `injection_reconcile*.md` |
| Planned-vs-flown, real missions (declared) | Only 6 distinct missions in archive; no deviation in mission mode; 2 reported = drone had left mission mode (RTL / pilot takeover). Too few for a rate | `real_mission_reconcile.md` |
| Description search, leave-one-out (declared) | Top-1 20% vs 32% base rate: criterion not met; product now orders checklist by expert frequency | `troubleshoot_loo.md` |
| Second coding of forum threads | First returned sheet unusable (50 rows, 6 pasted quotes); redo pending | `forum_agreement_interim.md` |

---

## 6. Current status (25 Oct 2026)

**Paper** (31 pages, 7 figures, 9 tables, 36 references, abstract 228 words, all DOIs checked on Crossref):
complete except the items in section 7. Internal rating 7.5/10. Authors, affiliation and corresponding e-mail are in.
The CRediT section was removed at the owner's request (Elsevier may ask for roles in the submission system).

**Product**: all features work locally and are tested; 657 tests pass; app typechecks. Internal rating 7/10.
Removed on 25 Oct: four old start scripts, and "Incident replay" (the earlier product's AI-council view) from the VR
view. "Live swarm" in the VR view is still from the earlier dispatch product (simulated drones).

---

## 7. Open work, in priority order

1. **Second coding (blocks the label-reliability claim).** Atharv codes all 161 threads on the blank sheet
   `research/px4_log_study/forum_review/forum_diagnosis_Atharv_REDO.xlsx` (git-ignored, on the drive), following
   `research/px4_log_study/SECOND_CODER.md`. Then run the scoring command in that file (it verifies every quote against
   its thread). Declared pass mark: kappa >= 0.60 for conclusion and cause. Put the kappa in the paper: Section 3.3
   ("Expert diagnoses"), Threats to validity ("Labels"), Future work (remove the second-coding item). If below 0.60,
   say so and settle disagreements, then re-run `build_fault_kb.py`, `eval_troubleshoot.py` and the Q4 numbers.
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
