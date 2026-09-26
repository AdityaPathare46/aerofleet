using System.Collections.Generic;
using TMPro;
using UnityEngine;

namespace AeroFleet.VR.View
{
    /// <summary>One labelled line of a tag. A bar is optional; `mark` draws the limit tick on it.</summary>
    public struct TagRow
    {
        public string Label, Value;
        public Color ValueColor;
        public bool HasBar;
        public float Frac, Mark;
        public Color BarColor;

        public static TagRow Text(string label, string value, Color color) =>
            new TagRow { Label = label, Value = value, ValueColor = color, Mark = -1 };

        public static TagRow Bar(string label, string value, float frac, float mark, Color color) =>
            new TagRow { Label = label, Value = value, ValueColor = Palette.Text, HasBar = true, Frac = frac, Mark = mark, BarColor = color };
    }

    /// <summary>
    /// A billboarded data card: title plus named rows ("ALT 42 m / 100", "BATT 71 %"), each with an
    /// optional bar and a tick at the limit — so no bar is ever an unlabelled coloured stripe.
    /// Rows are pooled; updating a card every poll does not allocate new GameObjects.
    /// Laid out in multiples of `size` (the text height in metres), bottom-centre at the anchor.
    /// </summary>
    public class DataTag : MonoBehaviour
    {
        class RowGo
        {
            public GameObject Root;
            public TextMeshPro Label, Value;
            public Transform BarBg, BarFill, BarMark;
        }

        const float WidthEm = 21f, LabelEm = 4.4f, RowEm = 1.9f, PadEm = 0.7f, TitleEm = 1.9f;

        float size;
        Transform card, accent;
        TextMeshPro title;
        readonly List<RowGo> rows = new List<RowGo>();

        public static DataTag Create(Transform parent, Vector3 localPos, float size)
        {
            var go = new GameObject("DataTag");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            go.AddComponent<Billboard>();
            var tag = go.AddComponent<DataTag>();
            tag.Init(size);
            return tag;
        }

        void Init(float s)
        {
            size = s;
            card = Draw.Prim(PrimitiveType.Quad, transform, Vector3.zero, Vector3.one, Draw.Solid(Palette.Panel), "Card").transform;
            accent = Draw.Prim(PrimitiveType.Quad, transform, Vector3.zero, Vector3.one, Draw.Solid(Palette.Accent), "Accent").transform;
            title = Draw.Text(transform, "", s * 1.05f, Palette.Text, TextAlignmentOptions.Left, Vector3.zero, 0f, FontStyles.Bold);
            title.rectTransform.pivot = new Vector2(0, 0.5f);
        }

        public void Set(string titleText, Color titleColor, IReadOnlyList<TagRow> content, Color accentColor)
        {
            title.text = titleText;
            title.color = titleColor;
            accent.GetComponent<Renderer>().sharedMaterial = Draw.Solid(accentColor);

            int n = content?.Count ?? 0;
            while (rows.Count < n) rows.Add(MakeRow());
            for (int i = 0; i < rows.Count; i++) rows[i].Root.SetActive(i < n);

            float s = size, pad = PadEm * s;
            // A collapsed tag (title only) hugs its text so it doesn't hide the map underneath.
            float w = n > 0 ? WidthEm * s : title.GetPreferredValues(titleText).x + pad * 2 + s * 0.5f;
            float h = (n > 0 ? pad * 2 : pad) + TitleEm * s + n * RowEm * s;
            float left = -w / 2 + pad;
            const float front = -0.0006f; // text and bars sit just in front of the opaque card

            card.localPosition = new Vector3(0, h / 2, 0);
            card.localScale = new Vector3(w, h, 1);
            accent.localPosition = new Vector3(-w / 2 + s * 0.12f, h / 2, front / 2);
            accent.localScale = new Vector3(s * 0.24f, h, 1);

            float y = h - (n > 0 ? pad : pad / 2) - TitleEm * s / 2;
            title.transform.localPosition = new Vector3(left + s * 0.2f, y, front);
            title.rectTransform.sizeDelta = new Vector2(w - pad * 2, TitleEm * s);

            for (int i = 0; i < n; i++)
            {
                var r = rows[i];
                var c = content[i];
                y -= RowEm * s;
                float textY = c.HasBar ? y + s * 0.18f : y;
                r.Label.text = c.Label;
                r.Label.transform.localPosition = new Vector3(left + s * 0.2f, textY, front);
                r.Value.text = c.Value;
                r.Value.color = c.ValueColor;
                r.Value.transform.localPosition = new Vector3(left + LabelEm * s, textY, front);
                r.Value.rectTransform.sizeDelta = new Vector2(w - pad * 2 - LabelEm * s, s * 1.4f);

                r.BarBg.gameObject.SetActive(c.HasBar);
                r.BarFill.gameObject.SetActive(c.HasBar);
                r.BarMark.gameObject.SetActive(c.HasBar && c.Mark >= 0 && c.Mark <= 1);
                if (!c.HasBar) continue;
                float bx = left + LabelEm * s, bw = (w / 2 - pad) - bx;
                float by = y - s * 0.55f, bh = s * 0.22f;
                r.BarBg.localPosition = new Vector3(bx + bw / 2, by, front);
                r.BarBg.localScale = new Vector3(bw, bh, 1);
                float f = Mathf.Clamp01(c.Frac);
                r.BarFill.localPosition = new Vector3(bx + bw * f / 2, by, front * 2);
                r.BarFill.localScale = new Vector3(Mathf.Max(bw * f, 0.0001f), bh, 1);
                r.BarFill.GetComponent<Renderer>().sharedMaterial = Draw.Solid(c.BarColor);
                r.BarMark.localPosition = new Vector3(bx + bw * c.Mark, by, front * 3);
                r.BarMark.localScale = new Vector3(s * 0.12f, bh * 2.4f, 1);
            }
        }

        RowGo MakeRow()
        {
            var r = new RowGo { Root = new GameObject("Row") };
            r.Root.transform.SetParent(transform, false);
            var t = r.Root.transform;
            r.Label = Draw.Text(t, "", size * 0.78f, Palette.TextDim, TextAlignmentOptions.Left, Vector3.zero, 0f, FontStyles.Bold);
            r.Label.rectTransform.pivot = new Vector2(0, 0.5f);
            r.Label.characterSpacing = 6f;
            r.Value = Draw.Text(t, "", size * 0.9f, Palette.Text, TextAlignmentOptions.Left);
            r.Value.rectTransform.pivot = new Vector2(0, 0.5f);
            r.Value.overflowMode = TextOverflowModes.Ellipsis;
            r.BarBg = Draw.Prim(PrimitiveType.Quad, t, Vector3.zero, Vector3.one, Draw.Solid(Palette.Bezel), "BarBg").transform;
            r.BarFill = Draw.Prim(PrimitiveType.Quad, t, Vector3.zero, Vector3.one, Draw.Solid(Palette.Ok), "BarFill").transform;
            r.BarMark = Draw.Prim(PrimitiveType.Quad, t, Vector3.zero, Vector3.one, Draw.Solid(Palette.Text), "Limit").transform;
            return r;
        }

        /// <summary>Card size in local metres, for placing a hit collider over it.</summary>
        public Vector2 CardSize => card == null ? Vector2.zero : new Vector2(card.localScale.x, card.localScale.y);
    }
}
