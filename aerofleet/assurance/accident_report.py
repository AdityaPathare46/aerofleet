"""Accident record prepared for Digital Sky (Drone Rules 2021, Rule 30 — 48-hour reporting dossier).

Under Rule 30 of India's Drone Rules 2021 (G.S.R. 589(E)), an unmanned aircraft system accident must be
reported to the Director General on the Digital Sky platform within 48 hours. AeroFleet is not an official
DGCA form and cannot submit to Digital Sky; this module assembles a self-contained, tamper-evident,
print-to-PDF operator record from facts already stored locally:

  * Aircraft & legal identity: DGCA UIN & Digital Sky attestation (Rule 14), Type Certificate (Rule 8;
    exemptions Rule 13), third-party liability insurance policy & validity (Rule 44), assigned pilot &
    Remote Pilot Certificate (Rule 31 / Rule 34).
  * Statutory 48-hour deadline: UTC + IST event timestamp, exact 48 h filing deadline, and hours left/overdue.
  * Flight facts & deterministic evidence timeline: takeoff & last-known GPS coordinates, duration, max height,
    plan deviation (if reconciled), in-flight parameter changes, evidence quality, and timeline — with an
    explicit statement that AeroFleet never assigns blame or cause.
  * Maintenance & grounding logbook: recent maintenance entries and post-incident grounding status.
  * Cryptographic integrity block: Ed25519 ledger entry #, SHA-256 payload & entry hashes, live DB match,
    and instructions for attaching a DigiCert-pinned RFC 3161 TSA-timestamped receipt.

Pure deterministic Python, zero AI, all user/file strings HTML-escaped.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape as e
from typing import Any, Dict, List, Optional

IST = timezone(timedelta(hours=5, minutes=30))
STATUTORY_HOURS = 48        # Drone Rules, 2021 (G.S.R. 589(E)), Rule 30: Digital Sky accident report within 48 hours
AAIB_NOTIFY_HOURS = 24      # Aircraft (Investigation of Accidents and Incidents) Rules, 2025: AAIB/DGCA notice within 24 hours

CSS = (
    "body{font:13.5px/1.45 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#111;max-width:860px;"
    "margin:28px auto;padding:0 20px}h1{font-size:21px;margin:0 0 4px}h2{font-size:14.5px;margin:22px 0 8px;"
    "border-bottom:1.5px solid #cbd5e1;padding-bottom:3px;text-transform:uppercase;letter-spacing:.03em;color:#0f172a}"
    "table{border-collapse:collapse;width:100%;font-size:13px;margin-bottom:8px}th,td{text-align:left;"
    "padding:5px 10px 5px 0;border-bottom:1px solid #e2e8f0;vertical-align:top}th{color:#475569;font-weight:600;width:34%}"
    ".banner{padding:10px 14px;border-radius:6px;margin:12px 0;font-size:13px}"
    ".banner-red{background:#fef2f2;border-left:4px solid #dc2626;color:#991b1b}"
    ".banner-amber{background:#fffbeb;border-left:4px solid #d97706;color:#92400e}"
    ".banner-green{background:#f0fdf4;border-left:4px solid #16a34a;color:#166534}"
    ".muted{color:#64748b;font-size:12px}.bad{color:#b91c1c;font-weight:700}.ok{color:#15803d;font-weight:700}"
    ".mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;word-break:break-all}"
    "@media print{body{margin:0}.no-print{display:none}}"
)


def _parse_utc(iso: Optional[str]) -> Optional[datetime]:
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _fmt_dt(dt: Optional[datetime]) -> Dict[str, Optional[str]]:
    if dt is None:
        return {"utc": None, "ist": None}
    return {
        "utc": dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "ist": dt.astimezone(IST).strftime("%Y-%m-%d %H:%M IST"),
    }


def _clock(s: float) -> str:
    t = max(0, int(round(s)))
    return f"{t // 60}:{t % 60:02d}"


def build_accident_dossier(
    fleet: str,
    drone_id: str,
    registration: Optional[Dict[str, Any]],
    compliance: Optional[Dict[str, Any]],
    review: Optional[Dict[str, Any]],
    maintenance_entries: List[Dict[str, Any]],
    grounded: Optional[Dict[str, Any]],
    ledger_entry: Optional[Dict[str, Any]],
    matches_record: Optional[bool],
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Assemble structured DGCA Rule 45 48-hour accident/incident dossier from recorded facts."""
    now = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rep = (review or {}).get("report") or {}
    event_iso = (
        (grounded or {}).get("done_at")
        or (rep.get("vibration") or {}).get("flown_at")
        or (review or {}).get("uploaded_at")
    )
    event_dt = _parse_utc(event_iso)
    deadline_dt = event_dt + timedelta(hours=STATUTORY_HOURS) if event_dt else None
    aaib_dt = event_dt + timedelta(hours=AAIB_NOTIFY_HOURS) if event_dt else None
    hours_left = round((deadline_dt - now).total_seconds() / 3600.0, 1) if deadline_dt else None
    aaib_hours_left = round((aaib_dt - now).total_seconds() / 3600.0, 1) if aaib_dt else None
    deadline_status = (
        "UNKNOWN" if hours_left is None else ("OVERDUE" if hours_left < 0 else ("URGENT" if hours_left <= 12 else "WITHIN_48H"))
    )

    track = (rep.get("replay") or {}).get("track") or []
    takeoff = (
        {"lat": round(float(track[0][1]), 6), "lon": round(float(track[0][2]), 6)}
        if track and len(track[0]) >= 3
        else None
    )
    last_pos = (
        {"lat": round(float(track[-1][1]), 6), "lon": round(float(track[-1][2]), 6),
         "alt_m": round(float(track[-1][3]), 1) if len(track[-1]) >= 4 else None}
        if track and len(track[-1]) >= 3
        else None
    )

    return {
        "rule": (
            "Drone Rules, 2021 (G.S.R. 589(E)), Rule 30 (48-hour Digital Sky accident report) & "
            "Aircraft (Investigation of Accidents and Incidents) Rules, 2025 (24-hour AAIB/DGCA notification for UAS; no-blame safety investigation)"
        ),
        "generated_at": _fmt_dt(now),
        "fleet": fleet,
        "simulated_fleet": fleet == "pune-agri",
        "drone_id": drone_id,
        "event_time": _fmt_dt(event_dt),
        "deadline": {
            "statutory_hours": STATUTORY_HOURS,
            "due": _fmt_dt(deadline_dt),
            "hours_remaining": hours_left,
            "status": deadline_status,
            "aaib_2025_hours": AAIB_NOTIFY_HOURS,
            "aaib_2025_due": _fmt_dt(aaib_dt),
            "aaib_2025_hours_remaining": aaib_hours_left,
        },
        "aircraft": {
            "uin": (registration or {}).get("uin"),
            "uin_status": (registration or {}).get("status") or "NONE",
            "uin_verified_by": (registration or {}).get("verified_by"),
            "type_certificate_no": (compliance or {}).get("type_certificate_no"),
            "insurance_policy": (compliance or {}).get("insurance_policy"),
            "insurance_insurer": (compliance or {}).get("insurance_insurer"),
            "insurance_valid_until": (compliance or {}).get("insurance_valid_until"),
            "pilot_name": (compliance or {}).get("pilot_name"),
            "pilot_rpc_no": (compliance or {}).get("pilot_rpc_no"),
            "pilot_rpc_valid_until": (compliance or {}).get("pilot_rpc_valid_until"),
        },
        "grounded": grounded,
        "flight": None if review is None else {
            "review_id": review.get("id"),
            "verdict": review.get("verdict"),
            "log_name": review.get("log_name"),
            "plan_name": review.get("plan_name"),
            "flight_s": rep.get("flight_s"),
            "max_height_m": (rep.get("max_height_m") or {}).get("flown"),
            "takeoff": takeoff,
            "last_known_position": last_pos,
            "episodes": rep.get("episodes") or [],
            "manual_control": rep.get("manual_control") or [],
            "settings_changed_in_flight": (rep.get("settings_changed_in_flight") or {}).get("changes") or [],
            "evidence_timeline": rep.get("evidence_timeline") or [],
            "data_quality": rep.get("data_quality"),
            "input_files": rep.get("input_files"),
        },
        "maintenance_history": sorted(maintenance_entries, key=lambda m: str(m.get("done_at") or ""), reverse=True)[:10],
        "ledger": None if ledger_entry is None else {
            "seq": ledger_entry.get("seq"),
            "created_at": ledger_entry.get("created_at"),
            "payload_sha256": ledger_entry.get("payload_sha256"),
            "entry_hash": ledger_entry.get("entry_hash"),
            "matches_record": matches_record,
        },
        "disclaimer": (
            "Operator-prepared record generated locally by AeroFleet for Digital Sky Rule 30 filing (48 h) and "
            "AAIB/DGCA notification under the Aircraft (Investigation of Accidents and Incidents) Rules, 2025 (24 h; "
            "explicitly a no-blame safety-prevention investigation aligned with ICAO Annex 13). Not an official DGCA/AAIB "
            "form. AeroFleet lists deterministic telemetry facts only and never attributes pilot or aircraft blame."
        ),
    }


def _kv_table(rows: List[List[str]]) -> str:
    return (
        "<table><tbody>"
        + "".join(f"<tr><th>{e(k)}</th><td>{v}</td></tr>" for k, v in rows)
        + "</tbody></table>"
    )


def accident_dossier_html(d: Dict[str, Any]) -> str:
    """Render a self-contained, print-to-PDF HTML dossier for DGCA Rule 45 / insurer submission."""
    dl = d["deadline"]
    if dl["status"] == "OVERDUE":
        banner_cls = "banner-red"
        banner_txt = (
            f"<b>48-hour statutory deadline PASSED</b> ({abs(dl['hours_remaining']):.1f} h overdue — "
            f"due {e(dl['due']['ist'] or '')} / {e(dl['due']['utc'] or '')}). File immediately on Digital Sky."
        )
    elif dl["status"] in ("URGENT", "WITHIN_48H"):
        banner_cls = "banner-amber" if dl["status"] == "URGENT" else "banner-green"
        aaib_part = (
            f"<br><b>2025 Accident Investigation Rules (AAIB/DGCA 24 h notice):</b> "
            + (f"<b>{abs(dl['aaib_2025_hours_remaining']):.1f} h overdue</b>" if dl["aaib_2025_hours_remaining"] < 0
               else f"{dl['aaib_2025_hours_remaining']:.1f} h remaining")
            + f" (due {e(dl['aaib_2025_due']['ist'] or '')})."
            if dl.get("aaib_2025_hours_remaining") is not None else ""
        )
        banner_txt = (
            f"<b>Drone Rules 2021 Rule 30 (Digital Sky 48 h report):</b> {dl['hours_remaining']:.1f} hours remaining — "
            f"due by <b>{e(dl['due']['ist'] or '')}</b> ({e(dl['due']['utc'] or '')}).{aaib_part}"
        )
    else:
        banner_cls = "banner-amber"
        banner_txt = "<b>Event time not recorded</b> — verify exact UTC/IST occurrence time before filing on Digital Sky."

    ac = d["aircraft"]
    fl = d["flight"]
    gr = d["grounded"]
    led = d["ledger"]

    sim_banner = (
        "<div class='banner banner-amber'><b>SIMULATED DEMO FLEET (ArduPilot SITL):</b> This record was generated from "
        "simulated autopilot firmware logs for demonstration, not a real field accident.</div>"
        if d.get("simulated_fleet") else ""
    )

    parts = [
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>Accident Record for Digital Sky (Rule 30) — {e(d['drone_id'])}</title><style>{CSS}</style></head><body>",
        f"<h1>Accident Record Prepared for Digital Sky: {e(d['drone_id'])}</h1>",
        f"<div class='muted'>{e(d['rule'])} · Fleet {e(d['fleet'])} · Generated {e(d['generated_at']['ist'] or '')} ({e(d['generated_at']['utc'] or '')})</div>",
        sim_banner,
        f"<div class='banner {banner_cls}'>{banner_txt}</div>",
        "<h2>1. Aircraft, Insurance &amp; Pilot Credentials</h2>",
        _kv_table([
            ["Drone ID / Fleet", f"{e(d['drone_id'])} ({e(d['fleet'])})"],
            ["DGCA UIN (Rule 14)", f"<span class='mono'>{e(ac['uin'] or 'NOT RECORDED')}</span> ({e(ac['uin_status'])})"],
            ["Type Certificate / DAN (Rule 8; exemptions Rule 13)", e(ac["type_certificate_no"] or "Not recorded")],
            ["Third-Party Insurance (Rule 44)",
             e(f"{ac['insurance_policy']} — {ac['insurance_insurer'] or 'Insurer not recorded'} (valid until {ac['insurance_valid_until'] or 'not set'})")
             if ac["insurance_policy"] else "<span class='bad'>Not recorded</span>"],
            ["Assigned Pilot &amp; RPC (Rule 31 / Rule 34)",
             e(f"{ac['pilot_name'] or 'Unnamed'} — RPC {ac['pilot_rpc_no']} (valid until {ac['pilot_rpc_valid_until'] or 'not set'})")
             if ac["pilot_rpc_no"] else e(ac["pilot_name"] or "Not recorded")],
            ["Grounding status",
             f"<span class='bad'>GROUNDED</span> ({e(str(gr.get('done_at', ''))[:16])} UTC — {e(str(gr.get('note') or gr.get('action') or ''))})"
             if gr else "Not currently grounded in maintenance logbook"],
        ]),
    ]

    parts.append("<h2>2. Occurrence &amp; Flight Telemetry Summary</h2>")
    if fl is None:
        parts.append("<p class='muted'>No reviewed flight log is stored for this drone yet.</p>")
    else:
        to = fl["takeoff"]
        lp = fl["last_known_position"]
        parts.append(_kv_table([
            ["Occurrence / Flight time", f"{e(d['event_time']['ist'] or 'Unknown')} ({e(d['event_time']['utc'] or 'Unknown')})"],
            ["Flight log / Mission plan",
             f"<span class='mono'>{e(fl['log_name'] or '')}</span>"
             + (f" vs <span class='mono'>{e(fl['plan_name'])}</span> ({e(fl['verdict'])})" if fl["plan_name"] else f" ({e(fl['verdict'])}) ORIGINAL LOG")],
            ["Flight duration / Max height",
             f"{e(_clock(fl['flight_s'] or 0))} · {e(str(fl['max_height_m']))} m above take-off"],
            ["Take-off coordinates (WGS84)", f"{to['lat']}, {to['lon']}" if to else "Not recorded"],
            ["Last recorded position (WGS84)",
             f"{lp['lat']}, {lp['lon']} (alt {lp['alt_m']} m)" if lp else "Not recorded"],
            ["Log SHA-256 fingerprint",
             f"<span class='mono'>{e(str(((fl.get('input_files') or {}).get('log') or {}).get('sha256') or '—'))}</span>"],
        ]))

        tl = fl["evidence_timeline"]
        if tl:
            lvl = {"warning": "bad", "notice": "", "info": "muted"}
            rows = "".join(
                f"<tr><td style='width:80px'>{e(_clock(x['t_s']))}</td><td class='{lvl.get(x.get('level', ''), '')}'>{e(x['text'])}</td></tr>"
                for x in tl
            )
            parts.append("<h2>3. Deterministic Telemetry Timeline (No Cause Attributed)</h2>")
            parts.append(f"<table><thead><tr><th>At</th><th>Recorded autopilot / telemetry fact</th></tr></thead><tbody>{rows}</tbody></table>")
            parts.append("<p class='muted'>AeroFleet reports time-ordered telemetry facts only. In the underlying 590-crash study, neither rules nor ML separated pilot from aircraft blame better than chance (BA 0.47), so causation is left to human investigators.</p>")

        ch = [c for c in fl["settings_changed_in_flight"] if c.get("severity") in ("CRITICAL", "HIGH")]
        if ch:
            rows = "".join(
                f"<tr><td>{e(_clock(c['t_s']))}</td><td class='mono'>{e(c['name'])}</td><td>{e(str(c['old']))} → {e(str(c['new']))}</td></tr>"
                for c in ch
            )
            parts.append("<h2>4. Safety-Critical Settings Changed In Flight</h2>")
            parts.append(f"<table><thead><tr><th>At</th><th>Parameter</th><th>Change</th></tr></thead><tbody>{rows}</tbody></table>")

    parts.append("<h2>5. Recent Maintenance &amp; Inspection Logbook</h2>")
    if not d["maintenance_history"]:
        parts.append("<p class='muted'>No maintenance entries recorded for this drone.</p>")
    else:
        rows = "".join(
            f"<tr><td style='width:140px'>{e(str(m.get('done_at', ''))[:16])}</td><td><b>{e(str(m.get('action', '')))}</b></td>"
            f"<td>{e(str(m.get('note') or ''))}</td><td>{e(str(m.get('done_by') or ''))}</td></tr>"
            for m in d["maintenance_history"]
        )
        parts.append(f"<table><thead><tr><th>UTC</th><th>Action</th><th>Note</th><th>By</th></tr></thead><tbody>{rows}</tbody></table>")

    parts.append("<h2>6. Cryptographic Integrity &amp; Auditor Verification</h2>")
    if led is None:
        parts.append("<p class='bad'>No matching signed ledger entry found for the latest review.</p>")
    else:
        match_html = (
            "<span class='ok'>VERIFIED — stored review matches signed ledger entry</span>"
            if led["matches_record"]
            else "<span class='bad'>MISMATCH — stored review does NOT match signed ledger entry</span>"
        )
        parts.append(_kv_table([
            ["Signed ledger entry", f"#{e(str(led['seq']))} ({e(str(led['created_at']))} UTC) — {match_html}"],
            ["Review SHA-256", f"<span class='mono'>{e(str(led['payload_sha256']))}</span>"],
            ["Ledger entry hash", f"<span class='mono'>{e(str(led['entry_hash']))}</span>"],
            ["External proof", "Attach the exported Ed25519 auditor bundle and RFC 3161 TSA-timestamped receipt from Fleet Assurance → Signed record."],
        ]))

    parts.append(f"<p class='muted' style='margin-top:18px;border-top:1px solid #e2e8f0;padding-top:10px'>{e(d['disclaimer'])}</p>")
    parts.append("</body></html>")
    return "".join(parts)
