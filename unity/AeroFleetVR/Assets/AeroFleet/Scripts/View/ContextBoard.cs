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
            string key = app.Mode == ViewMode.Replay
                ? "replay:" + (app.Scene?.IncidentId ?? "none")
                : "live:" + (app.Selected == null ? "" : app.Selected + ":" + (app.Live?.GeneratedAt ?? 0));
            if (key == builtFor) return;
            builtFor = key;

            if (content != null) Destroy(content.gameObject);
            content = new GameObject("Content").transform;
            content.SetParent(transform, false);
            if (app.Mode == ViewMode.Replay) BuildReplay(app.Scene); else BuildLive(app);
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
                d.Progress != null ? (d.Arrived ? "Arrived, holding" : $"Leg {d.Progress * 100:0} % complete, {GeoMath.FormatDistance(d.RemainingM ?? 0)} to go") : "No active leg",
                $"Position source: {Vocab.SourceLabel(d.PositionSource)}  ·  C2 link: {d.LinkMode}",
            };
            foreach (var line in lines) { T(line, M, y, 0.0155f, Palette.TextDim); y += 0.028f; }
        }
    }
}
