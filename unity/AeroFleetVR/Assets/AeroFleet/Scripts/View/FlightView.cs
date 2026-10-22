using System.Collections.Generic;
using AeroFleet.VR.Data;
using AeroFleet.VR.Geo;
using TMPro;
using UnityEngine;

namespace AeroFleet.VR.View
{
    /// <summary>
    /// A reviewed flight on the table: the approved plan (dashed, accent), the flown track (green within the
    /// fleet's tolerances, red during a deviation), its shadow on the table, the log's warnings and notices
    /// pinned where they happened, and a playhead looping at ×10. Same data and colours as the web view
    /// (tauri-app/src/components/vr/Flight.tsx). No cause is named — the facts are laid out for a person.
    /// </summary>
    public class FlightView : MonoBehaviour
    {
        const float Speed = 10f;
        const int MaxPins = 12;

        FlightReviewDto f;
        Diorama dio;
        Vector2d home;
        Transform head;
        TextMeshPro headLabel;
        Renderer headRenderer;
        float t, end;

        public float TimeS => t;

        /// <summary>Centre on the flight's home and fit the plan and the track (east, north, half-extent in metres).</summary>
        public static (float east, float north, float extentM) Frame(FlightReviewDto f)
        {
            var c = new Vector2d(f.Replay.Home[0], f.Replay.Home[1]);
            float minE = float.MaxValue, maxE = float.MinValue, minN = float.MaxValue, maxN = float.MinValue;
            void Take(double lat, double lon)
            {
                Vector2 p = GeoMath.ToLocal(lat, lon, c.x, c.y);
                minE = Mathf.Min(minE, p.x); maxE = Mathf.Max(maxE, p.x); minN = Mathf.Min(minN, p.y); maxN = Mathf.Max(maxN, p.y);
            }
            foreach (var p in f.Replay.Planned) Take(p[0], p[1]);
            foreach (var p in f.Replay.Flown) Take(p[1], p[2]);
            return ((minE + maxE) / 2, (minN + maxN) / 2, Mathf.Max(80f, 0.6f * Mathf.Max(maxE - minE, maxN - minN)));
        }

        public void Show(FlightReviewDto review, Diorama d)
        {
            Hide();
            f = review; dio = d;
            home = new Vector2d(f.Replay.Home[0], f.Replay.Home[1]);
            end = f.Replay.Flown.Count > 0 ? (float)f.Replay.Flown[f.Replay.Flown.Count - 1][0] : 0f;
            t = 0f;

            // planned path, dashed: draw every other short piece
            var planned = new List<Vector3>();
            foreach (var p in f.Replay.Planned) planned.Add(At(p[0], p[1], p[2]));
            Dashed(planned, 0.012f, 0.008f);

            // flown track in runs: green within tolerance, red during a deviation; plus its ground shadow
            var shadow = new List<Vector3>();
            var run = new List<Vector3>();
            bool? runBad = null;
            foreach (var s in f.Replay.Flown)
            {
                Vector3 p = At(s[1], s[2], s[3]);
                shadow.Add(At(s[1], s[2], 0));
                bool bad = InEpisode(s[0]);
                if (runBad != null && bad != runBad.Value)
                {
                    Draw.Line(transform, run, runBad.Value ? 0.0045f : 0.003f, runBad.Value ? Palette.Bad : Palette.Ok, name: "Flown");
                    run = new List<Vector3> { run[run.Count - 1] };
                }
                run.Add(p);
                runBad = bad;
            }
            if (run.Count > 1) Draw.Line(transform, run, runBad == true ? 0.0045f : 0.003f, runBad == true ? Palette.Bad : Palette.Ok, name: "Flown");
            if (shadow.Count > 1) Draw.Line(transform, shadow, 0.0015f, Palette.WithAlpha(Palette.TextFaint, 0.5f), name: "Shadow");

            // the log's events where they happened (warnings and notices; info is on the board only)
            int pins = 0;
            foreach (var e in f.Timeline)
            {
                if (pins >= MaxPins || e.Level == "info" || e.Kind == "end") continue;
                var s = f.Replay.Flown[SampleAt(e.TS)];
                Color c = e.Level == "warning" ? Palette.Bad : Palette.Warn;
                Vector3 top = At(s[1], s[2], s[3]), baseP = At(s[1], s[2], 0);
                Draw.Line(transform, new[] { baseP, top }, 0.001f, Palette.WithAlpha(c, 0.7f), name: "Pin");
                Draw.Prim(PrimitiveType.Sphere, transform, top, Vector3.one * 0.009f, Draw.Unlit(c), "PinHead");
                var label = Draw.Text(transform, $"{Clock(e.TS)} {e.Text}", 0.0085f, c, localPos: top + new Vector3(0, 0.016f + (pins % 3) * 0.013f, 0));
                label.gameObject.AddComponent<Billboard>();
                pins++;
            }

            var h = At(home.x, home.y, 0);
            Draw.Prim(PrimitiveType.Cylinder, transform, h, new Vector3(0.02f, 0.001f, 0.02f), Draw.Unlit(Palette.Accent), "Home");
            Draw.Text(transform, "HOME", 0.008f, Palette.Accent, localPos: h + new Vector3(0, 0.014f, 0)).gameObject.AddComponent<Billboard>();

            var headGo = Draw.Prim(PrimitiveType.Sphere, transform, Vector3.zero, Vector3.one * 0.016f, Draw.Unlit(Palette.Text), "Playhead");
            head = headGo.transform;
            headRenderer = headGo.GetComponent<Renderer>();
            headLabel = Draw.Text(transform, "", 0.009f, Palette.Text);
            headLabel.gameObject.AddComponent<Billboard>();

            Draw.Text(transform, $"dashed = approved plan · green = flown within tolerance · red = deviation · table {GeoMath.FormatDistance(2 * d.ExtentM)} across",
                0.0075f, Palette.TextDim, TextAlignmentOptions.Left, new Vector3(-d.TableHalf + 0.02f, 0.004f, -d.TableHalf + 0.03f));
            Place();
        }

        public void Hide()
        {
            foreach (Transform c in transform) Destroy(c.gameObject);
            f = null; head = null;
        }

        void Update()
        {
            if (f == null || head == null || end <= 0) return;
            t += Time.deltaTime * Speed;
            if (t > end + 3f) t = 0f;          // hold briefly at the end, then loop
            Place();
        }

        void Place()
        {
            var s = f.Replay.Flown[SampleAt(Mathf.Min(t, end))];
            head.localPosition = At(s[1], s[2], s[3]);
            bool bad = InEpisode(s[0]);
            headRenderer.sharedMaterial = Draw.Unlit(bad ? Palette.Bad : Palette.Ok);
            headLabel.transform.localPosition = head.localPosition + new Vector3(0, 0.024f, 0);
            headLabel.text = $"{Clock(s[0])} · {Mathf.RoundToInt((float)s[3])} m";
        }

        Vector3 At(double lat, double lon, double h)
        {
            Vector2 p = GeoMath.ToLocal(lat, lon, home.x, home.y);
            return dio.Point(p.x, p.y, Mathf.Max(0f, (float)h));
        }

        bool InEpisode(double ts)
        {
            foreach (var e in f.Episodes) if (ts >= e.StartS && ts <= e.StartS + e.DurationS) return true;
            return false;
        }

        int SampleAt(double ts)
        {
            var fl = f.Replay.Flown;
            int lo = 0, hi = fl.Count - 1;
            while (lo < hi) { int mid = (lo + hi + 1) / 2; if (fl[mid][0] <= ts) lo = mid; else hi = mid - 1; }
            return lo;
        }

        void Dashed(List<Vector3> pts, float dash, float gap)
        {
            for (int i = 0; i + 1 < pts.Count; i++)
            {
                Vector3 a = pts[i], b = pts[i + 1];
                float len = (b - a).magnitude;
                for (float s = 0; s < len; s += dash + gap)
                {
                    Vector3 p0 = a + (b - a) * (s / len), p1 = a + (b - a) * (Mathf.Min(s + dash, len) / len);
                    Draw.Line(transform, new[] { p0, p1 }, 0.0025f, Palette.Accent, name: "Planned");
                }
            }
        }

        public static string Clock(double s)
        {
            int total = Mathf.Max(0, Mathf.RoundToInt((float)s));
            return $"{total / 60}:{total % 60:00}";
        }
    }
}
