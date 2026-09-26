using System.Collections.Generic;
using AeroFleet.VR.Data;
using AeroFleet.VR.Geo;
using TMPro;
using UnityEngine;

namespace AeroFleet.VR.View
{
    /// <summary>
    /// The static layer of the tabletop: surface, real streets, DGCA zones (exact circle-and-table
    /// prisms — red is the whole column, yellow caps flight at the 60 m airport-vicinity ceiling),
    /// both ceilings, altitude ruler with the real bands, scale bar, north arrow, depots.
    /// Everything is a child of this transform in table-local metres.
    /// </summary>
    public class TableView : MonoBehaviour
    {
        const float ReducedCeilingNearAirportM = 60f;
        static readonly (string name, float floor, float ceiling, Color color)[] Bands =
        {
            ("LOW", 0f, 60f, Palette.BandLow), ("MID", 60f, 80f, Palette.BandMid), ("HIGH", 80f, 100f, Palette.BandHigh),
        };

        Transform content;

        public void Build(Diorama d, Vector2d cityCenter, RoadsDto roads, List<ZoneDto> zones, List<DepotDto> depots,
                          LiveConstants constants, bool showPlinth)
        {
            if (content != null) Destroy(content.gameObject);
            content = new GameObject("TableContent").transform;
            content.SetParent(transform, false);

            BuildSurface(d, showPlinth);
            if (roads != null) BuildStreets(d, cityCenter, roads);
            if (zones != null)
            {
                foreach (var z in zones) if (z.ZoneType == "YELLOW") BuildZone(d, cityCenter, z);
                foreach (var z in zones) if (z.ZoneType == "RED") BuildZone(d, cityCenter, z);
            }
            BuildCeilings(d, (float)constants.OperationalCeilingM, (float)constants.LegalCeilingM);
            BuildRuler(d);
            BuildScaleAndNorth(d);
            if (depots != null) BuildDepots(d, cityCenter, depots);
        }

        // ── surface ────────────────────────────────────────────────────────

        void BuildSurface(Diorama d, bool showPlinth)
        {
            float H = d.TableHalf;
            Draw.Prim(PrimitiveType.Cube, content, new Vector3(0, -0.006f, 0), new Vector3(H * 2, 0.012f, H * 2), Draw.Lit(Palette.Table), "Surface");
            var bezel = Draw.Lit(Palette.Bezel);
            Draw.Prim(PrimitiveType.Cube, content, new Vector3(0, -0.01f, H + 0.02f), new Vector3(H * 2 + 0.08f, 0.028f, 0.04f), bezel, "BezelN");
            Draw.Prim(PrimitiveType.Cube, content, new Vector3(0, -0.01f, -H - 0.02f), new Vector3(H * 2 + 0.08f, 0.028f, 0.04f), bezel, "BezelS");
            Draw.Prim(PrimitiveType.Cube, content, new Vector3(H + 0.02f, -0.01f, 0), new Vector3(0.04f, 0.028f, H * 2), bezel, "BezelE");
            Draw.Prim(PrimitiveType.Cube, content, new Vector3(-H - 0.02f, -0.01f, 0), new Vector3(0.04f, 0.028f, H * 2), bezel, "BezelW");
            if (showPlinth)
                Draw.Prim(PrimitiveType.Cube, content, new Vector3(0, -0.41f, 0), new Vector3(H * 2 + 0.04f, 0.78f, H * 2 + 0.04f), Draw.Lit(Palette.Floor), "Plinth");
            Draw.Line(content, Square(H, 0.0015f), 0.0015f, Palette.TableEdge, loop: true, name: "TableEdge");
        }

        static Vector3[] Square(float h, float y) =>
            new[] { new Vector3(-h, y, -h), new Vector3(h, y, -h), new Vector3(h, y, h), new Vector3(-h, y, h) };

        // ── streets ────────────────────────────────────────────────────────

        void BuildStreets(Diorama d, Vector2d cityCenter, RoadsDto roads)
        {
            // Roads are served relative to their own centre; shift into this diorama's frame.
            Vector2 off = GeoMath.ToLocal(roads.Center[0], roads.Center[1], cityCenter.x, cityCenter.y);
            AddStreetLayer(d, off, roads.Minor, Palette.RoadMinor, 0.0008f, "StreetsMinor");
            AddStreetLayer(d, off, roads.Major, Palette.RoadMajor, 0.0011f, "StreetsMajor");
        }

        void AddStreetLayer(Diorama d, Vector2 off, List<int[]> polylines, Color color, float y, string name)
        {
            if (polylines == null) return;
            var pts = new List<Vector3>();
            float pad = -d.ExtentM * 0.002f;
            foreach (var flat in polylines)
            {
                for (int i = 0; i + 3 < flat.Length; i += 2)
                {
                    float e1 = flat[i] + off.x, n1 = flat[i + 1] + off.y, e2 = flat[i + 2] + off.x, n2 = flat[i + 3] + off.y;
                    if (!d.Contains(e1, n1, pad) || !d.Contains(e2, n2, pad)) continue;
                    pts.Add(new Vector3(d.X(e1), y, d.Z(n1)));
                    pts.Add(new Vector3(d.X(e2), y, d.Z(n2)));
                }
            }
            Draw.MeshObject(name, content, Draw.SegmentMesh(pts, color), Draw.Unlit(Color.white));
        }

        // ── zones ──────────────────────────────────────────────────────────

        void BuildZone(Diorama d, Vector2d cityCenter, ZoneDto zone)
        {
            bool red = zone.ZoneType == "RED";
            Color color = red ? Palette.Bad : Palette.Warn;
            float topM = red ? d.LegalCeilingM : ReducedCeilingNearAirportM;
            Vector2 c = GeoMath.ToLocal(zone.CenterLat, zone.CenterLon, cityCenter.x, cityCenter.y);
            float r = (float)zone.RadiusM * d.Scale, cx = d.X(c.x), cz = d.Z(c.y);

            var circle = new List<Vector2>();
            for (int i = 0; i < 96; i++)
            {
                float a = i / 96f * Mathf.PI * 2f;
                circle.Add(new Vector2(cx + Mathf.Cos(a) * r, cz + Mathf.Sin(a) * r));
            }
            var poly = ClipToSquare(circle, d.TableHalf - 0.0005f);
            if (poly.Count < 3) return;

            float h = d.Y(topM);
            var root = new GameObject(red ? "NoFlyZone" : "PermissionZone").transform;
            root.SetParent(content, false);
            Draw.MeshObject("Volume", root, PrismWalls(poly, h), Draw.Unlit(Palette.WithAlpha(color, red ? 0.09f : 0.03f)));
            Draw.Line(root, Ring(poly, 0.0012f), 0.0016f, color, loop: true, name: "Ground");
            Draw.Line(root, Ring(poly, h), 0.001f, Palette.WithAlpha(color, 0.7f), loop: true, name: "Top");

            // Label at the zone centre when it's on the table; otherwise just inside the table edge
            // facing the centre, so a zone that covers the whole view doesn't label the middle of it.
            float inset = d.TableHalf - 0.09f;
            Vector2 labelAt = new Vector2(Mathf.Clamp(cx, -inset, inset), Mathf.Clamp(cz, -inset, inset));
            string title = red ? "NO-FLY ZONE" : $"PERMISSION ZONE · ceiling {ReducedCeilingNearAirportM:0} m";
            Label(root, new Vector3(labelAt.x, h + 0.022f, labelAt.y), title, 0.011f, color, FontStyles.Bold);
            if (!string.IsNullOrEmpty(zone.Reason))
            {
                string reason = zone.Reason.Length > 48 ? zone.Reason.Substring(0, 46) + "…" : zone.Reason;
                Label(root, new Vector3(labelAt.x, h + 0.008f, labelAt.y), reason, 0.0085f, Palette.TextDim);
            }
        }

        static List<Vector2> ClipToSquare(List<Vector2> poly, float h)
        {
            System.Func<Vector2, bool>[] inside =
            {
                p => p.x >= -h, p => p.x <= h, p => p.y >= -h, p => p.y <= h,
            };
            System.Func<Vector2, Vector2, Vector2>[] cut =
            {
                (a, b) => { float t = (-h - a.x) / (b.x - a.x); return new Vector2(-h, a.y + t * (b.y - a.y)); },
                (a, b) => { float t = (h - a.x) / (b.x - a.x); return new Vector2(h, a.y + t * (b.y - a.y)); },
                (a, b) => { float t = (-h - a.y) / (b.y - a.y); return new Vector2(a.x + t * (b.x - a.x), -h); },
                (a, b) => { float t = (h - a.y) / (b.y - a.y); return new Vector2(a.x + t * (b.x - a.x), h); },
            };
            var output = poly;
            for (int e = 0; e < 4; e++)
            {
                var input = output;
                output = new List<Vector2>();
                for (int i = 0; i < input.Count; i++)
                {
                    Vector2 cur = input[i], prev = input[(i + input.Count - 1) % input.Count];
                    if (inside[e](cur))
                    {
                        if (!inside[e](prev)) output.Add(cut[e](prev, cur));
                        output.Add(cur);
                    }
                    else if (inside[e](prev)) output.Add(cut[e](prev, cur));
                }
                if (output.Count == 0) break;
            }
            return output;
        }

        static Mesh PrismWalls(List<Vector2> poly, float h)
        {
            var v = new List<Vector3>();
            var tri = new List<int>();
            for (int i = 0; i < poly.Count; i++)
            {
                Vector2 a = poly[i], b = poly[(i + 1) % poly.Count];
                int k = v.Count;
                v.Add(new Vector3(a.x, 0, a.y)); v.Add(new Vector3(b.x, 0, b.y));
                v.Add(new Vector3(b.x, h, b.y)); v.Add(new Vector3(a.x, h, a.y));
                // both windings: the volume is seen from inside and outside
                tri.AddRange(new[] { k, k + 1, k + 2, k, k + 2, k + 3, k, k + 2, k + 1, k, k + 3, k + 2 });
            }
            var m = new Mesh();
            m.SetVertices(v);
            m.SetTriangles(tri, 0);
            m.RecalculateBounds();
            return m;
        }

        static Vector3[] Ring(List<Vector2> poly, float y)
        {
            var pts = new Vector3[poly.Count];
            for (int i = 0; i < poly.Count; i++) pts[i] = new Vector3(poly[i].x, y, poly[i].y);
            return pts;
        }

        // ── ceilings, ruler, scale, north ─────────────────────────────────

        void BuildCeilings(Diorama d, float opsM, float legalM)
        {
            float H = d.TableHalf;
            foreach (var (m, label, color, alpha) in new[]
            {
                (opsM, $"AeroFleet ops ceiling · {opsM:0} m", Palette.Accent, 0.018f),
                (legalM, $"DGCA legal limit · {legalM:0} m AGL", Palette.Bad, 0.0f),
            })
            {
                float y = d.Y(m);
                if (alpha > 0) // the legal limit is an outline only — two tinted planes wash out the map
                {
                    var q = Draw.Prim(PrimitiveType.Quad, content, new Vector3(0, y, 0), new Vector3(H * 2, H * 2, 1), Draw.Unlit(Palette.WithAlpha(color, alpha)), "Ceiling");
                    q.transform.localRotation = Quaternion.Euler(90, 0, 0);
                }
                Draw.Line(content, Square(H, y), 0.0012f, Palette.WithAlpha(color, 0.55f), loop: true, name: "CeilingEdge");
                Label(content, new Vector3(H - 0.01f, y + 0.012f, -H), label, 0.0095f, color, FontStyles.Normal, TextAlignmentOptions.Right);
            }
        }

        void BuildRuler(Diorama d)
        {
            float H = d.TableHalf;
            var ruler = new GameObject("AltitudeRuler").transform;
            ruler.SetParent(content, false);
            ruler.localPosition = new Vector3(-H - 0.055f, 0, -H);
            foreach (var b in Bands)
                Draw.Prim(PrimitiveType.Cube, ruler, new Vector3(0, (d.Y(b.floor) + d.Y(b.ceiling)) / 2, 0),
                          new Vector3(0.006f, d.Y(b.ceiling) - d.Y(b.floor), 0.006f), Draw.Unlit(b.color), b.name);
            Draw.Prim(PrimitiveType.Cube, ruler, new Vector3(0, (d.Y(100) + d.Y(120)) / 2, 0),
                      new Vector3(0.004f, d.Y(120) - d.Y(100), 0.004f), Draw.Unlit(Palette.TextFaint), "Reserve100to120");
            foreach (float m in new[] { 0f, 60f, 80f, 100f, 120f })
            {
                Draw.Prim(PrimitiveType.Cube, ruler, new Vector3(0, d.Y(m), 0), new Vector3(0.018f, 0.0012f, 0.0012f), Draw.Unlit(Palette.Text), "Tick");
                Label(ruler, new Vector3(-0.014f, d.Y(m), 0), $"{m:0} m", 0.008f, Palette.TextDim, FontStyles.Normal, TextAlignmentOptions.Right);
            }
            foreach (var b in Bands)
                Label(ruler, new Vector3(0.016f, (d.Y(b.floor) + d.Y(b.ceiling)) / 2, 0), b.name, 0.008f, b.color, FontStyles.Bold, TextAlignmentOptions.Left);
            Label(ruler, new Vector3(0, -0.02f, 0), $"vertical ×{d.VExag:0}", 0.0075f, Palette.TextFaint);
        }

        void BuildScaleAndNorth(Diorama d)
        {
            float H = d.TableHalf;
            float barM = GeoMath.NiceScaleBar(d.ExtentM);
            float barW = barM * d.Scale;
            var bar = new GameObject("ScaleBar").transform;
            bar.SetParent(content, false);
            bar.localPosition = new Vector3(H - 0.04f - barW, 0.002f, -H - 0.06f);
            var white = Draw.Unlit(Palette.Text);
            Draw.Prim(PrimitiveType.Cube, bar, new Vector3(barW / 2, 0, 0), new Vector3(barW, 0.002f, 0.004f), white);
            Draw.Prim(PrimitiveType.Cube, bar, new Vector3(0, 0.004f, 0), new Vector3(0.0015f, 0.01f, 0.004f), white);
            Draw.Prim(PrimitiveType.Cube, bar, new Vector3(barW, 0.004f, 0), new Vector3(0.0015f, 0.01f, 0.004f), white);
            Label(bar, new Vector3(barW / 2, 0.018f, 0), GeoMath.FormatDistance(barM), 0.0095f, Palette.Text);

            var north = new GameObject("North").transform;
            north.SetParent(content, false);
            north.localPosition = new Vector3(0, 0.004f, H + 0.06f);
            Draw.Prim(PrimitiveType.Cube, north, Vector3.zero, new Vector3(0.012f, 0.004f, 0.03f), Draw.Unlit(Palette.Accent), "Arrow");
            Label(north, new Vector3(0, 0.022f, 0), "N", 0.016f, Palette.Accent, FontStyles.Bold);
        }

        void BuildDepots(Diorama d, Vector2d cityCenter, List<DepotDto> depots)
        {
            foreach (var p in depots)
            {
                if (p.Lat == null || p.Lon == null) continue;
                Vector2 en = GeoMath.ToLocal(p.Lat.Value, p.Lon.Value, cityCenter.x, cityCenter.y);
                if (!d.Contains(en.x, en.y)) continue;
                var pad = new GameObject(p.DepotId).transform;
                pad.SetParent(content, false);
                pad.localPosition = d.Point(en.x, en.y);
                Draw.Prim(PrimitiveType.Cylinder, pad, new Vector3(0, 0.002f, 0), new Vector3(0.022f, 0.002f, 0.022f), Draw.Unlit(Palette.Depot), "Pad");
                Label(pad, new Vector3(0, 0.018f, 0), p.Name.Replace("Micro-Depot", "Depot"), 0.0085f, Palette.Depot);
            }
        }

        static void Label(Transform parent, Vector3 pos, string text, float height, Color color,
                          FontStyles style = FontStyles.Normal, TextAlignmentOptions align = TextAlignmentOptions.Center)
        {
            var t = Draw.Text(parent, text, height, color, align, pos, 0f, style);
            t.gameObject.AddComponent<Billboard>();
        }
    }

    /// <summary>Double-precision lat/lon pair (Unity's Vector2 is float — too coarse for degrees).</summary>
    public struct Vector2d
    {
        public double x, y;
        public Vector2d(double x, double y) { this.x = x; this.y = y; }
    }
}
