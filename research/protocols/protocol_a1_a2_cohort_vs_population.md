# Protocol A1 & A2: Isolating Cohort Selection versus Comparison Population Effects on Crash Anticipation

**Date:** 26 October 2026  
**Status:** Exploratory ($^\dagger$), declared and committed to version control prior to running analysis code.  
**Author:** Research Team (AeroFleet Study)

---

## 1. Background and Motivation
In Section 5.3 and Table 6 of the manuscript, model ROC AUC drops from 0.88 (Step 0) to 0.53--0.57 (Steps 5 and 6). However, moving from Step 0 to Step 5 changes two factors simultaneously:
1. The crash cohort changes from 148 discovery crashes to 67 multi-flight crashes.
2. The comparison population changes from other aircraft's normal flights to the same aircraft's earlier flights.

This protocol pre-declares two analyses to isolate these mechanisms before inspecting any numbers:
- **A1:** Holding the crash set fixed to the 67 multi-flight airframes, evaluate them against matched normal flights from *other aircraft*, using identical features, L2-regularized logistic regression, and 5-fold cross-validation.
- **A2:** In the 372-flight multi-flight cohort, evaluate the predictive power of duration alone, and evaluate a duration-matched (caliper) comparison within each airframe.

---

## 2. Protocol A1 Specification (Cohort vs. Population Isolation)

### 2.1 Sample Selection
- **Crash Sample:** Exactly the 67 crash flights from `within_drone_features.jsonl` that have $\ge 1$ usable earlier non-crash flight, cut 10 s before estimated crash impact.
- **Control Sample (Other Aircraft):** Normal comparison flights drawn from the independent normal flight pool (`leak_curve_features.jsonl`), strictly excluding any `vehicle_uuid` belonging to the 67 multi-flight airframes. Controls are matched 2:1 on vehicle type (multicopter) and PX4 firmware generation.

### 2.2 Features and Model
- Identical to Table 6 Steps 0--5: normalized whole-window telemetry features (`tune_rms`, `tilt_p95`, `vib_p95`, `sat_frac`, `volt_sag`, `manual_frac`).
- Imputation: training-fold median.
- Model: L2-regularized logistic regression ($\lambda = 1.0$), 5-fold cross-validation repeated 5 times.

### 2.3 Pre-declared Decision Rule
Before running the code, we pre-specify the following interpretation thresholds:
- **Comparison Population Effect Supported:** If the 67 crashes against other-aircraft normal flights achieves an ROC AUC $\ge 0.75$, the drop from 0.88 to 0.55 is primarily driven by the comparison population (comparing against other aircraft introduces between-airframe confounding that vanishes when comparing against the same aircraft).
- **Cohort Selection Effect Supported:** If the 67 crashes against other-aircraft normal flights achieves an ROC AUC $\le 0.65$, the drop is primarily driven by cohort selection (the 67 multi-flight drones represent a distinct, less separable airframe sample than the 148 discovery crashes).
- **Mixed Effect:** If $0.65 < \text{AUC} < 0.75$, both cohort selection and comparison population contribute substantially.

### 2.4 Resampling and Inference
- 2,000 cluster bootstrap resamples by vehicle/drone cluster.
- 2,000 flight-level bootstrap resamples for comparison.
- Fixed random seed: 42.

---

## 3. Protocol A2 Specification (Duration Confounding & Caliper Matching)

### 3.1 Duration-Only Separation
- Evaluate ROC AUC of flight duration alone on the 372-flight cohort (67 crash flights cut 10 s before impact vs. 305 earlier flights).

### 3.2 Duration-Matched Caliper Step
- For each of the 67 crash flights, select earlier flights of the same drone whose flight duration falls within a pre-specified log-duration caliper:
  $$|\ln(\text{duration}_{\text{earlier}}) - \ln(\text{duration}_{\text{crash}})| \le 0.50$$
  (corresponding to a duration ratio between 0.60 and 1.65).
- Crashes with no matching earlier flight within the caliper are dropped, and sample attrition is explicitly reported.
- Evaluate model ROC AUC and mean pairwise within-drone AUC on the duration-matched subset.

### 3.3 Institutional Data Caveat
- In the public Flight Review index, earlier non-crash flights were required to have recorded duration $\ge 30$\,s, whereas crash flights were eligible if $\ge 5$\,s. This institutional filter inevitably creates a baseline duration difference that this analysis quantifies.
