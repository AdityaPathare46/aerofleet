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

            if (s.Origin?.Lat != null && s.Origin.Lon != null)
            {
                Vector2 oe = GeoMath.ToLocal(s.Origin.Lat.Value, s.Origin.Lon.Value, city.x, city.y);
                Vector3 og = dio.Point(oe.x, oe.y, 0), oc = dio.Point(oe.x, oe.y, alt);
                Draw.Prim(PrimitiveType.Cylinder, transform, og + Vector3.up * 0.003f, new Vector3(0.026f, 0.0025f, 0.026f), Draw.Solid(Palette.Ok), "OriginDepot");
                Label(og + Vector3.up * 0.022f, "origin depot", 0.0085f, Palette.Ok);
                Draw.Line(transform, new[] { og, oc, dest }, 0.0018f, Palette.Accent, name: "PlannedLeg");
                Label((oc + dest) / 2 + Vector3.up * 0.014f, "planned leg — straight line; the flown path isn't in the frozen record", 0.0068f, Palette.TextFaint);
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
            foreach (var v in s.Violations)
            {
                string unit = Vocab.ConstraintUnit(v.ConstraintName);
                rows.Add(TagRow.Text("FAIL", $"{Vocab.ConstraintLabel(v.ConstraintName)}  −{v.ViolationMagnitude:0.0}{(unit != "" ? " " + unit : "")}", Palette.Bad));
            }
            rows.Add(TagRow.Text("ALT", $"{alt:0} m attempted / ceiling {ceiling:0} m", altBreach ? Palette.Bad : Palette.TextDim));
            if (s.InRedZone) rows.Add(TagRow.Text("ZONE", "destination inside DGCA red zone", Palette.Bad));
            else if (s.InYellowZone) rows.Add(TagRow.Text("ZONE", "destination in airport permission zone", Palette.Warn));

            var tag = DataTag.Create(transform, new Vector3(dest.x, Mathf.Max(dest.y, cy) + 0.02f, dest.z), 0.0082f);
            tag.Set($"REJECTED{(s.DroneId != null ? " · " + s.DroneId : "")}", Palette.Bad, rows, Palette.Bad);
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
