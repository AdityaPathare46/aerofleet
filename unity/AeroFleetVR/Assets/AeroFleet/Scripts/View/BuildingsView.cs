using System.Collections.Generic;
using AeroFleet.VR.Data;
using AeroFleet.VR.Geo;
using UnityEngine;

namespace AeroFleet.VR.View
{
    /// <summary>
    /// The real city in 3D: OpenStreetMap footprints extruded to their heights, on the same vertical
    /// scale as the drones — so a drone's cruise altitude reads directly against the towers under it.
    /// Heights tagged in OSM (height, or storeys) are drawn light; untagged buildings use the stated
    /// assumed height and are drawn dark, so the viewer never mistakes an assumption for a survey.
    /// </summary>
    public class BuildingsView : MonoBehaviour
    {
        static readonly Color MeasuredWall = Palette.Hex("5C7394"), MeasuredRoof = Palette.Hex("A9BCD6");
        static readonly Color AssumedWall = Palette.Hex("1F2C40"), AssumedRoof = Palette.Hex("2D3D55");

        public int Drawn { get; private set; }
        public int DrawnMeasured { get; private set; }

        public void Build(Diorama d, Vector2d cityCenter, BuildingsDto data)
        {
            foreach (Transform c in transform) Destroy(c.gameObject);
            Drawn = DrawnMeasured = 0;
            if (data == null || !data.Available || data.Buildings.Count == 0) return;

            Vector2 off = GeoMath.ToLocal(data.Center[0], data.Center[1], cityCenter.x, cityCenter.y);
            int assumedIdx = data.Sources.IndexOf("assumed");
            var measured = new MeshBuilder();
            var assumed = new MeshBuilder();
            var ring = new List<Vector2>();

            foreach (var b in data.Buildings)
            {
                if (b.Length < 8) continue;
                ring.Clear();
                bool inside = true;
                for (int i = 2; i + 1 < b.Length; i += 2)
                {
                    float e = b[i] + off.x, n = b[i + 1] + off.y;
                    if (!d.Contains(e, n)) { inside = false; break; }
                    ring.Add(new Vector2(d.X(e), d.Z(n)));
                }
                if (!inside) continue;
                bool isAssumed = b[1] == assumedIdx;
                (isAssumed ? assumed : measured).AddPrism(ring, d.Y(b[0] / 10f));
                Drawn++;
                if (!isAssumed) DrawnMeasured++;
            }
            assumed.Emit(transform, "AssumedHeight", AssumedWall, AssumedRoof);
            measured.Emit(transform, "MeasuredHeight", MeasuredWall, MeasuredRoof);
        }

        /// <summary>Accumulates prisms into meshes (walls and roofs as two submeshes), split at 60k vertices.</summary>
        class MeshBuilder
        {
            readonly List<(List<Vector3> v, List<int> walls, List<int> roofs)> chunks = new List<(List<Vector3>, List<int>, List<int>)>();
            List<Vector3> v;
            List<int> walls, roofs;
            readonly List<int> tri = new List<int>();

            public void AddPrism(List<Vector2> ring, float h)
            {
                if (v == null || v.Count > 60000) { v = new List<Vector3>(); walls = new List<int>(); roofs = new List<int>(); chunks.Add((v, walls, roofs)); }
                int n = ring.Count;
                float area = 0;
                for (int i = 0; i < n; i++) area += ring[i].x * ring[(i + 1) % n].y - ring[(i + 1) % n].x * ring[i].y;
                bool ccw = area > 0; // counter-clockwise in (x, z) seen from above

                // walls: one quad per edge, own vertices so edges stay crisp
                for (int i = 0; i < n; i++)
                {
                    Vector2 a = ring[i], c = ring[(i + 1) % n];
                    Vector3 outward = ccw ? new Vector3(c.y - a.y, 0, -(c.x - a.x)) : new Vector3(-(c.y - a.y), 0, c.x - a.x);
                    int k = v.Count;
                    v.Add(new Vector3(a.x, 0, a.y)); v.Add(new Vector3(c.x, 0, c.y));
                    v.Add(new Vector3(c.x, h, c.y)); v.Add(new Vector3(a.x, h, a.y));
                    AddTri(walls, k, k + 1, k + 2, outward);
                    AddTri(walls, k, k + 2, k + 3, outward);
                }

                // roof
                int r = v.Count;
                for (int i = 0; i < n; i++) v.Add(new Vector3(ring[i].x, h, ring[i].y));
                tri.Clear();
                if (!EarClip(ring, ccw, tri))
                {
                    tri.Clear();
                    for (int i = 1; i + 1 < n; i++) { tri.Add(0); tri.Add(i); tri.Add(i + 1); }
                }
                for (int i = 0; i < tri.Count; i += 3) AddTri(roofs, r + tri[i], r + tri[i + 1], r + tri[i + 2], Vector3.up);
            }

            // Unity front faces are those whose Cross(b-a, c-a) points at the viewer.
            void AddTri(List<int> into, int a, int b, int c, Vector3 facing)
            {
                if (Vector3.Dot(Vector3.Cross(v[b] - v[a], v[c] - v[a]), facing) < 0) { int t = b; b = c; c = t; }
                into.Add(a); into.Add(b); into.Add(c);
            }

            static bool EarClip(List<Vector2> p, bool ccw, List<int> outTri)
            {
                var idx = new List<int>();
                for (int i = 0; i < p.Count; i++) idx.Add(i);
                int guard = p.Count * p.Count;
                while (idx.Count > 3 && guard-- > 0)
                {
                    bool clipped = false;
                    for (int i = 0; i < idx.Count; i++)
                    {
                        int ia = idx[(i + idx.Count - 1) % idx.Count], ib = idx[i], ic = idx[(i + 1) % idx.Count];
                        Vector2 a = p[ia], b = p[ib], c = p[ic];
                        float cross = (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
                        if (ccw ? cross <= 0 : cross >= 0) continue; // reflex vertex
                        bool contains = false;
                        foreach (int j in idx)
                        {
                            if (j == ia || j == ib || j == ic) continue;
                            if (InTriangle(p[j], a, b, c)) { contains = true; break; }
                        }
                        if (contains) continue;
                        outTri.Add(ia); outTri.Add(ib); outTri.Add(ic);
                        idx.RemoveAt(i);
                        clipped = true;
                        break;
                    }
                    if (!clipped) return false;
                }
                if (idx.Count == 3) { outTri.Add(idx[0]); outTri.Add(idx[1]); outTri.Add(idx[2]); }
                return true;
            }

            static bool InTriangle(Vector2 p, Vector2 a, Vector2 b, Vector2 c)
            {
                float d1 = (p.x - b.x) * (a.y - b.y) - (a.x - b.x) * (p.y - b.y);
                float d2 = (p.x - c.x) * (b.y - c.y) - (b.x - c.x) * (p.y - c.y);
                float d3 = (p.x - a.x) * (c.y - a.y) - (c.x - a.x) * (p.y - a.y);
                bool neg = d1 < 0 || d2 < 0 || d3 < 0, pos = d1 > 0 || d2 > 0 || d3 > 0;
                return !(neg && pos);
            }

            public void Emit(Transform parent, string name, Color wall, Color roof)
            {
                for (int i = 0; i < chunks.Count; i++)
                {
                    var (cv, cw, cr) = chunks[i];
                    if (cv.Count == 0) continue;
                    var mesh = new Mesh { indexFormat = UnityEngine.Rendering.IndexFormat.UInt32, subMeshCount = 2 };
                    mesh.SetVertices(cv);
                    mesh.SetTriangles(cw, 0);
                    mesh.SetTriangles(cr, 1);
                    mesh.RecalculateNormals();
                    mesh.RecalculateBounds();
                    var go = Draw.MeshObject($"{name} {i}", parent, mesh, Draw.Lit(wall));
                    go.GetComponent<MeshRenderer>().sharedMaterials = new[] { Draw.Lit(wall), Draw.Lit(roof) };
                }
            }
        }
    }
}
