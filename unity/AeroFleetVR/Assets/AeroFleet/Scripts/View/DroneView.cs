using System;
using System.Collections.Generic;
using AeroFleet.VR.Data;
using AeroFleet.VR.Geo;
using AeroFleet.VR.Interaction;
using TMPro;
using UnityEngine;

namespace AeroFleet.VR.View
{
    /// <summary>
    /// One airborne drone on the table: quad glyph pointing along its heading, a drop-line to the
    /// ground (the altitude you read against the ruler), a ground ring (where it is over the map),
    /// its 4D trajectory — climb, cruise, descent; the flown part faint, the part ahead bright, with
    /// +30 s time ticks and the touchdown point — and a data tag. Position eases toward each new poll so the swarm moves
    /// smoothly between 1.5 s updates instead of jumping.
    /// </summary>
    public class DroneView : MonoBehaviour
    {
        public const float G = 0.02f; // symbol span in metres — a symbol, not to scale (the legend says so)

        public string Id { get; private set; }
        /// <summary>Height of this drone's tag card in metres (0 when collapsed to a title).</summary>
        public float TagHeight => tag != null ? tag.CardSize.y : 0f;
        float tagLift;
        public Action<string> OnSelect;

        Transform glyph, rotors, stem, shadow;
        Renderer nose, light;
        LineRenderer statusRing, pastLine, futureLine;
        Transform destMarker;
        TextMeshPro destLabel;
        readonly List<(Transform mark, TextMeshPro label)> ticks = new List<(Transform, TextMeshPro)>();
        const int TickEveryS = 30, MaxTicks = 4;
        DataTag tag;
        BoxCollider tagHit;
        Vector3 target;
        bool placed;
        bool emphasised;

        public static DroneView Create(Transform parent, string id)
        {
            var go = new GameObject("Drone " + id);
            go.transform.SetParent(parent, false);
            var v = go.AddComponent<DroneView>();
            v.Id = id;
            v.Build();
            return v;
        }

        void Build()
        {
            glyph = new GameObject("Glyph").transform;
            glyph.SetParent(transform, false);
            var body = Draw.Lit(Palette.Hex("D9E3EF"));
            var arm = Draw.Lit(Palette.Hex("9FB0C6"));
            Draw.Prim(PrimitiveType.Cube, glyph, Vector3.zero, new Vector3(0.3f, 0.12f, 0.34f) * G, body, "Body");
            foreach (float a in new[] { 45f, -45f })
                Draw.Prim(PrimitiveType.Cube, glyph, Vector3.zero, new Vector3(1.02f, 0.045f, 0.06f) * G, arm, "Arm").transform.localRotation = Quaternion.Euler(0, a, 0);
            rotors = new GameObject("Rotors").transform;
            rotors.SetParent(glyph, false);
            foreach (var (x, z) in new[] { (0.36f, 0.36f), (-0.36f, 0.36f), (0.36f, -0.36f), (-0.36f, -0.36f) })
            {
                var hub = new GameObject("Rotor").transform;
                hub.SetParent(rotors, false);
                hub.localPosition = new Vector3(x * G, 0.07f * G, z * G);
                Draw.Prim(PrimitiveType.Cube, hub, Vector3.zero, new Vector3(0.42f, 0.012f, 0.05f) * G, Draw.Unlit(Palette.Hex("C8D6E8")), "Blade");
            }
            nose = Draw.Prim(PrimitiveType.Cube, glyph, new Vector3(0, 0, 0.3f * G), new Vector3(0.08f, 0.08f, 0.18f) * G, Draw.Solid(Palette.Ok), "Nose").GetComponent<Renderer>();
            light = Draw.Prim(PrimitiveType.Sphere, glyph, new Vector3(0, 0.09f * G, 0), Vector3.one * 0.1f * G, Draw.Solid(Palette.Ok), "Beacon").GetComponent<Renderer>();
            statusRing = Draw.Line(glyph, Draw.Circle(0.66f * G, 40, -0.02f * G), 0.0012f, Palette.Ok, loop: true, name: "StatusRing");

            // generous invisible hit target — controller rays and the mouse both need it
            var hit = new GameObject("Hit");
            hit.transform.SetParent(transform, false);
            hit.AddComponent<SphereCollider>().radius = 0.028f;
            hit.AddComponent<Clickable>().OnClick = () => OnSelect?.Invoke(Id);

            stem = Draw.Prim(PrimitiveType.Cylinder, transform, Vector3.zero, Vector3.one, Draw.Unlit(Palette.Ok), "DropLine").transform;
            shadow = new GameObject("GroundRing").transform;
            shadow.SetParent(transform, false);
            Draw.Line(shadow, Draw.Circle(0.0045f, 20), 0.0016f, Palette.Ok, loop: true, name: "Ring");

            pastLine = Draw.Line(transform.parent, new Vector3[0], 0.0008f, Palette.Accent, name: "Flown " + Id);
            futureLine = Draw.Line(transform.parent, new Vector3[0], 0.0012f, Palette.Accent, name: "Ahead " + Id);
            destMarker = new GameObject("Touchdown " + Id).transform;
            destMarker.SetParent(transform.parent, false);
            Draw.Prim(PrimitiveType.Cube, destMarker, Vector3.zero, Vector3.one * 0.0075f, Draw.Solid(Palette.Accent), "Diamond")
                .transform.localRotation = Quaternion.Euler(45, 0, 45);
            destLabel = Draw.Text(destMarker, "", 0.0068f, Palette.Accent, TextAlignmentOptions.Center, new Vector3(0, 0.0165f, 0));
            destLabel.gameObject.AddComponent<Billboard>();
            for (int i = 0; i < MaxTicks; i++)
            {
                var mark = Draw.Prim(PrimitiveType.Sphere, transform.parent, Vector3.zero, Vector3.one * 0.0042f, Draw.Solid(Palette.Accent), "Tick " + Id).transform;
                var label = Draw.Text(mark, $"+{(i + 1) * TickEveryS} s", 0.0058f / 0.0042f, Palette.Accent, TextAlignmentOptions.Left, new Vector3(1.6f, 0.9f, 0));
                label.gameObject.AddComponent<Billboard>();
                ticks.Add((mark, label));
            }

            tag = DataTag.Create(transform, new Vector3(0, G * 1.1f, 0), 0.0082f);
            tagHit = tag.gameObject.AddComponent<BoxCollider>();
            tag.gameObject.AddComponent<Clickable>().OnClick = () => OnSelect?.Invoke(Id);
        }

        void OnDestroy()
        {
            if (pastLine != null) Destroy(pastLine.gameObject);
            if (futureLine != null) Destroy(futureLine.gameObject);
            if (destMarker != null) Destroy(destMarker.gameObject);
            foreach (var t in ticks) if (t.mark != null) Destroy(t.mark.gameObject);
        }

        public void Apply(LiveDrone d, Diorama dio, Vector2d cityCenter, LiveConstants k, bool selected, bool expanded)
        {
            var status = Vocab.Status(d);
            Color color = Vocab.StatusColor(status);
            Vector2 en = GeoMath.ToLocal(d.Lat, d.Lon, cityCenter.x, cityCenter.y);
            target = dio.Point(en.x, en.y, (float)d.AltitudeM);
            if (!placed || (transform.localPosition - target).magnitude > 0.3f) transform.localPosition = target;
            placed = true;
            glyph.localRotation = Quaternion.Euler(0, (float)(d.HeadingDeg ?? 0), 0);

            nose.sharedMaterial = Draw.Solid(color);
            light.sharedMaterial = Draw.Solid(color);
            statusRing.startColor = statusRing.endColor = selected ? Palette.Text : color;
            statusRing.widthMultiplier = selected ? 0.0022f : 0.0012f;
            stem.GetComponent<Renderer>().sharedMaterial = Draw.Unlit(Palette.WithAlpha(color, 0.55f));
            var ring = shadow.GetComponentInChildren<LineRenderer>();
            ring.startColor = ring.endColor = color;

            // trajectory: flown part faint, the part ahead bright, time ticks and touchdown when emphasised
            emphasised = selected || expanded;
            var past = new List<Vector3>();
            var ahead = new List<Vector3>();
            var traj = d.Trajectory;
            if (traj != null && traj.Count >= 2)
            {
                foreach (var p in traj)
                {
                    Vector3 v = TablePoint(dio, cityCenter, p);
                    if (p[3] <= 0) past.Add(v);
                    if (p[3] >= 0) ahead.Add(v);
                }
            }
            else if (d.Route != null && d.Route.Count >= 2) // no plan (e.g. LIVE telemetry): remaining route only
            {
                foreach (var p in d.Route) ahead.Add(TablePoint(dio, cityCenter, new[] { p[0], p[1], d.AltitudeM, 0 }));
            }
            SetLine(pastLine, past, 0.0008f, Palette.WithAlpha(Palette.Accent, emphasised ? 0.35f : 0.12f));
            SetLine(futureLine, ahead, emphasised ? 0.0016f : 0.0009f, Palette.WithAlpha(Palette.Accent, emphasised ? 0.9f : 0.32f));

            bool hasTouchdown = traj != null && traj.Count >= 2 && traj[traj.Count - 1][3] > 0;
            destMarker.gameObject.SetActive(emphasised && (hasTouchdown || ahead.Count >= 2));
            if (ahead.Count >= 2)
            {
                Vector3 end = ahead[ahead.Count - 1];
                destMarker.localPosition = new Vector3(end.x, Mathf.Max(end.y, 0.004f), end.z);
                destLabel.text = hasTouchdown ? $"lands in {Clock(traj[traj.Count - 1][3])}" : "destination";
            }
            for (int i = 0; i < ticks.Count; i++)
            {
                double t = (i + 1) * TickEveryS;
                bool show = emphasised && traj != null && traj.Count >= 2 && t < traj[traj.Count - 1][3];
                ticks[i].mark.gameObject.SetActive(show);
                if (show) ticks[i].mark.localPosition = TablePoint(dio, cityCenter, AtTime(traj, t));
            }

            // tag
            string title = expanded ? $"{Vocab.ShortId(Id)}  {d.State?.Replace('_', ' ')}" : Vocab.ShortId(Id);
            tag.Set(title, expanded ? color : Palette.Text, expanded ? Rows(d, k) : new List<TagRow>(), color);
            Vector2 cs = tag.CardSize;
            tagHit.center = new Vector3(0, cs.y / 2, 0);
            tagHit.size = new Vector3(cs.x, cs.y, 0.002f);
        }

        static List<TagRow> Rows(LiveDrone d, LiveConstants k)
        {
            float legal = (float)k.LegalCeilingM;
            double usable = d.BatteryAvailableWh + d.BatteryReserveWh;
            double capacity = d.BatterySocPct > 0 ? usable / (d.BatterySocPct / 100.0) : 0;
            float reserveFrac = capacity > 0 ? (float)(d.BatteryReserveWh / capacity) : 0;
            var rows = new List<TagRow>
            {
                TagRow.Bar("ALT", $"{d.AltitudeM:0} m  of {d.AltitudeCeilingM:0} m ceiling",
                    (float)d.AltitudeM / legal, (float)d.AltitudeCeilingM / legal,
                    Vocab.MarginColor(d.AltitudeCeilingM - d.AltitudeM, Vocab.WarnBands["altitude_ceiling"])),
                TagRow.Bar("BATT", $"{d.BatterySocPct:0} %  ·  {d.BatteryAvailableWh:0} Wh above reserve",
                    (float)d.BatterySocPct / 100f, reserveFrac,
                    Vocab.MarginColor(d.BatteryAvailableWh, Vocab.WarnBands["battery_reserve_margin"])),
            };
            if (d.NearestDroneId != null)
                rows.Add(TagRow.Bar("SEP", $"{GeoMath.FormatDistance(d.NearestHorizontalM)} to {Vocab.ShortId(d.NearestDroneId)}  ↕{d.NearestVerticalM:0} m",
                    (float)(d.NearestHorizontalM / (k.MinSeparationM * 4)), 0.25f,
                    Vocab.MarginColor(d.NearestHorizontalM - k.MinSeparationM, Vocab.WarnBands["min_separation"])));
            else
                rows.Add(TagRow.Text("SEP", "no other drone airborne", Palette.TextDim));
            if (d.Progress != null)
            {
                string leg = d.Phase switch
                {
                    "CLIMB" => $"climbing to {CruiseAltitude(d):0} m over the depot",
                    "DESCENT" => $"descending · lands in {Clock(d.EtaS ?? 0)}",
                    "LANDED" => "landed at destination",
                    _ => $"{d.Progress * 100:0} %  ·  {GeoMath.FormatDistance(d.RemainingM ?? 0)} left · lands in {Clock(d.EtaS ?? 0)}",
                };
                rows.Add(TagRow.Bar("LEG", leg, (float)d.Progress.Value, -1, Palette.Accent));
            }
            rows.Add(TagRow.Text("SRC", Vocab.SourceLabel(d.PositionSource), Palette.TextDim));
            return rows;
        }

        static Vector3 TablePoint(Diorama dio, Vector2d city, double[] p)
        {
            Vector2 en = GeoMath.ToLocal(p[0], p[1], city.x, city.y);
            return dio.Point(en.x, en.y, (float)p[2]);
        }

        /// <summary>Trajectory position at t seconds from now (linear between samples).</summary>
        static double[] AtTime(List<double[]> traj, double t)
        {
            for (int i = 0; i + 1 < traj.Count; i++)
            {
                double[] a = traj[i], b = traj[i + 1];
                if (t < a[3] || t > b[3]) continue;
                double u = b[3] > a[3] ? (t - a[3]) / (b[3] - a[3]) : 0;
                return new[] { a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u, t };
            }
            return traj[traj.Count - 1];
        }

        static double CruiseAltitude(LiveDrone d)
        {
            double max = d.AltitudeM;
            if (d.Trajectory != null) foreach (var p in d.Trajectory) max = System.Math.Max(max, p[2]);
            return max;
        }

        public static string Clock(double seconds)
        {
            int s = Mathf.Max(0, Mathf.RoundToInt((float)seconds));
            return s >= 60 ? $"{s / 60}:{s % 60:00}" : $"{s} s";
        }

        static void SetLine(LineRenderer lr, List<Vector3> pts, float width, Color c)
        {
            lr.positionCount = pts.Count;
            lr.SetPositions(pts.ToArray());
            lr.widthMultiplier = width;
            lr.startColor = lr.endColor = c;
        }

        /// <summary>Raise the tag so it doesn't sit on a nearby drone's tag (set by SwarmView).</summary>
        public void SetTagLift(float lift) => tagLift = lift;

        void Update()
        {
            tag.transform.localPosition = Vector3.Lerp(tag.transform.localPosition, new Vector3(0, G * 1.1f + tagLift, 0), 1 - Mathf.Exp(-Time.deltaTime * 6f));
            float dt = Time.deltaTime;
            transform.localPosition = Vector3.Lerp(transform.localPosition, target, 1 - Mathf.Exp(-dt * 2.5f));
            rotors.GetChild(0).Rotate(0, -38 * Mathf.Rad2Deg * dt, 0);
            rotors.GetChild(1).Rotate(0, 38 * Mathf.Rad2Deg * dt, 0);
            rotors.GetChild(2).Rotate(0, 38 * Mathf.Rad2Deg * dt, 0);
            rotors.GetChild(3).Rotate(0, -38 * Mathf.Rad2Deg * dt, 0);

            float h = Mathf.Max(transform.localPosition.y, 0.0001f);
            stem.localScale = new Vector3(0.0014f, h / 2, 0.0014f); // Unity cylinders are 2 units tall
            stem.localPosition = new Vector3(0, -h / 2, 0);
            shadow.localPosition = new Vector3(0, -h + 0.0015f, 0);
        }
    }
}
