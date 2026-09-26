"""Populate a running AeroFleet API with a realistic airborne swarm.

Everything goes through the real HTTP API — real order creation, the real
CBF gate, real zone/energy-aware routing — so what the VR Safety View then
shows is the actual system's behaviour, not fabricated positions. A few
orders are deliberately aimed into DGCA red zones: the gate rejects them,
which auto-creates the incidents that Incident Replay verifies.

Usage (with the API already running on :8000):
    python tools/seed_demo_swarm.py                 # 14 flights + 2 red-zone rejections, Pune
    python tools/seed_demo_swarm.py --orders 24 --city mumbai

Dev-only demo account (local API only — never use against a shared server):
    username: demo_operator
    password: AEROFLEET_DEMO_PASSWORD env var, else "aerofleet-demo-2026"
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
import time

import requests

DEMO_USER = "demo_operator"
DEMO_EMAIL = "demo_operator@aerofleet.local"
DEMO_PASSWORD = os.environ.get("AEROFLEET_DEMO_PASSWORD", "aerofleet-demo-2026")


def offset(lat: float, lon: float, bearing_deg: float, dist_m: float) -> tuple[float, float]:
    b = math.radians(bearing_deg)
    dlat = dist_m * math.cos(b) / 111320.0
    dlon = dist_m * math.sin(b) / (111320.0 * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--city", default="pune")
    ap.add_argument("--orders", type=int, default=14, help="flights to dispatch")
    ap.add_argument("--rejections", type=int, default=2, help="deliberate red-zone dispatches (create incidents)")
    ap.add_argument("--stagger", type=float, default=2.5, help="seconds between launches from the same depot")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    api = args.api.rstrip("/")

    s = requests.Session()
    s.post(f"{api}/api/v1/auth/register", json={"username": DEMO_USER, "email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    r = s.post(f"{api}/api/v1/auth/login", data={"username": DEMO_USER, "password": DEMO_PASSWORD})
    if r.status_code != 200:
        print(f"Login failed ({r.status_code}): {r.text}", file=sys.stderr)
        return 1
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    depots = [d for d in s.get(f"{api}/api/v1/fleet/depots", params={"city": args.city}).json() if d.get("lat") is not None]
    red_zones = [z for z in s.get(f"{api}/api/v1/geofence/zones", params={"city": args.city}).json() if z["zone_type"] == "RED"]
    if not depots:
        print("No depots with coordinates — is the API running and the city seeded?", file=sys.stderr)
        return 1

    def dispatch(depot: dict, lat: float, lon: float, priority: str) -> dict:
        order = s.post(f"{api}/api/v1/orders/", json={
            "city": args.city, "origin_depot_id": depot["depot_id"],
            "destination_lat": lat, "destination_lon": lon,
            "payload_kg": round(rng.uniform(0.5, 3.5), 1), "priority": priority, "deadline_minutes": 30,
        })
        order.raise_for_status()
        return s.post(f"{api}/api/v1/orders/{order.json()['order_id']}/dispatch").json()

    approved = rejected = 0
    last_launch: dict[str, float] = {}
    for i in range(args.orders):
        depot = depots[i % len(depots)]
        wait = args.stagger - (time.time() - last_launch.get(depot["depot_id"], 0.0))
        if wait > 0:
            time.sleep(wait)
        lat, lon = offset(depot["lat"], depot["lon"], rng.uniform(0, 360), rng.uniform(1200, 3500))
        priority = rng.choice(["STANDARD", "STANDARD", "EXPRESS", "MEDICAL"])
        result = dispatch(depot, lat, lon, priority)
        last_launch[depot["depot_id"]] = time.time()
        verdict = result.get("verdict", result.get("detail", "?"))
        approved += verdict == "APPROVED"
        rejected += verdict != "APPROVED"
        print(f"  flight {i + 1:>2}/{args.orders}  {depot['depot_id']:<10} -> {verdict}  {result.get('assigned_drone_id') or ''}")

    for i in range(min(args.rejections, len(red_zones) * 3)):
        zone = red_zones[i % len(red_zones)]
        depot = min(depots, key=lambda d: (d["lat"] - zone["center_lat"]) ** 2 + (d["lon"] - zone["center_lon"]) ** 2)
        lat, lon = offset(zone["center_lat"], zone["center_lon"], rng.uniform(0, 360), zone["radius_m"] * 0.4)
        result = dispatch(depot, lat, lon, "STANDARD")
        print(f"  red-zone probe {i + 1}: {result.get('verdict')} (expected a rejection -> incident)")

    print(f"\n{approved} airborne, {rejected} rejected in the normal set. Open the VR Safety View "
          f"(Live swarm / Incident replay) and sign in as {DEMO_USER}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
