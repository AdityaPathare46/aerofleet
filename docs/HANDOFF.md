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
| Q1 settings differ crash vs normal? | No: protection disabled 51% vs 46%, p = 0.63 | `summary.md` |
| Q2 pilot vs aircraft from logs? | No: rule BA 0.57 dev, **0.47 held-out**; model 0.42-0.52 at all cut-offs | `holdout.md`, `pilot_vs_drone.md`, `leak_curve.md` |
| Q3a crash window leakage | Model AUC 0.88 to 0.86 (no model-level leak); single tuning check 10/12 to 1/9 without last 10 s (settled labels; first recording 13/15 to 2/10) | `leak_curve.md`, `test_flight_check*_settled.md` |
| Q3b within same drone | No warning: vibration rank 0.48, p = 0.67 (61 drones) | `within_drone.md` |
| Q3c between drones (the positive result) | Crashed drones rougher: **0.67, 95% CI 0.57-0.77, p = 0.0023, Holm 0.016** (60 sets) | `rough_drone.md` |
| Robustness (post hoc) | Held with same airframe, without crash-day flights, duration-adjusted; mainly older estimator metric (48 sets) | `sensitivity*.md` |
| Newer metric replication (declared) | **Not confirmed: 0.58, CI 0.39-0.76, p = 0.25, 19 sets**; archive has no more cases | `rough_drone_newer.md` |
| Q4 expert diagnoses | 148 real crash threads (settled labels): drone 94, pilot 9, both 2, unclear/no diagnosis 43; tuning/config most named (26/94) | `forum_expert_labels.md` |
| LLM panels | Fixed rule 45/60 right, 0 wrong; panels 6-38 wrong; one adversary flipped 45-56 of 60 | `research/panel_eval/` |
| Planned-vs-flown, injected deviations (declared) | Sideways >= 35 m found 90-98%, upward >= 20 m 92-98%; false alarms 9/40 (22%) on track-built plans, 0/40 with 5 s waypoints | `injection_reconcile*.md` |
| Planned-vs-flown, real missions (declared) | Only 6 distinct missions in archive; no deviation in mission mode; 2 reported = drone had left mission mode (RTL / pilot takeover). Too few for a rate | `real_mission_reconcile.md` |
| Description search, leave-one-out (declared) | Top-1 22% vs 27% base rate on 96 cases (settled; first recording 20% vs 32% on 90): criterion not met; product orders checklist by expert frequency | `troubleshoot_loo_settled.md` |
| Second coding of forum threads (declared) | Blind redo: kappa **0.81** conclusion (0.71-0.88), **0.73** cause (0.65-0.81), 0.79 confirmed; pass mark 0.60 met; 45 disagreements settled (13 labels changed); `forum_expert_labels.csv` now holds settled labels, first recording kept in `forum_expert_labels_first_recording.csv`. First attempt rejected (pasted quotes) | `forum_agreement.md`, `forum_disagreements_settled.csv` |

---

## 6. Current status (25 Oct 2026)

**Paper** (second coding done: kappa 0.81 / 0.73; 31 pages, 7 figures, 9 tables, 36 references, abstract 228 words, all DOIs checked on Crossref):
complete except the items in section 7. Internal rating 7.5/10. Authors, affiliation and corresponding e-mail are in.
The CRediT section was removed at the owner's request (Elsevier may ask for roles in the submission system).

**Product**: all features work locally and are tested; 657 tests pass; app typechecks. Internal rating 7/10.
Removed on 25 Oct: four old start scripts, and "Incident replay" (the earlier product's AI-council view) from the VR
view. "Live swarm" in the VR view is still from the earlier dispatch product (simulated drones).

---

## 7. Open work, in priority order

1. *(Done 25 Oct: second coding, kappa 0.81/0.73; 45 disagreements settled, 13 labels changed; Q4, fault checks, knowledge base and leave-one-out re-run on settled labels.)*
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
