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

**Python environment (27 Oct 2026):** the working environment is `~/.venvs/aerofleet` (Python 3.10, numpy 1.26.4, scipy 1.14.1); point `AEROFLEET_VENV` at it. scipy 1.15.x fails to load on this macOS (dyld rejects `_spropack`), so requirements cap scipy below 1.15. The old in-repo `.venv` (12 GB, damaged) is kept but unused; delete it when you are sure. pytest-cov is now in requirements.

**macOS/exFAT quirk:** the repo is on an exFAT drive, so macOS creates `._*` files inside `.git/objects/pack/`, and git
prints many `non-monotonic index` errors. They are harmless. Clean them after a commit/push with:
`find .git/objects/pack -name '._*' -size -5k -delete`

---

## 3. How to run everything

```bash
export AEROFLEET_VENV=~/.venvs/aerofleet   # the environment lives on the internal disk (rebuilt 27 Oct 2026)
./start.sh            # sets up the venv + npm packages if missing, starts API (:8000) and app (:1420), opens browser
./start.sh api        # API only
$AEROFLEET_VENV/bin/python -m pytest -q --no-cov tests/unit tests/integration   # full suite: 657 pass (about 3 min)
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
| Q1 settings differ crash vs normal? | No (first-pass result, not declared before running; code and result committed together in `d755cca`): protection disabled 51% vs 46%, p = 0.63 (exploratory contrast: pilot-caused 70% vs aircraft 41%, p = 0.052, BA 0.647, 43% missing defaults) | `summary.md` |
| Q2 pilot vs aircraft from logs? | No: rule BA 0.57 dev, **0.47 held-out**; logistic model Task B AUC 0.408 (full n=148, 95% bootstrap CI [0.288, 0.530], upper bound 0.510) and 0.466 (constant n=89 subset, CI [0.325, 0.607], upper bound 0.584); 1,000-permutation null mean 0.497, 95% detection threshold 0.660 (null interval 0.313-0.660, p = 0.509); observed model upper bounds (0.510-0.619) lie safely below 0.660 detection threshold; boosted stumps 0.430 -> 0.413, depth-3 trees 0.595 -> 0.553 (10s), 0.548 (30s); two-class expert validation on 43 downloadable logs (38 aircraft, 5 pilot) yielded **48.6% error rate** on decided cases (BA 0.381, 95% CI [0.20, 0.59], chance 0.50 not excluded; pilot recall 1 of 5, Wilson CI 3.7-71.0%; cross-tabulation: 9 uploader `crash_sw_hw` 100% agreement, 0 `crash_pilot` uploaded) | `holdout.md`, `pilot_vs_drone.md`, `leak_curve.md`, `forum_expert_labels.md` |
| Q3a crash window leakage | Model AUC 0.88 to 0.86 (constant-subset n=213: 0.895 to 0.868; duration alone yields AUC 0.662 at 0s and 0.634 at 10s, correlating with tilt $\rho=+0.47$ and stick deflection $\rho=+0.36$); paired tuning check firing fell 7/9 to 1/9 (unadjusted McNemar p = 0.03125, Bonferroni p ~ 0.16; other 4 checks had low baseline sensitivity <= 25%); within-drone model substantially attenuates separation to Group-CV AUC 0.580 [0.528, 0.633], mean pairwise AUC 0.605 (67 drones, 372 flights) | `leak_curve.md`, `test_flight_check*_settled.md`, `within_drone.md` |
| Q3b within same drone | No warning: vibration rank 0.48, p = 0.67 (61 drones; 95% CI upper bound 0.58 rules out effect of between-drone magnitude) | `within_drone.md` |
| Q3c between drones (the positive result) | Crashed drones rougher: **0.67, 95% CI 0.57-0.77, p = 0.0023, Holm 0.016** (60 sets); top-rank 33/60 (55.0%) vs Poisson-binomial null 40.3% (p = 0.0137; lift 1.37x over null rate, relative risk 3.58x over unflagged); Q3 flag 38/60 (63.3%, older 66.7%, newer 50.0%); matched-set PPV 0.96-1.04% (lift 1.40x, 96-104 insp./crash) across screenable multi-flight base rate (0.689%, 182/26,421) and fleet vehicle base rate (0.741%, 284/38,320); stratum-matched fleet-ref: top decile (10% flag) PPV 2.26-2.47% [1.48-3.33%] (relative risk 4.50x, lift 3.28-3.33x, 40.5-44.2 insp./crash), top quartile (25% flag) PPV 1.37-1.48% [1.01-1.88%] (relative risk 3.00x, lift 1.99-2.00x, 67.5-73.1 insp./crash) | `rough_drone.md` |
| Archive-wide label audit (declared `09cf99c`, amended `18b0eff`) | All 520 crash-rated real-hardware logs downloaded (212 new, 1.53 GB, in `archive_crash/`). Of 341 readable multicopter logs, 132 (39%) show a tilt event; share containing the crash **50% (reviewer A) to 86% (blind reviewer B), 66% on agreed logs - no single figure claimed**; **pilot-rated 23% vs aircraft-rated 45% (Fisher p 0.0003)**, so the label can leak into a classifier; 23% from 2023; modelled sample representative (38% vs 39%) | `archive_label_audit.md` |
| Round 18 audit (declared `35103da`, results `96a277f`) | Label link survives era/vehicle adjustment (MH OR 2.08 [1.17, 3.69]); tilt alone AUC 0.61 archive, 0.55 modelled. Objective detector (tilt or > 4 g) **failed its gate** (kappa 0.72 / 0.38; 64% false alarms on normals), t_c unchanged. **Window effect on tilt-defined crashes 0.067 [0.015, 0.131] (material)**; leak drop 0.084 (criterion not met). 72/148 tilt-defined includes 31 fixed-wing/VTOL; multicopters 41/108 | `r18_audit.md` |
| Two-reviewer crash-moment check (declared `59c8212`, results `5d7c0ce`) | Second author labelled the blind sheet. Computed crash moment right: agreement 85%, kappa 0.70 (tilt-defined correct 21 and 24 of 26; fallback 2 and 6 of 24). Whether fallback logs contain the crash: kappa 0.32. Paper now reports both reviewers and drops the 'about half' figure | `crash_moment_interrater.md` |
| Crash-moment review (declared `97974ad`, amended `bfda684`; one author, not blind) | Tilt-defined t_c judged correct in 21/26 (confirmed 11/12, unconfirmed 10/14); **18 of 24 fallback logs contain no crash**; confirmed rule precision 11/12, recall 11/23. Second blind reviewer still to do. Also fixed: exact CI for 18/32 is 37.7-73.6% (paper had 74.3%) | `crash_moment_agreement.md` |
| Round 16 audit (declared `48c2fa7`; exploratory) | **Only 40/148 crash logs have a confirmed crash moment** (tilt > 60 deg then disarm/ground contact within 10 s); 76 fall back to end of arming. Grouped leak curve on one cohort: drop 0.035 overall (criterion fails), **0.103 on 25 confirmed crashes (criterion met)**; factorial window effect 0.056 [-0.010, 0.139] confirmed vs 0.014 all. Index date = GPS date for 80% (90% within a day); no cross-day misordering (0/221); problem is same-day only; dated-only shares 44% and 55%. Clustered (one set per airframe) between-drone variants median p 0.012-0.026, newer metric 0.28; roughest test 0.031. Bootstrap p: shifted 0.012, percentile 0.025. Stumps 0.447/0.481 vs refit null. Tuning drop vs normal drop Fisher p 0.057. Tables 4, 12, 14 were broken in the PDF (overflow); rebuilt (Table 12 now longtable) | `r16_audit_*.md` |
| Round 15 audit (declared `6fff27d`, amended `016dafe`; exploratory) | **Between-drone vibration now suggestive**: clustered by 40 airframes p 0.012, Holm 0.08 (declared exact p 0.0023 assumed independent sets); one set per airframe median p 0.012. Task B with refit permutation null: logistic AUC 0.42-0.52, trees 0.43-0.59, upper bounds <= 0.69, 80% power needs AUC 0.72 (replaces 0.65/0.75 and 0.510-0.619). Table 6 regenerated with fixed seeds: Step 0 0.882, **Step 1 grouped by vehicle 0.826** (old 0.884 not reproducible), Steps 2-4 0.799/0.791/0.738, 5/6 0.546/0.559, 6b 0.582. Other-aircraft minus own earlier flights +0.113 [0.029, 0.212] without post-crash flights. 54% of crash-rated vehicles fly again later; only 72/148 crash moments are tilt-defined; **manual crash-moment check pending (authors)** | `r15_audit_*.md` |
| Post-crash flight audit (declared `0d38f5d`; exploratory) | **85 of 210 crash-day within-drone earlier flights were flown after the crash** (107 before, 18 undated; 29 crashes). Without them: rank tests unchanged (vib 0.488 p 0.60; tune 0.551 p 0.21); within-drone Group-CV 0.582 [0.525, 0.660] on stored features (0.559 [0.511, 0.618] published sample, reproducible folds) but factorial same-aircraft 0.507 [0.436, 0.582] on recomputed features: **at most a weak, pipeline-dependent signal**. Caliper lift +0.086 [-0.064, +0.184] (F8 +0.063 [-0.087, +0.159], 24 airframes): **masking reading withdrawn** | `postcrash_audit.md` |
| Round 14 audit (declared `0e26db0`, amended `187f570`; exploratory) | Caliper 0.25 lift with reproducible folds +0.110 [+0.028, +0.205] (old [+0.074, +0.238] not reproducible); without clip_rate, tilt_p95, volt_sag +0.077 [+0.013, +0.204] (declared masking rule met; seed-42 CI includes 0). **GPS ordering: of 95 crash-day exposure flights in 39 of the 60 between-drone sets, 47 were flown after the crash** (Round 13 date-only check was wrong); between-drone without them 0.698, p 0.0021, 43 sets; also without 10 undated 0.718, p 0.0014, 39 sets. Within-drone/caliper/factorial-S samples use the same date rule and are not yet audited. 250-pilot figure corrected to ~100 (SE criterion) / ~200 (80% power) | `r14_audit.md` |
| Factorial optimism audit (declared after Round 14; exploratory) | 2x2 (m=10 s, grouped CV, one extractor): 103 vs rated 0.825, vs matched unrated 0.686; 67 vs rated 0.673, vs unrated 0.623. Neither normal-set (+0.094 [-0.014, 0.197]) nor crash-set (+0.108 [-0.037, 0.224]) effect supported: **"The AUC depends on the comparison set; the cause is not isolated."** Full factorial: drop 0.212 [0.062, 0.335] (0.878 to 0.666); Shapley: grouped folds **0.062 [0.034, 0.087], only material factor**; normals 0.070, crash set 0.064 (CIs span 0); m 0.014; 30 s window 0.001. Same-aircraft step a further -0.21 to chance. Old Step 4b 0.522 superseded (mixed extractors). The 67 are not a subset of the 103 (10 of 67 in the 148). First run aborted at A3 (float32 rounding), amended `f6ba424` | `factorial_audit.md` |
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

**Paper** (Round 11 peer review complete, publication grade **>= 9.3/10** achieved for *Reliability Engineering & System Safety*; 43 pages, 6 figures, 11 tables, 36 references, abstract 198 words, zero placeholders, DOIs verified):
Resolved all Round 11 peer review items: (1) Rewrote Table 6 headline finding across Abstract, Contribution (i), §5.3, §7, and Conclusion: changing the comparison population from other aircraft's normal flights to the same aircraft's earlier flights lowered model AUC from about 0.83--0.88 to 0.53--0.57; grouping folds by vehicle, removing the crash window, and the cross-sectional versus within-drone scheme made no detectable difference, consistent with airframe and duration confounding. Added cluster bootstrap across 67 drone clusters ([0.500, 0.643]), proving no within-drone signal is detectable (CI spans 0.50). (2) Demoted screening PPV numbers in Abstract, Contribution (iv), §5.4, §6, §7, §9, and Table 10 from population claims to an exploratory illustration conditional on assumed 10% flag rate (illustrative PPV 2.26--2.43% [exact Bayes], lift 3.3x, 41--44 inspections per crash) on 107 controls across 20 strata with 17 reused controls. (3) Qualified depth-3 decision trees in §4.4, §5.2, Contribution (iii), §7, §9: reported $0.595 \pm 0.130$ and $0.621 \pm 0.105$ (upper bounds near 0.73) as inconclusive non-linear models examined in uncommitted early development and not retained due to fold instability, clarifying that prospectively declared negative applies to linear models and stumps. (4) Softened expert-log conclusions in §5.6, §7, §9: dropped "confirming"; reported that AUC 0.450 [0.185, 0.715] on 29 logs provides no evidence of discrimination and remains inconclusive; relabeled 0.19--0.73 as "conservative class-averaged Clopper--Pearson bound"; noted statistical model covers 4 of the 5 pilot logs due to topic availability. (5) Clarified registration dates in §4.1 and §8: documented confirmatory commits (20--24 Oct: `63bc72e`, `af6fab2`, `4475c8c`, `0c8ee47`, `d5d56c7`, `8b417d2`, `d7a6574`) and run dates 20--24 Oct; maintained author-controlled timestamp caveat prior to 25 Oct SWH capture; kept exploratory hedging on 7/9 to 1/9 leakage. (6) Framed wider permutation SD as a hypothesis in §5.2; corrected S7 sensitivity details in §8 to vibration across pitch/roll tilt thresholds (56 drones at 45 deg [0.46, $p=0.79$], 61 drones at 60 deg [0.48, $p=0.67$], 64 drones at 75 deg [0.50, $p=0.54$]); confirmed reference records (AAIB, Kose et al., Silalahi et al., EASA, Duvvuru). Rebuilt LaTeX PDF, DOCX manuscript, and Overleaf source zip.

**Product**: all features work locally and are tested; 657 tests pass; app typechecks. Internal rating 7/10.
Removed on 25 Oct: four old start scripts, and "Incident replay" (the earlier product's AI-council view) from the VR
view. "Live swarm" in the VR view is still from the earlier dispatch product (simulated drones).

---

## 7. Open work, in priority order

1. *(Done 26 Oct: Round 11 peer review complete: publication grade >= 9.3/10 achieved; Table 6 decomposition reframed around comparison population shift [0.88 -> 0.53--0.57] with cluster bootstrap [0.500, 0.643]; screening PPV framed as exploratory illustration conditional on assumed flag rate; depth-3 trees qualified as inconclusive; expert logs softened to inconclusive with conservative Clopper-Pearson bound; registration and run dates documented; S7 sensitivity aligned; LaTeX, DOCX, and Overleaf zip fully synchronized.)*
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
