"""
vr_bridge.py — VR/AR scene data exporter for Space Mission Architect.

Exports mission data as a structured JSON payload ready for:
  - Three.js / React Three Fiber (WebXR)
  - Unity WebGL export
  - Unreal Engine via Live Link
  - NASA WorldWind / Cesium.js

The VR viewer is a separate frontend (not included here).
This module purely prepares and exports the data, zero breaking changes.

Usage:
    from vr_bridge import get_vr_scene_data, export_vr_json
    scene = get_vr_scene_data(mission_plan, trajectory_data)
    path  = export_vr_json(scene, "Mars_Orbiter_Mission")
"""

import json
import math
import os
from datetime import datetime
from typing import Dict, Any, Optional, List

# Scale factors for Three.js scene (1 unit = 1000 km)
KM_TO_SCENE_UNITS = 1 / 1000.0

# Planetary data for 3D scene (mean orbital radius from Sun, km)
PLANETS_3D = {
    "SUN":     {"radius_km": 695700,  "orbital_radius_km": 0,         "color": "#FDB813", "texture": "sun"},
    "MERCURY": {"radius_km": 2439.7,  "orbital_radius_km": 5.791e7,   "color": "#B5B5B5", "texture": "mercury"},
    "VENUS":   {"radius_km": 6051.8,  "orbital_radius_km": 1.082e8,   "color": "#E8C47A", "texture": "venus"},
    "EARTH":   {"radius_km": 6371.0,  "orbital_radius_km": 1.496e8,   "color": "#1E90FF", "texture": "earth"},
    "MOON":    {"radius_km": 1737.4,  "orbital_radius_km": 3.844e5,   "color": "#999999", "texture": "moon", "parent": "EARTH"},
    "MARS":    {"radius_km": 3389.5,  "orbital_radius_km": 2.279e8,   "color": "#C1440E", "texture": "mars"},
    "JUPITER": {"radius_km": 69911.0, "orbital_radius_km": 7.783e8,   "color": "#C88B3A", "texture": "jupiter"},
    "SATURN":  {"radius_km": 58232.0, "orbital_radius_km": 1.427e9,   "color": "#E8D5A3", "texture": "saturn", "has_rings": True},
    "URANUS":  {"radius_km": 25362.0, "orbital_radius_km": 2.870e9,   "color": "#7DE8E8", "texture": "uranus"},
    "NEPTUNE": {"radius_km": 24622.0, "orbital_radius_km": 4.497e9,   "color": "#3F54BA", "texture": "neptune"},
}

# Spacecraft component meshes (maps to glTF assets in /public/models/)
SPACECRAFT_MESHES = {
    "single satellite mission": "satellite_generic.glb",
    "interplanetary transfer":  "probe_interplanetary.glb",
    "deep space exploration":   "probe_deep_space.glb",
    "lunar orbit":              "lunar_orbiter.glb",
    "mars":                     "mars_spacecraft.glb",
    "multi-satellite constellation": "constellation_sat.glb",
}


def _scale_position(x_km: float, y_km: float, z_km: float = 0.0) -> Dict[str, float]:
    """Convert km coordinates to Three.js scene units."""
    s = KM_TO_SCENE_UNITS
    return {"x": round(x_km * s, 6), "y": round(z_km * s, 6), "z": round(y_km * s, 6)}


def _orbit_circle_points(orbital_radius_km: float, n: int = 128) -> List[Dict]:
    """Generate circular orbit path for Three.js LineLoop."""
    pts = []
    for i in range(n + 1):
        angle = 2 * math.pi * i / n
        pts.append(_scale_position(
            math.cos(angle) * orbital_radius_km,
            math.sin(angle) * orbital_radius_km,
        ))
    return pts


def get_vr_scene_data(
    mission_plan: Dict[str, Any],
    trajectory_data: Optional[Dict] = None,
    telemetry: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Build a complete 3D/VR scene descriptor from mission data.

    Args:
        mission_plan:    Mission spec dict (from sim.specs.__dict__)
        trajectory_data: Output from TrajectoryEngine.plan_mission()
        telemetry:       Live telemetry data (optional)

    Returns:
        scene dict ready for JSON export and Three.js consumption
    """
    overview = {}
    orbit    = {}
    config   = {}

    if hasattr(mission_plan, '__dict__'):
        overview = getattr(mission_plan, 'overview', {})
        orbit    = getattr(mission_plan, 'orbit', {})
        config   = getattr(mission_plan, 'configuration', {})
    elif isinstance(mission_plan, dict):
        overview = mission_plan.get("overview", {})
        orbit    = mission_plan.get("orbit", {})
        config   = mission_plan.get("configuration", {})

    mission_name = overview.get("name", "Unnamed Mission")
    mission_type = overview.get("type", "Single Satellite Mission").lower()
    target_type  = orbit.get("target", {}).get("type", "LEO") if isinstance(orbit.get("target"), dict) else str(orbit.get("target", "LEO"))
    target_up    = target_type.upper()

    # --- Spacecraft mesh selection ---
    mesh_key = "single satellite mission"
    for k in SPACECRAFT_MESHES:
        if k in mission_type or k in target_type.lower():
            mesh_key = k
            break
    spacecraft_mesh = SPACECRAFT_MESHES[mesh_key]

    # --- Spacecraft orbit position ---
    initial_orbit = orbit.get("initial", {}) if isinstance(orbit.get("initial"), dict) else {}
    orbit_alt_km  = float(initial_orbit.get("a", 6778)) - 6378.137
    orbit_radius_km = 6378.137 + orbit_alt_km
    inclination_deg = float(initial_orbit.get("i", 0))

    spacecraft_pos = _scale_position(orbit_radius_km, 0, orbit_alt_km * math.sin(math.radians(inclination_deg)))

    # --- Planets to include in scene ---
    bodies_in_scene = ["SUN", "EARTH"]
    if target_up in PLANETS_3D:
        bodies_in_scene.append(target_up)
    if target_up in ("EUROPA", "GANYMEDE", "CALLISTO", "IO"):
        bodies_in_scene.append("JUPITER")
    elif target_up in ("TITAN", "ENCELADUS", "RHEA"):
        bodies_in_scene.append("SATURN")
    elif target_up in ("MOON", "LUNA"):
        bodies_in_scene.append("MOON")

    planets_scene = {}
    for body in bodies_in_scene:
        if body in PLANETS_3D:
            pd = PLANETS_3D[body]
            planets_scene[body] = {
                "position": _scale_position(pd["orbital_radius_km"], 0),
                "radius_scene_units": round(pd["radius_km"] * KM_TO_SCENE_UNITS * 10, 6),  # exaggerated for visibility
                "color": pd["color"],
                "texture": pd["texture"],
                "orbit_path": _orbit_circle_points(pd["orbital_radius_km"]),
                **({k: v for k, v in pd.items() if k not in ("radius_km", "orbital_radius_km", "color", "texture")})
            }

    # --- Trajectory spline ---
    traj_spline = []
    if trajectory_data and "departure_velocity_vector" in trajectory_data:
        dv = trajectory_data["departure_velocity_vector"]
        origin = _scale_position(PLANETS_3D["EARTH"]["orbital_radius_km"], 0)
        dest_body = PLANETS_3D.get(target_up, PLANETS_3D.get("MARS", {}))
        dest = _scale_position(dest_body.get("orbital_radius_km", 2.279e8), 0) if dest_body else origin
        # Bezier control point (midpoint with angular offset)
        ctrl_x = (origin["x"] + dest["x"]) / 2 + (dest["z"] - origin["z"]) * 0.5
        ctrl_z = (origin["z"] + dest["z"]) / 2 + (dest["x"] - origin["x"]) * 0.5
        traj_spline = [origin, {"x": ctrl_x, "y": 0, "z": ctrl_z}, dest]

    # --- Spacecraft metadata for HUD ---
    dry_mass  = float(config.get("physical", {}).get("mass_dry", 500)) if isinstance(config.get("physical"), dict) else 500
    wet_mass  = float(config.get("physical", {}).get("mass_wet", 1000)) if isinstance(config.get("physical"), dict) else 1000
    power_gen = float(config.get("power", {}).get("generation_w", 1000)) if isinstance(config.get("power"), dict) else 1000

    scene = {
        "schema_version": "1.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "mission": {
            "name": mission_name,
            "type": mission_type,
            "target": target_up,
        },
        "spacecraft": {
            "mesh": spacecraft_mesh,
            "position": spacecraft_pos,
            "orbit_alt_km": round(orbit_alt_km, 1),
            "orbit_radius_km": round(orbit_radius_km, 1),
            "inclination_deg": round(inclination_deg, 2),
            "dry_mass_kg": dry_mass,
            "wet_mass_kg": wet_mass,
            "power_generation_w": power_gen,
            "orbit_path": _orbit_circle_points(orbit_radius_km),
        },
        "solar_system": planets_scene,
        "trajectory": {
            "spline_bezier_points": traj_spline,
            "type": "interplanetary" if len(bodies_in_scene) > 2 else "earth_orbit",
        },
        "telemetry": telemetry or {},
        "vr_config": {
            "scale": "1 scene unit = 1000 km",
            "coordinate_system": "heliocentric J2000 ecliptic (simplified circular)",
            "recommended_viewer": "Three.js r158+ or Babylon.js 6+",
            "webxr_compatible": True,
            "positional_audio": False,
            "haptics": False,
        },
    }

    return scene


def export_vr_json(scene: Dict[str, Any], mission_name: str = "mission") -> str:
    """
    Save scene data to saved_missions/<name>_vr.json.

    Returns the path to the saved file.
    """
    save_dir = os.path.join(os.path.dirname(__file__), "..", "saved_missions")
    os.makedirs(save_dir, exist_ok=True)

    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in mission_name).strip().replace(" ", "_")
    filename = f"{safe_name}_vr.json"
    filepath = os.path.join(save_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(scene, f, indent=2, default=str)

    return os.path.abspath(filepath)
