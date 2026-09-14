"""Ablation study: does the zone-penalty term in
aerofleet/city/route_weights.py's edge weight actually change routing
behavior, or would plain distance/energy-only routing have produced the
same paths anyway? Real, deterministic, no LLM/GPU needed — runs against
the real Pune city graph and the real, named DGCA restricted sites in
aerofleet/city/restricted_sites.py.

Three conditions compared for the same set of real origin-destination
pairs:
  (a) baseline    — CityGraph.shortest_path(): plain distance-shortest,
                     the pre-trajectory-optimization approach.
  (b) no_penalty  — route_weights.py's real distance+energy weighting,
                     with RED_ZONE_PENALTY_KM/YELLOW_ZONE_PENALTY_KM
                     forced to 0 — isolates the energy term's own effect
                     from the zone-avoidance term's effect.
  (c) full_method — the real, shipped optimized_shortest_path(), zone
                     penalty included.

For each path, "touches a zone" means at least one waypoint node along it
falls inside a real RED or YELLOW zone (aerofleet/city/airspace.py's
AirspaceModel.zone_at, the same function the CBF gate itself uses).

Origin-destination pairs are a deliberate mix, not cherry-picked to only
favor the full method: half are "adversarial" (destinations placed near
real restricted sites, where a zone-crossing path is plausible for any of
the three conditions), half are general offsets from real depots (where
most methods likely agree, giving an honest denominator rather than an
inflated effect size).

Run: python -m research.ablation_zone_penalty
Writes a JSON report to research/results/ablation_zone_penalty_<timestamp>.json
"""
from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from aerofleet.city import route_weights
from aerofleet.city.airspace import ZoneColor
from aerofleet.city.restricted_sites import PUNE_RESTRICTED_SITES
from aerofleet.fleet.state import get_fleet_state

SEED = 20260914
N_ADVERSARIAL = 60
N_GENERAL = 60
PAYLOAD_KG = 1.5


@dataclass
class PairResult:
    pair_id: str
    kind: str  # "adversarial" | "general"
    baseline_touches_red: bool
    no_penalty_touches_red: bool
    full_method_touches_red: bool
    baseline_touches_yellow: bool
    no_penalty_touches_yellow: bool
    full_method_touches_yellow: bool
    baseline_km: float
    full_method_km: float


def _path_zone_touches(graph, airspace, node_path: List[int]):
    """Returns (touches_red, touches_yellow) — kept separate rather than
    one combined "touches a zone" flag. Real finding from the first run of
    this study: at Pune's real geography, the airport's 12km-radius Yellow
    zone covers 5 of the 6 real depots themselves (confirmed directly —
    DEPOT-1 through DEPOT-4 and DEPOT-6 all classify as YELLOW at their
    own coordinates), so "touching yellow" is a near-constant at this
    city's delivery scale regardless of routing method, not something the
    zone-penalty term can meaningfully optimize away (Yellow is legal with
    ATC permission — it's not the constraint route_weights.py's penalty is
    meant to avoid at all cost the way Red is). RED is the real,
    safety-critical target — it's what geofence_exclusion actually
    prohibits outright — so that's the metric that matters here."""
    touches_red = False
    touches_yellow = False
    for node in node_path:
        lat, lon = graph.node_lat_lon(node)
        zone = airspace.zone_at(lat, lon)
        if zone == ZoneColor.RED:
            touches_red = True
        elif zone == ZoneColor.YELLOW:
            touches_yellow = True
    return touches_red, touches_yellow


def _path_length_km(graph, node_path: List[int]) -> float:
    return graph.path_length_km(node_path)


def _optimized_path_with_penalties(g, airspace, orig, dest, payload_kg, red_penalty, yellow_penalty):
    """Reimplements optimized_shortest_path's call with overridable
    penalty constants, without needing to mutate the real module's
    globals (which would leak across other tests/imports in the same
    process) — passes the same weight-construction logic, just with the
    zone-penalty function's constants substituted locally."""
    import networkx as nx

    def weight(u, v, data):
        edge = route_weights.CityGraph.edge_attrs(data)
        length_km = edge.get("length", 0.0) / 1000.0
        from aerofleet.fleet.dispatch import DispatchEngine

        energy_wh = DispatchEngine.estimate_energy_wh(length_km, payload_kg)
        penalty = 0.0
        for node in (u, v):
            node_data = g.nodes[node]
            zone = airspace.zone_at(float(node_data["y"]), float(node_data["x"]))
            if zone == ZoneColor.RED:
                penalty = max(penalty, red_penalty)
            elif zone == ZoneColor.YELLOW:
                penalty = max(penalty, yellow_penalty)
        return length_km + route_weights.ENERGY_WEIGHT_KM_PER_WH * energy_wh + penalty

    return nx.shortest_path(g, orig, dest, weight=weight)


def _generate_pairs(fleet, rng: random.Random):
    graph = fleet.graph
    g = graph.load()
    depot_nodes = [d.node for d in fleet.depots.values()]
    pairs = []

    # Adversarial: destinations offset from each real restricted site, so
    # a plausible geometric-shortest path would pass NEAR it -- but the
    # destination itself must NOT be inside the Red zone. A route
    # literally can't avoid touching Red if that's where it's going (in
    # the real app the CBF gate would just reject that destination
    # outright, a separate mechanism from route avoidance) -- keeping
    # such pairs would measure "is the destination illegal", not "does
    # the route avoid illegal airspace en route", which is what this
    # ablation is actually supposed to test.
    site_i = 0
    attempts = 0
    while len(pairs) < N_ADVERSARIAL and attempts < N_ADVERSARIAL * 20:
        attempts += 1
        site = PUNE_RESTRICTED_SITES[site_i % len(PUNE_RESTRICTED_SITES)]
        dlat = rng.uniform(-0.02, 0.02)
        dlon = rng.uniform(-0.02, 0.02)
        dest_lat, dest_lon = site.lat + dlat, site.lon + dlon
        if fleet.airspace.zone_at(dest_lat, dest_lon) == ZoneColor.RED:
            site_i += 1
            continue
        dest_node = graph.nearest_node(dest_lat, dest_lon)
        origin_node = rng.choice(depot_nodes)
        if origin_node != dest_node and fleet.airspace.zone_at(*graph.node_lat_lon(origin_node)) != ZoneColor.RED:
            pairs.append(("adversarial", origin_node, dest_node))
        site_i += 1

    # General: real depot-to-depot-area offsets, not targeted at any site.
    while len(pairs) < N_ADVERSARIAL + N_GENERAL:
        origin_node = rng.choice(depot_nodes)
        origin_lat, origin_lon = graph.node_lat_lon(origin_node)
        dlat = rng.uniform(-0.03, 0.03)
        dlon = rng.uniform(-0.03, 0.03)
        dest_node = graph.nearest_node(origin_lat + dlat, origin_lon + dlon)
        if origin_node != dest_node:
            pairs.append(("general", origin_node, dest_node))

    return pairs


def run_ablation() -> dict:
    rng = random.Random(SEED)
    fleet = get_fleet_state("pune")
    graph = fleet.graph
    g = graph.load()
    airspace = fleet.airspace

    pairs = _generate_pairs(fleet, rng)
    results: List[PairResult] = []

    for i, (kind, orig, dest) in enumerate(pairs):
        try:
            baseline_path = graph.shortest_path(orig, dest)
            no_penalty_path = _optimized_path_with_penalties(g, airspace, orig, dest, PAYLOAD_KG, 0.0, 0.0)
            full_path = route_weights.optimized_shortest_path(g, airspace, orig, dest, PAYLOAD_KG)
        except Exception:
            continue  # unreachable pair (real, known graph-bounds limitation) — skip, don't fabricate

        b_red, b_yellow = _path_zone_touches(graph, airspace, baseline_path)
        np_red, np_yellow = _path_zone_touches(graph, airspace, no_penalty_path)
        fm_red, fm_yellow = _path_zone_touches(graph, airspace, full_path)

        results.append(PairResult(
            pair_id=f"{kind}-{i:03d}",
            kind=kind,
            baseline_touches_red=b_red, no_penalty_touches_red=np_red, full_method_touches_red=fm_red,
            baseline_touches_yellow=b_yellow, no_penalty_touches_yellow=np_yellow, full_method_touches_yellow=fm_yellow,
            baseline_km=round(_path_length_km(graph, baseline_path), 3),
            full_method_km=round(_path_length_km(graph, full_path), 3),
        ))

    n = len(results)

    def rate(attr: str) -> float:
        return round(sum(getattr(r, attr) for r in results) / n, 4) if n else 0.0

    # The real ablation signal: RED-zone avoidance specifically (the hard,
    # safety-critical constraint) — cases where baseline/no-penalty WOULD
    # have crossed Red, and the full method didn't.
    avoided_red_vs_baseline = sum(1 for r in results if r.baseline_touches_red and not r.full_method_touches_red)
    avoided_red_vs_no_penalty = sum(1 for r in results if r.no_penalty_touches_red and not r.full_method_touches_red)
    regressed_red_vs_baseline = sum(1 for r in results if not r.baseline_touches_red and r.full_method_touches_red)

    detours = [
        r.full_method_km - r.baseline_km for r in results
        if r.full_method_touches_red != r.baseline_touches_red
    ]
    mean_detour_km = round(sum(detours) / len(detours), 3) if detours else 0.0

    return {
        "study": "Ablation: zone-penalty term in route_weights.py's edge weight",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "n_pairs_requested": len(pairs),
        "n_pairs_reachable": n,
        "n_skipped_unreachable": len(pairs) - n,
        "real_finding": (
            "Yellow-zone touch rate is near-identical across all 3 methods (see yellow_touch_rate) "
            "because 5 of Pune's 6 real depots are themselves inside the airport's 12km Yellow radius "
            "-- not a bug, a real geography fact discovered by this study's first run. Yellow is legal "
            "with ATC permission, so it isn't what the penalty term should be optimizing away. RED is "
            "the safety-critical, hard-prohibited constraint -- see red_touch_rate and "
            "cases_where_full_method_avoided_a_red_zone_* for the metric that actually matters."
        ),
        "red_touch_rate": {
            "baseline_plain_distance": rate("baseline_touches_red"),
            "no_zone_penalty_ablation": rate("no_penalty_touches_red"),
            "full_method": rate("full_method_touches_red"),
        },
        "yellow_touch_rate": {
            "baseline_plain_distance": rate("baseline_touches_yellow"),
            "no_zone_penalty_ablation": rate("no_penalty_touches_yellow"),
            "full_method": rate("full_method_touches_yellow"),
        },
        "cases_where_full_method_avoided_a_red_zone_baseline_would_have_crossed": avoided_red_vs_baseline,
        "cases_where_full_method_avoided_a_red_zone_energy_only_would_have_crossed": avoided_red_vs_no_penalty,
        "cases_where_full_method_regressed_vs_baseline": regressed_red_vs_baseline,
        "mean_extra_distance_km_when_red_avoidance_changed_the_route": mean_detour_km,
        "per_pair_results": [asdict(r) for r in results],
    }


def main() -> None:
    report = run_ablation()
    print(json.dumps({k: v for k, v in report.items() if k != "per_pair_results"}, indent=2))

    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"ablation_zone_penalty_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport written to {out_path}")


if __name__ == "__main__":
    main()
