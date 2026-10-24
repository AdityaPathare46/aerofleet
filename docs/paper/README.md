# Paper: where to submit, and what is left before submitting

**Final manuscript (Elsevier `elsarticle` LaTeX, numbered references):** `latex/main.tex` + `latex/refs.bib`.
It builds to `submission/manuscript.pdf`: 31 pages (line-numbered preprint layout), 9 tables, 7 figures, 36 verified
references, and a 228-word abstract.

| File | What it is |
|---|---|
| `submission/manuscript.pdf` | The manuscript as it will be reviewed (line-numbered) |
| `submission/latex_source_for_overleaf.zip` | Everything needed to build it; upload to Overleaf or attach as source files |
| `submission/highlights.txt` | Five highlights, each 85 characters or fewer (Elsevier asks for a separate file) |
| `submission/cover_letter.pdf` | Cover letter to the editor, signed by the corresponding author |
| `critical_review.md` | The internal reviewer's report and what was changed in response |
| `originality_check.md` | Partial similarity check against the cited arXiv abstracts |

Rebuild after any edit:

```bash
python3 research/px4_log_study/paper_figures.py docs/paper/figures
cd docs/paper/latex && tectonic -X compile main.tex
```

The first Word draft was replaced by this version; it remains in the git history (commit `87394f7`).

## Journal choice

Checked on 23 October 2026 using third-party metric sites and publisher pages, not Clarivate or SCImago
directly. Confirm the current quartile before submitting.

| Journal | Quartile and impact (as found) | Fit | Cost | Verdict |
|---|---|---|---|---|
| **Reliability Engineering & System Safety** (Elsevier) | Q1 (Safety, Risk, Reliability and Quality); IF reported about 12–14 | Fault diagnosis, risk and safety analysis of technical systems: our core topic | Hybrid: subscription route normally has no fee (confirm) | **First choice.** Very selective, so expect a fast desk decision |
| **Safety Science** (Elsevier) | Q1; IF about 5.4 | Accident analysis and human vs technical causes | Hybrid (confirm) | Good second choice if RESS desk-rejects for "no new method" |
| **Drones** (MDPI) | JCR Q2 (Remote Sensing); CiteScore Q1 (Aerospace Engineering); IF 4.8 (2024) | Exact topic, often publishes datasets and empirical studies | Open access with an article fee (check the current amount) | Most likely to accept; fast review |
| Journal of Intelligent & Robotic Systems (Springer) | Reported Q3 | — | — | Below the Q1/Q2 bar, so skipped |

**Plan:** submit to RESS. If it's desk-rejected, reformat for Safety Science; if a quick, near-certain outcome
matters more than prestige, go to Drones.

Sources: [RESS metrics (SciJournal)](https://www.scijournal.org/reliab-eng-syst-safe),
[RESS (journalmetrics)](https://www.journalmetrics.org/journal/reliability-engineering-and-system-safety),
[Drones (MDPI)](https://mdpi.com/journal/Drones), [Drones (journalmetrics)](https://www.journalmetrics.org/journal/drones),
[Safety Science (journalmetrics)](https://www.journalmetrics.org/journal/safety-science),
[JIRS (journalmetrics)](https://www.journalmetrics.org/journal/journal-of-intelligent-and-robotic-systems).

## Why it can stand out (for the cover letter)

1. **Real crashes at scale.** It uses uploader-labelled crashes from 479,547 public logs. The nearest datasets
   use simulation or injected faults (ALFA, RflyMAD), or annotate anomalies rather than who caused the crash (UAV-SEAD).
2. **Declared tests.** Every hypothesis and threshold was committed before running, and the repository history
   proves it. Decisive tests were repeated on held-out data.
3. **A clear practical message.** Logs show which drones are at risk (between drones, rank 0.67, p = 0.002), not
   why one flight crashed (within the same drone, 0.48; pilot vs drone attribution at chance).
4. **A methods warning.** A check can appear to find the cause only because the crash is in the window
   (13/15 vs 2/10 for the tuning check).
5. **A timely negative result on small language models** used as safety reviewers.

## Before submitting (in order)

Items 2, 3 and 6 below were done in the revision (references verified, text and methods expanded, Elsevier format).
Still open: 1, 4, 5 and 7, plus an iThenticate check through the institution.

1. **Second recorder for the forum labels.** Add Atharv's independent recording and report agreement (kappa),
   or measure the error rate on a random 30-thread sample. Reviewers will ask for this.
2. **Verify every reference marked [to verify]** (authors and pages of RflyMAD, AeroTSBoost, the 2026
   Sensors testbed, the LLM-agents paper, DroPTC, and the ESEC/FSE pages). Add 10–15 more related-work papers
   on UAV fault detection and accident analysis. A Q1 journal will expect about 40 references.
3. **Lengthen to journal size.** The main text is about 2,900 words; RESS papers are usually 7,000–9,000. Expand:
   - the related work;
   - the method details: feature definitions, crash-moment estimation, matching, null distribution;
   - a figure of the study design;
   - the per-feature table from `leak_curve.md`;
   - the settings table from `summary.md`.
4. **Fill in the placeholders:** authors, affiliations, CRediT roles, competing interests, funding, and the repository
   URL for data and code.
5. **Licensing of the data.** Check PX4 Flight Review's terms before publishing anything beyond log IDs and
   derived features.
6. **Check the journal's own author guide.** It wasn't readable from here (ScienceDirect blocked automated
   access). Confirm the abstract limit (250 words assumed; currently 246), highlights (3–5 bullets of 85 characters
   or fewer; done), keywords, the reference style, and the generative-AI declaration wording.
7. **Optional, would strengthen it:** repeat the between-drone test on ArduPilot logs, and add a larger
   language model as a ceiling.

## Where each number comes from

| Section | File |
|---|---|
| 5.1 settings | `research/results/px4_log_study/summary.md` |
| 5.2 attribution | `pilot_vs_drone.md`, `holdout.md`, `leak_curve.md` |
| 5.3 crash window | `leak_curve.md`, `test_flight_check.md`, `test_flight_check_minus10s.md` |
| 5.4 within/between drones | `within_drone.md`, `rough_drone.md` (CIs: `paper_figures.py`) |
| 5.5 expert diagnoses | `forum_expert_labels.md` / `.csv`, `test_flight_check_minus10s.md` |
| 5.6 language models | `research/results/panel_eval/summary.md`, `injection_reach.md` |

The pre-declaration commit for each test is in `git log -- research/px4_log_study/` (e.g. `63bc72e`, `af6fab2`,
`4475c8c`, `0c8ee47`, `d5d56c7`, `8b417d2` + amendment `f911bcf`, `d7a6574`).
