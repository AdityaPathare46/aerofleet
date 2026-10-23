# Declared protocols: a prospective test of the vibration ranking, and a user study of the 3D views

Declared 24 October 2026, before any data are collected. Neither has been run yet; the paper says so.

## 1. Prospective test of the vibration ranking

**Question.** Do drones flagged by the fleet vibration ranking go on to have more crashes or forced repairs than drones
not flagged, when the ranking is recorded before the outcome?

**Fleet.** Any partner fleet using AeroFleet with at least 8 drones of one type flown regularly (target: 2–3 fleets,
30+ drones in total).

**Procedure.** Every reviewed flight is uploaded as usual. On the first day of each month the ranking (`GET
/fleets/{fleet}/vibration`) is written to the signed record, so the flags are timestamped before any outcome. The
fleet keeps its normal maintenance and records every crash, hard landing and unplanned part replacement in the tool,
with date and drone. Safety comes first: the fleet may inspect any drone at any time, flagged or not. Every
inspection and what it found is recorded, so that a fault found because of a flag still counts as an outcome rather
than disappearing.

**Outcome and test.** Primary: crash, unplanned propulsion/airframe repair, or a defect found at inspection, within
60 days of a monthly ranking.
Compare flagged and unflagged drone-months with a Poisson or logistic model clustered by drone; report the rate ratio
with a 95% CI. Supported if the lower bound of the rate ratio is above 1. Duration: 6 months or 20 outcome events,
whichever comes later.

**What it cannot show.** That acting on a flag prevents crashes; that would need flags randomised between drones.

## 2. User study of the 3D flight replay and mission rehearsal

**Question.** Do operators find plan deviations and losses of separation faster and more accurately in the 3D tabletop
view than in the 2D map and table?

**Participants.** 12–16 people who plan or fly drones (students of a drone course, operators of partner fleets). The
authors and anyone who worked on the tool do not take part.

**Design.** Within subjects, two conditions (2D map + tables; 3D tabletop on desktop; a headset arm if available),
counterbalanced order, 8 tasks per condition from prepared material: 4 reviewed flights (find when and where the drone
left the plan and how far) and 4 mission sets (which pairs conflict, where and when). Material prepared from real logs
and synthetic plans; the correct answer is known for each task.

**Measures.** Task accuracy (primary), time to answer, NASA-TLX workload, preference. Analysis: mixed-effects model
with participant as random effect. Supported if accuracy in 3D is higher with a 95% CI excluding zero. Also report
where 3D was worse.

**Ethics.** Institutional ethics approval and informed consent before recruitment; no personal data beyond age band
and experience.
