# Critical review of the first draft (23 October 2026), and what was done about it

Written the way a demanding reviewer at *Reliability Engineering & System Safety* would write it. Each point says
whether it was fixed in the revised manuscript (`latex/main.tex`), answered with new analysis, or is still open.

## Verdict on the first draft

**Major revision: not submittable as it stood.** The core findings are interesting and unusually well
protected against self-deception, because the tests were declared in advance. But the draft was too short for the
journal (about 2,900 words), its single positive result had not been tested for robustness, several references
were unverified, and it read partly as an advertisement for the authors' tool.

## Major issues

| # | Criticism | Action | Status |
|---|---|---|---|
| M1 | **The one positive result could be confounded.** Vibration differs between airframes, so matching only on flight controller, firmware and vehicle type is weak. | Re-ran with same-airframe controls only (S1): 0.69, p = 0.008, 39 sets | Fixed: holds |
| M2 | **Case flights close to the crash** may show damage that already happened rather than a "rough airframe". | Removed crash-day flights (S2): 0.76, p = 0.003, 25 sets. Within-drone null shows no build-up within the crash flight | Fixed: holds |
| M3 | **Flight duration** differs (cases 289 s vs controls 173 s), and longer flights could vibrate more. | Duration is barely correlated with vibration (Spearman ρ = 0.05 and −0.04 by source); after adjusting for duration, 0.69, p = 0.0005 (S8) | Fixed: holds |
| M4 | **Mixed vibration measures.** The older estimator metric and the modern accelerometer metric differ. | Split by source (S3): estimator 0.68, p = 0.005 (48 sets); modern metric 0.62, p = 0.19 (12 sets, underpowered). Stated as a limitation: the effect is shown mainly on older firmware | Disclosed; needs more modern-firmware data |
| M5 | **Multiple testing.** One positive result among many tests could be chance. | Holm correction over all seven p-valued confirmatory tests: between-drone vibration stays significant (adjusted p = 0.016); all others stay non-significant | Fixed |
| M6 | **Crash-moment estimate** (tilt over 60°) is arbitrary. | Within-drone test at 45° and 75° (S7): 0.46 and 0.50, unchanged | Fixed: robust |
| M7 | **Label validity.** Uploader ratings are unverified, "normal" is self-rated, and controls "without a crash rating" may have crashed. | Agreement with expert diagnoses reported; misclassification of controls biases the test towards no difference, which is stated; full threats section | Disclosed |
| M8 | **Forum labels** were AI-assisted with one recorder. | Disclosed in Methods and the AI declaration; quote verification reported (123/124) | **Open**: needs a second independent recording or a measured spot-check before submission |
| M9 | **Sample representativeness.** The archive is dominated by developer and test flights, and crash logs differ from good logs in duration and firmware era. | Added a composition table (S0) and a generalisability paragraph | Disclosed |
| M10 | **Practical value is asserted, not shown.** Does the ranking help? | Added a screening figure: the crashed drone was the roughest of its matched set in 55% of sets, against 41% expected by chance | Fixed (modest effect, stated as such) |
| M11 | **Conflict of interest and promotion.** The draft promoted the authors' tool. | Tool reduced to one sentence in the Discussion, with a disclosure; title has no product name | Fixed |
| M12 | **Too short; thin methods and related work.** | Rewritten in Elsevier LaTeX: about 4,700 words of text plus 7 tables and 6 figures (up from about 2,900 words, 3 tables, 3 figures). Adds feature definitions, the test formula and null distribution, matching details, a dataset comparison, a per-feature AUC table, both fault-check runs and 33 verified references | Fixed (a compact full-length article; lengthen only if the journal asks) |

## Minor issues

| # | Criticism | Action |
|---|---|---|
| m1 | No study-design overview | Added a sample-flow figure (Fig. 1) |
| m2 | "Scaled rank" needs a formula and an interpretation | Defined, and related to the probability that the case exceeds a random control |
| m3 | AUCs reported without uncertainty | SD over repeated cross-validation reported; rank CIs by bootstrap |
| m4 | Units of the vibration metrics not given | Stated per source; comparisons are within source only |
| m5 | Results depend on a snapshot of a changing archive | Snapshot date, index size and a SHA-256 of the index file are reported |
| m6 | Ethics of forum data | Only public posts are used; usernames and post text are not redistributed; derived labels only |
| m7 | LLM experiment uses generated cases | Moved to a clearly secondary subsection; limitation stated |
| m8 | Six references marked "to verify" | All verified against publisher or index records, except AAIB/EASA/FAA documents cited as institutional sources |
| m9 | Inconsistent wording (aircraft / drone / UAV) | Unified: "drone" for the vehicle, "aircraft-caused" vs "pilot-caused" for the labels |
| m10 | Abstract and highlights limits | Abstract 250 words or fewer; 5 highlights of 85 characters or fewer, in a separate file as Elsevier requires |

## Originality and AI-text checks: what was and was not done

- **Similarity (plagiarism) check.** No commercial checker (iThenticate or Turnitin) is available here. Elsevier runs
  iThenticate (Crossref Similarity Check) on every submission, and a university library can run it beforehand.
  What was done here:
  - the text was written from our own results, not adapted from sources;
  - no sentence was copied from any cited paper;
  - forum posts are summarised, never quoted;
  - a script compared the manuscript against the abstracts of the cited works available in this session, looking
    for shared 8-word sequences. The result is in `originality_check.md`.
- **"AI plagiarism" (AI-text detection).** AI detectors are unreliable and are not a publisher requirement. Elsevier's
  rule is **disclosure**: AI-assisted writing is allowed if declared, and the authors stay responsible. The manuscript
  contains that declaration. The text was revised to be specific and plain. It was **not** written to evade
  detectors, and nothing should be: hiding AI assistance would breach the journal's policy.

## Still open before submission

1. A second independent forum recording (M8), with agreement reported.
2. Author names, affiliations, CRediT roles, competing interests and funding (placeholders in the LaTeX file).
3. A public repository URL (and a Zenodo DOI for the release), plus a check of PX4 Flight Review's terms before
   sharing anything beyond log IDs and derived features.
4. Read the journal's current guide for authors; the publisher page could not be fetched from here.
5. Run the institution's iThenticate check, and have every author read and edit the full text.

## Second review: Atharv's critic and gap analysis (23 October 2026)

Atharv's critic reviewed `aerofleet/README.md` (his working README, not the repository README or this paper). His
points were checked against the code; what was done:

| Point | Verdict after checking the code | Action |
|---|---|---|
| Raw uploaded files not bound to the signed record | Correct | Every record now carries name, size and SHA-256 of the exact files received |
| Operator can rebuild the whole chain | Correct (the code said so) | Heads file written after each commit; `GET /ledger/head`; verify checks recorded heads; threat model in README |
| No standalone verifier | Partly (export existed; tamper tests existed) | `tools/verify_ledger.py` (Python + `cryptography` only), with tamper tests incl. a full re-signing with a new key |
| Concurrent appends fork the chain | Wrong (sequence is the primary key), but a request could fail | Savepoint retry; 12-writer test |
| Reports imply false precision | Correct | Evidence-quality block: sample rate, GPS, height reference, clock, tolerances |
| Reconciliation has no ground truth | Correct, and it found a real flaw | Injection test on 40 real flights; nearest-leg matching replaced by whole-flight ordered alignment (90-95% detection of 35-50 m, 0/40 false alarms at 5 s waypoint spacing) |
| LLM numbers need intervals and coverage; cases are self-built | Correct | Wilson intervals and the 35-of-50 coverage in the paper; circularity stated in threats; blind cases still needed from a second person |
| Accident reporting is Rule 29 | Wrong: the Drone Rules 2021 text has Rule 30 | None |
| Type certificate is Rule 6, not 14(3) | Both: Rule 6 is the general rule, Rule 14(3) repeats it for registered systems | Notes now cite both |
| HTML report open to injected script | Wrong (all values escaped) | None |
| Pairing code brute-forceable | Largely wrong (desktop approval required; 120 s expiry) | None now |

## Third review: final pass after retitling and the tool section (23 October 2026)

**Rating before this pass: 6.5/10.** Sound, honest empirical core, but the new title promised something for operators
that the paper only covered in one Discussion paragraph; the abstract did not mention the tool; one data sentence
mixed up 161 expert threads and 148 real crashes; the panel method repeated itself; the title page overflowed.

What was done:

| Problem | Fix |
|---|---|
| Title and paper did not match the project | New Section 6 "Design implications": a finding → decision → check table, evidence-not-verdicts, vibration ranking, signed record, planned-versus-flown (injection results incl. the rejected first version), description search, 3D replay and rehearsal |
| VR part absent | Section 6.3 and Fig. 7 (mission rehearsal, real capture from the tool, before/after deconfliction), with its limits: kinematic rehearsal, no wind or dynamics, desktop-checked only, headset app not run, no user study |
| New feature untested | Declared and ran a leave-one-out test of the description search: 20% vs a 32% base rate, criterion not met. Reported in the abstract and Section 6.2; the product changed to a checklist ordered by expert frequency |
| Overclaims in the new text | "declared before they were run" limited to the two declared checks; the search is said to have been tested after a first release |
| Abstract over-long, title page overflow | Abstract cut to ~230 words; page 1 fits |
| 161 vs 148 threads | Data section now says 161 expert threads, 148 describing a real crash |
| Related work had nothing on the tool's methods | Case-based reasoning, BM25, worlds-in-miniature (DOIs checked on Crossref) |
| Competing-interest pointer and data statement | Point to Section 6; tool source code listed as released |
| Highlights, cover letter | Updated; all highlights ≤ 85 characters |

**Rating after this pass: 7.5/10.** What holds it below 8–9 cannot be fixed by editing:

- Labels are the uploaders' own; normal flights are self-rated. A second, independent coding of the forum threads
  (inter-rater agreement) is the cheapest real improvement: one person, about a day. **Ask Atharv.**
- The positive result rests mainly on the older vibration estimate (48 sets); the newer metric has 12 sets.
- No prospective test of the vibration ranking; no user study of the 3D views; the description search was tested on
  forum titles, not operators' reports.
- Language-model cases were written by the authors; the blind set is still to come.
- Author names, affiliations, repository URL and archived DOI are placeholders.

## Fourth pass: the three remaining weaknesses (24 October 2026)

| Weakness | What was done | Status |
|---|---|---|
| One forum recorder | Blind second coding set up on the existing reviewer-B sheet; `SECOND_CODER.md`; scoring compares it with the first recording; pass mark kappa >= 0.60 declared | **Waiting for Atharv** (about a day) |
| Newer vibration metric only 12 sets | Declared replication with every eligible newer-firmware drone (`rough_drone_newer.py`, 170 logs downloaded): 19 usable sets, mean rank 0.58, 95% CI 0.39-0.76, p = 0.25. **Not confirmed.** Reported in the abstract, results, discussion, threats, conclusion and a highlight | Done; the headline is now qualified |
| No prospective test, no users | Both declared in `research/protocols/prospective_and_user_study.md` with outcomes and pass marks; cited in Future work | Needs partner fleets and 12-16 participants; cannot be done today |

Rating stays at **7.5/10**. The replication honestly weakens the positive result (the archive has no more
newer-firmware cases), and the transparency strengthens the paper. The next real gain is the kappa from the second
coding.

## Fifth pass: the remaining list (25 October 2026)

| Weakness | What was done | Status |
|---|---|---|
| False alarms unknown on real mission plans | Declared check on archive logs that record their mission (`real_mission_reconcile.py`): only 6 distinct missions; no deviation in mission mode; the 2 reported were real departures (RTL, pilot takeover). Added to Section 6.1 | Inconclusive (too few); needs a partner fleet's files |
| Leftovers from the earlier product | Four old start scripts deleted; Incident replay (AI council) removed from the VR view | Done; Live swarm (simulated) remains |
| Second coding | First returned sheet rejected by the new quote check; blank redo sheet issued | Waiting for Atharv |
| Newer metric | Archive exhausted (19 usable sets, not confirmed) | Cannot improve from this archive |
| No real operator, no fleet, no headset run, no user study | Protocols declared; handoff written (`docs/HANDOFF.md`) so work can continue with any assistant | Needs people and hardware |

Ratings unchanged: paper 7.5/10, product 7/10. The next gains need people, not code.

## Sixth pass: second coding returned (25 October 2026)

Atharv's blind redo passed the quote check (150 of 151 rows quote their own thread or record no diagnosis; the
first attempt, 2 of 50). The check itself was corrected first: it had compared whole sentences and wrongly failed
quotes that are part of a sentence; the corrected check still rejects the first attempt. Agreement on 147 threads:
kappa 0.81 (0.71-0.88) for the expert's conclusion, 0.73 (0.65-0.81) for the cause, 0.79 for confirmation; the
declared pass mark of 0.60 is met. Reported in Section 3.3 and Threats. 45 threads differ and are to be settled.

**Paper rating: 8/10.** The labels behind Q4, Fig. 6 and the knowledge base are now shown to be reliable. What
remains below 9: the positive result rests on the older vibration metric, and there is no prospective or user data.

## Seventh pass: disagreements settled (25 October 2026)

The two coders settled the 45 disagreements; 13 labels changed (6 threads became aircraft-caused). Everything that
uses the labels was re-run on the settled labels, and the published first-recording results were kept beside them:

| Result | First recording | Settled labels |
|---|---|---|
| Expert blamed the aircraft | 88 of 148 (59%) | 94 of 148 (64%) |
| Tuning check, crash included / last 10 s removed | 13/15 / 2/10 | 10/12 / 1/9 |
| Any expert-fault check meeting the pass mark | none | none |
| Description search vs base rate (leave-one-out) | 20% vs 32% (90 cases) | 22% vs 27% (96 cases) |
| Aircraft-rated threads where the expert agreed | 9 of 14 | 11 of 14 |

Every conclusion is unchanged. The full-window fault check was re-run with the script version that produced the
published table (commit 4475c8c), which reproduced 13/15 exactly on the first recording; the later version adds a
10 s minimum window. Paper rating stays at 8/10.

## Eighth pass: external review (25 October 2026)

An external reviewer rated the manuscript **7.8/10**, highlighting four core weaknesses and asking for explicit grounding on the new **AeroFleet 2.0** tool. Each point was addressed in the manuscript and documentation:

| # | Review critique | Action taken | Status |
|---|---|---|---|
| 1 | **The main positive result needs stronger replication.** The between-drone vibration result relies mainly on an older vibration metric; the replication on the newer accelerometer metric was inconclusive with only 19 usable matched sets (page 14). | Section 5.5, Discussion (`Drone-level risk`), and Threats (`Measurement`) now state explicitly that the public archive has no further newer-firmware cases satisfying matching criteria, so the archive is exhausted. Stated plainly that the main positive result requires stronger replication with prospective recording in modern fleets (`research/protocols/prospective_and_user_study.md`). | Disclosed & acknowledged |
| 2 | **The crash labels are imperfect.** Uploader-assigned responsibility labels are not independently verified ground truth. The expert-diagnosed sample is useful, but many logs are no longer available and some diagnostic comparisons have very small sample sizes. | Section 3.1, Section 8 (`Labels`), and Section 8 (`Attrition`) explicitly state that uploader-assigned responsibility labels are not independently verified ground truth and reflect uploaders' perceptions. Acknowledged that only 37 of 73 logs behind expert aircraft diagnoses could still be downloaded, leaving small cell counts in Table 7 ($n = 2$ to $9$) that are indicative only. | Disclosed & acknowledged |
| 3 | **The software needs real-world validation.** AeroFleet's checks are primarily engineering tests, not evidence of improved operational safety. Prospective fleet evaluation and user studies remain future work (Sections 6 and 7). | Section 6 opening paragraph, Section 6.3, Section 8 (`The tool`), and Discussion (`Future work`) state unequivocally that AeroFleet~2.0's checks are engineering validation tests on archive data and synthetic fault injections, not evidence of improved operational safety. Establishing safety benefit requires prospective fleet trials and user studies, which are declared in `research/protocols/prospective_and_user_study.md`. | Disclosed & framed conservatively |
| 4 | **The AI comparison is preliminary.** The language-model experiments use 60 author-generated cases and relatively small local models. The fixed rule's performance may be optimistic on cases created by the same authors. | Section 5.7 and Section 8 (`Language models`) explicitly characterize the AI comparison as preliminary, using 60 author-generated cases and small 3--4B local models. The text openly acknowledges in first-person author voice that the fixed rule's score is close to a training score; an independent blind-case protocol is in preparation. | Disclosed & acknowledged |
| 5 | **Grounding on AeroFleet 2.0.** The paper describes the new ground-side assurance tool. | Updated Abstract, Introduction, Section 6, Table 9 caption, Discussion, Threats, Cover letter, and competing interest / data availability declarations to specify **AeroFleet 2.0** throughout, distinguishing it from legacy dispatch systems. | Fixed everywhere |
| 6 | **Placeholders & sample drops.** Complete end matter and explain exact sample drops. | Filled competing interest, funding, and repository URL; verified no `[...]` or `??` remain; documented exact drop numbers in Section 3.2 (within-drone: 101 selected, 55 unreadable/<10s -> 61 and 46 analysed; between-drone: 66 sets, 71 unreadable/<10s -> 60 and 47 analysed). | Fixed |
| 7 | **Reviewer editorial & layout fixes.** Editorial voice in Section 8, page references, figure positioning, and axis clipping. | Replaced third-person reviewer phrasing in Section 8 with author voice; replaced hardcoded page numbers with section cross-references; added `\FloatBarrier\clearpage` before references so Figure A.7 renders in Appendix A without interrupting the bibliography; widened Figure 4 canvas to 5.0 inches with `pad_inches=0.1` so x-axis labels are fully intact. | Fixed |

## Ninth pass: peer review revision (25 October 2026)

A formal peer review for *Reliability Engineering & System Safety* rated the submission **6.5/10**, identifying key methodological nuances and framing requirements to reach **~8/10**. Every weakness, required fix, and smaller critique has been addressed:

| # | Peer review critique | Action taken | Status |
|---|---|---|---|
| 1 | **Negative attribution result framing & pilot blame gap.** Hand-built rule and L2 regression against noisy labels cannot separate "logs can't attribute crashes" from "noisy labels or weak features." Agreement only checked on aircraft-rated logs. Experts blamed pilots in 6% of threads vs 32% of uploader labels (politeness bias or different definitions). Below-chance CV AUCs (0.42–0.46) signal small-sample label artefacts. | Softened "not achievable" to "not achievable with these labels and features" across abstract, intro, results, discussion, and conclusion. Added thorough discussion of the 6% vs 32% pilot blame discrepancy in Section 3.1, 7, and 8 (politeness bias on developer forums, selection bias in submitted logs, or narrower engineer definitions of pilot error). Clarified that expert agreement (11/14) was verified for aircraft-rated crashes only, leaving pilot-rated labels unverified against expert ground truth. Explained that regularized models on small samples with label noise produce below-chance CV AUCs within the permutation null. | Addressed & softened |
| 2 | **Headline positive result is fragile; overreaching interpretation.** Effect is carried by older estimator metric; newer metric replication was inconclusive ($p=0.25$), yet Table 5 says "Supported." Removing crash-day flights shrinks sample from 60 to 25 sets, indicating earlier flights came from the same session (confounding by experimental tuning sessions vs gradual wear-and-tear degradation). Matching ignores airframe size, propellers, payload, and operator clustering. Low operational PPV. | Relabeled Table 5 outcome as `Supported on older metric only; replication inconclusive` and stated this prominently in the abstract and discussion. In Section 5.5 and 7, discussed that removing crash-day flights shrinks sample from 60 to 25 sets, directly contrasting the "maintenance degradation" hypothesis with the "experimental airframe tuning" hypothesis. Acknowledged unmodeled clustering (matching ignored propellers, payload, airframe size, and operator identity). Calculated and reported operational screening metrics at the upper-quartile flag: sensitivity ~55%, specificity ~75%, and operational PPV $\approx 3.3\%$ (approx 1 in 30 flagged drones crashes given the ~1.5% base rate), framing the metric strictly as a broad inspection filter rather than a crash warning. | Addressed & conservatively framed |
| 3 | **Crash-versus-normal AUC (0.88) is confounded.** Crash and normal flights differ in duration (54 s vs 388 s), firmware era, and flight style (lower tilt and stick deflections). Full-model separation is not simply "a property of the drone." | De-emphasized the claim that 0.88 AUC is "a property of the drone." Explicitly explained in Section 5.3, 7, and 8 that model-level separation reflects baseline group confounders (flight duration, firmware era, and cautious or truncated flight style) rather than unconfounded pre-crash anomaly detection. | Reframed |
| 4 | **Confusing headline numbers and sample flow.** Retitle or clarify real N vs 479,547 logs in title. Counts vary (590 in index, 520 with complete records in Table 2, 100, 93+112, 148, 101 -> 61/46, 66 -> 60/47). PX4 1.10+ filter in Section 3.2 conflicts with older-firmware vibration study. High attrition (55/101 and 71 flights). | Reconciled all numbers across Section 3.1, 3.2, Table 2, and Table 3: 479,547 logs in public index -> 442,929 real hardware -> 38,320 vehicle IDs -> 590 uploader crash ratings (402 aircraft, 188 pilot) -> 520 real-hardware crash logs with complete duration and firmware records. Clarified that while initial exploratory cross-sectional samples (Q1, Q2) selected PX4 1.10+, the longitudinal studies (Q3b, Q3c) lifted the firmware filter in advance to avoid sample collapse and matched within firmware generation and measurement source. Explicitly detailed attrition in both within-drone and between-drone samples. | Fully reconciled |
| 5 | **Self-hosted "pre-registration."** Commits in author-controlled repo can be rewritten; lifting firmware filter after seeing $n=12$ was data-dependent. | Replaced "pre-registration" with "declared test protocols committed to version control in advance of data analysis" in title keywords, intro, and methods. Explicitly acknowledged in Section 4.1 that git commits are self-hosted and lack third-party timestamped registries (like OSF), and transparently documented that lifting the firmware filter was data-dependent. | Clarified & disclosed |
| 6 | **Language-model review panel circularity & clarification.** 60 cases written by rule authors; single-agent right/wrong counts do not sum to 60; 40 hostile strings not reaching prompt is true by construction; adversary test measures compromised reviewer sensitivity, not prompt injection. | In Section 5.6 and Table 8 caption, explicitly clarified single-agent counts: right + wrong + referred/abstentions sum to 60 (gemma3: 10 right, 0 wrong, 50 referred; phi4: 10 right, 0 wrong, 50 referred; qwen2.5: 9 right, 44 wrong, 7 referred; qwen3: 0 right, 41 wrong, 19 schema parse failures). Clarified that 40 hostile strings not reaching prompts is by construction of deterministic numeric parsing, and clarified that the adversary test evaluates susceptibility to a rogue participant in multi-agent voting rather than prompt injection. | Clarified & framed conservatively |
| 7 | **Section 6 focus & tool checks.** Software checks (planned-vs-flown 22% false alarms, $n=6$ real missions, BM25 search underperforming base rate at 22% vs 27%, desktop 3D replay without user study) should not pull paper apart from empirical findings. | Focused Section 6 directly on how empirical findings translate into design: (1) evidence-only review with no automatic verdicts, and (2) fleet vibration ranking for maintenance screening with explicit low PPV (~3.3%). Contextualized all other software tests as engineering verification rather than evidence of operational safety benefit. | Focused & streamlined |
| 8 | **Smaller fixes.** Fisher test on pilot vs aircraft contrast; windowing asymmetry; multi-causal framing; 41% chance expectation; within-drone exclusion bound; abstract leading with 3 takeaways; verify 2026 references. | (a) Computed and reported Fisher's exact test for pilot vs aircraft protection-disabled contrast: 14/20 (70%) vs 15/37 (41%), difference $+29.5\%$ (95% CI $3.9$--$55.0\%$, OR 3.42, two-sided $p=0.052$). (b) Documented windowing asymmetry (normal flights include landing/disarm; crash windows cut at tilt). (c) Framed accident attribution as multi-causal (HFACS) rather than binary. (d) Explained the 41% null expectation mathematically: $(35 \times 1/3 + 25 \times 1/2)/60 \approx 40.3\%$. (e) Reported within-drone null as an exclusion bound (upper 95% CI of 0.58 rules out surges of magnitude $\bar{r}=0.67$). (f) Rewrote abstract to 214 words leading with three takeaways. (g) Verified 2026 references on arXiv and added complete URLs and DOIs in `refs.bib`. | All resolved |


