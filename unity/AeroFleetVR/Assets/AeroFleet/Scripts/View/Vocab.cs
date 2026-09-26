using System.Collections.Generic;
using AeroFleet.VR.Data;
using UnityEngine;

namespace AeroFleet.VR.View
{
    public enum DroneStatus { Ok, Watch, Violation }

    /// <summary>
    /// Human names, units and thresholds for the backend's constraint/factor identifiers. Kept
    /// identical to tauri-app/src/components/vr/theme.ts so the headset and the desktop app never
    /// describe the same number differently.
    /// </summary>
    public static class Vocab
    {
        public static readonly (string key, string label, string unit)[] Constraints =
        {
            ("min_separation", "Min separation", "m"),
            ("geofence_exclusion", "Geofence", ""),
            ("battery_reserve_margin", "Battery reserve", "Wh"),
            ("altitude_ceiling", "Altitude ceiling", "m"),
            ("wind_limit", "Wind envelope", "m/s"),
            ("payload_weight_limit", "Payload", "kg"),
            ("noise_limit", "Ground noise", "dB"),
            ("collision_probability", "Conflict prob.", ""),
            ("comms_link_margin", "C2 link margin", "dB"),
            ("depot_capacity", "Depot pad slots", "slots"),
            ("weather_visibility", "Visibility", "m"),
        };

        public static string ConstraintLabel(string key)
        {
            foreach (var c in Constraints) if (c.key == key) return c.label;
            return key;
        }

        public static string ConstraintUnit(string key)
        {
            foreach (var c in Constraints) if (c.key == key) return c.unit;
            return "";
        }

        public static readonly Dictionary<string, string> Factors = new Dictionary<string, string>
        {
            { "battery_energy", "Battery / energy" },
            { "airspace_conflict", "Airspace conflict" },
            { "weather_environmental", "Weather" },
            { "communications_link", "Comms link" },
            { "routing_navigation", "Routing / navigation" },
            { "ops_scheduling_capacity", "Ops / depot capacity" },
            { "cross_check_anomaly", "Cross-check anomaly" },
        };

        public static readonly Dictionary<string, (string label, Color color, string note)> ClaimStatus =
            new Dictionary<string, (string, Color, string)>
            {
                { "CONFIRMED", ("CONFIRMED", Palette.Ok, "council claim matches a violated constraint") },
                { "MISSED", ("MISSED", Palette.Bad, "geometry shows a violation the council did not claim") },
                { "NO_GEOMETRIC_EVIDENCE", ("UNBACKED", Palette.Warn, "claimed, but no violated constraint supports it") },
                { "UNCERTAIN", ("UNCERTAIN", Palette.Neutral, "council could not decide") },
                { "AGREES_NOT_INVOLVED", ("AGREES", Palette.TextDim, "neither side implicates it") },
                { "NO_CLAIM", ("NO CLAIM", Palette.TextFaint, "council made no statement") },
                { "NOT_CHECKABLE", ("N/A", Palette.TextFaint, "no CBF margin exists to check this factor") },
            };

        /// <summary>How close to a limit counts as "watch this", per live constraint, in its own units.</summary>
        public static readonly Dictionary<string, double> WarnBands = new Dictionary<string, double>
        {
            { "min_separation", 35 },
            { "battery_reserve_margin", 40 },
            { "altitude_ceiling", 5 },
            { "payload_weight_limit", 0.5 },
            { "geofence_exclusion", 0.5 },
        };

        public static DroneStatus Status(LiveDrone d)
        {
            if (!d.Passed) return DroneStatus.Violation;
            if (d.SafetyMargins != null)
                foreach (var kv in WarnBands)
                    if (d.SafetyMargins.TryGetValue(kv.Key, out double m) && m < kv.Value) return DroneStatus.Watch;
            return DroneStatus.Ok;
        }

        public static Color StatusColor(DroneStatus s) =>
            s == DroneStatus.Violation ? Palette.Bad : s == DroneStatus.Watch ? Palette.Warn : Palette.Ok;

        public static Color MarginColor(double margin, double warnBand) =>
            margin < 0 ? Palette.Bad : margin < warnBand ? Palette.Warn : Palette.Ok;

        public static string ShortId(string id) => id != null && id.Length > 10 ? id.Substring(id.Length - 8) : id;

        public static string SourceLabel(string positionSource) =>
            positionSource == "TELEMETRY" ? "live MAVLink"
            : positionSource == "ROUTE_DEAD_RECKONING" ? "sim · on route" : "sim · at depot";
    }
}
