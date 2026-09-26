using System.Collections.Generic;
using AeroFleet.VR.Data;
using AeroFleet.VR.Geo;
using TMPro;
using UnityEngine;

namespace AeroFleet.VR.View
{
    /// <summary>
    /// Left board: what state is the swarm in right now (four KPIs), which constraint is closest to
    /// its limit across the whole fleet, and whether that number comes from a live source or a
    /// dispatch-time default — plus every control, reachable with the controller ray.
    /// In replay it shows the frozen incident's violations against the same constraint list.
    /// </summary>
    public class FleetBoard : MonoBehaviour
    {
        public const float Width = 0.86f, Height = 1.0f;

        Panel panel;
        TextMeshPro title, subtitle;
        readonly List<(TextMeshPro value, TextMeshPro key, TextMeshPro sub)> kpis = new List<(TextMeshPro, TextMeshPro, TextMeshPro)>();
        TextMeshPro tableHeader;
        readonly List<(TextMeshPro label, TextMeshPro value, Transform chip, TextMeshPro chipText)> rows =
            new List<(TextMeshPro, TextMeshPro, Transform, TextMeshPro)>();
        TextMeshPro legend;
        Button3D live, replay, allTags, prev, next, cityButton, buildingsButton;
        readonly Dictionary<int, Button3D> ranges = new Dictionary<int, Button3D>();

        public static FleetBoard Create(Transform parent, AeroFleetApp app)
        {
            var p = Panel.Create(parent, "FleetBoard", Width, Height);
            var b = p.gameObject.AddComponent<FleetBoard>();
            b.panel = p;
            b.Build(app);
            return b;
        }

        void Build(AeroFleetApp app)
        {
            var p = panel;
            const float m = 0.04f;
            title = p.Text("AEROFLEET · FLEET SAFETY", m, 0.045f, 0.022f, Palette.Accent, style: FontStyles.Bold);
            title.characterSpacing = 4;
            subtitle = p.Text("connecting…", m, 0.088f, 0.018f, Palette.TextDim);
            buildingsButton = p.Button("3D CITY", Width - m - 0.30f, 0.022f, 0.11f, 0.05f, app.ToggleBuildings);
            cityButton = p.Button("CITY", Width - m - 0.18f, 0.022f, 0.18f, 0.05f, app.NextCity);

            float tileW = (Width - 2 * m - 3 * 0.012f) / 4, tileY = 0.115f, tileH = 0.13f;
            for (int i = 0; i < 4; i++)
            {
                float x = m + i * (tileW + 0.012f);
                p.Rect(x, tileY, tileW, tileH, Palette.Table, "Tile");
                var key = p.Text("", x + 0.014f, tileY + 0.022f, 0.0135f, Palette.TextDim, style: FontStyles.Bold);
                key.characterSpacing = 5;
                var val = p.Text("—", x + 0.014f, tileY + 0.066f, 0.044f, Palette.Text, style: FontStyles.Bold);
                var sub = p.Text("", x + 0.014f, tileY + 0.108f, 0.0125f, Palette.TextFaint);
                kpis.Add((val, key, sub));
            }

            tableHeader = p.Text("FLEET WORST CASE · PER CBF CONSTRAINT", m, 0.282f, 0.0135f, Palette.TextFaint, style: FontStyles.Bold);
            tableHeader.characterSpacing = 5;
            for (int i = 0; i < Vocab.Constraints.Length; i++)
            {
                float y = 0.318f + i * 0.036f;
                if (i % 2 == 0) p.Rect(m - 0.01f, y - 0.018f, Width - 2 * m + 0.02f, 0.036f, Palette.Hex("0D1B2E"), "Stripe");
                var label = p.Text(Vocab.Constraints[i].label, m, y, 0.0185f, Palette.Text);
                var value = p.Text("—", Width - 0.19f, y, 0.0185f, Palette.TextDim, TextAlignmentOptions.Right, style: FontStyles.Bold);
                var chip = p.Rect(Width - m - 0.125f, y - 0.013f, 0.125f, 0.026f, Palette.Bezel, "Chip");
                var chipText = p.Text("", Width - m - 0.0625f, y, 0.0115f, Palette.TextDim, TextAlignmentOptions.Center, style: FontStyles.Bold);
                chipText.characterSpacing = 4;
                rows.Add((label, value, chip, chipText));
            }

            legend = p.Text("", m, 0.72f, 0.0122f, Palette.TextFaint, wrapW: Width - 2 * m);

            float bw = (Width - 2 * m - 5 * 0.01f) / 6, bh = 0.058f, r1 = 0.80f, r2 = r1 + bh + 0.012f;
            float X(int i) => m + i * (bw + 0.01f);
            live = p.Button("LIVE", X(0), r1, bw, bh, () => app.SetMode(ViewMode.Live));
            replay = p.Button("REPLAY", X(1), r1, bw, bh, () => app.SetMode(ViewMode.Replay));
            ranges[1] = p.Button("1 km", X(2), r1, bw, bh, () => app.SetRange(1));
            ranges[2] = p.Button("2 km", X(3), r1, bw, bh, () => app.SetRange(2));
            ranges[4] = p.Button("4 km", X(4), r1, bw, bh, () => app.SetRange(4));
            allTags = p.Button("ALL TAGS", X(5), r1, bw, bh, app.ToggleDetailAll);
            prev = p.Button("◄ INCIDENT", X(0), r2, bw, bh, () => app.StepIncident(-1));
            next = p.Button("INCIDENT ►", X(1), r2, bw, bh, () => app.StepIncident(1));
            p.Button("ROTATE", X(2), r2, bw, bh, app.RotateTable);
            p.Button("TABLE ▲", X(3), r2, bw, bh, () => app.NudgeTable(0.05f));
            p.Button("TABLE ▼", X(4), r2, bw, bh, () => app.NudgeTable(-0.05f));
            p.Button("RECENTER", X(5), r2, bw, bh, app.Recenter);
        }

        public void Refresh(AeroFleetApp app)
        {
            bool isLive = app.Mode == ViewMode.Live;
            live.SetOn(isLive);
            replay.SetOn(!isLive);
            foreach (var kv in ranges) { kv.Value.SetOn(isLive && app.RangeKm == kv.Key); kv.Value.SetEnabled(isLive); }
            allTags.SetOn(app.DetailAll);
            allTags.SetEnabled(isLive);
            prev.SetEnabled(!isLive && app.Incidents.Count > 1);
            next.SetEnabled(!isLive && app.Incidents.Count > 1);

            cityButton.SetLabel($"{app.CityName?.ToUpperInvariant()} ►");
            buildingsButton.SetOn(app.ShowBuildings);
            subtitle.text = app.StatusLine;
            subtitle.color = app.StatusIsError ? Palette.Bad : Palette.TextDim;
            if (isLive) RefreshLive(app.Live, app.Diorama, app); else RefreshReplay(app);
        }

        static string BuildingNote(AeroFleetApp app)
        {
            var b = app.Buildings;
            if (!app.ShowBuildings || b == null || !b.Available) return "";
            return $" · {app.BuildingsDrawn:N0} OSM buildings shown: {app.BuildingsDrawnMeasured:N0} with a tagged height (light), " +
                   $"the rest drawn at an assumed {b.AssumedHeightM:0} m (dark)";
        }

        void RefreshLive(LiveMarginsDto data, Diorama dio, AeroFleetApp app)
        {
            title.text = "AEROFLEET · FLEET SAFETY";
            tableHeader.text = "FLEET WORST CASE · PER CBF CONSTRAINT";
            var drones = data?.Drones?.Values;
            int airborne = data?.Drones?.Count ?? 0, watch = 0, loss = 0;
            double minSep = data?.Constants.MinSeparationM ?? 15;
            if (drones != null) foreach (var d in drones) if (Vocab.Status(d) != DroneStatus.Ok) watch++;
            if (data != null) foreach (var pr in data.Pairs) if (pr.SeparationMarginM < 0) loss++;
            DronePair closest = data != null && data.Pairs.Count > 0 ? data.Pairs[0] : null;

            SetKpi(0, "AIRBORNE", airborne.ToString(), Palette.Text, "drones in the air");
            SetKpi(1, "LOSS OF SEP.", loss.ToString(), loss > 0 ? Palette.Bad : Palette.Ok, $"pairs < {minSep:0} m");
            SetKpi(2, "WATCH / VIOL.", watch.ToString(), watch > 0 ? Palette.Warn : Palette.Ok, "drones near a limit");
            SetKpi(3, "CLOSEST PAIR", closest != null ? GeoMath.FormatDistance(closest.HorizontalM) : "—",
                closest != null && closest.SeparationMarginM < 0 ? Palette.Bad : Palette.Text, "horizontal");

            var liveSet = new HashSet<string>(data?.ConstraintSources.Live ?? new List<string>());
            for (int i = 0; i < rows.Count; i++)
            {
                var (key, _, unit) = Vocab.Constraints[i];
                bool has = data != null && data.FleetWorstCase.TryGetValue(key, out _);
                double v = has ? data.FleetWorstCase[key] : 0;
                bool isLive = liveSet.Contains(key);
                Color c = !has ? Palette.TextFaint
                    : v < 0 ? Palette.Bad
                    : Vocab.WarnBands.TryGetValue(key, out double band) && v < band ? Palette.Warn
                    : isLive ? Palette.Ok : Palette.TextDim;
                string text = !has ? "—"
                    : key == "geofence_exclusion" ? (v < 0 ? "INSIDE" : "clear")
                    : $"{(System.Math.Abs(v) >= 1000 ? v.ToString("0") : v.ToString(System.Math.Abs(v) < 10 ? "0.0" : "0"))}{(unit != "" ? " " + unit : "")}";
                SetRow(i, text, c, has ? (isLive ? "LIVE" : "ASSUMED") : "", isLive ? Palette.Ok : Palette.TextDim);
            }
            legend.text = $"Drop-line to the ground = altitude · beam = pair within {Vocab.WarnBands["min_separation"] + minSep:0} m · " +
                          "faint line = remaining route · ASSUMED = no live per-drone sensor yet, the dispatch-time default is used · " +
                          $"symbols not to scale, vertical ×{(dio != null ? dio.VExag : 0):0}" + BuildingNote(app);
        }

        void RefreshReplay(AeroFleetApp app)
        {
            var s = app.Scene;
            int n = app.Incidents.Count;
            title.text = n > 0 ? $"REPLAY · INCIDENT {app.IncidentIndex + 1} OF {n}" : "REPLAY · NO REJECTIONS YET";
            tableHeader.text = "CONSTRAINTS AT THE MOMENT OF REJECTION";
            var violated = new Dictionary<string, double>();
            if (s != null) foreach (var v in s.Violations) violated[v.ConstraintName] = v.ViolationMagnitude;

            SetKpi(0, "VIOLATED", s != null ? violated.Count.ToString() : "—", violated.Count > 0 ? Palette.Bad : Palette.Text, "CBF constraints");
            SetKpi(1, "ALTITUDE", s?.AltitudeM != null ? $"{s.AltitudeM:0} m" : "—", violated.ContainsKey("altitude_ceiling") ? Palette.Bad : Palette.Text,
                s?.MaxAltitudeM != null ? $"ceiling {s.MaxAltitudeM:0} m" : "");
            SetKpi(2, "ZONE", s == null ? "—" : s.InRedZone ? "RED" : s.InYellowZone ? "YELLOW" : "GREEN",
                s == null ? Palette.Text : s.InRedZone ? Palette.Bad : s.InYellowZone ? Palette.Warn : Palette.Ok, "at destination");
            string verdict = s == null ? "—" : s.ClaimCheck.HasCouncilClaims ? (s.ClaimCheck.AgreesWithGeometry ? "AGREES" : "DIFFERS") : "PENDING";
            SetKpi(3, "COUNCIL", verdict, verdict == "AGREES" ? Palette.Ok : verdict == "DIFFERS" ? Palette.Warn : Palette.Neutral, "vs. geometry");

            for (int i = 0; i < rows.Count; i++)
            {
                var (key, _, unit) = Vocab.Constraints[i];
                bool bad = violated.TryGetValue(key, out double mag);
                SetRow(i, bad ? $"−{mag:0.0}{(unit != "" ? " " + unit : "")}" : "within limit", bad ? Palette.Bad : Palette.TextFaint,
                    bad ? "VIOLATED" : "", Palette.Bad);
            }
            legend.text = "Red rod = the cruise altitude the gate checked · ring = the ceiling that applied there · " +
                          "dashed leg = planned straight line from the origin depot (the flown path is not stored) · " +
                          "the right-hand board checks the AI council's causal claims against these violations." + BuildingNote(app);
        }

        void SetKpi(int i, string key, string value, Color color, string sub)
        {
            kpis[i].key.text = key;
            kpis[i].value.text = value;
            kpis[i].value.color = color;
            kpis[i].sub.text = sub;
        }

        void SetRow(int i, string value, Color color, string chip, Color chipColor)
        {
            var r = rows[i];
            r.value.text = value;
            r.value.color = color;
            r.chip.gameObject.SetActive(chip != "");
            r.chipText.text = chip;
            r.chipText.color = chipColor;
            r.chip.GetComponent<Renderer>().sharedMaterial = Draw.Solid(chip == "LIVE" ? Palette.Hex("0E2A22") : chip == "VIOLATED" ? Palette.Hex("331418") : Palette.Bezel);
        }
    }
}
