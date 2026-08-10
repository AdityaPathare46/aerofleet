"""
satellite_tracker.py — Live Satellite Position Tracker
=======================================================
Fetches TLE data from the public TLE API (tle.ivanstanojevic.me) and
propagates positions using SGP4/SDP4.

Primary API : https://tle.ivanstanojevic.me  (free, no auth, JSON)
Physics     : SGP4 via python-sgp4 (Brandon Rhodes, MIT licence)
"""
from __future__ import annotations

import math, time, threading, requests
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from sgp4.api import Satrec, jday

# ─────────────────────────────────────────────────────────────────────────────
# Public API: tle.ivanstanojevic.me
#   /api/tle/{NORAD_CAT_ID}          → single satellite
#   /api/tle/?search=<name>&limit=N  → search by name
# Returns JSON with keys: name, line1, line2
# ─────────────────────────────────────────────────────────────────────────────
_TLE_API_BASE = "https://tle.ivanstanojevic.me/api/tle"

# Group definitions: human label → search keyword + NORAD IDs for common groups
# Approach: search the TLE API by name keyword, works brilliantly for Starlink etc.
CONFIRMED_GROUPS: Dict[str, Dict] = {
    "Space Stations":      {"search": "ISS",      "exact_ids": [25544, 48274]},
    "Starlink":            {"search": "STARLINK",  "exact_ids": [], "limit": 200},
    "GPS Operational":     {"search": "GPS",       "exact_ids": [], "limit": 60},
    "GLONASS":             {"search": "GLONASS",   "exact_ids": [], "limit": 50},
    "Galileo":             {"search": "GALILEO",   "exact_ids": [], "limit": 50},
    "OneWeb":              {"search": "ONEWEB",    "exact_ids": [], "limit": 100},
    "Weather Satellites":  {"search": "NOAA",      "exact_ids": [], "limit": 40},
    "Scientific Sats":     {"search": "TERRA",     "exact_ids": [25994, 27424, 33591]},
    "CubeSats":            {"search": "CUBESAT",   "exact_ids": [], "limit": 100},
    "Iridium":             {"search": "IRIDIUM",   "exact_ids": [], "limit": 80},
    "Active GEO (Intelsat)":{"search": "INTELSAT", "exact_ids": [], "limit": 50},
    "Hubble Space Telescope":{"search": "HST",     "exact_ids": [20580]},
}

# ── Module-level cache ───────────────────────────────────────────────────────
_cache_lock: threading.Lock                     = threading.Lock()
_tle_cache: Dict[str, Tuple[float, List[dict]]] = {}
CACHE_TTL_SECONDS: int                          = 300   # 5 minutes


def _fetch_group_tles(group_key: str, limit: int = 500) -> List[Tuple[str, str, str]]:
    """
    Fetch TLEs for a named group from tle.ivanstanojevic.me API.
    Returns list of (name, line1, line2).
    """
    cfg     = CONFIRMED_GROUPS.get(group_key, {"search": group_key, "exact_ids": []})
    keyword = cfg.get("search", group_key)
    api_limit = min(limit, cfg.get("limit", limit))
    headers = {"User-Agent": "SpaceMissionArchitect/2.0"}
    results: List[Tuple[str, str, str]] = []

    # Fetch by search keyword (paginated up to api_limit)
    page   = 1
    pg_size = min(api_limit, 100)
    while len(results) < api_limit:
        url  = f"{_TLE_API_BASE}/?search={keyword}&page-size={pg_size}&page={page}"
        try:
            r = requests.get(url, timeout=12, headers=headers)
            if r.status_code != 200:
                break
            data = r.json()
            members = data.get("member", [])
            if not members:
                break
            for sat in members:
                nm = sat.get("name", "")
                l1 = sat.get("line1", "")
                l2 = sat.get("line2", "")
                if l1.startswith("1 ") and l2.startswith("2 "):
                    results.append((nm, l1, l2))
            # Stop if we got fewer than requested (last page)
            if len(members) < pg_size:
                break
            page += 1
        except Exception:
            break

    # Fetch exact NORAD IDs (e.g. ISS, HST)
    for norad_id in cfg.get("exact_ids", []):
        if any(t[1][2:7].strip() == str(norad_id).strip() for t in results):
            continue   # already in list
        try:
            r = requests.get(f"{_TLE_API_BASE}/{norad_id}", timeout=8, headers=headers)
            if r.status_code == 200:
                sat = r.json()
                l1  = sat.get("line1", "")
                l2  = sat.get("line2", "")
                nm  = sat.get("name", f"NORAD-{norad_id}")
                if l1.startswith("1 ") and l2.startswith("2 "):
                    results.insert(0, (nm, l1, l2))
        except Exception:
            pass

    return results[:api_limit]


def _parse_tle_text(raw: str, limit: int) -> List[Tuple[str, str, str]]:
    """Fallback: parse raw 3-line TLE block text."""
    lines = [ln.rstrip() for ln in raw.splitlines() if ln.strip()]
    results: List[Tuple[str, str, str]] = []
    i = 0
    while i < len(lines) and len(results) < limit:
        if i + 2 < len(lines):
            l0, l1, l2 = lines[i], lines[i + 1], lines[i + 2]
            if (not l0.startswith("1 ") and not l0.startswith("2 ")
                    and l1.startswith("1 ") and l2.startswith("2 ")):
                results.append((l0.strip()[:25], l1, l2))
                i += 3; continue
        if i + 1 < len(lines):
            l0, l1 = lines[i], lines[i + 1]
            if l0.startswith("1 ") and l1.startswith("2 "):
                results.append((f"NORAD-{l0[2:7].strip()}", l0, l1))
                i += 2; continue
        i += 1
    return results


def propagate_all(tles: List[Tuple[str, str, str]]) -> List[dict]:
    """Propagate all TLEs to current UTC using SGP4 → lat/lon/alt."""
    now_utc = datetime.now(timezone.utc)
    jd, fr  = jday(now_utc.year, now_utc.month, now_utc.day,
                   now_utc.hour, now_utc.minute,
                   now_utc.second + now_utc.microsecond / 1e6)
    results: List[dict] = []
    for name, line1, line2 in tles:
        try:
            sat     = Satrec.twoline2rv(line1, line2)
            e, r, v = sat.sgp4(jd, fr)
            if e != 0 or r is None:
                continue
            lat, lon, alt = _eci_to_geodetic(r, jd + fr)
            if alt < -200:
                continue
            alt = max(alt, 0.0)
            results.append({
                "name":          name,
                "lat":           round(lat, 4),
                "lon":           round(lon, 4),
                "alt_km":        round(alt, 1),
                "inclination":   round(float(line2[8:16].strip()), 2),
                "period_min":    round(1440.0 / max(float(line2[52:63].strip()), 0.001), 1),
                "norad_id":      line1[2:7].strip(),
                "velocity_km_s": round(math.sqrt(v[0]**2 + v[1]**2 + v[2]**2), 3),
                "error":         False,
            })
        except Exception:
            continue
    return results


def _eci_to_geodetic(r_eci: tuple, jd_full: float) -> Tuple[float, float, float]:
    x, y, z = r_eci
    T = (jd_full - 2451545.0) / 36525.0
    gmst_deg = (280.46061837
                + 360.98564736629 * (jd_full - 2451545.0)
                + 0.000387933 * T * T
                - T * T * T / 38710000.0) % 360.0
    g  = math.radians(gmst_deg)
    xe = math.cos(g) * x + math.sin(g) * y
    ye = -math.sin(g) * x + math.cos(g) * y
    ze = z
    a  = 6378.137; e2 = 0.00669437999014
    lon_rad = math.atan2(ye, xe)
    p = math.sqrt(xe**2 + ye**2)
    lat_rad = math.atan2(ze, p * (1 - e2))
    for _ in range(5):
        sl = math.sin(lat_rad)
        N  = a / math.sqrt(1 - e2 * sl**2)
        lat_rad = math.atan2(ze + e2 * N * sl, p)
    sl = math.sin(lat_rad)
    N  = a / math.sqrt(1 - e2 * sl**2)
    alt = (p / math.cos(lat_rad) - N) if abs(lat_rad) < math.radians(89) \
          else (ze / math.sin(lat_rad) - N * (1 - e2))
    return math.degrees(lat_rad), math.degrees(lon_rad), alt


def get_cached_satellites(group: str = "Space Stations", limit: int = 500) -> List[dict]:
    """Return positions from cache or fetch+propagate fresh data."""
    now = time.time()
    with _cache_lock:
        cached = _tle_cache.get(group)
        if cached and (now - cached[0]) < CACHE_TTL_SECONDS:
            return cached[1]
    tles      = _fetch_group_tles(group, limit=limit)
    positions = propagate_all(tles) if tles else []
    with _cache_lock:
        _tle_cache[group] = (now, positions)
    return positions


# ── Globe figure ──────────────────────────────────────────────────────────────
def build_satellite_globe(positions: List[dict],
                          title: str = "Live Satellite Tracker") -> "go.Figure":
    """Orthographic Plotly globe with satellite positions."""
    import plotly.graph_objects as go
    if not positions:
        fig = go.Figure()
        fig.add_annotation(text="No satellite data — click Fetch / Refresh",
                           showarrow=False, font=dict(size=18, color="#7eb8f7"),
                           xref="paper", yref="paper", x=0.5, y=0.5)
        fig.update_layout(paper_bgcolor="#060e1a", plot_bgcolor="#060e1a",
                          font_color="white", height=650)
        return fig

    def _col(a):
        if a < 450:   return "#00ff88"
        if a < 800:   return "#00e5ff"
        if a < 2000:  return "#4d9fff"
        if a < 5000:  return "#aa44ff"
        if a < 20000: return "#ff44cc"
        return "#ffaa00"

    lats  = [p["lat"]  for p in positions]
    lons  = [p["lon"]  for p in positions]
    alts  = [p["alt_km"] for p in positions]
    texts = [
        f"<b>{p['name']}</b><br>NORAD: {p.get('norad_id','')}<br>"
        f"Alt: {p['alt_km']:.0f} km | Incl: {p.get('inclination',0):.1f}°<br>"
        f"Period: {p.get('period_min',0):.0f} min | Speed: {p.get('velocity_km_s',0):.2f} km/s"
        for p in positions
    ]
    colors = [_col(a) for a in alts]

    fig = go.Figure(go.Scattergeo(
        lat=lats, lon=lons, mode="markers",
        marker=dict(size=[3.5 + min(a / 3000, 3) for a in alts],
                    color=colors, opacity=0.9, line=dict(width=0)),
        text=texts, hoverinfo="text", name="Satellites",
    ))
    fig.update_layout(
        title=dict(
            text=f"<b>🌍 {title}</b> — <span style='color:#7eb8f7'>{len(positions):,} satellites tracked</span>",
            font=dict(size=19, color="#e8f0ff"), x=0.5,
        ),
        geo=dict(
            projection_type="orthographic",
            showland=True,     landcolor="#1c2e45",
            showocean=True,    oceancolor="#0a1522",
            showcountries=True,countrycolor="#2a4060", countrywidth=0.5,
            showcoastlines=True,coastlinecolor="#1e4080", coastlinewidth=0.8,
            showlakes=True,    lakecolor="#0d1f35",
            showframe=False,   bgcolor="#060e1a",
            lataxis=dict(showgrid=True, gridcolor="#1a2e4a", gridwidth=0.4),
            lonaxis=dict(showgrid=True, gridcolor="#1a2e4a", gridwidth=0.4),
            center=dict(lat=20, lon=0),
            projection_rotation=dict(lat=20, lon=0, roll=0),
        ),
        paper_bgcolor="#060e1a", font_color="#c0d8ff", height=680,
        margin=dict(t=60, b=10, l=10, r=10),
        hoverlabel=dict(bgcolor="#0a1a30", bordercolor="#446688",
                        font=dict(color="white", size=12)),
    )
    return fig


def build_altitude_histogram(positions: List[dict]) -> "go.Figure":
    """Histogram of satellite altitude distribution."""
    import plotly.graph_objects as go
    alts = [p["alt_km"] for p in positions if p.get("alt_km", 0) > 0]
    fig  = go.Figure(go.Histogram(
        x=alts, nbinsx=60,
        marker=dict(color="#00ccff", line=dict(color="#003366", width=0.4)),
        opacity=0.85,
    ))
    fig.update_layout(
        title="Altitude Distribution", xaxis_title="Altitude (km)",
        yaxis_title="Count", paper_bgcolor="#060e1a", plot_bgcolor="#0a1520",
        font_color="#c0d8ff", height=300,
        margin=dict(t=40, b=40, l=50, r=20),
        xaxis=dict(gridcolor="#1e3050"), yaxis=dict(gridcolor="#1e3050"),
    )
    return fig
