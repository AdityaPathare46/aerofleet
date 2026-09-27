using System.Collections.Generic;
using AeroFleet.VR.Data;
using AeroFleet.VR.Geo;
using TMPro;
using UnityEngine;

namespace AeroFleet.VR.View
{
    /// <summary>
    /// Right board. Replay: the claim check — every causal factor the AI council named, set
    /// against the constraints the CBF geometry actually violated, with a deterministic verdict
    /// (this is the reason to review an incident spatially). Live: how to read the table, plus the
    /// selected drone.
    /// </summary>
    public class ContextBoard : MonoBehaviour
    {
        public const float Width = 0.86f, Height = 1.0f;
        const float M = 0.04f;

        Panel panel;
        Transform content;
        string builtFor;

        public static ContextBoard Create(Transform parent)
        {
            var p = Panel.Create(parent, "ContextBoard", Width, Height);
            var b = p.gameObject.AddComponent<ContextBoard>();
            b.panel = p;
            return b;
        }

        public void Refresh(AeroFleetApp app)
        {
            string key = app.ActiveTool != AeroFleetApp.Tool.None
                ? $"tool:{app.ActiveTool}:{app.UiVersion}:{app.AllowDispatch}:{app.PlanBusy}"
                : app.Mode == ViewMode.Replay
                ? "replay:" + (app.Scene?.IncidentId ?? "none")
                : "live:" + (app.Selected == null ? "" : app.Selected + ":" + app.FollowSelected + ":" +
                             (app.SelectedInspection?.InspectionId ?? (app.SelectedInspectionLoaded ? "none" : "…")) + ":" +
                             // rebuild with fresh numbers every ~3 s, not every poll (TMP churn on Quest)
                             Mathf.FloorToInt((float)((app.Live?.GeneratedAt ?? 0) / 3.0)));
            if (key == builtFor) return;
            builtFor = key;

            if (content != null) Destroy(content.gameObject);
            content = new GameObject("Content").transform;
            content.SetParent(transform, false);
            if (app.ActiveTool == AeroFleetApp.Tool.Build) BuildBuilder(app);
            else if (app.ActiveTool == AeroFleetApp.Tool.Plan) BuildPlanner(app);
            else if (app.Mode == ViewMode.Replay) BuildReplay(app.Scene);
            else if (app.Selected != null && app.Live != null && app.Live.Drones.TryGetValue(app.Selected, out var sel)) BuildInspection(app, app.Selected, sel);
            else BuildLive(app);
        }

        TextMeshPro T(string text, float x, float y, float h, Color c, TextAlignmentOptions a = TextAlignmentOptions.Left,
                      float wrap = 0f, FontStyles s = FontStyles.Normal)
        {
            var t = panel.Text(text, x, y, h, c, a, wrap, s);
            t.transform.SetParent(content, true);
            return t;
        }

        Transform R(float x, float y, float w, float h, Color c)
        {
            var r = panel.Rect(x, y, w, h, c);
            r.SetParent(content, true);
            return r;
        }

        void Heading(string text, float y)
        {
            var t = T(text, M, y, 0.0135f, Palette.TextFaint, s: FontStyles.Bold);
            t.characterSpacing = 5;
        }

        // ── replay: claim check ────────────────────────────────────────────

        void BuildReplay(VrSceneDto s)
        {
            var title = T("DOES THE AI EXPLANATION MATCH THE GEOMETRY?", M, 0.045f, 0.022f, Palette.Accent, s: FontStyles.Bold);
            title.characterSpacing = 2;
            if (s == null)
            {
                T("No CBF rejection selected. Rejections are created when the safety gate refuses a dispatch " +
                  "(e.g. tools/seed_demo_swarm.py --rejections 6).", M, 0.09f, 0.017f, Palette.TextDim, wrap: Width - 2 * M);
                return;
            }
            T($"Incident {Vocab.ShortId(s.IncidentId)} · {s.TriggerType?.Replace('_', ' ')} · {s.Status}", M, 0.088f, 0.017f, Palette.TextDim);

            var check = s.ClaimCheck;
            int missed = check.Counts.TryGetValue("MISSED", out int a) ? a : 0;
            int unbacked = check.Counts.TryGetValue("NO_GEOMETRIC_EVIDENCE", out int b) ? b : 0;
            int disagreements = missed + unbacked;
            Color vc; string vt;
            if (!check.HasCouncilClaims) { vc = Palette.Neutral; vt = "The council has not produced factor claims for this incident yet."; }
            else if (disagreements == 0) { vc = Palette.Ok; vt = "The council's factor claims are consistent with the rejection geometry."; }
            else
            {
                vc = disagreements > 1 ? Palette.Bad : Palette.Warn;
                vt = $"The council disagrees with the geometry on {disagreements} factor{(disagreements == 1 ? "" : "s")} — verify before acting on its report.";
            }
            R(M, 0.115f, 0.008f, 0.075f, vc);
            R(M + 0.008f, 0.115f, Width - 2 * M - 0.008f, 0.075f, Palette.Table);
            T(vt, M + 0.024f, 0.128f, 0.0185f, vc, wrap: Width - 2 * M - 0.04f, s: FontStyles.Bold);

            float y = 0.228f;
            Heading("FACTOR", y);
            T("COUNCIL SAID", 0.3f, y, 0.0135f, Palette.TextFaint, s: FontStyles.Bold).characterSpacing = 5;
            T("GEOMETRY SHOWS", 0.49f, y, 0.0135f, Palette.TextFaint, s: FontStyles.Bold).characterSpacing = 5;
            T("CHECK", Width - M, y, 0.0135f, Palette.TextFaint, TextAlignmentOptions.Right, s: FontStyles.Bold).characterSpacing = 5;

            y += 0.04f;
            foreach (var row in check.Rows)
            {
                var st = Vocab.ClaimStatus.TryGetValue(row.Status, out var v) ? v : (row.Status, Palette.TextDim, "");
                string label = Vocab.Factors.TryGetValue(row.Factor, out string l) ? l : row.Factor;
                string claim = row.CouncilClaim != null
                    ? row.CouncilClaim.Replace('_', ' ').ToLowerInvariant() + (row.CouncilConfidence != null ? $" · {row.CouncilConfidence * 100:0}%" : "")
                    : "—";
                string evidence = row.EvidenceConstraints.Count > 0
                    ? string.Join(", ", row.EvidenceConstraints.ConvertAll(Vocab.ConstraintLabel))
                    : row.Status == "NOT_CHECKABLE" ? "no CBF margin" : "none violated";
                bool checkable = row.Status != "NOT_CHECKABLE";
                T(label, M, y, 0.0175f, checkable ? Palette.Text : Palette.TextFaint);
                T(claim, 0.3f, y, 0.0155f, Palette.TextDim);
                var ev = T(evidence, 0.49f, y, 0.0155f, row.ImplicatedByGeometry ? Palette.Bad : Palette.TextFaint);
                ev.rectTransform.sizeDelta = new Vector2(0.2f, 0.03f);
                ev.overflowMode = TextOverflowModes.Ellipsis;
                R(Width - M - 0.13f, y - 0.014f, 0.13f, 0.028f, Palette.Bezel);
                var chip = T(st.Item1, Width - M - 0.065f, y, 0.0115f, st.Item2, TextAlignmentOptions.Center, s: FontStyles.Bold);
                chip.characterSpacing = 4;
                y += 0.047f;
            }

            y += 0.01f;
            Heading("COUNCIL ROOT-CAUSE SUMMARY", y);
            string summary = string.IsNullOrWhiteSpace(s.RootCauseSummary) ? "not produced yet" : Trim(s.RootCauseSummary, 300);
            T(summary, M, y + 0.02f, 0.0155f, Palette.TextDim, wrap: Width - 2 * M);
            y += 0.14f;
            Heading("RECOMMENDED ACTION", y);
            T(string.IsNullOrWhiteSpace(s.RecommendedAction) ? "—" : Trim(s.RecommendedAction, 160), M, y + 0.02f, 0.0155f, Palette.TextDim, wrap: Width - 2 * M);

            T("Geometry = the CBF constraints violated at rejection time. The comparison is deterministic — no LLM decides the verdict.",
              M, Height - 0.07f, 0.0125f, Palette.TextFaint, wrap: Width - 2 * M);
        }

        static string Trim(string s, int n) => s.Length > n ? s.Substring(0, n - 1) + "…" : s;

        // ── live: legend + selection ───────────────────────────────────────

        Button3D B(string label, float x, float y, float w, System.Action click, bool on = false)
        {
            var b = panel.Button(label, x, y, w, 0.058f, click);
            b.transform.SetParent(content, true);
            b.SetOn(on);
            return b;
        }

        /// <summary>Everything known about one drone, from the live feed and its last compliance inspection.</summary>
        void BuildInspection(AeroFleetApp app, string id, LiveDrone d)
        {
            var status = Vocab.Status(d);
            var title = T("DRONE INSPECTION", M, 0.045f, 0.022f, Palette.Accent, s: FontStyles.Bold);
            title.characterSpacing = 2;
            T(id, Width - M, 0.045f, 0.022f, Vocab.StatusColor(status), TextAlignmentOptions.Right, s: FontStyles.Bold);
            T($"{d.State?.Replace('_', ' ')} · {(d.Phase ?? "no plan").ToLowerInvariant()} · {d.Zone} zone · {Vocab.SourceLabel(d.PositionSource)}",
              M, 0.083f, 0.0155f, Palette.TextDim);
            T($"Order {Vocab.ShortId(d.OrderId) ?? "—"} · payload {d.PayloadKg:0.0} kg · heading {(d.HeadingDeg != null ? d.HeadingDeg.Value.ToString("0") + "°" : "—")} · C2 link {d.LinkMode}",
              M, 0.107f, 0.0145f, Palette.TextDim);

            float y = 0.14f;
            void Gauge(string label, string value, float frac, float mark, Color c)
            {
                T(label, M, y, 0.014f, Palette.TextDim, s: FontStyles.Bold).characterSpacing = 4;
                T(value, Width - M, y, 0.0165f, Palette.Text, TextAlignmentOptions.Right);
                R(M, y + 0.014f, Width - 2 * M, 0.012f, Palette.Bezel);
                R(M, y + 0.014f, (Width - 2 * M) * Mathf.Clamp01(frac), 0.012f, c);
                if (mark >= 0 && mark <= 1) R(M + (Width - 2 * M) * mark - 0.0015f, y + 0.009f, 0.003f, 0.022f, Palette.Text);
                y += 0.052f;
            }
            double usable = d.BatteryAvailableWh + d.BatteryReserveWh;
            double capacity = d.BatterySocPct > 0 ? usable / (d.BatterySocPct / 100.0) : 0;
            Gauge("BATTERY", $"{d.BatterySocPct:0} % · {d.BatteryAvailableWh:0} Wh above reserve", (float)d.BatterySocPct / 100f,
                  capacity > 0 ? (float)(d.BatteryReserveWh / capacity) : -1, Vocab.MarginColor(d.BatteryAvailableWh, 40));
            Gauge("ALTITUDE", $"{d.AltitudeM:0} m of {d.AltitudeCeilingM:0} m ceiling", (float)(d.AltitudeM / 120), (float)(d.AltitudeCeilingM / 120),
                  Vocab.MarginColor(d.AltitudeCeilingM - d.AltitudeM, 5));
            if (d.Progress != null)
                Gauge("LEG", d.Arrived ? "landed at destination" : $"{d.Progress * 100:0} % · {Geo.GeoMath.FormatDistance(d.RemainingM ?? 0)} to go · lands in {DroneView.Clock(d.EtaS ?? 0)}",
                      (float)d.Progress.Value, -1, Palette.Accent);

            // predicted conflicts involving this drone
            var mine = app.Live.PredictedConflicts.FindAll(c => c.A == id || c.B == id);
            string near = d.NearestDroneId != null ? $"nearest {Vocab.ShortId(d.NearestDroneId)} {Geo.GeoMath.FormatDistance(d.NearestHorizontalM)} ↔ {d.NearestVerticalM:0} m ↕" : "no other drone airborne";
            T(near, M, y, 0.0155f, Palette.TextDim);
            y += 0.026f;
            foreach (var c in mine)
            {
                string other = c.A == id ? c.B : c.A;
                T($"{(c.Severity == "CONFLICT" ? "PREDICTED CONFLICT" : "near miss")} with {Vocab.ShortId(other)} in {DroneView.Clock(c.TS)} · {c.HorizontalM:0} m ↔",
                  M, y, 0.0155f, c.Severity == "CONFLICT" ? Palette.Bad : Palette.Warn, s: FontStyles.Bold);
                y += 0.026f;
            }

            // all CBF margins for this drone
            y += 0.008f;
            Heading("CBF MARGINS FOR THIS DRONE", y);
            y += 0.026f;
            var live = new HashSet<string>(app.Live.ConstraintSources.Live);
            foreach (var (key, label, unit) in Vocab.Constraints)
            {
                bool has = d.SafetyMargins != null && d.SafetyMargins.TryGetValue(key, out _);
                double v = has ? d.SafetyMargins[key] : 0;
                Color col = !has ? Palette.TextFaint : v < 0 ? Palette.Bad
                    : Vocab.WarnBands.TryGetValue(key, out double band) && v < band ? Palette.Warn : live.Contains(key) ? Palette.Ok : Palette.TextDim;
                T(label, M, y, 0.0145f, Palette.Text);
                string val = !has ? "—" : Vocab.FormatMargin(key, v);
                T(val, Width - M - 0.12f, y, 0.0145f, col, TextAlignmentOptions.Right, s: FontStyles.Bold);
                T(live.Contains(key) ? "LIVE" : "ASSUMED", Width - M, y, 0.0105f, live.Contains(key) ? Palette.Ok : Palette.TextFaint,
                  TextAlignmentOptions.Right, s: FontStyles.Bold);
                y += 0.0235f;
            }

            // compliance record
            y += 0.006f;
            var insp = app.SelectedInspection;
            string rec = insp != null
                ? $"Compliance inspection {insp.InspectionId}: {insp.Verdict ?? insp.Status} · {(insp.CompletedAt ?? "").Split('T')[0]} — parts coloured on the stand"
                : app.SelectedInspectionLoaded ? "No flight-controller compliance inspection on file for this drone (Hardware ▸ Drone compliance)."
                : "Looking up its compliance inspection…";
            T(rec, M, y, 0.0135f, insp != null ? Palette.TextDim : Palette.TextFaint, wrap: Width - 2 * M);

            float by = Height - M - 0.058f;
            B(app.FollowSelected ? "FOLLOWING" : "FOLLOW", M, by, 0.24f, app.ToggleFollow, app.FollowSelected);
            B("CLOSE", Width - M - 0.2f, by, 0.2f, () => app.Select(id));
        }

        // ── plan a delivery ────────────────────────────────────────────────

        void BuildPlanner(AeroFleetApp app)
        {
            var title = T("PLAN A DELIVERY", M, 0.045f, 0.022f, Palette.Accent, s: FontStyles.Bold);
            title.characterSpacing = 2;
            T("Pick where it starts and where it goes; the backend routes it and the CBF safety gate decides.",
              M, 0.075f, 0.0155f, Palette.TextDim, wrap: Width - 2 * M);

            float y = 0.15f;
            void Step(string n, string head, string value, bool done)
            {
                R(M, y - 0.016f, 0.032f, 0.032f, done ? Palette.Accent : Palette.Bezel);
                T(n, M + 0.016f, y, 0.016f, done ? Palette.Void : Palette.TextDim, TextAlignmentOptions.Center, s: FontStyles.Bold);
                T(head, M + 0.05f, y - 0.006f, 0.0165f, Palette.Text, s: FontStyles.Bold);
                T(value, M + 0.05f, y + 0.014f, 0.0145f, done ? Palette.TextDim : Palette.TextFaint);
                y += 0.068f;
            }
            Step("1", "Origin depot", app.PlanOrigin != null ? $"{app.PlanOrigin.Name} ({app.PlanOrigin.DepotId})" : "point at a depot pylon on the table, pull the trigger",
                 app.PlanOrigin != null);
            Step("2", "Destination", app.PlanLat != null ? $"{app.PlanLat:0.00000}, {app.PlanLon:0.00000}" : "point at the map where the parcel goes, pull the trigger",
                 app.PlanLat != null);

            T("PAYLOAD", M, y, 0.0135f, Palette.TextFaint, s: FontStyles.Bold).characterSpacing = 5;
            T("PRIORITY", M + 0.3f, y, 0.0135f, Palette.TextFaint, s: FontStyles.Bold).characterSpacing = 5;
            y += 0.016f;
            B($"{AeroFleetApp.PlanPayloads[app.PlanPayloadIndex]:0.0} kg ►", M, y, 0.26f, app.CyclePlanPayload);
            B($"{AeroFleetApp.PlanPriorities[app.PlanPriorityIndex]} ►", M + 0.3f, y, 0.3f, app.CyclePlanPriority);
            y += 0.09f;

            var dispatch = B(app.PlanBusy ? "DISPATCHING…" : "DISPATCH", M, y, 0.3f, app.DispatchPlan, app.CanDispatch);
            dispatch.SetEnabled(app.PlanOrigin != null && app.PlanLat != null && !app.PlanBusy);
            B("CLEAR", M + 0.32f, y, 0.16f, () => { app.ClearPlan(); app.SetTool(AeroFleetApp.Tool.Plan); });
            y += 0.085f;

            if (!app.AllowDispatch)
            {
                T(app.Following
                    ? "Dispatching from the headset is off. On the computer: VR panel ▸ tick “Allow the headset to dispatch”. You can still plan and look."
                    : "Sign in (aerofleet_config.json) to dispatch.", M, y, 0.0145f, Palette.Warn, wrap: Width - 2 * M);
                y += 0.06f;
            }
            if (!string.IsNullOrEmpty(app.PlanStatus))
            {
                T(app.PlanStatus, M, y, 0.0165f, app.PlanStatusBad ? Palette.Bad : Palette.Text, wrap: Width - 2 * M, s: FontStyles.Bold);
                y += 0.07f;
            }

            var r = app.PlanResult;
            if (r?.Certificate?.SafetyMargins != null && r.Certificate.SafetyMargins.Count > 0)
            {
                Heading($"CBF GATE · {(r.Certificate.Passed ? "PASSED" : "REJECTED")} IN {r.Certificate.ExecutionTimeMs:0.0} ms" +
                        (r.Compliance?.OverallStatus != null ? $" · COMPLIANCE {r.Compliance.OverallStatus.Replace('_', ' ')}" : ""), y);
                y += 0.026f;
                foreach (var (key, label, unit) in Vocab.Constraints)
                {
                    if (!r.Certificate.SafetyMargins.TryGetValue(key, out double v)) continue;
                    Color col = v < 0 ? Palette.Bad : Vocab.WarnBands.TryGetValue(key, out double band) && v < band ? Palette.Warn : Palette.Ok;
                    T(label, M, y, 0.0145f, Palette.Text);
                    T(key == "geofence_exclusion" ? (v < 0 ? "INSIDE A NO-FLY ZONE" : "clear")
                      : v < 0 ? "VIOLATED by " + Vocab.FormatMargin(key, -v) : Vocab.FormatMargin(key, v) + " spare",
                      Width - M, y, 0.0145f, col, TextAlignmentOptions.Right, s: FontStyles.Bold);
                    y += 0.0235f;
                    if (y > Height - 0.12f) break;
                }
            }

            T("The straight line on the table is only the request — the router picks the real path, and an approved drone's 4D trajectory " +
              "appears with the swarm. A headset only ever dispatches simulated drones.", M, Height - M - 0.1f, 0.0122f, Palette.TextFaint, wrap: Width - 2 * M);
            B("CLOSE", Width - M - 0.2f, Height - M - 0.058f, 0.2f, () => app.SetTool(AeroFleetApp.Tool.Plan));
        }

        // ── build a drone ──────────────────────────────────────────────────

        void BuildBuilder(AeroFleetApp app)
        {
            var b = app.Build;
            var title = T("BUILD A DRONE", M, 0.045f, 0.022f, Palette.Accent, s: FontStyles.Bold);
            title.characterSpacing = 2;
            T("Choose parts; the stand shows the airframe and these numbers update.", M, 0.075f, 0.0155f, Palette.TextDim);

            float y = 0.11f;
            void Part(string label, string part, string value)
            {
                T(label, M, y + 0.029f, 0.0135f, Palette.TextFaint, s: FontStyles.Bold).characterSpacing = 4;
                B("◄", M + 0.15f, y, 0.06f, () => app.StepBuild(part, -1));
                T(value, M + 0.22f, y + 0.029f, 0.0165f, Palette.Text, s: FontStyles.Bold);
                B("►", Width - M - 0.06f, y, 0.06f, () => app.StepBuild(part, 1));
                y += 0.068f;
            }
            Part("FRAME", "frame", b.F.Name);
            Part("MOTORS", "motor", $"{b.F.Arms} × {b.M.Name}");
            Part("BATTERY", "battery", $"{b.B.Name} · {b.B.Wh:0} Wh");
            Part("PAYLOAD", "payload", $"{b.PayloadKg:0.0} kg");

            y += 0.012f;
            Heading("RESULT", y);
            y += 0.03f;
            void Row(string label, string value, Color c)
            {
                T(label, M, y, 0.0165f, Palette.Text);
                T(value, Width - M, y, 0.0165f, c, TextAlignmentOptions.Right, s: FontStyles.Bold);
                y += 0.031f;
            }
            Row("All-up mass", $"{b.AllUpKg:0.00} kg  (empty {b.EmptyKg:0.00} kg)", Palette.Text);
            Row("DGCA weight category", b.Category, Palette.Accent);
            Row("Hover power", $"{b.HoverW:0} W", Palette.Text);
            Row("Hover endurance", $"{b.EnduranceMin:0} min", b.EnduranceMin < 5 ? Palette.Bad : b.EnduranceMin < 12 ? Palette.Warn : Palette.Ok);
            Row("Thrust / weight", $"{b.ThrustToWeight:0.0}", b.ThrustToWeight < 1 ? Palette.Bad : b.ThrustToWeight < DroneBuild.MinThrustToWeight ? Palette.Warn : Palette.Ok);
            Row("Disc loading", $"{b.AllUpKg * DroneBuild.G / b.DiscAreaM2:0} N/m²", Palette.TextDim);

            string problem = b.Problem;
            T(problem == "" ? "Flyable on these numbers." : problem, M, y + 0.005f, 0.0165f,
              problem == "" ? Palette.Ok : b.ThrustToWeight < 1 || b.PropTooBigForMotor ? Palette.Bad : Palette.Warn,
              wrap: Width - 2 * M, s: FontStyles.Bold);
            y += 0.075f;

            T($"How these are worked out: hover power from actuator-disc momentum theory, √((mg)³ / 2ρA) with ρ = {DroneBuild.Rho} kg/m³, " +
              $"÷ an assumed figure of merit {DroneBuild.FigureOfMerit:0.00} and motor+ESC efficiency {DroneBuild.DriveEfficiency:0.00}, + {DroneBuild.AvionicsW:0} W avionics. " +
              $"Endurance uses {DroneBuild.UsableFraction * 100:0} % of rated energy (the rest is the landing reserve), in still air. " +
              "Category by all-up weight under the Drone Rules 2021. Part figures are typical of their class, not a specific product — " +
              "confirm with the real datasheets and a bench test (Hardware ▸ Drone compliance) before flying.",
              M, y, 0.0122f, Palette.TextFaint, wrap: Width - 2 * M);
            B("CLOSE", Width - M - 0.2f, Height - M - 0.058f, 0.2f, () => app.SetTool(AeroFleetApp.Tool.Build));
        }

        void BuildLive(AeroFleetApp app)
        {
            var title = T("HOW TO READ THE TABLE", M, 0.045f, 0.022f, Palette.Accent, s: FontStyles.Bold);
            title.characterSpacing = 2;
            float y = 0.1f;
            void Item(Color swatch, string head, string body)
            {
                R(M, y - 0.012f, 0.024f, 0.024f, swatch);
                T(head, M + 0.04f, y, 0.0175f, Palette.Text, s: FontStyles.Bold);
                T(body, M + 0.04f, y + 0.017f, 0.0145f, Palette.TextDim, wrap: Width - 2 * M - 0.04f);
                y += 0.072f;
            }
            Item(Palette.Ok, "Drone within limits", "Every live margin is outside its watch band.");
            Item(Palette.Warn, "Drone on watch", "A margin is inside its watch band (e.g. < 35 m spare separation, < 40 Wh above reserve).");
            Item(Palette.Bad, "Violation", "The CBF gate reports a margin below zero for this drone.");
            Item(Palette.Warn, "Separation beam", "Drawn between two drones inside the watch band, labelled horizontal ↔ and vertical ↕ distance.");
            Item(Palette.Bad, "Red column = DGCA no-fly zone", "Flight prohibited at every altitude. Yellow column = airport permission zone, ceiling 60 m.");
            Item(Palette.Accent, "Ceilings", "Blue plane = AeroFleet ops ceiling (100 m); red plane = DGCA legal limit (120 m AGL).");
            Item(Palette.Bad, "Predicted conflict", "Where two planned trajectories will pass closer than 15 m within the next 2 min: rings mark both drones' future positions.");

            y += 0.01f;
            Heading("SELECTED DRONE", y);
            y += 0.03f;
            var d = app.Selected != null && app.Live != null && app.Live.Drones.TryGetValue(app.Selected, out var sel) ? sel : null;
            if (d == null)
            {
                T("Point at a drone (or its tag) and pull the trigger. At 1 km / 2 km the table re-centres on it.",
                  M, y, 0.0155f, Palette.TextDim, wrap: Width - 2 * M);
                return;
            }
            var st = Vocab.Status(d);
            T($"{app.Selected}  ·  {d.State?.Replace('_', ' ')}  ·  {d.Zone} zone", M, y, 0.0175f, Vocab.StatusColor(st), s: FontStyles.Bold);
            y += 0.034f;
            string[] lines =
            {
                $"Order {Vocab.ShortId(d.OrderId) ?? "—"}  ·  payload {d.PayloadKg:0.0} kg",
                $"Altitude {d.AltitudeM:0} m (ceiling here {d.AltitudeCeilingM:0} m)  ·  heading {(d.HeadingDeg != null ? d.HeadingDeg.Value.ToString("0") + "°" : "—")}",
                d.NearestDroneId != null
                    ? $"Nearest {Vocab.ShortId(d.NearestDroneId)}: {GeoMath.FormatDistance(d.NearestHorizontalM)} horizontal, {d.NearestVerticalM:0} m vertical"
                    : "No other drone airborne",
                d.Progress == null ? "No planned trajectory (live telemetry only)"
                    : d.Phase == "LANDED" ? "Landed at the destination"
                    : $"{d.Phase?.ToLowerInvariant()} · {d.Progress * 100:0} % of the route, {GeoMath.FormatDistance(d.RemainingM ?? 0)} to go · lands in {DroneView.Clock(d.EtaS ?? 0)}",
                $"Position source: {Vocab.SourceLabel(d.PositionSource)}  ·  C2 link: {d.LinkMode}",
            };
            foreach (var line in lines) { T(line, M, y, 0.0155f, Palette.TextDim); y += 0.028f; }
        }
    }
}
