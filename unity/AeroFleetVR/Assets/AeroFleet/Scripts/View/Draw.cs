using System.Collections.Generic;
using TMPro;
using UnityEngine;

namespace AeroFleet.VR.View
{
    /// <summary>Same night-ops palette as the web VR view (tauri-app/src/components/vr/theme.ts).</summary>
    public static class Palette
    {
        public static readonly Color Void = Hex("050A13");
        public static readonly Color Floor = Hex("08101C");
        public static readonly Color Table = Hex("0B1626");
        public static readonly Color TableEdge = Hex("1D3858");
        public static readonly Color Bezel = Hex("132740");
        public static readonly Color RoadMajor = Hex("4D7CB3");
        public static readonly Color RoadMinor = Hex("1E3656");
        public static readonly Color Text = Hex("EAF1FA");
        public static readonly Color TextDim = Hex("93A8C4");
        public static readonly Color TextFaint = Hex("5E7493");
        public static readonly Color Accent = Hex("86B7F2");
        public static readonly Color Panel = Hex("0A1526");
        public static readonly Color PanelEdge = Hex("2A507E");
        public static readonly Color Ok = Hex("2ED47A");
        public static readonly Color Warn = Hex("F5A524");
        public static readonly Color Bad = Hex("F0484B");
        public static readonly Color Neutral = Hex("94A3B8");
        public static readonly Color Depot = Hex("86B7F2");
        public static readonly Color BandLow = Hex("3B82F6");
        public static readonly Color BandMid = Hex("8B5CF6");
        public static readonly Color BandHigh = Hex("EC4899");

        public static Color Hex(string hex)
        {
            ColorUtility.TryParseHtmlString("#" + hex, out var c);
            return c;
        }

        public static Color WithAlpha(Color c, float a) => new Color(c.r, c.g, c.b, a);
    }

    public static class Draw
    {
        static AeroFleetTheme theme;
        static readonly Dictionary<Color, Material> litCache = new Dictionary<Color, Material>();
        static readonly Dictionary<Color, Material> unlitCache = new Dictionary<Color, Material>();
        static readonly Dictionary<Color, Material> solidCache = new Dictionary<Color, Material>();

        // Material assets live in Resources so their shaders ship in builds (Shader.Find alone can
        // strip them). Created by AeroFleet ▸ Setup ▸ 1. Create Theme & Materials.
        public static AeroFleetTheme Theme
        {
            get
            {
                if (theme == null) theme = Resources.Load<AeroFleetTheme>("AeroFleetTheme");
                if (theme == null) Debug.LogError("[AeroFleet] Missing Resources/AeroFleetTheme — run AeroFleet ▸ Setup ▸ 1. Create Theme & Materials.");
                return theme;
            }
        }

        public static Material Lit(Color c)
        {
            if (litCache.TryGetValue(c, out var m) && m != null) return m;
            m = new Material(Theme.lit);
            m.SetColor("_BaseColor", c);
            litCache[c] = m;
            return m;
        }

        public static Material Unlit(Color c)
        {
            if (unlitCache.TryGetValue(c, out var m) && m != null) return m;
            m = new Material(Theme.unlit) { color = c };
            unlitCache[c] = m;
            return m;
        }

        public static Material Solid(Color c)
        {
            if (solidCache.TryGetValue(c, out var m) && m != null) return m;
            m = new Material(Theme.solid);
            m.SetColor("_BaseColor", c);
            solidCache[c] = m;
            return m;
        }

        public static GameObject Prim(PrimitiveType type, Transform parent, Vector3 localPos, Vector3 scale, Material mat, string name = null)
        {
            var go = GameObject.CreatePrimitive(type);
            if (name != null) go.name = name;
            Object.Destroy(go.GetComponent<Collider>());
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            go.transform.localScale = scale;
            go.GetComponent<Renderer>().sharedMaterial = mat;
            return go;
        }

        public static GameObject MeshObject(string name, Transform parent, Mesh mesh, Material mat)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            go.AddComponent<MeshRenderer>().sharedMaterial = mat;
            return go;
        }

        // Measured in play mode (LiberationSans SDF): fontSize F gives a line height of 0.115·F m and
        // a cap height of 0.077·F m. `heightM` below is therefore ~0.87 of the line height.
        public const float TmpUnitsPerPoint = 0.1f;

        public static TextMeshPro Text(Transform parent, string text, float heightM, Color color,
                                       TextAlignmentOptions align = TextAlignmentOptions.Center,
                                       Vector3 localPos = default, float wrapWidthM = 0f, FontStyles style = FontStyles.Normal)
        {
            var go = new GameObject("Text");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            var t = go.AddComponent<TextMeshPro>();
            if (Theme != null && Theme.font != null) t.font = Theme.font;
            t.text = text;
            t.fontSize = heightM / TmpUnitsPerPoint;
            t.color = color;
            t.alignment = align;
            // Anchor the rect on the side the text is aligned to, so `localPos` is where the text
            // starts (left), ends (right) or is centred — not the middle of a 2 m wide box.
            int horizontal = (int)align & 0xFF; // TMP: Left = 1, Center = 2, Right = 4
            t.rectTransform.pivot = new Vector2(horizontal == 1 ? 0f : horizontal == 4 ? 1f : 0.5f, 0.5f);
            t.fontStyle = style;
            t.textWrappingMode = wrapWidthM > 0 ? TextWrappingModes.Normal : TextWrappingModes.NoWrap;
            t.rectTransform.sizeDelta = new Vector2(wrapWidthM > 0 ? wrapWidthM : 2f, heightM * 1.5f);
            t.overflowMode = TextOverflowModes.Overflow;
            t.outlineWidth = 0.18f;
            t.outlineColor = Palette.Void;
            return t;
        }

        public static LineRenderer Line(Transform parent, IList<Vector3> localPoints, float width, Color color, bool loop = false, string name = "Line")
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            var lr = go.AddComponent<LineRenderer>();
            lr.useWorldSpace = false;
            lr.loop = loop;
            lr.widthMultiplier = width;
            lr.sharedMaterial = Unlit(Color.white);
            lr.startColor = lr.endColor = color;
            lr.numCapVertices = 2;
            lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            lr.receiveShadows = false;
            lr.positionCount = localPoints.Count;
            for (int i = 0; i < localPoints.Count; i++) lr.SetPosition(i, localPoints[i]);
            return lr;
        }

        /// <summary>Many 1-px segments in one draw call (streets, loose separation links).</summary>
        public static Mesh SegmentMesh(List<Vector3> pairs, Color color)
        {
            var mesh = new Mesh { indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 };
            mesh.SetVertices(pairs);
            var colors = new Color[pairs.Count];
            for (int i = 0; i < colors.Length; i++) colors[i] = color;
            mesh.colors = colors;
            var idx = new int[pairs.Count];
            for (int i = 0; i < idx.Length; i++) idx[i] = i;
            mesh.SetIndices(idx, MeshTopology.Lines, 0);
            mesh.RecalculateBounds();
            return mesh;
        }

        public static Vector3[] Circle(float radius, int segments, float y = 0f)
        {
            var pts = new Vector3[segments];
            for (int i = 0; i < segments; i++)
            {
                float a = i / (float)segments * Mathf.PI * 2f;
                pts[i] = new Vector3(Mathf.Cos(a) * radius, y, Mathf.Sin(a) * radius);
            }
            return pts;
        }
    }
}
