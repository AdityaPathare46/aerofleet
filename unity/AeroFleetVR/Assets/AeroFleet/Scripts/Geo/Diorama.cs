using UnityEngine;

namespace AeroFleet.VR.Geo
{
    public static class GeoMath
    {
        const double MetresPerDegLat = 111320.0;

        /// <summary>Flat-earth east/north metres from a reference point. Same formula as the backend's
        /// /cities/{slug}/roads and the web view (tauri-app/src/components/vr/geo.ts).</summary>
        public static Vector2 ToLocal(double lat, double lon, double centerLat, double centerLon)
        {
            double east = (lon - centerLon) * MetresPerDegLat * System.Math.Cos(centerLat * System.Math.PI / 180.0);
            double north = (lat - centerLat) * MetresPerDegLat;
            return new Vector2((float)east, (float)north);
        }

        public static string FormatDistance(double m) =>
            m >= 1000 ? $"{m / 1000:0.0} km" : $"{Mathf.RoundToInt((float)m)} m";

        /// <summary>A round distance for a scale bar about a quarter of the table wide.</summary>
        public static float NiceScaleBar(float extentM)
        {
            float target = extentM / 2f;
            float pow = Mathf.Pow(10, Mathf.Floor(Mathf.Log10(target)));
            foreach (float m in new[] { 5f, 2f, 1f })
                if (m * pow <= target) return m * pow;
            return pow;
        }
    }

    /// <summary>
    /// World-in-miniature mapping of real metres onto a tabletop (local space of the table root).
    /// Unity is left-handed with +z forward, so east = +x and north = +z reads unmirrored from above.
    /// Vertical is exaggerated so the 0-120 m legal airspace column is ~columnHeight tall; the factor
    /// is always shown to the viewer.
    /// </summary>
    public class Diorama
    {
        public readonly float FocusEast, FocusNorth, ExtentM, TableHalf, ColumnHeight, LegalCeilingM;
        public readonly float Scale, VExag;

        public Diorama(float focusEast, float focusNorth, float extentM,
                       float tableHalf = 0.7f, float columnHeight = 0.32f, float legalCeilingM = 120f)
        {
            FocusEast = focusEast; FocusNorth = focusNorth; ExtentM = extentM;
            TableHalf = tableHalf; ColumnHeight = columnHeight; LegalCeilingM = legalCeilingM;
            Scale = tableHalf / extentM;
            VExag = columnHeight / (legalCeilingM * Scale);
        }

        public float X(float east) => (east - FocusEast) * Scale;
        public float Z(float north) => (north - FocusNorth) * Scale;
        public float Y(float altitudeM) => altitudeM * Scale * VExag;

        public Vector3 Point(float east, float north, float altitudeM = 0f) =>
            new Vector3(X(east), Y(altitudeM), Z(north));

        public bool Contains(float east, float north, float pad = 0f)
        {
            float h = ExtentM + pad;
            return Mathf.Abs(east - FocusEast) <= h && Mathf.Abs(north - FocusNorth) <= h;
        }
    }
}
