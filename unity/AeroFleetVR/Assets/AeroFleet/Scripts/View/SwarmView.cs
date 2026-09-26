using System;
using System.Collections.Generic;
using AeroFleet.VR.Data;
using AeroFleet.VR.Geo;
using TMPro;
using UnityEngine;

namespace AeroFleet.VR.View
{
    /// <summary>
    /// All airborne drones plus the separation picture between them. Pairs inside the watch band
    /// (min separation + 35 m) get a solid beam and a distance label — amber when close, red when
    /// below the minimum; every other pair within the 250 m awareness radius gets a faint link.
    /// Beams follow the eased drone positions every frame, not the raw poll.
    /// Predicted conflicts (the backend's look-ahead over planned trajectories) are drawn where they
    /// will happen: a ring at each drone's predicted position, a link, and "in 42 s" — and both
    /// drones' trajectories and tags are expanded so the operator sees the two paths converge.
    /// </summary>
    public class SwarmView : MonoBehaviour
    {
        public Action<string> OnSelect;

        readonly Dictionary<string, DroneView> drones = new Dictionary<string, DroneView>();
        readonly List<(DronePair pair, LineRenderer beam, TextMeshPro label)> beams = new List<(DronePair, LineRenderer, TextMeshPro)>();
        List<DronePair> loose = new List<DronePair>();
        readonly List<(Transform root, LineRenderer link, LineRenderer ringA, LineRenderer ringB, TextMeshPro label)> forecasts =
            new List<(Transform, LineRenderer, LineRenderer, LineRenderer, TextMeshPro)>();
        Mesh looseMesh;

        void Awake()
        {
            looseMesh = new Mesh();
            looseMesh.MarkDynamic();
            Draw.MeshObject("AwarenessLinks", transform, looseMesh, Draw.Unlit(Color.white));
        }

        public void Clear()
        {
            foreach (var d in drones.Values) Destroy(d.gameObject);
            drones.Clear();
            SetPairs(new List<DronePair>(), 15);
            SetForecast(new List<PredictedConflict>(), null, default);
        }

        public void Apply(LiveMarginsDto data, Diorama dio, Vector2d cityCenter, string selected, bool detailAll)
        {
            var seen = new HashSet<string>();
            var inConflict = new HashSet<string>();
            foreach (var c in data.PredictedConflicts)
                if (c.Severity == "CONFLICT") { inConflict.Add(c.A); inConflict.Add(c.B); }
            foreach (var kv in data.Drones)
            {
                Vector2 en = GeoMath.ToLocal(kv.Value.Lat, kv.Value.Lon, cityCenter.x, cityCenter.y);
                if (!dio.Contains(en.x, en.y, dio.ExtentM * 0.02f)) continue;
                seen.Add(kv.Key);
                if (!drones.TryGetValue(kv.Key, out var view))
                {
                    view = DroneView.Create(transform, kv.Key);
                    view.OnSelect = id => OnSelect?.Invoke(id);
                    drones[kv.Key] = view;
                }
                bool expanded = detailAll || selected == kv.Key || Vocab.Status(kv.Value) != DroneStatus.Ok || inConflict.Contains(kv.Key);
                view.Apply(kv.Value, dio, cityCenter, data.Constants, selected == kv.Key, expanded);
            }
            var gone = new List<string>();
            foreach (var id in drones.Keys) if (!seen.Contains(id)) gone.Add(id);
            foreach (var id in gone) { Destroy(drones[id].gameObject); drones.Remove(id); }

            StackTags();
            var visible = data.Pairs.FindAll(p => drones.ContainsKey(p.A) && drones.ContainsKey(p.B));
            SetPairs(visible, data.Constants.MinSeparationM);
            SetForecast(data.PredictedConflicts.FindAll(c => drones.ContainsKey(c.A) && drones.ContainsKey(c.B)
                && OnTable(dio, cityCenter, c.AAt) && OnTable(dio, cityCenter, c.BAt)), dio, cityCenter);
        }

        /// <summary>Drones close together on the table would have overlapping tags: lift each tag above
        /// the tags of nearer-to-the-table neighbours within reach, so every card stays readable.</summary>
        void StackTags()
        {
            const float reach = 0.09f; // metres on the table, about a card's width
            var list = new List<DroneView>(drones.Values);
            list.Sort((x, y) => string.CompareOrdinal(x.Id, y.Id));
            var lifts = new Dictionary<DroneView, float>();
            foreach (var d in list)
            {
                float lift = 0f;
                Vector3 p = d.transform.localPosition;
                foreach (var kv in lifts)
                {
                    Vector3 q = kv.Key.transform.localPosition;
                    if (new Vector2(p.x - q.x, p.z - q.z).magnitude < reach)
                        lift = Mathf.Max(lift, (q.y - p.y) + kv.Value + kv.Key.TagHeight + 0.006f);
                }
                lifts[d] = Mathf.Max(lift, 0f);
                d.SetTagLift(lifts[d]);
            }
        }

        void SetForecast(List<PredictedConflict> list, Diorama dio, Vector2d city)
        {
            while (forecasts.Count > list.Count)
            {
                Destroy(forecasts[forecasts.Count - 1].root.gameObject);
                forecasts.RemoveAt(forecasts.Count - 1);
            }
            for (int i = 0; i < list.Count; i++)
            {
                var c = list[i];
                bool conflict = c.Severity == "CONFLICT";
                Color col = conflict ? Palette.Bad : Palette.Warn;
                if (i >= forecasts.Count)
                {
                    var root = new GameObject("PredictedConflict").transform;
                    root.SetParent(transform, false);
                    var link = Draw.Line(root, new Vector3[2], 0.0012f, col, name: "Link");
                    var ra = Draw.Line(root, Draw.Circle(0.009f, 28), 0.0014f, col, loop: true, name: "RingA");
                    var rb = Draw.Line(root, Draw.Circle(0.009f, 28), 0.0014f, col, loop: true, name: "RingB");
                    var t = Draw.Text(root, "", 0.0068f, col);
                    t.gameObject.AddComponent<Billboard>();
                    forecasts.Add((root, link, ra, rb, t));
                }
                var (_, l, ringA, ringB, label) = forecasts[i];
                Vector3 pa = At(dio, city, c.AAt), pb = At(dio, city, c.BAt);
                l.SetPosition(0, pa);
                l.SetPosition(1, pb);
                ringA.transform.localPosition = pa;
                ringB.transform.localPosition = pb;
                foreach (var lr in new[] { l, ringA, ringB }) lr.startColor = lr.endColor = col;
                label.color = col;
                // below the rings: the space above is where the drones' tags are
                label.transform.localPosition = (pa + pb) / 2 - Vector3.up * 0.014f;
                label.text = (conflict ? "PREDICTED CONFLICT" : "near miss") +
                             $" in {DroneView.Clock(c.TS)}\n{c.HorizontalM:0} m ↔   ↕{c.VerticalM:0} m";
            }
        }

        static bool OnTable(Diorama dio, Vector2d city, double[] p)
        {
            Vector2 en = GeoMath.ToLocal(p[0], p[1], city.x, city.y);
            return dio.Contains(en.x, en.y);
        }

        static Vector3 At(Diorama dio, Vector2d city, double[] p)
        {
            Vector2 en = GeoMath.ToLocal(p[0], p[1], city.x, city.y);
            return dio.Point(en.x, en.y, (float)p[2]);
        }

        void SetPairs(List<DronePair> pairs, double minSep)
        {
            double band = Vocab.WarnBands["min_separation"];
            var close = pairs.FindAll(p => p.SeparationMarginM < band);
            loose = pairs.FindAll(p => p.SeparationMarginM >= band);

            while (beams.Count > close.Count)
            {
                var b = beams[beams.Count - 1];
                Destroy(b.beam.gameObject);
                Destroy(b.label.gameObject);
                beams.RemoveAt(beams.Count - 1);
            }
            for (int i = 0; i < close.Count; i++)
            {
                var p = close[i];
                bool critical = p.SeparationMarginM < 0;
                Color c = critical ? Palette.Bad : Palette.Warn;
                if (i >= beams.Count)
                {
                    var lr = Draw.Line(transform, new[] { Vector3.zero, Vector3.zero }, 0.0016f, c, name: "PairBeam");
                    var t = Draw.Text(transform, "", 0.0068f, c);
                    t.gameObject.AddComponent<Billboard>();
                    beams.Add((p, lr, t));
                }
                var (_, beam, label) = beams[i];
                beams[i] = (p, beam, label);
                beam.startColor = beam.endColor = c;
                beam.widthMultiplier = critical ? 0.0024f : 0.0016f;
                label.color = c;
                label.text = $"{p.HorizontalM:0} m ↔   ↕{p.VerticalM:0} m" + (critical ? $"   < {minSep:0} m min" : "");
            }
        }

        void LateUpdate()
        {
            foreach (var (pair, beam, label) in beams)
            {
                if (!drones.TryGetValue(pair.A, out var a) || !drones.TryGetValue(pair.B, out var b)) continue;
                Vector3 pa = a.transform.localPosition, pb = b.transform.localPosition;
                beam.SetPosition(0, pa);
                beam.SetPosition(1, pb);
                label.transform.localPosition = (pa + pb) / 2 + Vector3.up * 0.012f;
            }

            var verts = new List<Vector3>(loose.Count * 2);
            foreach (var p in loose)
            {
                if (!drones.TryGetValue(p.A, out var a) || !drones.TryGetValue(p.B, out var b)) continue;
                verts.Add(a.transform.localPosition);
                verts.Add(b.transform.localPosition);
            }
            looseMesh.Clear();
            looseMesh.SetVertices(verts);
            var colors = new Color[verts.Count];
            for (int i = 0; i < colors.Length; i++) colors[i] = Palette.WithAlpha(Palette.Accent, 0.35f);
            looseMesh.colors = colors;
            var idx = new int[verts.Count];
            for (int i = 0; i < idx.Length; i++) idx[i] = i;
            looseMesh.SetIndices(idx, MeshTopology.Lines, 0);
            looseMesh.RecalculateBounds();
        }

        public int VisibleCount => drones.Count;
    }
}
