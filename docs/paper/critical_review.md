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
