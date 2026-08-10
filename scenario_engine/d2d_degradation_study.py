"""D2D degradation empirical study — Phase AD.

Not a YAML-driven pass/fail regression scenario like the ones under
scenario_engine/scenarios/ (those check one mission's outputs against a
tolerance band around a known-good expected value — a different job). This
is a Monte Carlo measurement study answering the three questions
docs/D2D_MESH_RESEARCH_DESIGN.md Section 5 says a Q1 submission actually
needs numbers for, not just an architecture diagram:

  1. Verdict-equivalence rate: across many random two-drone conflict
     geometries, how often does a CBF verdict computed from (possibly
     stale, packet-loss-affected) D2D broadcasts match the verdict a
     centralized, always-fresh FleetState would have produced at the same
     instant? Both verdicts go through the exact same, unmodified
     aerofleet.safety.cbf_gate.ControlBarrierFunctionGate — divergence, when
     it happens, comes only from D2D operating on a stale last-known peer
     position, never from different safety logic.
  2. Degradation-response latency: time from central-link loss to a
     drone's link-state machine (aerofleet/safety/d2d_mesh.py's
     D2DLinkStateMachine) reaching STORE_FORWARD. This one is reported
     directly, not sampled — it's a closed-form function of two already
     unit-tested constants (STORE_FORWARD_MISSED_HEARTBEATS x heartbeat
     interval), not something that varies trial to trial.
  3. Undetected-conflict rate: during a simulated central-link outage
     window, how many real (ground-truth) near-miss conflicts does the D2D
     backstop catch, versus a no-D2D baseline. The baseline's number is
     trivially zero by construction (no central link + no D2D = no
     conflict-awareness data of any kind) — this metric exists to put an
     actual number on the failure mode this whole design responds to, not
     because the baseline's behavior is in question.

Modeling note on simulated time: this script advances a SIMULATED clock
across each trial's duration_s in a tight Python loop (no real sleeping —
otherwise a few thousand trials would take hours). aerofleet.safety.d2d_mesh
.D2DTransceiver's peer-message TTL eviction is real-wall-clock-based (by
design — correct for the live system), so it never fires during a
millisecond-fast simulated trial regardless of how much simulated time
elapses; that mechanism is exercised separately and already covered by
tests/unit/test_d2d_mesh.py. The "staleness" this script measures is
tracked independently, in simulated seconds, and is the honestly-relevant
number for this study.

Run: python -m scenario_engine.d2d_degradation_study [--trials N] [--seed S]
Writes a JSON report to scenario_reports/d2d_degradation_study_<timestamp>.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import List

from aerofleet.safety.cbf_gate import ControlBarrierFunctionGate
from aerofleet.safety.d2d_mesh import (
    DEGRADED_MISSED_HEARTBEATS,
    STORE_FORWARD_MISSED_HEARTBEATS,
    D2DBasicSafetyMessage,
    D2DTransceiver,
    haversine_m,
)

GATE_CONFIG = {"min_separation_m": 15.0}
M_PER_DEG_LAT = 111_195.0
START_LAT = 18.5300


@dataclass
class TrialResult:
    trial_id: int
    agreement: bool
    d2d_passed: bool
    centralized_passed: bool
    staleness_s: float
    true_separation_m: float
    d2d_separation_m: float
    within_outage_window: bool


def _simulate_trial(
    trial_id: int,
    rng: random.Random,
    duration_s: float,
    dt_s: float,
    broadcast_interval_s: float,
    packet_loss_rate: float,
    outage_start_s: float,
    outage_end_s: float,
    adversarial: bool = False,
) -> TrialResult:
    """Evolves two drones' positions over [0, duration_s], then evaluates
    the CBF verdict at a randomly-sampled instant eval_t within that
    window — NOT always at duration_s's end. Sampling the evaluation
    instant is what makes "does eval_t fall inside the outage window"
    actually vary trial to trial; evaluating only ever at a fixed endpoint
    would make that check constant across every trial.

    adversarial=True switches to importance sampling for the rare "real
    conflict" event: the ORIGINAL random-walk peer placement below almost
    never produces a true violation (Phase AD's first 5,000-trial run found
    only ~8), which is too few to put a defensible confidence interval on
    metric 3's d2d_catch_rate. Rather than discard that honest natural-rate
    number, adversarial trials directly draw a target true-separation
    biased toward small values and back-solve the peer's start position so
    a straight-line constant-velocity track actually reaches it at eval_t —
    standard rare-event/importance-sampling practice for exactly this
    problem, not cherry-picking: every trial still runs through the exact
    same unmodified CBF gate, and run_study() reports the natural-rate and
    importance-sampled results as two clearly separate numbers rather than
    blending them into one misleadingly-precise rate."""
    m_per_deg_lon = M_PER_DEG_LAT * abs(math.cos(math.radians(START_LAT)))

    own_vel_lat = rng.uniform(-8, 8) / M_PER_DEG_LAT
    own_vel_lon = rng.uniform(-8, 8) / m_per_deg_lon
    peer_vel_lat = rng.uniform(-8, 8) / M_PER_DEG_LAT
    peer_vel_lon = rng.uniform(-8, 8) / m_per_deg_lon

    own_lat, own_lon = START_LAT, 73.8600

    if adversarial:
        eval_t = rng.uniform(0.0, duration_s)
        # Where the own-drone will be at eval_t (closed form — own_vel is
        # constant over the whole trial).
        own_lat_at_eval = own_lat + own_vel_lat * eval_t
        own_lon_at_eval = own_lon + own_vel_lon * eval_t
        # Bias toward small separations: half the mass is inside the
        # violation threshold, half just outside it — a useful mix for
        # both "how often does D2D catch a real conflict" and "does D2D
        # ever falsely flag a near-but-safe encounter."
        target_sep_m = rng.uniform(0.0, GATE_CONFIG["min_separation_m"] * 2.0)
        bearing = rng.uniform(0.0, 2 * math.pi)
        peer_lat_at_eval = own_lat_at_eval + (target_sep_m * math.cos(bearing)) / M_PER_DEG_LAT
        peer_lon_at_eval = own_lon_at_eval + (target_sep_m * math.sin(bearing)) / m_per_deg_lon
        # Back-solve the peer's t=0 start position so its own constant-
        # velocity track reaches peer_{lat,lon}_at_eval exactly at eval_t.
        peer_lat = peer_lat_at_eval - peer_vel_lat * eval_t
        peer_lon = peer_lon_at_eval - peer_vel_lon * eval_t
    else:
        # Draw order (peer position, then eval_t) deliberately matches the
        # pre-Phase-AL code exactly, so stress_fraction=0.0 reproduces
        # Phase AD's original published numbers bit-for-bit for the same
        # seed — the adversarial branch above needs eval_t before it can
        # place the peer, but this branch doesn't, so there's no reason to
        # reorder it and every reason not to.
        #
        # Start peer close enough that a meaningful fraction of trials
        # actually produce a real conflict — a study where every trial is
        # trivially safe wouldn't say anything about verdict equivalence
        # under staleness. In practice this natural-rate placement still
        # yields very few true violations (see docstring above) — that
        # honest scarcity is exactly why the adversarial mode exists.
        peer_lat = START_LAT + rng.uniform(-0.0015, 0.0015)
        peer_lon = 73.8600 + rng.uniform(-0.0015, 0.0015)
        eval_t = rng.uniform(0.0, duration_s)

    tx = D2DTransceiver("OWN")
    last_received_sim_t: float = None
    last_broadcast_attempt_t = -broadcast_interval_s
    t = 0.0

    while t <= eval_t:
        if t - last_broadcast_attempt_t >= broadcast_interval_s:
            last_broadcast_attempt_t = t
            if rng.random() >= packet_loss_rate:
                tx.receive(D2DBasicSafetyMessage(
                    drone_id="PEER", timestamp_utc=time.time(), lat=peer_lat, lon=peer_lon,
                    alt_m=60.0, velocity_mps=0.0, heading_deg=0.0, battery_soc=1.0, link_state="NOMINAL",
                ))
                last_received_sim_t = t

        own_lat += own_vel_lat * dt_s
        own_lon += own_vel_lon * dt_s
        peer_lat += peer_vel_lat * dt_s
        peer_lon += peer_vel_lon * dt_s
        t += dt_s

    true_separation = haversine_m(own_lat, own_lon, peer_lat, peer_lon)
    own_state = {"lat": own_lat, "lon": own_lon}
    d2d_points = tx.to_trajectory_points(own_state)
    centralized_points = [{"separation_m": true_separation}]

    d2d_result = ControlBarrierFunctionGate(dict(GATE_CONFIG)).evaluate_trajectory(d2d_points)
    centralized_result = ControlBarrierFunctionGate(dict(GATE_CONFIG)).evaluate_trajectory(centralized_points)

    staleness_s = (eval_t - last_received_sim_t) if last_received_sim_t is not None else float("inf")

    return TrialResult(
        trial_id=trial_id,
        agreement=d2d_result.passed == centralized_result.passed,
        d2d_passed=d2d_result.passed,
        centralized_passed=centralized_result.passed,
        staleness_s=round(staleness_s, 3) if staleness_s != float("inf") else -1.0,
        true_separation_m=round(true_separation, 3),
        d2d_separation_m=round(d2d_points[0].get("separation_m", float("nan")), 3),
        within_outage_window=outage_start_s <= eval_t <= outage_end_s,
    )


def _degradation_response_latency(heartbeat_interval_s: float) -> float:
    """Closed-form, not sampled: time until enough consecutive missed
    heartbeats accumulate to reach STORE_FORWARD."""
    return STORE_FORWARD_MISSED_HEARTBEATS * heartbeat_interval_s


def _wilson_ci(successes: int, n: int, z: float = 1.96) -> "tuple[float, float] | None":
    """95% Wilson score interval for a binomial proportion — the standard
    choice over a normal (Wald) approximation for small n or a proportion
    near 0 or 1, both of which apply to the original n=8 catch-rate sample
    this phase exists to fix (a Wald interval can produce a nonsensical
    negative lower bound or >1 upper bound in exactly that regime; Wilson
    can't)."""
    if n == 0:
        return None
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half_width = (z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)) / denom
    return (round(max(0.0, center - half_width), 4), round(min(1.0, center + half_width), 4))


def run_study(
    trials: int = 500,
    seed: int = 42,
    duration_s: float = 30.0,
    dt_s: float = 1.0,
    broadcast_interval_s: float = 1.0,
    packet_loss_rate: float = 0.2,
    heartbeat_interval_s: float = 1.0,
    stress_fraction: float = 0.0,
) -> dict:
    """stress_fraction (0.0-1.0, default 0.0 = unchanged original behavior):
    the fraction of trials that use adversarial/importance-sampled peer
    placement (see _simulate_trial's docstring) instead of the natural
    random-walk placement. Each trial independently draws whether it's
    adversarial, seeded the same as everything else, so results stay
    reproducible for a given seed."""
    rng = random.Random(seed)
    # Separate RNG stream for the stress/natural coin flip, seeded
    # independently of `rng` — so that with stress_fraction=0.0 every
    # trial's geometry draws from `rng` in EXACTLY the same sequence as
    # before this parameter existed (reproducing Phase AD's original
    # published numbers bit-for-bit for the same seed), rather than being
    # shifted by an extra draw consumed on the shared stream.
    stress_rng = random.Random(seed + 1_000_000)
    outage_start_s, outage_end_s = duration_s * 0.4, duration_s * 0.8

    results: List[TrialResult] = []
    adversarial_flags: List[bool] = []
    for i in range(trials):
        is_adversarial = stress_rng.random() < stress_fraction
        adversarial_flags.append(is_adversarial)
        results.append(_simulate_trial(
            i, rng, duration_s, dt_s, broadcast_interval_s, packet_loss_rate,
            outage_start_s, outage_end_s, adversarial=is_adversarial,
        ))

    agreements = [r.agreement for r in results]
    disagreements = [r for r in results if not r.agreement]
    stale_receipts = [r.staleness_s for r in results if r.staleness_s >= 0]

    natural_results = [r for r, adv in zip(results, adversarial_flags) if not adv]
    stress_results = [r for r, adv in zip(results, adversarial_flags) if adv]

    # Metric 3 (natural rate, unchanged from Phase AD): within the
    # simulated outage window, a real conflict is one where ground truth
    # says the drones are inside the minimum separation. Computed only
    # over non-adversarial trials so this number stays the honest,
    # unbiased population estimate — small-n and all.
    outage_trials = [r for r in natural_results if r.within_outage_window]
    outage_true_conflicts = [r for r in outage_trials if not r.centralized_passed]
    outage_caught_by_d2d = [r for r in outage_true_conflicts if not r.d2d_passed]

    # Metric 3b (stress/importance-sampled): same computation, over the
    # adversarial subset only — deliberately reported as a SEPARATE number,
    # never blended into metric_3's rate, because it's drawn from a
    # different (biased) distribution and averaging the two together would
    # misrepresent both.
    stress_outage_trials = [r for r in stress_results if r.within_outage_window]
    stress_true_conflicts = [r for r in stress_outage_trials if not r.centralized_passed]
    stress_caught_by_d2d = [r for r in stress_true_conflicts if not r.d2d_passed]

    report = {
        "study": "D2D degradation empirical study (Phase AD)",
        "generated_at": datetime.utcnow().isoformat(),
        "parameters": {
            "trials": trials, "seed": seed, "duration_s": duration_s, "dt_s": dt_s,
            "broadcast_interval_s": broadcast_interval_s, "packet_loss_rate": packet_loss_rate,
            "heartbeat_interval_s": heartbeat_interval_s, "min_separation_m": GATE_CONFIG["min_separation_m"],
            "stress_fraction": stress_fraction, "n_natural_trials": len(natural_results),
            "n_stress_trials": len(stress_results),
        },
        "metric_1_verdict_equivalence": {
            "agreement_rate": round(sum(agreements) / len(agreements), 4),
            "n_trials": trials,
            "n_disagreements": len(disagreements),
            "disagreement_mean_staleness_s": round(mean([d.staleness_s for d in disagreements if d.staleness_s >= 0]), 3)
                if any(d.staleness_s >= 0 for d in disagreements) else None,
            "overall_mean_staleness_s": round(mean(stale_receipts), 3) if stale_receipts else None,
        },
        "metric_2_degradation_response_latency": {
            "heartbeat_interval_s": heartbeat_interval_s,
            "degraded_at_missed_heartbeats": DEGRADED_MISSED_HEARTBEATS,
            "store_forward_at_missed_heartbeats": STORE_FORWARD_MISSED_HEARTBEATS,
            "time_to_degraded_s": DEGRADED_MISSED_HEARTBEATS * heartbeat_interval_s,
            "time_to_store_forward_s": _degradation_response_latency(heartbeat_interval_s),
            "note": "Closed-form from tested constants in aerofleet/safety/d2d_mesh.py, not sampled.",
        },
        "metric_3_undetected_conflict_rate": {
            "note": "Natural-rate (non-adversarial trials only) — the honest, unbiased population estimate.",
            "outage_window_s": [outage_start_s, outage_end_s],
            "trials_landing_in_outage_window": len(outage_trials),
            "true_conflicts_during_outage": len(outage_true_conflicts),
            "conflicts_caught_by_d2d": len(outage_caught_by_d2d),
            "conflicts_caught_by_no_d2d_baseline": 0,
            "d2d_catch_rate": round(len(outage_caught_by_d2d) / len(outage_true_conflicts), 4)
                if outage_true_conflicts else None,
            "d2d_catch_rate_95pct_wilson_ci": _wilson_ci(len(outage_caught_by_d2d), len(outage_true_conflicts)),
        },
        "metric_3b_stress_undetected_conflict_rate": {
            "note": (
                "Importance-sampled toward near-miss/violation geometries (see _simulate_trial's "
                "docstring) — reported separately from metric_3 because it is drawn from a "
                "deliberately biased distribution, not the natural population. Exists to put a "
                "statistically defensible confidence interval on the catch rate, which the natural "
                "rate's small sample size (Phase AD's original run: ~8 true conflicts out of 5,000 "
                "trials) could not support."
            ),
            "outage_window_s": [outage_start_s, outage_end_s],
            "trials_landing_in_outage_window": len(stress_outage_trials),
            "true_conflicts_during_outage": len(stress_true_conflicts),
            "conflicts_caught_by_d2d": len(stress_caught_by_d2d),
            "d2d_catch_rate": round(len(stress_caught_by_d2d) / len(stress_true_conflicts), 4)
                if stress_true_conflicts else None,
            "d2d_catch_rate_95pct_wilson_ci": _wilson_ci(len(stress_caught_by_d2d), len(stress_true_conflicts)),
        },
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--trials", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--packet-loss-rate", type=float, default=0.2)
    parser.add_argument("--broadcast-interval-s", type=float, default=1.0)
    parser.add_argument(
        "--stress-fraction", type=float, default=0.0,
        help="Fraction of trials (0.0-1.0) using importance-sampled adversarial peer placement, "
             "for a statistically defensible catch-rate CI (see metric_3b in the report). Default "
             "0.0 reproduces Phase AD's original natural-rate-only study.",
    )
    args = parser.parse_args()

    report = run_study(
        trials=args.trials, seed=args.seed,
        packet_loss_rate=args.packet_loss_rate, broadcast_interval_s=args.broadcast_interval_s,
        stress_fraction=args.stress_fraction,
    )

    print(json.dumps(report, indent=2))

    out_dir = Path(__file__).resolve().parent.parent / "scenario_reports"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"d2d_degradation_study_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\nReport written to {out_path}")


if __name__ == "__main__":
    main()
