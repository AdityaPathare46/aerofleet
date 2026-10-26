# Pre-Declared Protocol: Round 13 Peer Review Audit and Empirical Refinements

**Date:** 26 October 2026  
**Status:** Exploratory ($\dagger$) additions answering Round 13 peer review critiques.  
**Governing Principle:** All hypotheses, criteria, sampling schemes, feature definitions, and random seeds are committed to version control *before* the corresponding code is executed. Every empirical number must derive strictly from executed code.

---

## 1. Analysis R13-1: Single-History vs. Multi-History Crashes Decomposition
- **Objective:** Determine whether the cross-sectional model separation (Step 0: AUC 0.883) is driven by single-history crashes (vehicles with no earlier flights in the archive: maiden flights, bench tests) or whether it holds equally across multi-flight vehicles.
- **Sample Selection:** The 148 crashes from Step 0 partitioned by whether the vehicle UUID has $\ge 2$ flights in the archive index (multi-history, $n=103$) or only 1 flight (single-history, $n=45$), evaluated against the 139 Step 0 normal flights.
- **Evaluation:** Stratified 5-fold CV repeated 5 times (seeds 0–4) evaluated at $m=0$\,s and $m=10$\,s with L2-regularized logistic regression.
- **Hypothesis:** If separability is concentrated in single-history crashes (AUC $\approx 0.88$ for single-history vs. $\approx 0.55$ for multi-history), the headline result is an artifact of maiden/test flights. If both subsets yield high separation ($\text{AUC} \ge 0.80$), cross-sectional separation is an archive-wide phenomenon driven by duration and vehicle-type confounding across all airframes.

---

## 2. Analysis R13-2: Duration Caliper Curve and Paired Cluster Bootstrap
- **Objective:** Characterize the sensitivity of within-drone precursor detection to the duration matching caliper and compute formal uncertainty bounds on the observed AUC lift.
- **Caliper Grid:** Evaluate within-drone Group-CV AUC across logarithm duration ratio calipers $\epsilon \in \{0.10, 0.20, 0.25, 0.30, 0.50, 0.75, 1.00\}$.
- **Paired Cluster Bootstrap:** For the $\epsilon = 0.25$ primary comparison ($n=36$ airframes), compute a paired cluster bootstrap over the 36 airframe clusters (2,000 resamples, seed `2026`) on the difference $\Delta = \text{AUC}_{\text{matched}} - \text{AUC}_{\text{unmatched}}$.
- **Permutation Control:** Permute within-cluster flight duration labels (1,000 permutations) to confirm that the $+0.110$ lift is non-random.
- **Feature Attribution:** Report univariate AUCs for each of the 11 telemetry features before and after caliper matching on the same 36 airframes.

---

## 3. Analysis R13-3: GPS Timestamp Ordering on Same-Day Sets
- **Objective:** Verify temporal sequencing for all 35 sets where exposure flights occurred on the same calendar day as the crash flight.
- **Procedure:** Compare the raw ISO/GPS start timestamps of each exposure flight against the crash flight timestamp in `dbinfo.json`.
- **Criterion:** Flag any exposure flight recorded after the crash flight. If any post-crash flights exist, exclude them and re-evaluate the between-drone scaled rank test.

---

## 4. Analysis R13-4: Two-Stage Cluster Bootstrap for Between-Drone Vibration
- **Objective:** Address reviewer concern that resampling only control airframes ignores case sampling uncertainty.
- **Procedure:** Perform two-stage cluster bootstrap resampling *both* case airframes ($n=60$) and unique control airframes ($n=107$) with replacement (2,000 resamples, seed `777`).

---

## 5. Analysis R13-5: Rule Discrimination across Margins
- **Objective:** Evaluate the eight-sign attribution rule's balanced accuracy across cut-offs $m \in \{0, 5, 10, 20, 30\}$\,s on held-out crashes ($n=112$) and expert logs ($n=43$).
