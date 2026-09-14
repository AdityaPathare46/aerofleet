# VR Safety View — User Study Protocol (Design Only)

Right now the VR Safety View's explainability claim ("VR grounds an AI decision in a way that
improves human understanding/trust") is *asserted*, backed by citing precedent papers that ran
real studies — it has zero human-subjects data of its own. This document designs a real, runnable
study, closely mirroring the methodology `docs/VR_RESEARCH_REFERENCES.md` already cites (de Heuvel
et al.'s 24-participant XR-explainability study), so results are comparable to a real precedent
rather than a from-scratch methodology a reviewer has to evaluate cold.

**This document is the protocol, not the results.** Running it needs real participants — that's on
you. What's below is designed to be executable without further redesign once you're ready.

## Research question

Does viewing a rejected dispatch's Incident Replay in VR (vs. the same information as a flat 2D
panel) change a participant's (a) accuracy in identifying *why* the CBF gate rejected the dispatch,
and (b) stated trust in the system's decision — the same two outcome types de Heuvel et al. measured
(objective understanding, subjective trust).

## Design

**Within-subjects, counterbalanced** (every participant sees both conditions, order randomized) —
more statistical power per participant than between-subjects, appropriate for a target N in the
15-30 range (de Heuvel et al. used 24; matching that order of magnitude keeps this comparable and
realistic for a student-project timeline, not a moonshot).

- **Condition A (VR)**: the real VR Safety View, Incident Replay mode, on whatever headset is
  available (even a desktop 3D view via the same React Three Fiber scene counts as a legitimate
  "stereo-optional" condition if no headset exists — state which was actually used, honestly).
- **Condition B (2D control)**: the same real data (frozen CBF geometry, violated constraint,
  council narrative if available) rendered as a flat 2D panel — build this as a stripped-down
  alternate view of `VRSafetyView.tsx`'s own data (same `VRSceneDto`), not a different mock dataset,
  so the *only* real variable between conditions is the rendering, not the underlying information.

**Materials**: 6-10 real incidents, pulled from actual CBF rejections your own system produced
(the property-based test suite's red-zone-rejection cases, or real rejections from the mass
forensics study, are legitimate real source material — not synthetic-for-the-study incidents).
Each incident needs a known correct answer (which constraint was violated — already in the real
`cbf_certificate`) for the accuracy measure.

## Tasks & measures

1. **Objective understanding** (per incident, per condition): "Which safety constraint caused this
   rejection?" (multiple choice, options = the 11 real constraint names) + "How confident are you?"
   (1-7 Likert). Score: accuracy (correct/incorrect) and confidence-accuracy calibration.
2. **Subjective trust** (per condition, after all incidents in that condition): a short validated
   trust scale — reuse an existing one rather than inventing a new instrument (e.g., the Jian et al.
   1998 Trust in Automation scale, or the shorter Trust Scale used in de Heuvel et al. itself — pull
   the exact instrument from that paper once you have full-text access, so the comparison is
   apples-to-apples).
3. **Task time** (secondary): time-to-answer per incident, per condition.
4. **Open-ended**: "What made you confident/unsure?" after each incident — qualitative data for the
   discussion section, costs nothing extra to collect.

## Procedure (per participant, ~20-30 min)

1. Consent + a 2-minute onboarding explaining what a CBF rejection means, in plain language (not
   assuming domain knowledge — matches this project's own "operator, not ML engineer" framing).
2. Condition order randomized (A-then-B or B-then-A, alternate by participant).
3. 3-5 incidents per condition, task + confidence rating per incident.
4. Trust scale after each condition block.
5. Brief open-ended debrief.

## Analysis plan (decide before collecting data, not after)

- Accuracy: paired comparison (McNemar's test or a mixed-effects logistic model with
  condition as a fixed effect, participant as random effect — the latter is more defensible with
  repeated incidents per participant).
- Trust scale: paired t-test (or Wilcoxon signed-rank if the scale is ordinal and N is small).
- Report both effect size (not just p-value) and a confidence interval — a Q1 reviewer will ask for
  both regardless of significance.
- **Pre-register the hypothesis and analysis plan** (even informally, in this repo, timestamped via
  a git commit before data collection starts) — this is cheap to do and meaningfully strengthens
  the study's credibility; a reviewer who sees the analysis was decided before seeing the data
  trusts the result more.

## Ethics

A university IRB/ethics review is very likely required for human-subjects data even for a small
student study — check your institution's requirement *before* recruiting, not after. This is a
process step outside what I can do, but it's a real gate, not optional paperwork to skip.

## Recruitment target

15-30 participants (matches the precedent paper's order of magnitude). Convenience sampling
(classmates, lab members) is standard and acceptable for a study this size — state the sampling
method honestly in the limitations section rather than implying a more rigorous recruitment
process than what actually happened.

## What's needed to actually run this (not done here)

1. IRB/ethics approval.
2. The 2D control-condition view (a real, small frontend build — reuses `VRSceneDto`, doesn't need
   new backend work).
3. Recruit participants.
4. Run it, following the procedure above exactly (protocol deviations weaken the result).
5. Analyze per the pre-registered plan.
