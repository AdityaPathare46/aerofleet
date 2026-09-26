using System.Collections.Generic;
using AeroFleet.VR.Data;
using AeroFleet.VR.Geo;
using TMPro;
using UnityEngine;

namespace AeroFleet.VR.View
{
    /// <summary>
    /// A frozen CBF rejection: origin depot, the planned leg (explicitly labelled straight-line —
    /// the flown path is not in the record), the attempted altitude rod at the rejection point, the
    /// ceiling that applied there, and a tag listing every violated constraint with its magnitude.
    /// </summary>
    public class ReplayView : MonoBehaviour
    {
        public static (float east, float north, float extentM)? Frame(VrSceneDto s, Vector2d city)
        {
            if (s.Position?.Lat == null || s.Position.Lon == null) return null;
            Vector2 d = GeoMath.ToLocal(s.Position.Lat.Value, s.Position.Lon.Value, city.x, city.y);
            if (s.Origin?.Lat == null || s.Origin.Lon == null) return (d.x, d.y, 700f);
            Vector2 o = GeoMath.ToLocal(s.Origin.Lat.Value, s.Origin.Lon.Value, city.x, city.y);
            float span = (d - o).magnitude;
            return ((d.x + o.x) / 2, (d.y + o.y) / 2, Mathf.Clamp(span * 0.75f, 600f, 6000f));
        }

        public void Show(VrSceneDto s, Diorama dio, Vector2d city)
        {
            foreach (Transform c in transform) Destroy(c.gameObject);
            if (s.Position?.Lat == null || s.Position.Lon == null) return;

            Vector2 de = GeoMath.ToLocal(s.Position.Lat.Value, s.Position.Lon.Value, city.x, city.y);
            float alt = (float)(s.AltitudeM ?? 40), ceiling = (float)(s.MaxAltitudeM ?? 100);
            var violated = new HashSet<string>();
            foreach (var v in s.Violations) violated.Add(v.ConstraintName);
            bool altBreach = violated.Contains("altitude_ceiling");
            bool geofence = violated.Contains("geofence_exclusion") || s.InRedZone;

            Vector3 dest = dio.Point(de.x, de.y, alt), destGround = dio.Point(de.x, de.y, 0);

            if (s.PlannedRoute != null && s.PlannedRoute.Count >= 2) DrawPlannedRoute(s.PlannedRoute, (float?)s.MaxAltitudeM, dio, city);
            else if (s.Origin?.Lat != null && s.Origin.Lon != null)
            {
                // Incidents recorded before the checked route was kept: straight line, labelled as such.
                Vector2 oe = GeoMath.ToLocal(s.Origin.Lat.Value, s.Origin.Lon.Value, city.x, city.y);
                Vector3 og = dio.Point(oe.x, oe.y, 0), oc = dio.Point(oe.x, oe.y, alt);
                Draw.Prim(PrimitiveType.Cylinder, transform, og + Vector3.up * 0.003f, new Vector3(0.026f, 0.0025f, 0.026f), Draw.Solid(Palette.Ok), "OriginDepot");
                Label(og + Vector3.up * 0.022f, "origin depot", 0.0085f, Palette.Ok);
                Draw.Line(transform, new[] { og, oc, dest }, 0.0018f, Palette.Accent, name: "PlannedLeg");
                Label((oc + dest) / 2 + Vector3.up * 0.014f, "planned leg — straight line; this incident predates stored routes", 0.0068f, Palette.TextFaint);
            }

            // the attempted cruise altitude at the rejection point — the exact number the gate checked
            Draw.Line(transform, new[] { destGround, dest }, altBreach ? 0.004f : 0.002f, altBreach ? Palette.Bad : Palette.TextDim, name: "AltitudeRod");
            Draw.Prim(PrimitiveType.Sphere, transform, dest, Vector3.one * 0.018f, Draw.Solid(geofence || altBreach ? Palette.Bad : Palette.Warn), "RejectionPoint");
            Draw.Line(transform, Offset(Draw.Circle(0.014f, 32), destGround + Vector3.up * 0.002f), 0.003f, Palette.Bad, loop: true, name: "GroundMark");

            // the ceiling that applied at this location
            float cy = dio.Y(ceiling);
            Color cc = altBreach ? Palette.Bad : Palette.Accent;
            Draw.Line(transform, Offset(Draw.Circle(0.03f, 48), new Vector3(dest.x, cy, dest.z)), 0.002f, cc, loop: true, name: "CeilingHere");
            Label(new Vector3(dest.x + 0.05f, cy, dest.z), $"ceiling here {ceiling:0} m", 0.0078f, cc);

            var rows = new List<TagRow>();
            foreach (var (name, worst, waypoints) in GroupViolations(s.Violations))
            {
                string unit = Vocab.ConstraintUnit(name);
                rows.Add(TagRow.Text("FAIL", $"{Vocab.ConstraintLabel(name)}  −{worst:0.0}{(unit != "" ? " " + unit : "")}" +
                                             (waypoints > 1 ? $"  at {waypoints} waypoints" : ""), Palette.Bad));
            }
            rows.Add(TagRow.Text("ALT", $"{alt:0} m attempted / ceiling {ceiling:0} m", altBreach ? Palette.Bad : Palette.TextDim));
            if (s.InRedZone) rows.Add(TagRow.Text("ZONE", "destination inside DGCA red zone", Palette.Bad));
            else if (s.InYellowZone) rows.Add(TagRow.Text("ZONE", "destination in airport permission zone", Palette.Warn));

            var tag = DataTag.Create(transform, new Vector3(dest.x, Mathf.Max(dest.y, cy) + 0.02f, dest.z), 0.0082f);
            tag.Set($"REJECTED{(s.DroneId != null ? " · " + s.DroneId : "")}", Palette.Bad, rows, Palette.Bad);
        }

        /// <summary>The route the CBF gate actually checked: climb at the depot, each waypoint at its
        /// assigned altitude, descent at the destination. Segments turn red where the waypoint is in a
        /// no-fly zone or the battery margin has gone negative, and the first failing waypoint is marked.</summary>
        /// <summary>The gate reports a violation per failing waypoint; group per constraint, keeping the worst.</summary>
        public static List<(string name, double worst, int waypoints)> GroupViolations(List<ViolationDto> vs)
        {
            var order = new List<string>();
            var by = new Dictionary<string, (double worst, int n)>();
            foreach (var v in vs)
            {
                if (!by.TryGetValue(v.ConstraintName, out var g)) { order.Add(v.ConstraintName); g = (v.ViolationMagnitude, 0); }
                by[v.ConstraintName] = (System.Math.Max(g.worst, v.ViolationMagnitude), g.n + 1);
            }
            return order.ConvertAll(k => (k, by[k].worst, by[k].n));
        }

        /// <summary>Why a waypoint fails the gate, or null: no-fly zone, battery below reserve, or above the ceiling.</summary>
        static string Failure(double[] w, float? ceilingM)
        {
            if (w[3] > 0.5) return "route enters a DGCA no-fly zone here";
            if (w[4] < 0) return $"battery reserve exhausted here ({w[4]:0} Wh)";
            if (ceilingM != null && w[2] > ceilingM.Value + 1e-6) return $"above the {ceilingM.Value:0} m ceiling from here ({w[2]:0} m)";
            return null;
        }

        void DrawPlannedRoute(List<double[]> route, float? ceilingM, Diorama dio, Vector2d city)
        {
            Vector3 P(double[] w, float? altOverride = null)
            {
                Vector2 en = GeoMath.ToLocal(w[0], w[1], city.x, city.y);
                return dio.Point(en.x, en.y, altOverride ?? (float)w[2]);
            }
            bool Fails(double[] w) => Failure(w, ceilingM) != null;

            var first = route[0];
            Vector3 og = P(first, 0);
            Draw.Prim(PrimitiveType.Cylinder, transform, og + Vector3.up * 0.003f, new Vector3(0.026f, 0.0025f, 0.026f), Draw.Solid(Palette.Ok), "OriginDepot");
            Label(og + Vector3.up * 0.022f, "origin depot", 0.0085f, Palette.Ok);
            Draw.Line(transform, new[] { og, P(first) }, 0.0014f, Palette.Accent, name: "Climb");

            // one line per run of same-status waypoints, so colour changes exactly where the check flips
            int runStart = 0;
            for (int i = 1; i <= route.Count; i++)
            {
                if (i < route.Count && Fails(route[i]) == Fails(route[runStart])) continue;
                var pts = new List<Vector3>();
                for (int k = Mathf.Max(runStart - 1, 0); k < i; k++) pts.Add(P(route[k]));
                bool bad = Fails(route[runStart]);
                Draw.Line(transform, pts, bad ? 0.003f : 0.0018f, bad ? Palette.Bad : Palette.Accent, name: bad ? "RouteFailing" : "Route");
                runStart = i;
            }
            var last = route[route.Count - 1];
            Draw.Line(transform, new[] { P(last), P(last, 0) }, 0.0014f, Palette.Accent, name: "Descent");

            int failAt = route.FindIndex(Fails);
            if (failAt >= 0)
            {
                var w = route[failAt];
                Vector3 at = P(w);
                Draw.Prim(PrimitiveType.Sphere, transform, at, Vector3.one * 0.011f, Draw.Solid(Palette.Bad), "FirstFailure");
                Label(at + Vector3.up * 0.018f, $"{Failure(w, ceilingM)} · waypoint {failAt + 1} of {route.Count}", 0.0075f, Palette.Bad);
            }
            Vector3 mid = P(route[route.Count / 2]);
            Label(mid + Vector3.up * 0.03f, $"route the CBF gate checked · {route.Count} waypoints", 0.0068f, Palette.TextDim);
        }

        public void Hide()
        {
            foreach (Transform c in transform) Destroy(c.gameObject);
        }

        static Vector3[] Offset(Vector3[] pts, Vector3 by)
        {
            for (int i = 0; i < pts.Length; i++) pts[i] += by;
            return pts;
        }

        void Label(Vector3 pos, string text, float h, Color c)
        {
            var t = Draw.Text(transform, text, h, c, TextAlignmentOptions.Center, pos);
            t.gameObject.AddComponent<Billboard>();
        }
    }
}
