using System;
using AeroFleet.VR.Interaction;
using TMPro;
using UnityEngine;

namespace AeroFleet.VR.View
{
    /// <summary>A board button: point a controller ray (or the mouse) at it and press trigger/click.</summary>
    public class Button3D : MonoBehaviour
    {
        Renderer bg;
        TextMeshPro label;
        bool on, hover, enabledState = true;

        public static Button3D Create(Transform parent, Vector3 localPos, Vector2 size, string text, Action onClick)
        {
            var go = new GameObject("Button " + text);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            var col = go.AddComponent<BoxCollider>();
            col.size = new Vector3(size.x, size.y, 0.01f);
            var b = go.AddComponent<Button3D>();
            b.bg = Draw.Prim(PrimitiveType.Quad, go.transform, Vector3.zero, new Vector3(size.x, size.y, 1), Draw.Solid(Palette.Bezel), "Face").GetComponent<Renderer>();
            b.label = Draw.Text(go.transform, text, Mathf.Min(size.y * 0.42f, 0.02f), Palette.Text, TextAlignmentOptions.Center, new Vector3(0, 0, -0.001f), 0f, FontStyles.Bold);
            b.label.rectTransform.sizeDelta = new Vector2(size.x, size.y);
            var c = go.AddComponent<Clickable>();
            c.OnClick = () => { if (b.enabledState) onClick?.Invoke(); };
            c.OnHover = h => { b.hover = h; b.Refresh(); };
            return b;
        }

        public void SetOn(bool value) { on = value; Refresh(); }
        public void SetEnabled(bool value) { enabledState = value; Refresh(); }
        public void SetLabel(string text) => label.text = text;

        void Refresh()
        {
            Color face = !enabledState ? Palette.Panel : on ? Palette.Accent : hover ? Palette.PanelEdge : Palette.Bezel;
            bg.sharedMaterial = Draw.Solid(face);
            label.color = !enabledState ? Palette.TextFaint : on ? Palette.Void : Palette.Text;
        }
    }
}
