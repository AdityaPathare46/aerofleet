# Protocol A1 & A2 (Amendment 1): Isolating Cohort Selection versus Comparison Population Effects on Crash Anticipation

**Date:** 26 October 2026  
**Status:** Exploratory ($^\dagger$), declared and committed to version control prior to running analysis code.  
**Prior Knowledge Disclosure:** The baseline values (cross-sectional AUC $\approx 0.88$, within-drone AUC $\approx 0.58$, duration-only AUC $\approx 0.662$) were observed in earlier rounds. The thresholds and design below are declared prior to executing this analysis, but are not blind.

---

## 1. Background and Motivation
In Section 5.3 and Table 6 of the manuscript, model ROC AUC drops from 0.88 (Step 0) to 0.53--0.57 (Steps 5 and 6). However, moving from Step 0 to Step 5 changes two factors simultaneously:
1. The crash cohort changes from 148 discovery crashes to 67 multi-flight crashes.
2. The comparison population changes from other aircraft's normal flights to the same aircraft's earlier flights.

This protocol pre-declares two analyses to isolate these mechanisms before inspecting any numbers:
- **A1:** Holding the crash set fixed to the 67 multi-flight airframes, evaluate them against matched normal flights from *other aircraft* strictly excluding the 67 airframes, using the identical 11 features, L2-regularized logistic regression, and 5-fold cross-validation.
- **A2:** In the 372-flight multi-flight cohort, evaluate the predictive power of feature-window duration alone, and evaluate duration-matched (caliper) comparisons within each airframe.

---

## 2. Anchor Runs and Abort Rule
To ensure pipeline integrity and exact comparability with existing manuscript figures, the analysis script must first execute two anchor runs:
1. **Anchor 1 (Step 0 Replication):** 148 crash vs. 139 normal discovery flights ($m=0$\,s, stratified 5-fold CV repeated 5 times, seed 42). Target ROC AUC: $0.883 \pm 0.03$.
2. **Anchor 2 (Step 6 Replication):** 67 crash vs. 305 earlier flights from the same 67 drones ($m=10$\,s, vehicle-grouped 5-fold CV repeated 5 times, seed 42). Target ROC AUC: $0.569 \pm 0.03$.
3. **Control (Label-Permutation):** Randomly permute labels across the cohort to confirm chance behavior (target AUC: $0.50 \pm 0.04$).

**Abort Rule:** If either Anchor 1 or Anchor 2 deviates by more than 0.03 from the target values, or if the permutation control deviates by more than 0.05 from 0.50, the run is immediately aborted and no A1/A2 results will be computed until the pipeline mismatch is resolved.

---

## 3. Protocol A1 Specification (Cohort vs. Population Isolation)

### 3.1 Features, Preprocessing, and Model
- **Features (11 features from Table 1):** Rate-tracking error (`tune_rms`), tilt 95th percentile (`tilt_p95`), vibration 95th percentile (`vib_p95`), clipping rate (`clip_rate`), motor saturation fraction (`sat_frac`), battery minimum (`batt_min`), voltage sag (`volt_sag`), poor GPS fraction (`poor_gps_frac`), failsafe active (`failsafe_active`), manual flight share (`manual_frac`), stick deflection 95th percentile (`stick_p95`).
- **Preprocessing:** Training-fold median imputation and z-score standardization (learned strictly on training folds and applied to test folds).
- **Model:** L2-regularized logistic regression ($\lambda = 1.0$), 5-fold vehicle-grouped cross-validation repeated 5 times with seeds 42, 43, 44, 45, 46.

### 3.2 Sample Selection & Matching
- **Crash Sample:** Exactly the 67 crash flights from `within_drone_features.jsonl` with $\ge 1$ usable earlier non-crash flight, cut 10\,s before estimated crash impact ($t_c - 10$\,s).
- **Control Sample (A1 - Task A matching):** Normal comparison flights drawn from the independent normal flight pool (`leak_curve_features.jsonl` / `per_log.jsonl`), strictly excluding every vehicle UUID belonging to the 67 multi-flight airframes. Controls are matched 2:1 on vehicle type (multicopter) and unrated/normal flight status (134 control flights).
- **Control Sample (A1b - Era-matched variant):** In addition to vehicle type, match 2:1 on PX4 firmware generation (PX4 v1.10–v1.11 vs. v1.12+) to pre-empt firmware era differences as the explanatory mechanism.

### 3.3 Resampling and Inference
- **Two-Stage Cluster Bootstrap:** 2,000 resamples. Resample crashed airframe clusters with replacement from the 67 crash clusters, and independently resample control airframe clusters with replacement from the control clusters.
- Compute the 95% two-stage cluster bootstrap confidence interval (BCa or empirical percentile).

### 3.4 Pre-declared Decision Rule on Intervals
Because sample size ($n=67$ crash vs. 134 controls) yields an expected 95% CI half-width of approximately $\pm 0.08$, decisions are governed strictly by interval bounds:
- **Comparison Population Effect Supported:** Supported *only* if the **lower bound** of the 95% cluster-bootstrap CI is $\ge 0.75$ ($\text{CI}_{95\%} \subset [0.75, 1.00]$). This indicates that the 67 crash flights retain high separability when evaluated against other aircraft, demonstrating that the comparison population (cross-sectional vs. within-drone) drives the gap.
- **Cohort Selection Effect Supported:** Supported *only* if the **upper bound** of the 95% cluster-bootstrap CI is $\le 0.65$ ($\text{CI}_{95\%} \subset [0.00, 0.65]$). This indicates that the 67 multi-flight crashes form an inherently less separable cohort across all comparison pools.
- **Inconclusive / Mixed:** If the 95% CI spans across 0.65 or 0.75, or lies within $(0.65, 0.75)$, the outcome is declared statistically inconclusive between cohort selection and comparison population mechanisms.

---

## 4. Protocol A2 Specification (Feature-Window Duration & Caliper Matching)

### 4.1 Feature-Window Duration Definition
- Duration is defined strictly as the **feature-window duration** (from take-off to $t_c - 10$\,s for crash flights; take-off to window end for earlier flights), NOT total flight length.

### 4.2 Duration-Only Separation
- Evaluate univariate ROC AUC of feature-window duration alone on the 372-flight cohort (67 pre-crash flights vs. 305 earlier flights) using 2,000 cluster bootstrap resamples.

### 4.3 Caliper Matching Within Drones
For each crash flight, select earlier flights of the same drone satisfying the log-duration caliper:
- **Primary Caliper:** $|\ln(\text{duration}_{\text{earlier}}) - \ln(\text{duration}_{\text{crash}})| \le 0.50$ (duration ratio 0.60 to 1.65).
- **Secondary (Tighter) Caliper:** $|\ln(\text{duration}_{\text{earlier}}) - \ln(\text{duration}_{\text{crash}})| \le 0.25$ (duration ratio 0.78 to 1.28).
- **Sample Attrition & Minimum Sample Size:** Minimum requirement of $n \ge 30$ matched drone pairs. If $n < 30$, mark caliper as underpowered.
- **Matched vs. Unmatched Comparison on Same Drones:** To isolate duration matching from drone attrition, report both the matched and unmatched model AUCs restricted to the exact same subset of retained drones.

### 4.4 Outcome Thresholds for A2
- **Duration Confounding Supported:** If duration-only AUC in the 372 cohort exceeds 0.65 (with 95% CI excluding 0.50), and caliper matching shifts within-drone AUC by $\ge 0.05$ or cross-sectional AUC drops by $\ge 0.05$, duration mismatch is confirmed as an active confounder.

---

## 5. Scope of Inference and Manuscript Impact

### 5.1 Causal Mechanism Wording
Results from A1 demonstrate whether the comparison population matters (incorporating duration, era, operator habits, and flight envelope differences), not that intrinsic physical airframe identity alone is the sole causal mechanism. Manuscript text must use:
*"This finding is consistent with comparison population differences (such as duration, firmware era, and operational flight envelope) that survive vehicle-grouped cross-validation..."* rather than attributing the gap purely to airframe identity.

### 5.2 Impact on Contribution (i) and Abstract
- **If Population Effect Supported ($\text{CI}_{\text{lower}} \ge 0.75$):** Contribution (i) and abstract retain the claim that changing comparison population from external aircraft to own baseline collapses diagnostic accuracy, explaining the cross-sectional illusion.
- **If Cohort Effect Supported ($\text{CI}_{\text{upper}} \le 0.65$):** Contribution (i) and abstract will be updated to state that the collapse is primarily driven by cohort selection (the multi-flight cohort is inherently less separable), qualifying the generality of cross-sectional detection.
- **If Inconclusive:** Contribution (i) will explicitly report that cohort selection and comparison population contributions cannot be statistically separated with the available sample of 67 multi-flight drones.
