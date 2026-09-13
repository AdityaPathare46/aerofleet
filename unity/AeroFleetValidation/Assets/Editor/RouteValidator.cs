// RouteValidator — headless physics validation of a real, optimized
// AeroFleet route (aerofleet/city/route_weights.py's optimized_shortest_path
// + trajectory_builder.py's per-waypoint accounting) against a real
// point-mass rigid-body simulation. The CBF gate checks each waypoint's
// state independently; this checks whether the drone can actually FLY the
// path between those waypoints — a real, separate verification, not a
// duplicate of the CBF math.
//
// Runs via `unity run` batch mode:
//   unity run <project> -- -batchmode -nographics -quit
//       -executeMethod RouteValidator.Run
//       -route <path/to/route.json> -output <path/to/result.json>
//
// HONEST STATUS NOTE: written against the real, confirmed Unity CLI batch-
// mode invocation (`unity run --help`) and standard, well-documented
// Unity APIs, but not yet compiled or run in a real Unity Editor — none
// was installed on the authoring machine at the time this was written.
// Treat this as a real first draft to test once an Editor is available
// (see the project's own README.md), not as already-verified code.
using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public static class RouteValidator
{
    // ── JSON shapes — must match aerofleet/validation/unity_bridge.py exactly ──

    [Serializable]
    private class Waypoint
    {
        public double lat;
        public double lon;
        public double altitude_m;
        public double wind_speed_mps;
    }

    [Serializable]
    private class RouteFile
    {
        public Waypoint[] waypoints;
        public double drone_mass_kg;
        // Reasonable, documented defaults for a small-category delivery
        // quadcopter — not a specific cited product's spec sheet, same
        // honesty standard as aerofleet/fleet/models.py's Drone.weight_kg.
        public double max_thrust_n = 60.0;
        public double drag_coefficient = 0.9;
    }

    [Serializable]
    private class WaypointResult
    {
        public int index;
        public bool reached;
        public double deviation_m;
    }

    [Serializable]
    private class ValidationResult
    {
        public bool success;
        public WaypointResult[] waypoints;
        public string[] events;
        public string error;
    }

    // ── Entry point ──

    public static void Run()
    {
        string routePath = GetArg("-route");
        string outputPath = GetArg("-output");
        ValidationResult result;

        try
        {
            string json = File.ReadAllText(routePath);
            RouteFile route = JsonUtility.FromJson<RouteFile>(json);
            result = SimulateRoute(route);
        }
        catch (Exception ex)
        {
            result = new ValidationResult
            {
                success = false,
                waypoints = new WaypointResult[0],
                events = new string[0],
                error = ex.Message,
            };
        }

        File.WriteAllText(outputPath, JsonUtility.ToJson(result, true));
        EditorApplication.Exit(result.success ? 0 : 1);
    }

    private static string GetArg(string name)
    {
        string[] args = Environment.GetCommandLineArgs();
        for (int i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == name)
            {
                return args[i + 1];
            }
        }
        throw new ArgumentException($"Missing required command-line argument: {name}");
    }

    // ── Simulation ──

    private const float FixedDt = 0.02f;          // 50 Hz, matches Unity's default fixed timestep
    private const float ReachToleranceM = 2.0f;    // waypoint "arrived" radius
    private const float MaxSecondsPerLeg = 120.0f; // safety cap so a bad route can't hang the process

    private static ValidationResult SimulateRoute(RouteFile route)
    {
        var waypointResults = new List<WaypointResult>();
        var events = new List<string>();

        if (route.waypoints == null || route.waypoints.Length < 2)
        {
            return new ValidationResult
            {
                success = false,
                waypoints = new WaypointResult[0],
                events = new string[0],
                error = "route needs at least 2 waypoints",
            };
        }

        double originLat = route.waypoints[0].lat;
        double originLon = route.waypoints[0].lon;
        Vector3 position = LatLonToLocal(route.waypoints[0], originLat, originLon);
        Vector3 velocity = Vector3.zero;

        float mass = (float)Math.Max(0.1, route.drone_mass_kg);
        float maxThrust = (float)route.max_thrust_n;
        float dragCoefficient = (float)route.drag_coefficient;

        waypointResults.Add(new WaypointResult { index = 0, reached = true, deviation_m = 0.0 });

        for (int i = 1; i < route.waypoints.Length; i++)
        {
            Waypoint wp = route.waypoints[i];
            Vector3 target = LatLonToLocal(wp, originLat, originLon);
            // Simple constant-direction wind model — a real force, not
            // just a reported number, but not a full wind field.
            Vector3 wind = new Vector3((float)wp.wind_speed_mps, 0f, 0f);

            float elapsed = 0f;
            bool reached = false;
            while (elapsed < MaxSecondsPerLeg)
            {
                Vector3 toTarget = target - position;
                float distance = toTarget.magnitude;
                if (distance < ReachToleranceM)
                {
                    reached = true;
                    break;
                }

                Vector3 thrust = toTarget.normalized * maxThrust;
                Vector3 gravity = new Vector3(0f, -9.81f * mass, 0f);
                Vector3 relativeVelocity = velocity - wind;
                Vector3 drag = -relativeVelocity * relativeVelocity.magnitude * dragCoefficient;

                Vector3 acceleration = (thrust + gravity + drag) / mass;
                velocity += acceleration * FixedDt;
                position += velocity * FixedDt;
                elapsed += FixedDt;
            }

            float finalDeviation = Vector3.Distance(position, target);
            if (!reached)
            {
                events.Add(
                    $"Waypoint {i}: did not reach within {MaxSecondsPerLeg}s " +
                    $"(deviation {finalDeviation:F1}m) — route may not be flyable as planned."
                );
            }
            waypointResults.Add(new WaypointResult { index = i, reached = reached, deviation_m = finalDeviation });
        }

        bool allReached = waypointResults.TrueForAll(w => w.reached);
        return new ValidationResult
        {
            success = allReached,
            waypoints = waypointResults.ToArray(),
            events = events.ToArray(),
            error = null,
        };
    }

    // Equirectangular local projection anchored at the route's first
    // waypoint — a real, standard, simple projection, accurate enough
    // over the few-km scale one delivery route spans. Not intended for
    // anything approaching the scale where Earth curvature would matter.
    private static Vector3 LatLonToLocal(Waypoint wp, double originLat, double originLon)
    {
        const double metersPerDegLat = 111320.0;
        double metersPerDegLon = 111320.0 * Math.Cos(originLat * Math.PI / 180.0);
        float x = (float)((wp.lon - originLon) * metersPerDegLon);
        float z = (float)((wp.lat - originLat) * metersPerDegLat);
        float y = (float)wp.altitude_m;
        return new Vector3(x, y, z);
    }
}
