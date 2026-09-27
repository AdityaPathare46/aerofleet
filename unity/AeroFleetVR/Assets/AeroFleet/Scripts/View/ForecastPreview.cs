using System.Collections.Generic;
using AeroFleet.VR.Data;
using AeroFleet.VR.Geo;
using TMPro;
using UnityEngine;

namespace AeroFleet.VR.View
{
    /// <summary>
    /// "▶ 2-MIN PREVIEW": plays the next two minutes of the swarm at ×10 — a ghost of every drone flies
    /// along its planned 4D trajectory (the same trajectories the backend forecasts conflicts from),
    /// and each predicted conflict lights up when the clock reaches it. Nothing is simulated here:
    /// positions are interpolated from the backend's trajectory samples, frozen at the moment PLAY
    /// was pressed so the preview is one consistent forecast.
    /// </summary>
    public class ForecastPreview : MonoBehaviour
    {
        public const float Speed = 10f;
        public bool Playing { get; private set; }
        public float T { get; private set; }          // forecast seconds from the snapshot
        public float Horizon { get; private set; } = 120f;

        readonly List<(List<double[]> traj, Transform ghost, LineRenderer trail, List<Vector3> path)> ghosts =
            new List<(List<double[]>, Transform, LineRenderer, List<Vector3>)>();
        readonly List<(PredictedConflict c, Transform mark, TextMeshPro label)> conflicts =
            new List<(PredictedConflict, Transform, TextMeshPro)>();
        TextMeshPro clock;
        Diorama dio;
        Vector2d city;

        public void Play(LiveMarginsDto live, Diorama d, Vector2d cityCenter)
        {
            Stop();
            if (live == null || d == null) return;
            dio = d; city = cityCenter;
            Horizon = (float)live.Constants.ForecastHorizonS;
            gameObject.SetActive(true);
            foreach (var kv in live.Drones)
            {
                var traj = kv.Value.Trajectory;
                if (traj == null || traj.Count < 2) continue;
                var root = new GameObject("Ghost " + kv.Key).transform;
                root.SetParent(transform, false);
                Color c = Vocab.StatusColor(Vocab.Status(kv.Value));
                Draw.Prim(PrimitiveType.Sphere, root, Vector3.zero, Vector3.one * 0.02f, Draw.Solid(c), "Ghost");
                Draw.Line(root, Draw.Circle(0.022f, 32), 0.0025f, Palette.Text, loop: true, name: "Halo");
                var id = Draw.Text(root, Vocab.ShortId(kv.Key), 0.011f, Palette.Text, TextAlignmentOptions.Center, new Vector3(0, 0.03f, 0), 0f, FontStyles.Bold);
                id.gameObject.AddComponent<Billboard>();
                var trail = Draw.Line(transform, new Vector3[0], 0.004f, Palette.WithAlpha(c, 0.85f), name: "Trail " + kv.Key);
                ghosts.Add((traj, root, trail, new List<Vector3>()));
            }
            foreach (var c in live.PredictedConflicts)
            {
                if (c.AAt == null || c.BAt == null) continue;
                Vector3 a = Point(c.AAt), b = Point(c.BAt);
                var mark = new GameObject("Conflict").transform;
                mark.SetParent(transform, false);
                mark.localPosition = (a + b) / 2;
                Color col = c.Severity == "CONFLICT" ? Palette.Bad : Palette.Warn;
                Draw.Line(mark, Draw.Circle(0.03f, 40), 0.003f, col, loop: true, name: "Ring");
                Draw.Line(mark, new[] { a - mark.localPosition, b - mark.localPosition }, 0.002f, col, name: "Link");
                var label = Draw.Text(mark, $"{(c.Severity == "CONFLICT" ? "CONFLICT" : "near miss")} · {c.HorizontalM:0} m",
                                      0.011f, col, TextAlignmentOptions.Center, new Vector3(0, 0.045f, 0), 0f, FontStyles.Bold);
                label.gameObject.AddComponent<Billboard>();
                mark.gameObject.SetActive(false);
                conflicts.Add((c, mark, label));
            }
            clock = Draw.Text(transform, "", 0.036f, Palette.Accent, TextAlignmentOptions.Center, new Vector3(0, 0.5f, 0), 0f, FontStyles.Bold);
            clock.gameObject.AddComponent<Billboard>();
            T = 0;
            Playing = true;
        }

        public void Stop()
        {
            Playing = false;
            foreach (Transform c in transform) Destroy(c.gameObject);
            ghosts.Clear();
            conflicts.Clear();
            gameObject.SetActive(false);
        }

        Vector3 Point(double[] p)
        {
            Vector2 en = GeoMath.ToLocal(p[0], p[1], city.x, city.y);
            return dio.Point(en.x, en.y, (float)p[2]);
        }

        void Update()
        {
            if (!Playing) return;
            T += Time.deltaTime * Speed;
            if (T > Horizon + 6) { Stop(); return; }
            float t = Mathf.Min(T, Horizon);
            foreach (var g in ghosts)
            {
                var p = DroneView.AtTime(g.traj, t);
                Vector3 pos = Point(p);
                g.ghost.localPosition = pos;
                if (g.path.Count == 0 || (g.path[g.path.Count - 1] - pos).sqrMagnitude > 1e-6f)
                {
                    g.path.Add(pos);
                    g.trail.positionCount = g.path.Count;
                    g.trail.SetPositions(g.path.ToArray());
                }
            }
            int shown = 0;
            foreach (var c in conflicts)
            {
                // visible from 8 s before the predicted moment until the end of the preview
                bool on = t >= c.c.TS - 8;
                c.mark.gameObject.SetActive(on);
                if (on) { shown++; c.mark.localScale = Vector3.one * (1f + 0.25f * Mathf.Sin(Time.time * 8f)); }
            }
            clock.text = $"FORECAST +{DroneView.Clock(t)}  ·  ×{Speed:0}" + (shown > 0 ? $"  ·  {shown} predicted" : "");
        }
    }
}
