using AeroFleet.VR.Data;
using AeroFleet.VR.Geo;
using TMPro;
using UnityEngine;

namespace AeroFleet.VR.View
{
    /// <summary>
    /// The delivery being planned in VR, drawn on the table: a ring on the origin depot, a pin where the
    /// operator pointed, and the straight line between them with its length. The line is only the
    /// request — the backend's router picks the real path (zone- and energy-aware), and once dispatched
    /// the drone's actual 4D trajectory appears with the rest of the swarm.
    /// </summary>
    public class PlanView : MonoBehaviour
    {
        public void Show(Diorama dio, Vector2d city, DepotDto origin, double? destLat, double? destLon, Color accent)
        {
            foreach (Transform c in transform) Destroy(c.gameObject);
            gameObject.SetActive(true);
            if (dio == null) return;
            Vector3? a = null, b = null;
            if (origin?.Lat != null && origin.Lon != null)
            {
                Vector2 en = GeoMath.ToLocal(origin.Lat.Value, origin.Lon.Value, city.x, city.y);
                a = dio.Point(en.x, en.y);
                Draw.Line(transform, Offset(Draw.Circle(0.03f, 48, 0.003f), a.Value), 0.004f, accent, loop: true, name: "OriginRing");
            }
            if (destLat != null && destLon != null)
            {
                Vector2 en = GeoMath.ToLocal(destLat.Value, destLon.Value, city.x, city.y);
                b = dio.Point(en.x, en.y);
                var pin = new GameObject("DestinationPin").transform;
                pin.SetParent(transform, false);
                pin.localPosition = b.Value;
                Draw.Prim(PrimitiveType.Cylinder, pin, new Vector3(0, 0.05f, 0), new Vector3(0.003f, 0.05f, 0.003f), Draw.Solid(accent), "Stem");
                Draw.Prim(PrimitiveType.Sphere, pin, new Vector3(0, 0.104f, 0), Vector3.one * 0.016f, Draw.Solid(accent), "Head");
                Draw.Line(pin, Draw.Circle(0.012f, 32, 0.002f), 0.0025f, accent, loop: true, name: "Ground");
                var t = Draw.Text(pin, "DESTINATION", 0.0095f, accent, TextAlignmentOptions.Center, new Vector3(0, 0.128f, 0), 0f, FontStyles.Bold);
                t.gameObject.AddComponent<Billboard>();
            }
            if (a != null && b != null)
            {
                Vector3 lift = Vector3.up * 0.004f;
                Draw.Line(transform, new[] { a.Value + lift, b.Value + lift }, 0.0025f, Palette.WithAlpha(accent, 0.8f), name: "Request");
                float metres = (b.Value - a.Value).magnitude / dio.Scale;
                var label = Draw.Text(transform, $"{GeoMath.FormatDistance(metres)} straight-line", 0.0095f, accent,
                                      TextAlignmentOptions.Center, (a.Value + b.Value) / 2 + Vector3.up * 0.02f);
                label.gameObject.AddComponent<Billboard>();
            }
        }

        public void Hide()
        {
            foreach (Transform c in transform) Destroy(c.gameObject);
            gameObject.SetActive(false);
        }

        static Vector3[] Offset(Vector3[] pts, Vector3 by)
        {
            for (int i = 0; i < pts.Length; i++) pts[i] += by;
            return pts;
        }
    }
}
