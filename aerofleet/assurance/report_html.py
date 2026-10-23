"""A self-contained, printable page for one flight review (print it to PDF from any browser).

No template engine and no external files: every value is HTML-escaped here, including file names and
parameter names that came from uploads. The page states whether the stored review still matches the
entry in the signed record.
"""
from __future__ import annotations

from html import escape as e
from typing import Any, Dict, Optional

KIND = {"off_route": "Off the planned route", "off_altitude": "Off the planned height", "in_no_fly_zone": "Inside a no-fly zone"}
SEVERITY = {"CRITICAL": "Safety-critical", "HIGH": "Flight limit", "TUNING": "Tuning", "INFO": "Other"}
CSS = ("body{font:14px/1.45 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#111;max-width:820px;margin:32px auto;padding:0 20px}"
       "h1{font-size:22px;margin:0 0 4px}h2{font-size:15px;margin:26px 0 8px;border-bottom:1px solid #ccc;padding-bottom:4px}"
       "table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:5px 10px 5px 0;border-bottom:1px solid #e5e5e5;vertical-align:top}"
       "th{color:#555;font-weight:600}.muted{color:#666;font-size:12px}.bad{color:#b91c1c;font-weight:700}.ok{color:#15803d;font-weight:700}"
       ".mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;word-break:break-all}@media print{body{margin:0}}")


def _clock(s: float) -> str:
    t = max(0, int(round(s)))          # round the total first: 299.9 s is 5:00, not 4:60
    return f"{t // 60}:{t % 60:02d}"


def _table(head, rows) -> str:
    if not rows:
        return ""
    return ("<table><thead><tr>" + "".join(f"<th>{e(h)}</th>" for h in head) + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table>")


def flight_review_html(review: Dict[str, Any], ledger_entry: Optional[Dict[str, Any]], matches_record: Optional[bool]) -> str:
    r = review["report"]
    deviated = review["verdict"] == "DEVIATED"
    tol = r["tolerances"]
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Flight review {e(str(review['id']))} - {e(review['drone_id'])}</title><style>{CSS}</style></head><body>",
             f"<h1>Flight review: {e(review['drone_id'])}</h1>",
             f"<div class='muted'>Fleet {e(review['fleet'])} · review #{e(str(review['id']))} · uploaded {e(review['uploaded_at'])} UTC by {e(review['uploaded_by'])}</div>",
             f"<p><span class='{'bad' if deviated else 'ok'}'>{'Deviated from the plan' if deviated else 'Flew the plan'}</span> — "
             f"log <span class='mono'>{e(review.get('log_name') or '')}</span> compared with mission <span class='mono'>{e(review.get('plan_name') or '')}</span>.</p>",
             "<h2>Summary</h2>",
             _table(["Measure", "Value"], [
                 ["Flight time", e(_clock(r["flight_s"]))],
                 ["Furthest off route", f"{e(str(r['horizontal_m']['max']))} m (typical {e(str(r['horizontal_m']['median']))} m)"],
                 ["Furthest off planned height", f"{e(str(r['vertical_m']['max']))} m"],
                 ["Highest flown / planned", f"{e(str(r['max_height_m']['flown']))} m / {e(str(r['max_height_m']['planned']))} m"],
                 ["Positions read from the log", e(str(r["log"]["points"]))],
                 ["No-fly zones checked for", e(str(r.get("zones_checked") or "not checked"))]])]
    events = [[e(KIND.get(x["kind"], x["kind"])), e(_clock(x["start_s"])), f"{e(str(x['duration_s']))} s",
               "—" if x["kind"] == "in_no_fly_zone" else f"{e(str(x['max_m']))} m", f"{e(str(x['lat']))}, {e(str(x['lon']))}"] for x in r["episodes"]]
    events += [[f"Pilot took manual control ({e(m['mode'])})", e(_clock(m["start_s"])), f"{e(str(m['duration_s']))} s", "—", "—"] for m in r["manual_control"]]
    parts += ["<h2>What happened</h2>", _table(["What", "Starting at", "For", "Worst", "Where"], events) or "<p>No excursions and no manual takeovers.</p>"]
    changed = r.get("settings_changed_in_flight") or {"count": 0, "changes": []}
    if changed["count"]:
        rows = [[e(_clock(c["t_s"])), f"<span class='mono'>{e(c['name'])}</span>", e(SEVERITY.get(c["severity"], c["severity"])), e(f"{c['old']:g}"), e(f"{c['new']:g}")]
                for c in changed["changes"] if c["severity"] in ("CRITICAL", "HIGH")]
        parts += [f"<h2>Settings changed during the flight ({e(str(changed['count']))})</h2>",
                  _table(["At", "Setting", "Kind", "From", "To"], rows) or "<p>Only tuning and other minor settings changed.</p>",
                  "<p class='muted'>A setting changed and put back before landing does not show in the final settings.</p>"]
    timeline = r.get("evidence_timeline") or []
    if timeline:
        level = {"warning": "bad", "notice": "", "info": "muted"}
        rows = [[e(_clock(x["t_s"])), f"<span class='{level.get(x['level'], '')}'>{e(x['text'])}</span>"] for x in timeline]
        parts += ["<h2>Timeline from the log</h2>", _table(["At", "Event"], rows)]
        around = r.get("around_episodes") or []
        if around:
            parts += ["<p><b>Around each deviation</b> (from 30 s before it to its end):</p><ul>"
                      + "".join(f"<li>{e(KIND.get(a['kind'], a['kind']))} at {e(_clock(a['start_s']))}: {e(a['summary'])}</li>" for a in around)
                      + "</ul>",
                      "<p class='muted'>AeroFleet lists these facts but does not name a cause: on public PX4 crash logs a fixed rule "
                      "could not reliably tell a pilot error from an aircraft fault, so that judgement is left to a person.</p>"]
    dq = r.get("data_quality")
    if dq:
        def v(x, unit=""):
            return "not recorded" if x is None else f"{e(str(x))}{unit}"
        parts += ["<h2>Quality of the evidence</h2>", _table(["Measure", "Value"], [
            ["Position samples", f"{v(dq.get('position_rate_hz'), ' per second')} (longest gap {v(dq.get('longest_gap_s'), ' s')})"],
            ["GPS satellites (median)", v(dq.get("gps_satellites_median"))],
            ["GPS HDOP (median / worst)", f"{v(dq.get('gps_hdop_median'))} / {v(dq.get('gps_hdop_worst'))}"],
            ["Height measured as", e(str(dq.get("height_reference") or ""))],
            ["Times are", e(str(dq.get("clock") or ""))]]),
            f"<p class='muted'>{e(dq.get('note') or '')}</p>"]
    parts += ["<h2>How this was judged</h2>",
              f"<p class='muted'>Counted as a deviation beyond {e(str(tol['corridor_m']))} m sideways or {e(str(tol['altitude_m']))} m in height for "
              f"{e(str(tol['min_duration_s']))} s or more. These are the fleet's tolerances, not regulatory limits. Every figure was computed by "
              "deterministic code from the uploaded files; no language model was involved. "
              + " ".join(e(n) + "." for n in list(r.get("notes", [])) + list(r["log"].get("notes", []))) + "</p>",
              "<h2>Signed record</h2>"]
    if ledger_entry is None:
        parts.append("<p class='bad'>No entry in the signed record matches this review as it is stored now.</p>")
    else:
        parts.append(f"<p><span class='{'ok' if matches_record else 'bad'}'>{'This review matches' if matches_record else 'This review does NOT match'} "
                     f"entry #{e(str(ledger_entry['seq']))} of the signed record</span> (recorded {e(ledger_entry['created_at'])} UTC).</p>"
                     f"<p class='muted'>Fingerprint of the review: <span class='mono'>{e(ledger_entry['payload_sha256'])}</span><br>"
                     f"Entry fingerprint: <span class='mono'>{e(ledger_entry['entry_hash'])}</span></p>"
                     "<p class='muted'>This shows whether the record was altered afterwards. It does not prove the uploaded files were genuine.</p>")
    parts.append("</body></html>")
    return "".join(parts)
