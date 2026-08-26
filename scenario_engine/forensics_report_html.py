"""Self-contained HTML report rendering for the mass forensics evaluation
study (scenario_engine/mass_forensics_evaluation.py). No CDN dependencies
— inline CSS and hand-drawn inline SVG charts, so these render correctly
offline on the college PC with no charting library. Conservative
academic/technical-report register, since this is meant to accompany a
publication, not read as a product dashboard.

Chart colors are the first three slots of the validated default categorical
palette (blue/orange/aqua — see the dataviz skill's references/palette.md),
checked with its validator against this report's actual paper surface
(#fbfaf7): all CVD/normal-vision separation checks pass; aqua's contrast
against the surface sits under 3:1, which is why every mark also carries a
direct text-ink label rather than relying on the fill color alone (the
skill's documented "relief" mitigation for that WARN).
"""
from __future__ import annotations

import html
from typing import Dict, List, Optional, Tuple

# Fixed categorical assignment, never cycled — same three metrics (in this
# order) everywhere a chart appears in this report.
_SERIES_COLORS = {"precision": "#2a78d6", "recall": "#eb6834", "f1": "#1baf7a"}
_SERIES_LABELS = {"precision": "Precision", "recall": "Recall", "f1": "F1"}

_STYLE = """
:root {
  --ink: #1b2430; --ink-soft: #4a5568; --paper: #fbfaf7; --panel: #ffffff;
  --line: #dcd7cc; --accent: #6b3f2a; --accent-soft: #b9865f;
  --good: #2f6f4f; --warn: #a15c00; --bad: #a3352b;
  --mono: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
  --serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  --sans: "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink); font-family: var(--sans); line-height: 1.5; }
.page { max-width: 980px; margin: 0 auto; padding: 2.5rem 1.5rem 4rem; }
h1 { font-family: var(--serif); font-size: 1.9rem; margin: 0 0 0.2rem; }
h2 { font-family: var(--serif); font-size: 1.3rem; margin: 2.5rem 0 0.75rem; border-bottom: 1px solid var(--line); padding-bottom: 0.4rem; }
.subtitle { color: var(--ink-soft); font-size: 0.95rem; margin: 0 0 1.5rem; }
.banner { border-radius: 4px; padding: 0.9rem 1.1rem; font-weight: 600; margin-bottom: 1.5rem; font-size: 0.95rem; }
.banner.mock { background: #fff3e0; color: var(--warn); border: 1px solid #e0b060; }
.banner.real { background: #eef5ef; color: var(--good); border: 1px solid #9cc4a8; }
.meta-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.75rem; margin-bottom: 1rem; }
.meta-item { background: var(--panel); border: 1px solid var(--line); border-radius: 4px; padding: 0.6rem 0.8rem; }
.meta-item .label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-soft); }
.meta-item .value { font-family: var(--mono); font-size: 1.15rem; font-variant-numeric: tabular-nums; }
table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
th, td { text-align: left; padding: 0.5rem 0.6rem; border-bottom: 1px solid var(--line); font-variant-numeric: tabular-nums; }
th { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.03em; color: var(--ink-soft); font-weight: 600; }
tr:last-child td { border-bottom: none; }
.bar-track { background: #ece7db; border-radius: 3px; height: 10px; width: 100px; overflow: hidden; display: inline-block; vertical-align: middle; }
.bar-fill { height: 100%; background: var(--accent-soft); }
.bar-fill.f1 { background: var(--accent); }
.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 4px; background: var(--panel); }
.table-wrap table { margin: 0; }
.table-wrap th, .table-wrap td { white-space: nowrap; }
details { background: var(--panel); border: 1px solid var(--line); border-radius: 4px; margin-bottom: 0.5rem; padding: 0.6rem 0.9rem; }
summary { cursor: pointer; font-weight: 600; font-size: 0.9rem; }
.case-detail { margin-top: 0.6rem; font-size: 0.85rem; }
.case-detail dt { color: var(--ink-soft); font-size: 0.72rem; text-transform: uppercase; margin-top: 0.5rem; }
.case-detail dd { margin: 0.1rem 0 0; font-family: var(--mono); }
.pill { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }
.pill.contrib { background: #fbe9e7; color: var(--bad); }
.pill.not-contrib { background: #eef5ef; color: var(--good); }
.pill.uncertain { background: #f1ede2; color: var(--ink-soft); }
footer { margin-top: 3rem; font-size: 0.78rem; color: var(--ink-soft); border-top: 1px solid var(--line); padding-top: 1rem; }
a { color: var(--accent); }
.progress-track { background: #ece7db; border-radius: 4px; height: 18px; overflow: hidden; margin: 0.5rem 0 1.5rem; }
.progress-fill { height: 100%; background: var(--accent); display: flex; align-items: center; padding-left: 0.5rem; color: white; font-size: 0.72rem; font-family: var(--mono); }
.batch-list { list-style: none; padding: 0; margin: 0; }
.batch-list li { padding: 0.5rem 0; border-bottom: 1px solid var(--line); display: flex; justify-content: space-between; font-size: 0.9rem; }
.batch-list li:last-child { border-bottom: none; }
.chart-card { background: var(--panel); border: 1px solid var(--line); border-radius: 4px; padding: 1rem 1.2rem 0.6rem; margin-bottom: 1rem; }
.chart-legend { display: flex; gap: 1.2rem; margin-bottom: 0.4rem; font-size: 0.8rem; }
.chart-legend span { display: inline-flex; align-items: center; gap: 0.4rem; color: var(--ink-soft); }
.chart-legend i { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.chart-svg { width: 100%; height: auto; display: block; }
.chart-svg text { font-family: var(--sans); }
.chart-svg .grid { stroke: var(--line); stroke-width: 1; }
.chart-svg .axis-label { fill: var(--ink-soft); font-size: 10px; }
.chart-svg .row-label { fill: var(--ink); font-size: 12px; }
.chart-svg .value-label { fill: var(--ink-soft); font-size: 10px; }
.chart-svg .end-label { fill: var(--ink); font-size: 11px; font-weight: 600; }
.chart-note { font-size: 0.76rem; color: var(--ink-soft); margin: 0.3rem 0 0; }
"""


def _e(s: object) -> str:
    return html.escape(str(s))


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _bar(value: float, cls: str = "") -> str:
    pct = max(0.0, min(1.0, value)) * 100
    return f'<span class="bar-track"><span class="bar-fill {cls}" style="width:{pct:.1f}%"></span></span> {value:.3f}'


def _legend(keys: List[str]) -> str:
    items = "".join(
        f'<span><i style="background:{_SERIES_COLORS[k]}"></i>{_e(_SERIES_LABELS[k])}</span>' for k in keys
    )
    return f'<div class="chart-legend">{items}</div>'


def _grouped_bar_chart_svg(per_factor: Dict[str, Dict], width: int = 640) -> str:
    """Horizontal grouped bars, one row per factor, one bar per metric
    (precision/recall/F1) — long factor names read better as row labels
    than as rotated column ticks. Mark specs per the dataviz skill: <=24px
    thick bars (14px + 2px gaps here), 4px rounded data-end, square at the
    baseline, value at the tip."""
    rows = [(name, s) for name, s in per_factor.items() if "f1" in s]
    if not rows:
        return "<p>No scored factors yet.</p>"
    row_h, label_w, bar_h, gap = 60, 190, 14, 2
    plot_w = width - label_w - 46
    height = len(rows) * row_h + 24
    parts = [
        f'<svg class="chart-svg" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="Precision, recall, and F1 by factor">'
    ]
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        x = label_w + plot_w * frac
        parts.append(f'<line class="grid" x1="{x:.1f}" y1="4" x2="{x:.1f}" y2="{height - 18:.1f}"/>')
        parts.append(f'<text class="axis-label" x="{x:.1f}" y="{height - 6}" text-anchor="middle">{frac:.2f}</text>')
    y = 10.0
    for name, s in rows:
        cy = y + row_h / 2
        parts.append(f'<text class="row-label" x="{label_w - 10}" y="{cy + 4:.1f}" text-anchor="end">{_e(name)}</text>')
        by = y + (row_h - (bar_h * 3 + gap * 2)) / 2
        for i, metric in enumerate(("precision", "recall", "f1")):
            val = s[metric]
            bw = max(2.0, plot_w * max(0.0, min(1.0, val)))
            by_i = by + i * (bar_h + gap)
            parts.append(
                f'<rect x="{label_w}" y="{by_i:.1f}" width="{bw:.1f}" height="{bar_h}" rx="4" ry="4" '
                f'fill="{_SERIES_COLORS[metric]}"/>'
            )
            parts.append(f'<text class="value-label" x="{label_w + bw + 6:.1f}" y="{by_i + bar_h - 3:.1f}">{val:.2f}</text>')
        y += row_h
    parts.append("</svg>")
    return _legend(["precision", "recall", "f1"]) + "".join(parts)


def _batch_trend_line_chart_svg(batches_meta: List[Dict], width: int = 640, height: int = 220) -> str:
    """Precision/recall/F1 across batches, in batch order — the one place
    in this report where "change across the study so far" is the actual
    question, so a line chart (not bars) is the right form. Only rendered
    once >=2 batches are complete."""
    if len(batches_meta) < 2:
        return "<p>Need at least 2 completed batches to show a trend.</p>"
    pad_l, pad_r, pad_t, pad_b = 40, 92, 10, 22
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    n = len(batches_meta)

    def x_at(i: int) -> float:
        return pad_l + (plot_w * i / (n - 1) if n > 1 else 0.0)

    def y_at(v: float) -> float:
        return pad_t + plot_h * (1 - max(0.0, min(1.0, v)))

    parts = [
        f'<svg class="chart-svg" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="Precision, recall, and F1 trend across batches">'
    ]
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = y_at(frac)
        parts.append(f'<line class="grid" x1="{pad_l}" y1="{y:.1f}" x2="{pad_l + plot_w:.1f}" y2="{y:.1f}"/>')
        parts.append(f'<text class="axis-label" x="{pad_l - 8}" y="{y + 3:.1f}" text-anchor="end">{frac:.2f}</text>')
    step = max(1, n // 10)
    for i, b in enumerate(batches_meta):
        if i % step == 0 or i == n - 1:
            parts.append(f'<text class="axis-label" x="{x_at(i):.1f}" y="{height - 6}" text-anchor="middle">{b["batch_number"]}</text>')

    end_labels: List[Dict] = []  # collision-avoided after all lines are drawn — see below
    for metric in ("precision", "recall", "f1"):
        key = f"macro_{metric}" if metric != "f1" else "macro_f1"
        color = _SERIES_COLORS[metric]
        pts = [(x_at(i), y_at(b.get(key, 0.0))) for i, b in enumerate(batches_meta)]
        path = " ".join(f'{"M" if i == 0 else "L"}{x:.1f},{y:.1f}' for i, (x, y) in enumerate(pts))
        parts.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')
        lx, ly = pts[-1]
        parts.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="4" fill="{color}" stroke="var(--panel)" stroke-width="2"/>')
        end_labels.append({
            "x": lx, "y": ly, "text": f"{_SERIES_LABELS[metric]} {batches_meta[-1].get(key, 0.0):.2f}", "color": color,
        })

    # Converging series (a common, real case — e.g. every metric at 1.0)
    # would otherwise stack illegible text at the same point; separate
    # labels that are within one line-height of each other, in y order,
    # and give each a short leader line back to its actual point.
    end_labels.sort(key=lambda d: d["y"])
    min_gap = 13.0
    for i in range(1, len(end_labels)):
        min_y = end_labels[i - 1]["label_y"] + min_gap if "label_y" in end_labels[i - 1] else end_labels[i - 1]["y"] + min_gap
        end_labels[i - 1].setdefault("label_y", end_labels[i - 1]["y"])
        end_labels[i].setdefault("label_y", end_labels[i]["y"])
        if end_labels[i]["label_y"] < min_y:
            end_labels[i]["label_y"] = min_y
    for lbl in end_labels:
        label_y = lbl.get("label_y", lbl["y"])
        if abs(label_y - lbl["y"]) > 1.0:
            parts.append(f'<line x1="{lbl["x"] + 6:.1f}" y1="{lbl["y"]:.1f}" x2="{lbl["x"] + 8:.1f}" y2="{label_y:.1f}" stroke="{lbl["color"]}" stroke-width="1"/>')
        parts.append(f'<text class="end-label" x="{lbl["x"] + 9:.1f}" y="{label_y + 3:.1f}">{_e(lbl["text"])}</text>')
    parts.append("</svg>")
    return _legend(["precision", "recall", "f1"]) + "".join(parts)


def _mode_banner(mock_mode: bool) -> str:
    if mock_mode:
        return (
            '<div class="banner mock">MOCK MODE — pipeline sanity check only. The mock backend\'s domain '
            "assessment is a deterministic regex over CBF margin fields; a perfect score here proves the "
            "plumbing works, nothing about reasoning quality. Do not cite these numbers. Re-run with "
            "USE_MOCK_AGENTS unset against a real Ollama backend for a citable result.</div>"
        )
    return (
        '<div class="banner real">REAL MODE — scored against actual LLM inference on the configured '
        "Ollama backend. These numbers reflect genuine model reasoning quality.</div>"
    )


def _per_factor_table(per_factor: Dict[str, Dict]) -> str:
    rows = []
    for factor, s in per_factor.items():
        if "f1" not in s:
            rows.append(f'<tr><td>{_e(factor)}</td><td colspan="7" style="color:var(--ink-soft)">no cases target this factor</td></tr>')
            continue
        rows.append(
            f"<tr><td>{_e(factor)}</td>"
            f"<td>{s['n']}</td>"
            f"<td>{s['tp']}</td><td>{s['fp']}</td><td>{s['fn']}</td><td>{s['tn']}</td>"
            f"<td>{_bar(s['precision'])}</td>"
            f"<td>{_bar(s['recall'])}</td>"
            f"<td>{_bar(s['f1'], 'f1')}</td>"
            f"<td>{_pct(s.get('uncertain_rate', 0.0))}</td></tr>"
        )
    return (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>Factor</th><th>N</th><th>TP</th><th>FP</th><th>FN</th><th>TN</th>"
        "<th>Precision</th><th>Recall</th><th>F1</th><th>Uncertain</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
    )


def _category_table(category_breakdown: Dict[str, Dict]) -> str:
    rows = [
        f"<tr><td>{_e(cat)}</td><td>{s['n']}</td><td>{_bar(s['macro_f1'], 'f1') if s['macro_f1'] is not None else '—'}</td></tr>"
        for cat, s in category_breakdown.items()
    ]
    return (
        '<div class="table-wrap"><table><thead><tr><th>Category</th><th>N</th><th>Macro F1</th></tr></thead>'
        "<tbody>" + "".join(rows) + "</tbody></table></div>"
    )


def _latency_block(latency: Dict[str, float]) -> str:
    if not latency or latency.get("n", 0) == 0:
        return "<p>No timed calls yet.</p>"
    return (
        '<div class="meta-grid">'
        f'<div class="meta-item"><div class="label">Mean</div><div class="value">{latency["mean"]:.1f}s</div></div>'
        f'<div class="meta-item"><div class="label">Median</div><div class="value">{latency["median"]:.1f}s</div></div>'
        f'<div class="meta-item"><div class="label">P95</div><div class="value">{latency["p95"]:.1f}s</div></div>'
        f'<div class="meta-item"><div class="label">Max</div><div class="value">{latency["max"]:.1f}s</div></div>'
        "</div>"
    )


def _pill(verdict: str) -> str:
    cls = "contrib" if verdict == "CONTRIBUTED" else ("uncertain" if verdict == "UNCERTAIN" else "not-contrib")
    return f'<span class="pill {cls}">{_e(verdict)}</span>'


def _failure_examples(failure_examples: Dict[str, List[Dict]]) -> str:
    blocks = []
    for factor, examples in failure_examples.items():
        if not examples:
            continue
        cards = []
        for ex in examples:
            cards.append(
                "<details><summary>"
                f"{_e(ex['case_id'])} — {_e(ex['label'])} — predicted {_pill(ex['predicted'])} vs ground truth {_pill(ex['ground_truth'])}"
                "</summary><dl class=\"case-detail\">"
                f"<dt>Evidence</dt><dd style=\"font-family:var(--sans);font-weight:normal\">{_e(ex.get('evidence') or '—')}</dd>"
                "</dl></details>"
            )
        blocks.append(f"<h3 style='font-size:0.95rem;margin-top:1.2rem'>{_e(factor)}</h3>" + "".join(cards))
    return "".join(blocks) if blocks else "<p>No misclassifications recorded.</p>"


def render_batch_report(batch_meta: Dict, scores: Dict, mock_mode: bool) -> str:
    title = f"Batch {batch_meta['batch_number']:04d} — Mass Forensics Evaluation"
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{_e(title)}</title><style>{_STYLE}</style></head>
<body><div class="page">
<h1>{_e(title)}</h1>
<p class="subtitle">Fleet Incident Forensics Council — ground-truth-derived accuracy study.
Cases {batch_meta['first_case_id']}–{batch_meta['last_case_id']} ({batch_meta['n_in_batch']} incidents).</p>
{_mode_banner(mock_mode)}
<div class="meta-grid">
<div class="meta-item"><div class="label">Attempted this run</div><div class="value">{batch_meta['n_attempted']}</div></div>
<div class="meta-item"><div class="label">Already complete</div><div class="value">{batch_meta['n_skipped']}</div></div>
<div class="meta-item"><div class="label">Excluded (failed retries)</div><div class="value">{batch_meta['n_excluded']}</div></div>
<div class="meta-item"><div class="label">Macro F1 (this batch)</div><div class="value">{scores['macro_f1']:.3f}</div></div>
</div>
<h2>Per-factor scores</h2>
<div class="chart-card">{_grouped_bar_chart_svg(scores['per_factor'])}</div>
{_per_factor_table(scores['per_factor'])}
<h2>Category breakdown</h2>
{_category_table(scores['category_breakdown'])}
<h2>Call latency</h2>
{_latency_block(scores['latency'])}
<h2>Failure examples</h2>
{_failure_examples(scores['failure_examples'])}
<footer>Methodology: precision/recall/F1 per factor, macro-averaged, ground truth derived directly from
synthesized CBF safety margins — mirrors "UAV Accident Forensics via HFACS-LLM Reasoning" (Drones 9(10):704, 2025).
Generated by scenario_engine/mass_forensics_evaluation.py.</footer>
</div></body></html>"""


def render_aggregate_index(run_config: Dict, batches_meta: List[Dict], scores: Dict, mock_mode: bool) -> str:
    completed = scores.get("n_completed", 0)
    target = run_config["target"]
    pct = completed / target if target else 0.0
    batch_rows = "".join(
        f'<li><span><a href="reports/batch_{b["batch_number"]:04d}.html">Batch {b["batch_number"]:04d}</a> '
        f'({b["n_in_batch"]} cases)</span><span>macro F1 {b["macro_f1"]:.3f}</span></li>'
        for b in batches_meta
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Mass Forensics Evaluation — Study Index</title><style>{_STYLE}</style></head>
<body><div class="page">
<h1>Mass Forensics Evaluation</h1>
<p class="subtitle">Fleet Incident Forensics Council — {target:,}-incident ground-truth-derived accuracy study.
Seed {run_config['seed']}, batch size {run_config['batch_size']}.</p>
{_mode_banner(mock_mode)}
<div class="progress-track"><div class="progress-fill" style="width:{pct*100:.1f}%">{completed:,} / {target:,} ({pct*100:.1f}%)</div></div>
<div class="meta-grid">
<div class="meta-item"><div class="label">Completed</div><div class="value">{completed:,}</div></div>
<div class="meta-item"><div class="label">Excluded</div><div class="value">{scores.get('n_excluded', 0):,}</div></div>
<div class="meta-item"><div class="label">Pending</div><div class="value">{max(target - completed, 0):,}</div></div>
<div class="meta-item"><div class="label">Macro F1 (pooled)</div><div class="value">{scores['macro_f1']:.3f}</div></div>
<div class="meta-item"><div class="label">Macro Precision</div><div class="value">{scores['macro_precision']:.3f}</div></div>
<div class="meta-item"><div class="label">Macro Recall</div><div class="value">{scores['macro_recall']:.3f}</div></div>
</div>
<h2>Trend across batches</h2>
<div class="chart-card">{_batch_trend_line_chart_svg(batches_meta)}
<p class="chart-note">Each point is that batch's own macro score, not cumulative — a stable line across
batches is what "the model isn't drifting as the study covers more of the case space" looks like.</p></div>
<h2>Per-factor scores (pooled across all completed batches)</h2>
<div class="chart-card">{_grouped_bar_chart_svg(scores['per_factor'])}</div>
{_per_factor_table(scores['per_factor'])}
<h2>Category breakdown</h2>
{_category_table(scores['category_breakdown'])}
<h2>Call latency (pooled)</h2>
{_latency_block(scores['latency'])}
<h2>Batches</h2>
<ul class="batch-list">{batch_rows}</ul>
<footer>Methodology: precision/recall/F1 per factor, macro-averaged, ground truth derived directly from
synthesized CBF safety margins — mirrors "UAV Accident Forensics via HFACS-LLM Reasoning" (Drones 9(10):704, 2025).
Extends scenario_engine/incident_forensics_evaluation.py's 12-case methodology to {target:,} systematically
generated cases across full combinatorial coverage of 5 real, margin-grounded factors.
Generated by scenario_engine/mass_forensics_evaluation.py.</footer>
</div></body></html>"""
