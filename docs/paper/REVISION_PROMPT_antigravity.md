# Revision prompt (external review, 7.8/10) — paste into Antigravity or another assistant

Fill in the three lines marked FILL IN before pasting.

```
You are revising the research paper in this repository. First read docs/HANDOFF.md completely and follow its rules
(section 2) exactly: no AI in the product's decisions; every new test is declared in its script docstring and
committed and pushed BEFORE it is run; report results whatever they are; never overclaim; never commit forum text,
reference PDFs, raw logs, secrets or the owner's untracked files; commit messages end with a co-author line for you.

The paper's master copy is docs/paper/latex/main.tex (+ refs.bib). An external reviewer rated it 7.8/10. Make
these changes, in this order, then rebuild everything.

1. PLACEHOLDERS (main.tex, end matter). Replace:
   - "Declaration of competing interest": FILL IN (e.g. "The authors declare that they have no known competing
     financial interests or personal relationships that could have appeared to influence the work reported in this
     paper. The authors develop the open-source tool described in Section 6; it is not commercial.")
   - "Funding": FILL IN (e.g. "This research did not receive any specific grant from funding agencies in the
     public, commercial, or not-for-profit sectors.")
   - "Data availability": replace "[repository URL; archived release DOI]" with FILL IN (GitHub URL
     https://github.com/AdityaPathare46/aerofleet and the Zenodo DOI once a release is archived; if there is no DOI
     yet, write only the GitHub URL and say a DOI-archived release will be provided on acceptance).
   No "[...]" placeholder may remain anywhere in main.tex or cover_letter.tex (grep for "\[" text placeholders).

2. EXPLAIN THE SAMPLE DROPS (Section 3.2 Samples, near Table 3). Add two or three sentences, using ONLY the facts
   in research/results/px4_log_study/within_drone.md, rough_drone.md and the declaration docstrings of
   research/px4_log_study/within_drone.py and rough_drone_test.py:
   - within-drone: 101 crashes selected; 55 logs could not be read or had under 10 s before the cut-off; a drone
     enters a feature's test only if the crash flight and earlier flights have that feature from the same
     measurement source; rate-tracking error is rotary-wing only and needs rate setpoints -> 61 (vibration) and
     46 (tracking) drones analysed.
   - between-drone: 66 matched sets; 71 flights unreadable or too short; a drone's value needs at least 2 readable
     flights and case and controls must share the measurement source -> 60 (vibration) and 47 (tracking) sets.
   Verify each reason in the code before writing it; do not invent reasons.

3. SECTION 6 FOCUS. Keep the paper anchored on the log evidence:
   - Shorten Section 6.3 (three-dimensional replay and rehearsal) to one paragraph (about 6 lines) that keeps:
     what the flight replay and mission rehearsal show, that the rehearsal is kinematic (no wind, no dynamics),
     and that there is no user study and no headset run. Move Figure 7 and the longer description to a new
     "Appendix A. Three-dimensional replay and mission rehearsal" placed before the references (elsarticle:
     \appendix then \section{...}). Update all cross-references.
   - In the opening paragraph of Section 6, add one sentence saying the section reports design consequences and
     engineering checks, and that the paper's evidence is in Sections 3-5.

4. LIMITATIONS (Section 8 Threats to validity). Add, briefly and plainly:
   - Attrition: only 37 of the 73 logs behind expert aircraft diagnoses with a checkable cause could still be
     downloaded, so Table 7 has very small cells (n = 2 to 9); its results are indicative only.
   - Features: whole-window summary features (percentiles, shares of time, RMS) were used; sequence models or
     frequency-domain IMU features might capture short precursors that summaries miss. This was not tested.
   - Strengthen the language-model paragraph: the 60 cases were written by the authors who wrote the fixed rule,
     so the rule's 0 wrong answers is close to a training score; only 3-4B local models were tested.
   Also add the frequency-domain/sequence-model point as one clause in the Future work paragraph.

5. OPTIONAL — LANGUAGE-MODEL PANEL ON REAL CASES (only if Ollama is installed with gemma3:4b, phi4-mini,
   qwen2.5:3b, qwen3:4b, and /Volumes/One Touch/AeroFleet_px4_data/forum_logs/ is reachable).
   a) Write research/panel_eval/real_cases.py. Its docstring is the declaration: cases = the forum threads in
      research/results/px4_log_study/forum_expert_labels.csv with is_crash=yes, expert_conclusion=drone and a
      downloadable log in forum_logs/ (first available log id); ground truth = the settled expert cause mapped to
      the panel's fixed cause list (write the mapping in the docstring; causes outside the list count as
      "no cause"); facts = the same numbered facts the existing pipeline extracts from a log, using the window that
      ends 10 s before the crash moment (to avoid the crash-window leakage the paper reports); methods = the fixed
      rule, single agent and the panel, exactly as in research/panel_eval/run.py, temperature 0; measures = right /
      wrong / referred counts with 95% Wilson intervals. State the expectation in advance: on real logs every
      method is expected to do worse than on generated cases.
   b) Commit and push the declaration. Then run it. Save results to research/results/panel_eval/real_cases*.md.
   c) Report the result in Section 5.7 (two or three sentences and, if useful, one extra row group in Table 8)
      and in the Language-models threat paragraph, whatever the numbers are. If the fixed rule also fails on real
      logs, say so plainly; that supports the paper's main finding.
   If the prerequisites are missing, skip this step and say so in your final report. Do not simulate results.

6. REBUILD AND CHECK.
   - cd docs/paper/latex && tectonic -X compile --keep-intermediates main.tex && tectonic -X compile cover_letter.tex
   - Render page 1 (pdftoppm) and confirm nothing overflows into the footer; the abstract must stay at or under
     about 230 words. Confirm no "??" or "[" placeholders in the PDF text (pdftotext | grep).
   - Copy main.pdf, cover_letter.pdf, highlights.txt to docs/paper/submission/; rebuild
     docs/paper/submission/latex_source_for_overleaf.zip (main.tex, refs.bib, cover_letter.tex, highlights.txt and
     every figure main.tex includes, under figures/).
   - Regenerate the Word file: .venv/bin/python docs/paper/make_docx.py (needs pandoc and python-docx). Check it
     opens and has the same number of tables and figures as the PDF.
   - If any number changed, update every place listed in docs/HANDOFF.md section 8 (README, highlights,
     critical_review.md, HANDOFF section 5).
   - Add a short "Eighth pass: external review" section to docs/paper/critical_review.md: each review point, what
     was done, and what was not done and why.
   - Run the tests touched (and the full suite if code changed): .venv/bin/python -m pytest -q --no-cov tests/unit tests/integration
   - Commit with a clear message and push. Then clean macOS metadata files:
     find .git/objects/pack -name '._*' -size -5k -delete

Finally, report back: what changed, the page count, the new abstract word count, the optional step's result (or
why it was skipped), and anything you could not do.
```
