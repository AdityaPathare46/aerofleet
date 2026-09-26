using TMPro;
using UnityEngine;

namespace AeroFleet.VR.View
{
    /// <summary>
    /// A standing world-space board. Content is placed in metres from the top-left corner
    /// (x right, y down) so layouts read like the HTML boards they mirror.
    /// Text is readable from the panel's −z side; orient with <see cref="Face"/>.
    /// </summary>
    public class Panel : MonoBehaviour
    {
        public const float Front = -0.002f;
        public float W { get; private set; }
        public float H { get; private set; }
        Transform bg;
        LineRenderer edge;

        public static Panel Create(Transform parent, string name, float width, float height)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            var p = go.AddComponent<Panel>();
            p.bg = Draw.Prim(PrimitiveType.Quad, go.transform, Vector3.zero, Vector3.one, Draw.Solid(Palette.Panel), "Background").transform;
            p.edge = Draw.Line(go.transform, new Vector3[4], 0.003f, Palette.PanelEdge, loop: true, name: "Edge");
            p.Resize(width, height);
            return p;
        }

        public void Resize(float width, float height)
        {
            W = width; H = height;
            bg.localScale = new Vector3(W, H, 1);
            edge.SetPositions(new[]
            {
                new Vector3(-W / 2, H / 2, Front / 2), new Vector3(W / 2, H / 2, Front / 2),
                new Vector3(W / 2, -H / 2, Front / 2), new Vector3(-W / 2, -H / 2, Front / 2),
            });
        }

        /// <summary>Stand the board at `worldPos` turned toward `viewer` (upright, no tilt).</summary>
        public void Face(Vector3 worldPos, Vector3 viewer)
        {
            transform.position = worldPos;
            Vector3 d = worldPos - viewer;
            d.y = 0;
            if (d.sqrMagnitude > 1e-6f) transform.rotation = Quaternion.LookRotation(d, Vector3.up);
        }

        public Vector3 At(float x, float y, float z = Front) => new Vector3(-W / 2 + x, H / 2 - y, z);

        public TextMeshPro Text(string text, float x, float y, float h, Color color,
                                TextAlignmentOptions align = TextAlignmentOptions.Left, float wrapW = 0f,
                                FontStyles style = FontStyles.Normal)
        {
            var t = Draw.Text(transform, text, h, color, align, At(x, y), wrapW, style);
            float px = align == TextAlignmentOptions.Right || align == TextAlignmentOptions.TopRight ? 1f
                : align == TextAlignmentOptions.Center || align == TextAlignmentOptions.Top ? 0.5f : 0f;
            t.rectTransform.pivot = new Vector2(px, wrapW > 0 ? 1f : 0.5f);
            if (wrapW > 0)
            {
                t.alignment = TextAlignmentOptions.TopLeft;
                t.rectTransform.sizeDelta = new Vector2(wrapW, h * 12);
            }
            return t;
        }

        public Transform Rect(float x, float y, float w, float h, Color color, string name = "Rect", float z = Front / 2)
        {
            var q = Draw.Prim(PrimitiveType.Quad, transform, At(x + w / 2, y + h / 2, z), new Vector3(w, h, 1), Draw.Solid(color), name).transform;
            return q;
        }

        public Button3D Button(string label, float x, float y, float w, float h, System.Action onClick)
        {
            var b = Button3D.Create(transform, At(x + w / 2, y + h / 2, Front / 2), new Vector2(w, h), label, onClick);
            return b;
        }
    }
}
