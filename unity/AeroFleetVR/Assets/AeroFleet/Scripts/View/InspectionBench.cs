using System.Collections.Generic;
using AeroFleet.VR.Data;
using TMPro;
using UnityEngine;

namespace AeroFleet.VR.View
{
    /// <summary>
    /// A large model of the selected drone on a stand beside the table, so it can be inspected up
    /// close. Every part is coloured only from real data: the battery from the live feed, and the
    /// flight controller, motors, sensors/wiring and frame from the drone's latest flight-controller
    /// compliance inspection (Hardware ▸ Drone compliance). A part with no inspection on file is grey
    /// and says so — nothing is invented (the previous VR app picked failures at random).
    /// </summary>
    public class InspectionBench : MonoBehaviour
    {
        const float Span = 0.36f;
        Transform pivot, model, labels, titles;
        string shownFor;

        public void Hide()
        {
            shownFor = null;
            gameObject.SetActive(false);
        }

        public void Show(string droneId, LiveDrone d, FcInspectionDto inspection, bool inspectionLoaded)
        {
            string key = droneId + "|" + (inspection?.InspectionId ?? (inspectionLoaded ? "none" : "loading")) + "|" +
                         Mathf.RoundToInt((float)d.BatterySocPct) + "|" + d.PayloadKg.ToString("0.0");
            if (!Begin(key)) return;

            Color Cat(string k) => CategoryColor(inspection, k);
            var fc = Cat("flight_controller");
            var motors = Cat("motors");
            var wiring = Cat("wiring");
            var frame = Cat("airframe");
            Color batt = d.BatteryAvailableWh < 0 ? Palette.Bad : d.BatteryAvailableWh < 40 ? Palette.Warn : Palette.Ok;

            var motorTips = Airframe(4, Span, 0.13f, 1f, frame, motors, fc, wiring, batt, d.PayloadKg > 0.01);

            // labels
            string src = inspection != null
                ? $"inspection {inspection.InspectionId} · {inspection.Verdict ?? inspection.Status} · {(inspection.CompletedAt ?? "").Split('T')[0]}"
                : inspectionLoaded ? "no flight-controller inspection on file for this drone" : "looking up inspection…";
            Label(new Vector3(0, 0.36f, 0), $"INSPECTION · {droneId}", 0.018f, Palette.Accent, FontStyles.Bold);
            Label(new Vector3(0, 0.33f, 0), src, 0.011f, inspection != null ? Palette.TextDim : Palette.TextFaint);
            Callout(new Vector3(0, 0.12f - 0.035f, 0), new Vector3(-0.3f, 0.02f, 0),
                    $"Battery · {d.BatterySocPct:0} % · {d.BatteryAvailableWh:0} Wh above reserve (live)" +
                    (inspection != null ? " · inspection: " + CategoryText(inspection, "battery") : ""), batt);
            Callout(new Vector3(0, 0.12f + 0.025f, -0.01f), new Vector3(-0.3f, 0.2f, 0), "Flight controller · " + CategoryText(inspection, "flight_controller"), fc);
            Callout(new Vector3(0, 0.12f + 0.097f, 0.045f), new Vector3(0.3f, 0.26f, 0), "GPS & sensors · " + CategoryText(inspection, "wiring"), wiring);
            Callout(model.localPosition + motorTips[0] + Vector3.up * 0.02f, new Vector3(0.32f, 0.14f, 0), "Motors & ESCs · " + CategoryText(inspection, "motors"), motors);
            Callout(new Vector3(0.06f, 0.12f, 0), new Vector3(0.3f, 0.05f, 0), "Frame · " + CategoryText(inspection, "airframe"), frame);
            if (d.PayloadKg > 0.01)
                Callout(new Vector3(0, 0.12f - 0.085f, 0), new Vector3(0.28f, -0.06f, 0), $"Payload · {d.PayloadKg:0.0} kg", Palette.TextDim);
            if (inspection != null)
                Label(new Vector3(0, -0.07f, 0), "Failsafes · " + CategoryText(inspection, "failsafes") + "   ·   DGCA · " + CategoryText(inspection, "dgca"),
                      0.011f, Palette.TextDim);
        }

        /// <summary>The drone being designed on the BUILD board: the same stand, geometry from the parts.</summary>
        public void ShowBuild(Data.DroneBuild b)
        {
            string key = $"build|{b.FrameIndex}|{b.MotorIndex}|{b.BatteryIndex}|{b.PayloadIndex}";
            if (!Begin(key)) return;
            string problem = b.Problem;
            Color ok = problem == "" ? Palette.Ok : b.ThrustToWeight < 1 || b.PropTooBigForMotor ? Palette.Bad : Palette.Warn;
            // Span grows with the prop so a 5" racer and a 17" hexa look different; props drawn to the same scale.
            float span = Mathf.Lerp(0.2f, 0.46f, Mathf.InverseLerp(5, 17, (float)b.F.PropInch));
            float prop = 0.9f * span * Mathf.Sin(Mathf.PI / b.F.Arms); // largest disc that clears its neighbours
            float battScale = Mathf.Lerp(0.6f, 1.5f, Mathf.InverseLerp(0.18f, 2.7f, (float)b.B.Kg));
            var tips = Airframe(b.F.Arms, span, prop, battScale, Palette.Accent, b.PropTooBigForMotor ? Palette.Bad : Palette.Accent,
                                Palette.Accent, Palette.Accent, Palette.Accent, b.PayloadKg > 0.01);

            Label(new Vector3(0, 0.36f, 0), $"YOUR BUILD · {b.AllUpKg:0.00} kg · DGCA {b.Category.ToUpperInvariant()}", 0.018f, Palette.Accent, FontStyles.Bold);
            Label(new Vector3(0, 0.33f, 0), problem == "" ? $"hover ≈ {b.HoverW:0} W · endurance ≈ {b.EnduranceMin:0} min · thrust/weight {b.ThrustToWeight:0.0}" : problem,
                  0.011f, problem == "" ? Palette.TextDim : ok);
            Callout(new Vector3(0, 0.12f - 0.035f * battScale, 0), new Vector3(-0.3f, 0.02f, 0), $"{b.B.Name} · {b.B.Wh:0} Wh · {b.B.Kg:0.00} kg", Palette.Accent);
            Callout(model.localPosition + tips[0] + Vector3.up * 0.02f, new Vector3(0.32f, 0.14f, 0),
                    $"{b.F.Arms} × {b.M.Name} · {b.M.MaxThrustKgf:0.0} kgf each", b.PropTooBigForMotor ? Palette.Bad : Palette.Accent);
            Callout(new Vector3(0.06f, 0.12f, 0), new Vector3(0.3f, 0.05f, 0), $"{b.F.Name} · {b.F.Kg:0.00} kg", Palette.Accent);
            if (b.PayloadKg > 0.01)
                Callout(new Vector3(0, 0.12f - 0.085f, 0), new Vector3(0.28f, -0.06f, 0), $"Payload · {b.PayloadKg:0.0} kg", Palette.TextDim);
            Label(new Vector3(0, -0.07f, 0), "First-order sizing (momentum theory) — see the board for the assumptions", 0.0105f, Palette.TextFaint);
        }

        /// <summary>Clear and set up the stand for new content; false when `key` is already shown.</summary>
        bool Begin(string key)
        {
            gameObject.SetActive(true);
            if (key == shownFor) return false;
            shownFor = key;
            foreach (Transform c in transform) Destroy(c.gameObject);

            // stand
            // a slim post and a plate, so the stand doesn't hide the table behind it
            Draw.Prim(PrimitiveType.Cylinder, transform, new Vector3(0, -0.21f, 0), new Vector3(0.035f, 0.2f, 0.035f), Draw.Lit(Palette.Bezel), "Post");
            Draw.Prim(PrimitiveType.Cylinder, transform, new Vector3(0, -0.006f, 0), new Vector3(0.3f, 0.006f, 0.3f), Draw.Lit(Palette.Bezel), "Plate");
            Draw.Line(transform, Draw.Circle(0.15f, 64, 0.002f), 0.003f, Palette.Accent, loop: true, name: "StandRing");
            // the model and its callouts turn together on one pivot; the titles stay put
            pivot = new GameObject("Pivot").transform;
            pivot.SetParent(transform, false);
            model = new GameObject("Model").transform;
            model.SetParent(pivot, false);
            model.localPosition = new Vector3(0, 0.12f, 0);
            labels = new GameObject("Callouts").transform;
            labels.SetParent(pivot, false);
            titles = new GameObject("Titles").transform;
            titles.SetParent(transform, false);
            return true;
        }

        /// <summary>Body, arms, motors, props, battery (under), flight controller and GPS (on top), payload.
        /// Returns the motor positions (model space).</summary>
        List<Vector3> Airframe(int arms, float span, float propDiameter, float battScale, Color frame, Color motors, Color fc,
                               Color wiring, Color batt, bool payload)
        {
            Draw.Prim(PrimitiveType.Cube, model, Vector3.zero, new Vector3(0.12f, 0.035f, 0.14f), Draw.Lit(Tint(frame, 0.35f)), "Body");
            var motorTips = new List<Vector3>();
            for (int i = 0; i < arms; i++)
            {
                float a = 360f / arms * i + (arms == 4 ? 45f : 0f);
                float r = span / 2;
                Vector3 tip = Quaternion.Euler(0, a, 0) * new Vector3(0, 0, r);
                var arm = Draw.Prim(PrimitiveType.Cube, model, tip / 2, new Vector3(0.018f, 0.014f, r), Draw.Lit(Tint(frame, 0.25f)), "Arm");
                arm.transform.localRotation = Quaternion.Euler(0, a, 0);
                Draw.Prim(PrimitiveType.Cylinder, model, tip + Vector3.up * 0.014f, new Vector3(0.036f, 0.014f, 0.036f), Draw.Solid(motors), "Motor");
                Draw.Prim(PrimitiveType.Cylinder, model, tip + Vector3.up * 0.031f, new Vector3(propDiameter, 0.0015f, propDiameter),
                          Draw.Unlit(Palette.WithAlpha(Palette.Text, 0.18f)), "Prop");
                motorTips.Add(tip);
            }
            Draw.Prim(PrimitiveType.Cube, model, new Vector3(0, -0.035f * battScale, 0), new Vector3(0.085f, 0.032f, 0.12f) * battScale, Draw.Solid(batt), "Battery");
            Draw.Prim(PrimitiveType.Cube, model, new Vector3(0, 0.025f, -0.01f), new Vector3(0.05f, 0.014f, 0.05f), Draw.Solid(fc), "FlightController");
            Draw.Prim(PrimitiveType.Cylinder, model, new Vector3(0, 0.06f, 0.045f), new Vector3(0.006f, 0.035f, 0.006f), Draw.Lit(Palette.Neutral), "GpsMast");
            Draw.Prim(PrimitiveType.Cylinder, model, new Vector3(0, 0.097f, 0.045f), new Vector3(0.04f, 0.006f, 0.04f), Draw.Solid(wiring), "Gps");
            if (payload)
                Draw.Prim(PrimitiveType.Cube, model, new Vector3(0, -0.085f, 0), Vector3.one * 0.055f, Draw.Lit(Palette.Hex("B08B5A")), "Payload");
            return motorTips;
        }

        void Update()
        {
            if (pivot != null) pivot.Rotate(0, 10f * Time.deltaTime, 0, Space.Self);
        }

        static Color Tint(Color c, float amount) => Color.Lerp(Palette.Hex("C8D3E0"), c, amount);

        static FcCategoryDto Category(FcInspectionDto i, string key) =>
            i?.Report?.Categories?.Find(c => c.Key == key);

        static int N(FcCategoryDto c, string status) => c != null && c.Counts != null && c.Counts.TryGetValue(status, out int n) ? n : 0;

        public static Color CategoryColor(FcInspectionDto i, string key)
        {
            var c = Category(i, key);
            if (c == null) return Palette.Neutral;
            if (N(c, "FAIL") > 0) return Palette.Bad;
            if (N(c, "WARN") > 0 || N(c, "UNKNOWN") > 0) return Palette.Warn;
            return N(c, "PASS") > 0 ? Palette.Ok : Palette.Neutral;
        }

        public static string CategoryText(FcInspectionDto i, string key)
        {
            var c = Category(i, key);
            if (c == null) return "not inspected";
            var parts = new List<string>();
            foreach (var s in new[] { "FAIL", "WARN", "UNKNOWN", "PASS", "MANUAL" })
                if (N(c, s) > 0) parts.Add($"{N(c, s)} {s.ToLowerInvariant()}");
            return parts.Count > 0 ? string.Join(", ", parts) : "no checks";
        }

        void Label(Vector3 pos, string text, float h, Color c, FontStyles style = FontStyles.Normal)
        {
            var t = Draw.Text(titles, text, h, c, TextAlignmentOptions.Center, pos, 0f, style);
            t.gameObject.AddComponent<Billboard>();
        }

        void Callout(Vector3 from, Vector3 labelAt, string text, Color c)
        {
            Draw.Line(labels, new[] { from, labelAt }, 0.0012f, Palette.WithAlpha(c, 0.8f), name: "Leader");
            Draw.Prim(PrimitiveType.Sphere, labels, from, Vector3.one * 0.008f, Draw.Solid(c), "Anchor");
            var t = Draw.Text(labels, text, 0.012f, c, labelAt.x < 0 ? TextAlignmentOptions.Right : TextAlignmentOptions.Left,
                              labelAt + Vector3.up * 0.01f);
            t.gameObject.AddComponent<Billboard>();
        }
    }
}
