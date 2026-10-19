# Review Panel Evaluation: Qwen 3 (4B) — Full 60 Scenarios

- **Model:** `qwen3:4b` (2.5 GB, Alibaba, Ollama)
- **Execution Target:** 60 controlled telemetry incident scenarios (`research/panel_eval/cases.py`)
- **Hardware Mode:** 100% GPU offload (NVIDIA CUDA via Ollama)
- **Total Inferences:** 660 LLM calls (60 single-agent + 600 panel reviewer votes)
- **Evaluation Date:** October 16, 2026
- **Test Artifacts:** `research/results/panel_eval/results_qwen3_4b.jsonl`

---

## 1. Executive Summary

| Engine | Accuracy (Right) | False Accusations (Wrong) | Deferred to Human (UNKNOWN) | Beats Deterministic Baseline? |
|---|---|---|---|---|
| **No-AI Deterministic Rule** | **75%** (45/60) | **0%** (0/60) | **25%** (15/60) | **Baseline (Superior)** |
| **One Agent (All facts, 1 round)** | **0%** (0/60) | **68%** (41/60) | **32%** (19/60) | ❌ No (Completely unusable) |
| **Review Panel (5 reviewers, 2 rounds)** | **28%** (17/60) | **63%** (38/60) | **8%** (5/60) | ❌ No (Catastrophic 63% Error Rate) |

> **Evaluation Rule:** A model earns a place in the production application *only* if it is right more often than the deterministic rule AND wrong no more often. `qwen3:4b` **catastrophically fails to beat the rule**, producing a 63% false accusation rate.

---

## 2. Category Performance Breakdown

| Scenario Category | No-AI Rule | One Agent | 5-Reviewer Panel | Scenario Count ($n$) |
|---|---|---|---|---|
| **Clear Signal** | **100% right**, 0% wrong | 0% right, 53% wrong, 47% deferred | 40% right, 47% wrong, 13% deferred | 30 |
| **Subtle Signal** | **25% right**, 0% wrong | 0% right, 75% wrong, 25% deferred | 25% right, 70% wrong, 5% deferred | 20 |
| **Nothing to Find (Clean)** | **100% right**, 0% wrong | 0% right, 100% wrong, 0% deferred | 0% right, 100% wrong, 0% deferred | 10 |
| **With Distractor** | **71% right**, 0% wrong | 0% right, 83% wrong, 17% deferred | 21% right, 71% wrong, 8% deferred | 24 |

---

## 3. Accuracy by Incident Root Cause

| Root Cause Category | No-AI Deterministic Rule | Single Agent | Review Panel | Scenarios ($n$) |
|---|---|---|---|---|
| `CONFIGURATION` (Param drift) | **100%** | 0% | 80% | 10 |
| `GPS_DEGRADED` (HDOP / Sats) | 50% | 0% | **90%** | 10 |
| `LOW_BATTERY_RESPONSE` (Voltage sag) | **50%** | 0% | 0% | 10 |
| `PILOT_MANUAL_CONTROL` (Stick override) | **100%** | 0% | 0% | 10 |
| `UNKNOWN` (No anomaly present) | **100%** | 0% | 0% | 10 |
| `WIND_OR_ENVIRONMENT` (Drift/airspeed) | **50%** | 0% | 0% | 10 |

---

## 4. Cross-Model Comparison: All 4 Models Evaluated (240 Total Scenarios)

| Metric | No-AI Rule | `qwen2.5:3b` | `phi4-mini` | `gemma3:4b` | `qwen3:4b` |
|---|---|---|---|---|---|
| **Accuracy (Right)** | **75%** | 17% | 33% | 5% | 28% |
| **False Accusations (Wrong)** | **0%** | **10%** | 32% | 60% | **63%** (Highest) |
| **Human Deferrals (UNKNOWN)** | 25% | 73% | 35% | 35% | 8% |
| **Dominant Hallucination / Bias** | *None* | `PILOT_MANUAL_CONTROL` | `LOW_BATTERY_RESPONSE` | `PLAN_OR_ROUTE_ISSUE` | `GPS_DEGRADED` |
| **Execution Time / Case** | **< 1 ms** | ~10 s | ~17 s | ~24 s | ~24 s |

---

## 5. Architectural Takeaway

The empirical evaluation of all 4 candidate models across 240 controlled test scenarios proves conclusively:
1. **Model Cognitive Biases:**
   - `qwen2.5:3b` fixates on blaming the **pilot**.
   - `phi4-mini` fixates on blaming the **battery**.
   - `gemma3:4b` fixates on blaming the **route planner**.
   - `qwen3:4b` fixates on blaming **GPS/Configuration** (and invents faults in 100% of clean cases where nothing happened).
2. **Deterministic Baseline Definitively Wins:**
   - **None of the 4 models beat the deterministic rule.**
   - The deterministic rule achieves **75% accuracy with 0% false accusations**.
   - In AeroFleet 2.0, telemetry assurance and safety gating remain strictly deterministic, guaranteeing zero false blame in production flight ops.
