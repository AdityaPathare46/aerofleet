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
    /// </summary>
    public class SwarmView : MonoBehaviour
    {
        public Action<string> OnSelect;

        readonly Dictionary<string, DroneView> drones = new Dictionary<string, DroneView>();
        readonly List<(DronePair pair, LineRenderer beam, TextMeshPro label)> beams = new List<(DronePair, LineRenderer, TextMeshPro)>();
        List<DronePair> loose = new List<DronePair>();
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
        }

        public void Apply(LiveMarginsDto data, Diorama dio, Vector2d cityCenter, string selected, bool detailAll)
        {
            var seen = new HashSet<string>();
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
                bool expanded = detailAll || selected == kv.Key || Vocab.Status(kv.Value) != DroneStatus.Ok;
                view.Apply(kv.Value, dio, cityCenter, data.Constants, selected == kv.Key, expanded);
            }
            var gone = new List<string>();
            foreach (var id in drones.Keys) if (!seen.Contains(id)) gone.Add(id);
            foreach (var id in gone) { Destroy(drones[id].gameObject); drones.Remove(id); }

            var visible = data.Pairs.FindAll(p => drones.ContainsKey(p.A) && drones.ContainsKey(p.B));
            SetPairs(visible, data.Constants.MinSeparationM);
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
