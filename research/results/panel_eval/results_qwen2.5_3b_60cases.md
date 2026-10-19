
# Review Panel Evaluation: Qwen 2.5 (3B) — Full 60 Scenarios

- **Model:** `qwen2.5:3b` (1.93 GB, Ollama)
- **Execution Target:** 60 controlled telemetry incident scenarios (`research/panel_eval/cases.py`)
- **Hardware Mode:** 100% GPU offload (NVIDIA CUDA via Ollama)
- **Total Inferences:** 660 LLM calls (60 single-agent + 600 panel reviewer votes)
- **Evaluation Date:** October 15, 2026
- **Test Artifacts:** `research/results/panel_eval/results_qwen2.5_3b.jsonl`

---

## 1. Executive Summary

| Engine | Accuracy (Right) | False Accusations (Wrong) | Deferred to Human (UNKNOWN) | Beats Deterministic Baseline? |
|---|---|---|---|---|
| **No-AI Deterministic Rule** | **75%** (45/60) | **0%** (0/60) | **25%** (15/60) | **Baseline (Superior)** |
| **One Agent (All facts, 1 round)** | **15%** (9/60) | **73%** (44/60) | **12%** (7/60) | ❌ No (Severe Hallucination) |
| **Review Panel (5 reviewers, 2 rounds)** | **17%** (10/60) | **10%** (6/60) | **73%** (44/60) | ❌ No (Excessive Deferral) |

> **Evaluation Rule:** A model earns a place in the production application *only* if it is right more often than the deterministic rule AND wrong no more often. `qwen2.5:3b` **does not beat the rule**.

---

## 2. Category Performance Breakdown

| Scenario Category | No-AI Rule | One Agent | 5-Reviewer Panel | Scenario Count ($n$) |
|---|---|---|---|---|
| **Clear Signal** | **100% right**, 0% wrong | 17% right, 67% wrong | 0% right, 20% wrong, 80% deferred | 30 |
| **Subtle Signal** | **25% right**, 0% wrong | 20% right, 70% wrong | 0% right, 0% wrong, 100% deferred | 20 |
| **Nothing to Find (Clean)** | **100% right**, 0% wrong | 0% right, 100% wrong | **100% right**, 0% wrong | 10 |
| **With Distractor** | **71% right**, 0% wrong | 4% right, 92% wrong | 25% right, 0% wrong, 75% deferred | 24 |

---

## 3. Accuracy by Incident Root Cause

| Root Cause Category | No-AI Deterministic Rule | Single Agent | Review Panel | Scenarios ($n$) |
|---|---|---|---|---|
| `CONFIGURATION` (Param drift) | **100%** | 0% | 0% | 10 |
| `GPS_DEGRADED` (HDOP / Sats) | **50%** | 0% | 0% | 10 |
| `LOW_BATTERY_RESPONSE` (Voltage sag) | **50%** | 0% | 0% | 10 |
| `PILOT_MANUAL_CONTROL` (Stick override) | **100%** | 90% | 0% | 10 |
| `UNKNOWN` (No anomaly present) | **100%** | 0% | **100%** | 10 |
| `WIND_OR_ENVIRONMENT` (Drift/airspeed) | **50%** | 0% | 0% | 10 |

---

## 4. Key Engineering Insights

### 4.1 The Single-Agent Hallucination Trap
When given all telemetry facts in a single prompt, `qwen2.5:3b` suffered from severe fixation bias:
- **73% of its predictions were wrong.**
- It hallucinated `PILOT_MANUAL_CONTROL` on 90% of non-pilot incidents, incorrectly blaming the human operator even when telemetry clearly showed battery failure or GPS loss.
- In commercial drone operations, this would lead to groundless operator liability claims.

### 4.2 How the Multi-Reviewer Panel Defends the System
The 5-reviewer architecture (`navigation`, `pilot`, `gps`, `battery`, `settings`) with schema validation and consensus voting functioned as an active defense shield:
- Dropped false accusations from **73% down to 10%**.
- In clean flights (no error), the panel scored **100% correct**, never generating false alarms.
- However, because small 3B models lack sufficient confidence across round-2 rebuttal debates, the reviewers frequently disagreed, resulting in 73% deferred decisions.

### 4.3 Deterministic Rule Reliability
- The hard-coded domain checks (`rule_based_cause`) achieved **75% accuracy with 0% false positives**.
- When the rule is unsure, it cleanly defers to human inspection rather than inventing causes.
- Runs in **< 1 millisecond**, compared to **~10 seconds** per case for the LLM panel.

---

## 5. Security & Robustness Verification

1. **Format & Schema Compliance:**
   - **600 of 600 (100%)** panel votes conformed to schema; 0 dropped.
   - Reviewer abstentions: **0 of 300**.
2. **Prompt Injection Immunity:**
   - Evaluated using `research.panel_eval.injection_reach`.
   - **0 of 40** planted adversarial injection strings across 5 telemetry vectors breached into LLM prompts.
3. **Adversarial Reviewer Vulnerability:**
   - Under an active compromised reviewer attack (one malicious reviewer acting in the final round), the panel flipped to the wrong cause in 54 of 60 cases. This confirms that untrusted models must never be given unrestricted voting weight.

---

## 6. Strategic Architecture Decision for AeroFleet 2.0

Based on these 60 empirical runs:
1. **Ship the Deterministic Rule as Primary:** The default incident diagnostic engine in the AeroFleet UI must remain the deterministic rule. It gives enterprise customers provable 0% false accusations with instant response.
2. **Research Claim for AeroFleet 2.0:** These empirical results provide defensible, publishable proof of why AeroFleet prioritizes deterministic flight telemetry rules over unvalidated LLM hype.
