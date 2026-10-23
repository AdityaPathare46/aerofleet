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
