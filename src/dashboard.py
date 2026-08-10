import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import math
import requests
import json
import sys
import os
import time as _time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from mission_core import MissionSimulation
from storage import MissionStorage
from report_gen import generate_pdf

API_BASE_URL = "http://127.0.0.1:8000/api/v1"

st.set_page_config(
    page_title="SMA-X | Space Mission Architect",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── GLOBAL STYLE ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  .stApp { background: linear-gradient(160deg, #0d1b2b 0%, #0a1520 60%, #050d1a 100%); color: #c8daf0; }
  h1, h2, h3 { color: #7eb8f7; letter-spacing: 0.5px; }
  .stButton>button { background: linear-gradient(135deg,#1a4a8a,#0d6efd); color:white; border:none; border-radius:8px; font-weight:600; transition:all .2s; }
  .stButton>button:hover { transform:translateY(-2px); box-shadow:0 6px 20px rgba(13,110,253,.35); }
  .stButton>button[kind="primary"] { background: linear-gradient(135deg,#0a5c3c,#1a8a5c); }
  .metric-card { background:rgba(255,255,255,.05); border:1px solid rgba(126,184,247,.2); border-radius:12px; padding:16px; text-align:center; }
  .status-box-pass { border-left:5px solid #1aff88; background:rgba(26,255,136,.08); padding:12px 16px; border-radius:6px; margin-top:10px; }
  .status-box-fail { border-left:5px solid #ff4466; background:rgba(255,68,102,.08); padding:12px 16px; border-radius:6px; margin-top:10px; }
  .live-telemetry { background:rgba(30,60,100,.4); padding:14px 20px; border-radius:12px; border:1px solid rgba(126,184,247,.3); margin-bottom:18px; backdrop-filter:blur(8px); }
  .agent-card { border:1px solid rgba(126,184,247,.2); padding:12px; border-radius:10px; margin-bottom:10px; background:rgba(255,255,255,.03); }
  .verdict-green { color:#1aff88; font-weight:700; }
  .verdict-yellow { color:#ffc107; font-weight:700; }
  .verdict-red { color:#ff4466; font-weight:700; }
  .section-header { background:rgba(13,110,253,.08); border:1px solid rgba(13,110,253,.2); border-radius:8px; padding:8px 14px; margin-bottom:8px; font-weight:600; color:#7eb8f7; }
  .stExpander { border:1px solid rgba(126,184,247,.15) !important; border-radius:10px !important; }
  div[data-testid="stMetricValue"] { color:#7eb8f7; font-weight:700; font-size:1.4rem; }
  .stTabs [data-baseweb="tab"] { color:#8bacc8; font-weight:600; }
  .stTabs [data-baseweb="tab"][aria-selected="true"] { color:#7eb8f7; border-bottom:2px solid #7eb8f7; }
</style>

<script>
  // Premium UI Polish: Fix browser 'autocomplete' warnings
  setTimeout(function() {
    var inputs = window.parent.document.querySelectorAll('input');
    inputs.forEach(function(input) {
      if (!input.getAttribute('autocomplete')) {
        if (input.type === 'password') {
          input.setAttribute('autocomplete', 'current-password');
        } else if (input.placeholder && input.placeholder.toLowerCase().includes('username')) {
          input.setAttribute('autocomplete', 'username');
        } else if (input.placeholder && input.placeholder.toLowerCase().includes('email')) {
          input.setAttribute('autocomplete', 'email');
        } else {
          input.setAttribute('autocomplete', 'off');
        }
      }
    });
  }, 1000);
</script>
""", unsafe_allow_html=True)

# ── SESSION STATE INIT ───────────────────────────────────────────────────────
for k, v in {
    "token": None,
    "username": None,
    "mission_stage": "DESIGN",
    "mrd_summary": "",
    "debate_transcript": [],
    "section_verdicts": {},
    "manual_mass_override": False,
    "advice_log": {},
    "cost_breakdown": {k: None for k in ["spacecraft_bus","payload","launch_vehicle","ground_segment","operations"]},
    "cost_na": {k: True for k in ["spacecraft_bus","payload","launch_vehicle","ground_segment","operations"]},
    "sat_positions": [],
    "sat_fetch_ts": 0.0,
    "porkchop_data": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "sim" not in st.session_state:
    st.session_state.sim = MissionSimulation()
    st.session_state.storage = MissionStorage()

sim = st.session_state.sim

# ── AUTH UI ──────────────────────────────────────────────────────────────────
if not st.session_state.token:
    st.title("🚀 SPACE MISSION ARCHITECT")
    st.markdown("### Authenticate to access the command centre")
    t_login, t_reg = st.tabs(["Login", "Register"])

    with t_login:
        with st.form("login_form"):
            l_user = st.text_input("Username")
            l_pass = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                if l_user and l_pass:
                    try:
                        r = requests.post(f"{API_BASE_URL}/auth/login",
                                          data={"username": l_user, "password": l_pass})
                        if r.status_code == 200:
                            st.session_state.token = r.json().get("access_token")
                            st.session_state.username = l_user
                            st.rerun()
                        else:
                            st.error(r.json().get("detail", "Login failed"))
                    except Exception as e:
                        st.error(f"Cannot reach API: {e}")
                else:
                    st.error("Fill both fields.")

    with t_reg:
        with st.form("register_form"):
            r_user = st.text_input("Username")
            r_email = st.text_input("Email")
            r_pass = st.text_input("Password", type="password")
            if st.form_submit_button("Register"):
                if r_user and r_email and r_pass:
                    try:
                        r = requests.post(f"{API_BASE_URL}/auth/register",
                                          json={"username": r_user, "email": r_email, "password": r_pass})
                        if r.status_code == 201:
                            st.success("Registered! Now login.")
                        else:
                            st.error(r.json().get("detail", "Registration failed"))
                    except Exception as e:
                        st.error(f"Cannot reach API: {e}")
                else:
                    st.error("Fill all fields.")
    st.stop()

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2530/2530862.png", width=60)
    st.title("MISSION CONTROL")
    st.markdown(f"**Agent:** `{st.session_state.username}`")
    st.markdown(f"**Phase:** `{st.session_state.mission_stage}`")
    st.divider()
    col_a, col_b = st.columns(2)
    if col_a.button("LOGOUT"):
        st.session_state.clear(); st.rerun()
    if col_b.button("RESET"):
        tok, usr = st.session_state.token, st.session_state.username
        st.session_state.clear()
        st.session_state.token = tok; st.session_state.username = usr; st.rerun()

st.title("🚀 SPACE MISSION ARCHITECT — Phase A Formulation")

# ── TABS ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 SPECIFICATIONS",
    "🏛 COUNCIL",
    "🚀 EXECUTION",
    "🌍 LIVE SATELLITES",
])

# ═══════════════════════════════════════════════════════════
# TAB 1 — SPECIFICATIONS (complete form)
# ═══════════════════════════════════════════════════════════
with tab1:
    if st.session_state.mission_stage in ["DESIGN", "DISCUSSION", "REVIEW"]:

        # ── Telemetry bar ────────────────────────────────────────────────────
        try:
            sim.recalculate_budgets()
            cost_val   = float(sim.specs.cost_estimate_m or 0.0)
            budget_val = float(sim.specs.budget_cap_m or 500.0)
            if not math.isfinite(cost_val):   cost_val   = 0.0
            if not math.isfinite(budget_val): budget_val = 500.0
            # Clamp for display
            DISP_MAX = 1_000_000.0
            cost_val   = min(cost_val,   DISP_MAX)
            budget_val = min(budget_val, DISP_MAX)
        except Exception:
            cost_val, budget_val = 0.0, 500.0

        st.markdown('<div class="live-telemetry">', unsafe_allow_html=True)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("💰 Cost Est.", f"${cost_val:.1f} M")
        c2.metric("🏦 Budget Cap", f"${budget_val:.1f} M",
                  delta=f"{budget_val - cost_val:.1f}")
        c3.metric("⚖️ Wet Mass",
                  f"{sim.specs.configuration['physical']['mass_wet']:.0f} kg")
        c4.metric("🚀 Type", sim.specs.overview['type'][:16])
        c5.metric("🎯 Target", str(sim.specs.orbit['target'].get('type','?'))[:12])
        st.markdown('</div>', unsafe_allow_html=True)

        # ── AI Natural Language Auto-Fill ─────────────────────────────────
        with st.expander("✨ AI Natural Language Auto-Fill", expanded=False):
            nl_input = st.text_area(
                "Describe your mission:",
                placeholder="E.g. I want a 1000 kg Mars orbiter with nuclear power and high-res cameras…",
            )
            
            uploaded_file = st.file_uploader("Or upload a mission document (PDF/DOCX/TXT)", type=["pdf", "docx", "txt"])
            
            if st.button("Auto-Fill Form"):
                with st.spinner("Parsing…"):
                    text_to_parse = nl_input
                    if uploaded_file is not None:
                        try:
                            if uploaded_file.name.endswith(".txt"):
                                text_to_parse += "\n" + uploaded_file.getvalue().decode("utf-8")
                            elif uploaded_file.name.endswith(".pdf"):
                                try:
                                    import PyPDF2
                                    reader = PyPDF2.PdfReader(uploaded_file)
                                    pdf_text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
                                    text_to_parse += "\n" + pdf_text
                                except ImportError:
                                    st.error("PyPDF2 is not installed. Please run `pip install PyPDF2` to enable PDF support.")
                                    st.stop()
                            elif uploaded_file.name.endswith(".docx"):
                                try:
                                    import docx
                                    doc = docx.Document(uploaded_file)
                                    docx_text = "\n".join(para.text for para in doc.paragraphs)
                                    text_to_parse += "\n" + docx_text
                                except ImportError:
                                    st.error("python-docx is not installed. Please run `pip install python-docx` to enable DOCX support.")
                                    st.stop()
                        except Exception as e:
                            st.error(f"Error reading file: {e}")
                            st.stop()
                            
                    if not text_to_parse.strip():
                        st.warning("Please provide a description or upload a document.")
                    else:
                        ok, msg = sim.parse_natural_language_mission(text_to_parse)
                        (st.success if ok else st.error)(msg)
                        if ok: st.rerun()

        # ════════════════════════════════════════════════════════
        # SECTION 1: MISSION OVERVIEW
        # ════════════════════════════════════════════════════════
        with st.expander("SECTION 1: MISSION OVERVIEW", expanded=True):
            st.caption("High-level goals, timeline, and objectives.")
            c1, c2, c3 = st.columns(3)
            sim.specs.overview['name']     = c1.text_input("1.1 Mission Name", sim.specs.overview['name'])
            sim.specs.overview['type']     = c2.selectbox("Mission Type", [
                "Single Satellite Mission", "Multi-Satellite Constellation",
                "Formation Flying", "Rendezvous & Docking",
                "Interplanetary Transfer", "Deep Space Exploration",
                "On-Orbit Servicing", "CubeSat Mission", "Technology Demonstrator",
            ])
            sim.specs.overview['priority'] = c3.selectbox("Priority / Risk Class",
                ["Critical (Class A)", "High (Class B)", "Medium (Class C)", "Low (Class D)"])

            sim.specs.overview['description'] = st.text_area(
                "Mission Description", sim.specs.overview['description'],
                placeholder="Describe the mission objectives, scientific goals, and operational concept…")

            c4, c5, c6 = st.columns(3)
            d_val = sim.specs.overview['launch_date']
            if isinstance(d_val, datetime): d_val = d_val.date()
            new_date = c4.date_input("Launch Date", d_val)
            sim.specs.overview['launch_date'] = datetime.combine(new_date, datetime.min.time())
            sim.specs.overview['duration_value'] = c5.number_input(
                "Duration (Value)", 0.1, 50.0, float(sim.specs.overview['duration_value']))
            sim.specs.overview['duration_unit']  = c6.selectbox("Unit", ["Years", "Months", "Days"])

            st.markdown("**1.2 Objectives**")
            sim.specs.overview['objectives']['primary']  = st.text_area(
                "Primary Objective", sim.specs.overview['objectives']['primary'],
                placeholder="e.g. Achieve sustained Mars surface observation from orbit")
            sim.specs.overview['objectives']['success_criteria'] = st.text_area(
                "Success Criteria", sim.specs.overview['objectives'].get('success_criteria',''),
                placeholder="e.g. ≥95% data downlink reliability, < 1 m GSD camera resolution")
            sec_obj = st.text_area("Secondary Objectives (one per line)",
                "\n".join(sim.specs.overview['objectives'].get('secondary', [])))
            sim.specs.overview['objectives']['secondary'] = [
                s.strip() for s in sec_obj.splitlines() if s.strip()]

            if st.button("🔍 Review Section 1", key="r1"):
                verdict, transcript = sim.review_section("OVERVIEW", sim.specs.overview)
                st.session_state.section_verdicts['s1'] = {"v": verdict, "t": transcript[-1]['text']}
            if 's1' in st.session_state.section_verdicts:
                v = st.session_state.section_verdicts['s1']
                st.markdown(f"**{v['v']}** — {v['t'][:300]}…")

        # ════════════════════════════════════════════════════════
        # SECTION 2: SPACECRAFT CONFIGURATION
        # ════════════════════════════════════════════════════════
        with st.expander("SECTION 2: SPACECRAFT CONFIGURATION"):
            st.markdown("#### 2.1 Physical Properties")
            c1, c2, c3, c4 = st.columns(4)
            sim.specs.configuration['physical']['number_of_spacecraft'] = c1.number_input(
                "No. of Spacecraft", 1, 1000, int(sim.specs.configuration['physical']['number_of_spacecraft']))
            sim.specs.configuration['physical']['mass_dry'] = c2.number_input(
                "Dry Mass (kg)", 1.0, 50000.0, float(sim.specs.configuration['physical']['mass_dry']))
            sim.specs.configuration['physical']['mass_wet'] = c3.number_input(
                "Wet Mass (kg)", 1.0, 100000.0, float(sim.specs.configuration['physical']['mass_wet']))
            sim.specs.configuration['physical']['payload_mass'] = c4.number_input(
                "Payload Mass (kg)", 0.0, 20000.0, float(sim.specs.configuration['physical']['payload_mass']))

            c5, c6, c7, c8 = st.columns(4)
            dim = sim.specs.configuration['physical']['dimensions']
            dim['L'] = c5.number_input("Length (m)", 0.1, 50.0, float(dim['L']))
            dim['W'] = c6.number_input("Width (m)", 0.1, 50.0, float(dim['W']))
            dim['H'] = c7.number_input("Height (m)", 0.1, 50.0, float(dim['H']))
            sim.specs.configuration['physical']['drag_coeff']   = c8.number_input(
                "Drag Coeff (Cd)", 1.0, 4.0, float(sim.specs.configuration['physical']['drag_coeff']))
            sim.specs.configuration['physical']['reflectivity'] = c8.number_input(
                "Reflectivity (Cr)", 1.0, 2.0,
                float(sim.specs.configuration['physical'].get('reflectivity', 1.3)), step=0.01)

            st.markdown("#### 2.2 Propulsion")
            c9, c10, c11 = st.columns(3)
            sim.specs.configuration['propulsion']['type'] = c9.selectbox("Propulsion Type", [
                "Chemical (Bipropellant)", "Chemical (Monopropellant)",
                "Electric (Ion)", "Electric (Hall)", "Cold Gas",
                "Solar Sail", "Nuclear Thermal", "Hybrid",
            ])
            sim.specs.configuration['propulsion']['isp']       = c10.number_input(
                "Specific Impulse (s)", 10.0, 10000.0,
                float(sim.specs.configuration['propulsion']['isp']))
            sim.specs.configuration['propulsion']['propellant_mass'] = c11.number_input(
                "Propellant Mass (kg)", 0.0, 50000.0,
                float(sim.specs.configuration['propulsion']['propellant_mass']))

            c12, c13, c14, c15 = st.columns(4)
            sim.specs.configuration['propulsion']['thrust_max']    = c12.number_input(
                "Max Thrust (N)", 0.0, 1000000.0,
                float(sim.specs.configuration['propulsion']['thrust_max']))
            sim.specs.configuration['propulsion']['thrust_min']    = c13.number_input(
                "Min Thrust (N)", 0.0, 100000.0,
                float(sim.specs.configuration['propulsion']['thrust_min']))
            sim.specs.configuration['propulsion']['thruster_count'] = c14.number_input(
                "Thruster Count", 1, 64,
                int(sim.specs.configuration['propulsion']['thruster_count']))
            sim.specs.configuration['propulsion']['vectoring']     = c15.checkbox(
                "Thrust Vectoring",
                bool(sim.specs.configuration['propulsion']['vectoring']))

            st.markdown("#### 2.3 Power")
            c16, c17, c18 = st.columns(3)
            sim.specs.configuration['power']['type'] = c16.selectbox(
                "Power Source", ["Solar Panels", "Nuclear RTG", "Fuel Cells", "Battery Only", "Hybrid (Solar+Battery)"])
            sim.specs.configuration['power']['generation_w']    = c17.number_input(
                "Max Power (W)", 0.0, 200000.0,
                float(sim.specs.configuration['power']['generation_w']))
            sim.specs.configuration['power']['battery_wh']      = c18.number_input(
                "Battery Capacity (Wh)", 0.0, 100000.0,
                float(sim.specs.configuration['power']['battery_wh']))

            c19, c20, c21, c22 = st.columns(4)
            sim.specs.configuration['power']['panel_area']      = c19.number_input(
                "Solar Panel Area (m²)", 0.0, 500.0,
                float(sim.specs.configuration['power']['panel_area']))
            sim.specs.configuration['power']['efficiency']      = c20.slider(
                "Panel Efficiency (%)", 5.0, 40.0,
                float(sim.specs.configuration['power']['efficiency'] * 100)) / 100.0
            sim.specs.configuration['power']['consumption_avg'] = c21.number_input(
                "Avg Consumption (W)", 0.0, 50000.0,
                float(sim.specs.configuration['power']['consumption_avg']))
            sim.specs.configuration['power']['consumption_peak']= c22.number_input(
                "Peak Consumption (W)", 0.0, 100000.0,
                float(sim.specs.configuration['power']['consumption_peak']))

            st.markdown("#### 2.4 Attitude Control System (ACS)")
            c23, c24, c25, c26 = st.columns(4)
            sim.specs.configuration['acs']['type'] = c23.selectbox(
                "ACS Mode", ["3-Axis Stabilized", "Spin Stabilized",
                              "Gravity Gradient", "Dual-Spin"])
            sim.specs.configuration['acs']['pointing_accuracy'] = c24.number_input(
                "Pointing Accuracy (°)", 0.001, 10.0,
                float(sim.specs.configuration['acs']['pointing_accuracy']), format="%.3f")
            sim.specs.configuration['acs']['slew_rate']         = c25.number_input(
                "Slew Rate (°/s)", 0.01, 20.0,
                float(sim.specs.configuration['acs']['slew_rate']))
            sim.specs.configuration['acs']['momentum_storage']  = c26.number_input(
                "Momentum Storage (Nms)", 0.0, 1000.0,
                float(sim.specs.configuration['acs']['momentum_storage']))

            st.markdown("#### 2.5 Communications")
            c27, c28, c29 = st.columns(3)
            sim.specs.configuration['comms']['bands']       = c27.multiselect(
                "Comm Bands", ["S-band","X-band","Ka-band","Ku-band","UHF","VHF","Optical","L-band"],
                default=sim.specs.configuration['comms']['bands'])
            sim.specs.configuration['comms']['antenna_type']= c28.selectbox(
                "Antenna Type", ["Directional","Omnidirectional","Phased Array","Dish","Patch"])
            sim.specs.configuration['comms']['data_rate_mbps']= c29.number_input(
                "Data Rate (Mbps)", 0.001, 10000.0,
                float(sim.specs.configuration['comms']['data_rate_mbps']))

            c30, c31, c32 = st.columns(3)
            sim.specs.configuration['comms']['windows_per_day']= c30.number_input(
                "Contact Windows/Day", 0, 48,
                int(sim.specs.configuration['comms']['windows_per_day']))
            sim.specs.configuration['comms']['latency_limit']  = c31.number_input(
                "Max Latency (s)", 0, 86400,
                int(sim.specs.configuration['comms']['latency_limit']))
            gnd_str = c32.text_input(
                "Ground Stations",
                ", ".join(sim.specs.configuration['comms']['ground_stations']))
            sim.specs.configuration['comms']['ground_stations'] = [
                g.strip() for g in gnd_str.split(",") if g.strip()]

            st.markdown("#### 2.6 Sensors & Payload")
            c33, c34 = st.columns(2)
            sim.specs.configuration['sensors']['navigation'] = c33.multiselect(
                "Navigation Sensors",
                ["Star Tracker","IMU","Sun Sensor","Earth Sensor",
                 "Magnetometer","GPS/GNSS","Horizon Sensor"],
                default=sim.specs.configuration['sensors']['navigation'])
            sim.specs.configuration['sensors']['payload_type'] = c34.multiselect(
                "Payload Instruments",
                ["Optical Camera","SAR","Multispectral","Hyperspectral",
                 "LiDAR","Magnetometer","Particle Detector","Radiometer",
                 "Communication Payload","Technology Demo"],
                default=sim.specs.configuration['sensors']['payload_type'])
            c35, c36 = st.columns(2)
            sim.specs.configuration['sensors']['payload_power']= c35.number_input(
                "Payload Power (W)", 0.0, 10000.0,
                float(sim.specs.configuration['sensors']['payload_power']))
            sim.specs.configuration['sensors']['duty_cycle']  = c36.slider(
                "Payload Duty Cycle (%)", 0.0, 100.0,
                float(sim.specs.configuration['sensors']['duty_cycle']))

            if st.button("🔍 Review Section 2", key="r2"):
                verdict, transcript = sim.review_section("CONFIG", sim.specs.configuration)
                st.session_state.section_verdicts['s2'] = {"v": verdict, "t": transcript[-1]['text']}
            if 's2' in st.session_state.section_verdicts:
                v = st.session_state.section_verdicts['s2']
                st.markdown(f"**{v['v']}** — {v['t'][:300]}…")

        # ════════════════════════════════════════════════════════
        # SECTION 2B: SPACECRAFT ARCHITECTURE
        # ════════════════════════════════════════════════════════
        with st.expander("SECTION 2B: SPACECRAFT ARCHITECTURE 🛰"):
            if 'architecture' not in dir(sim.specs):
                sim.specs.architecture = {}
            arch = sim.specs.architecture

            # 2B.1 Structural
            st.markdown("#### 2B.1 Structural / Mechanical")
            c1, c2, c3 = st.columns(3)
            arch['bus_form_factor']    = c1.selectbox("Bus Form Factor", [
                "CubeSat 1U","CubeSat 3U","CubeSat 6U","CubeSat 12U",
                "ESPA-class SmallSat (100–300 kg)","SmallSat (300–600 kg)",
                "Medium Platform (600–2000 kg)","Large Spacecraft (>2000 kg)",
            ], index=0 if 'bus_form_factor' not in arch else [
                "CubeSat 1U","CubeSat 3U","CubeSat 6U","CubeSat 12U",
                "ESPA-class SmallSat (100–300 kg)","SmallSat (300–600 kg)",
                "Medium Platform (600–2000 kg)","Large Spacecraft (>2000 kg)",
            ].index(arch.get('bus_form_factor',"CubeSat 3U")) if arch.get('bus_form_factor') in [
                "CubeSat 1U","CubeSat 3U","CubeSat 6U","CubeSat 12U",
                "ESPA-class SmallSat (100–300 kg)","SmallSat (300–600 kg)",
                "Medium Platform (600–2000 kg)","Large Spacecraft (>2000 kg)",
            ] else 0)
            arch['primary_structure_material'] = c2.selectbox("Primary Structure Material", [
                "Aluminium 6061-T6","Aluminium 7075-T6","CFRP (Carbon Fibre)",
                "Titanium Ti-6Al-4V","Steel","Honeycomb Sandwich Panel",
            ])
            arch['launch_adapter'] = c3.selectbox("Launch Adapter", [
                "ESPA Standard","RUAG LVAS","StarBus","NLAS (6U)",
                "Standard 937 mm","Custom","TBD",
            ])

            # 2B.2 Thermal
            st.markdown("#### 2B.2 Thermal Control System (TCS)")
            c4, c5, c6 = st.columns(3)
            arch['tcs_passive'] = c4.multiselect("Passive TCS", [
                "MLI Blankets","Radiator Panels","Surface Coatings (white paint)",
                "Second Surface Mirrors","Heat Spreaders",
            ], default=arch.get('tcs_passive', ["MLI Blankets","Radiator Panels"]))
            arch['tcs_active'] = c5.multiselect("Active TCS", [
                "Heaters","Variable Conductance Heat Pipes (VCHP)",
                "Loop Heat Pipes","Thermoelectric Coolers (TEC)",
                "Louvers","Cryogenic Cooler",
            ], default=arch.get('tcs_active', ["Heaters"]))
            arch['heater_power_w'] = c6.number_input(
                "Total Heater Power (W)", 0.0, 5000.0,
                float(arch.get('heater_power_w', 50.0)))

            c7, c8, c9, c10 = st.columns(4)
            arch['temp_op_min']  = c7.number_input("Op Temp Min (°C)", -100.0, 0.0,
                float(arch.get('temp_op_min', -20.0)))
            arch['temp_op_max']  = c8.number_input("Op Temp Max (°C)", 0.0, 120.0,
                float(arch.get('temp_op_max',  60.0)))
            arch['temp_sur_min'] = c9.number_input("Survival Min (°C)", -200.0, 0.0,
                float(arch.get('temp_sur_min', -40.0)))
            arch['temp_sur_max'] = c10.number_input("Survival Max (°C)", 0.0, 200.0,
                float(arch.get('temp_sur_max',  85.0)))

            # 2B.3 ADCS Details
            st.markdown("#### 2B.3 ADCS Actuators & Sensors (Detail)")
            c11, c12, c13 = st.columns(3)
            arch['rw_torque_nm']   = c11.number_input("Reaction Wheel Torque (mNm)", 0.0, 1000.0,
                float(arch.get('rw_torque_nm', 20.0)))
            arch['rw_momentum_nms']= c12.number_input("RW Momentum (Nms)", 0.0, 200.0,
                float(arch.get('rw_momentum_nms', 4.0)))
            arch['mtq_dipole']     = c13.number_input("Magnetorquer Dipole (Am²)", 0.0, 100.0,
                float(arch.get('mtq_dipole', 5.0)))
            c14, c15, c16 = st.columns(3)
            arch['star_tracker_accuracy_arcsec'] = c14.number_input(
                "Star Tracker Accuracy (arcsec)", 0.1, 300.0,
                float(arch.get('star_tracker_accuracy_arcsec', 5.0)))
            arch['imu_drift_deg_hr'] = c15.number_input(
                "IMU Drift (°/hr)", 0.0001, 10.0,
                float(arch.get('imu_drift_deg_hr', 0.1)), format="%.4f")
            arch['pointing_modes'] = c16.multiselect("Pointing Modes", [
                "Nadir-Pointing","Sun-Tracking","Inertial Hold",
                "Target Following","Eclipse Safe Mode",
            ], default=arch.get('pointing_modes', ["Nadir-Pointing","Sun-Tracking"]))

            # 2B.4 On-Board Data Handling (OBDH)
            st.markdown("#### 2B.4 On-Board Data Handling (OBDH)")
            c17, c18, c19, c20 = st.columns(4)
            arch['obc_type'] = c17.selectbox("OBC Processor", [
                "LEON4FT (GR740)","LEON3FT (GR712RC)","Rad-hard ARM Cortex-R5",
                "FPGA Hybrid (Xilinx Kintex)","Raspberry Pi CM4 (non-rad-hard)",
                "NanoMind A3200","iMTQ + ISIS OBC","Custom ASIC",
            ])
            arch['storage_gb']     = c18.number_input("Onboard Storage (GB)", 0.1, 10000.0,
                float(arch.get('storage_gb', 64.0)))
            arch['redundancy']     = c19.selectbox("Redundancy Level",
                ["None","Cold Spare","Hot Spare (dual)","Triple Modular (TMR)"])
            arch['data_compression']= c20.selectbox("Data Compression",
                ["None","Lossless (CCSDS 123)","Lossy (JPEG-2000)","FPGA-based"])

            # 2B.5 RF Link Budget
            st.markdown("#### 2B.5 RF Link Budget (auto-computed)")
            c21, c22, c23, c24 = st.columns(4)
            arch['tx_power_w']    = c21.number_input("TX Power (W)", 0.1, 500.0,
                float(arch.get('tx_power_w', 5.0)))
            arch['tx_gain_dbi']   = c22.number_input("TX Antenna Gain (dBi)", -5.0, 50.0,
                float(arch.get('tx_gain_dbi', 6.0)))
            arch['gs_gain_dbi']   = c23.number_input("G/S Antenna Gain (dBi)", 0.0, 80.0,
                float(arch.get('gs_gain_dbi', 40.0)))
            arch['gs_noise_k']    = c24.number_input("G/S System Noise (K)", 50.0, 500.0,
                float(arch.get('gs_noise_k', 135.0)))

            if st.button("📡 Compute RF Link Budget", key="link_budget"):
                try:
                    from physics_tools import PhysicsTools
                    pt = PhysicsTools()
                    orbit_alt = sim.specs.orbit['initial']['a'] - 6378.137
                    freq_band = sim.specs.configuration['comms']['bands']
                    freq_map  = {"X-band": 8.4, "Ka-band": 26.0, "S-band": 2.2,
                                 "Ku-band": 14.0, "UHF": 0.437, "L-band": 1.6}
                    freq_ghz  = freq_map.get(freq_band[0] if freq_band else "X-band", 8.4)
                    eirp_dbw  = 10 * math.log10(arch['tx_power_w']) + arch['tx_gain_dbi']
                    result    = pt.link_budget(
                        eirp_dbw=eirp_dbw,
                        distance_km=orbit_alt,
                        freq_ghz=freq_ghz,
                        rx_gain_db=arch['gs_gain_dbi'],
                        system_noise_temp_k=arch['gs_noise_k'],
                        data_rate_bps=sim.specs.configuration['comms']['data_rate_mbps'] * 1e6,
                    )
                    arch['link_budget_result'] = result
                    st.session_state.section_verdicts['link'] = result
                except Exception as e:
                    st.error(f"Link budget error: {e}")

            if st.session_state.section_verdicts.get('link') or arch.get('link_budget_result'):
                lb = arch.get('link_budget_result', st.session_state.section_verdicts.get('link', {}))
                if lb:
                    col_lb1, col_lb2, col_lb3, col_lb4 = st.columns(4)
                    col_lb1.metric("FSPL", f"{lb.get('free_space_path_loss_db', 0):.1f} dB")
                    col_lb2.metric("Eb/N₀", f"{lb.get('eb_n0_db', 0):.1f} dB")
                    col_lb3.metric("Link Margin", f"{lb.get('link_margin_db', 0):.1f} dB")
                    col_lb4.markdown(f"**Status:** {lb.get('status','')}")

        # ════════════════════════════════════════════════════════
        # SECTION 2C: MULTISTAGE PROPULSION
        # ════════════════════════════════════════════════════════
        with st.expander("SECTION 2C: MULTISTAGE PROPULSION 🔥", expanded=False):
            st.caption("Define each propulsion stage independently. First stage is primary launch thrust; upper stages for orbit insertion / TMI.")

            if 'stages' not in sim.specs.configuration:
                sim.specs.configuration['stages'] = []

            n_stages = st.number_input("Number of Propulsion Stages", 1, 5,
                                       max(len(sim.specs.configuration['stages']), 1))

            # Ensure list is right length
            while len(sim.specs.configuration['stages']) < n_stages:
                sim.specs.configuration['stages'].append({
                    "label": f"Stage {len(sim.specs.configuration['stages'])+1}",
                    "type": "Chemical (Bipropellant)",
                    "propellant": "LOX/LH2",
                    "isp": 450.0,
                    "thrust_kn": 1000.0,
                    "burn_time_s": 120.0,
                    "propellant_mass_kg": 5000.0,
                    "structure_mass_kg": 500.0,
                    "separation": True,
                })
            sim.specs.configuration['stages'] = sim.specs.configuration['stages'][:n_stages]

            STAGE_LABELS = ["1st Stage (Booster)", "2nd Stage (Core)", "3rd Stage (Upper)",
                            "4th Stage (Kick)", "5th Stage (Apogee Kick)"]
            PROP_COMBOS  = ["LOX/LH2 (cryogenic)", "LOX/RP-1 (kerosene)", "LOX/LCH4 (methane)",
                            "N2O4/UDMH (storable)", "HTPB Solid", "APCP Solid",
                            "N2H4 Monoprop", "Xenon (Electric Ion)", "Argon (Hall Thruster)"]

            dv_total = 0.0
            for si, stage in enumerate(sim.specs.configuration['stages']):
                with st.container(border=True):
                    st.markdown(f"#### {STAGE_LABELS[si]}")
                    s_c1, s_c2 = st.columns(2)
                    stage['label'] = s_c1.text_input(f"Stage {si+1} Label", stage['label'], key=f"slabel_{si}")
                    stage['type']  = s_c2.selectbox(f"Engine Type", [
                        "Chemical (Bipropellant)", "Chemical (Monopropellant)",
                        "Solid Rocket Motor", "Electric (Ion)", "Electric (Hall)",
                        "Nuclear Thermal", "Cold Gas", "Aerospike",
                    ], key=f"stype_{si}")
                    s_c3, s_c4, s_c5 = st.columns(3)
                    stage['propellant']         = s_c3.selectbox("Propellant", PROP_COMBOS, key=f"sprop_{si}")
                    stage['isp']                = s_c4.number_input("Isp (s)", 50.0, 5000.0, float(stage['isp']), key=f"sisp_{si}")
                    stage['thrust_kn']          = s_c5.number_input("Thrust (kN)", 0.001, 100000.0, float(stage['thrust_kn']), key=f"sthr_{si}")
                    s_c6, s_c7, s_c8, s_c9 = st.columns(4)
                    stage['burn_time_s']        = s_c6.number_input("Burn Time (s)", 1.0, 100000.0, float(stage['burn_time_s']), key=f"sbt_{si}")
                    stage['propellant_mass_kg'] = s_c7.number_input("Propellant Mass (kg)", 1.0, 500000.0, float(stage['propellant_mass_kg']), key=f"spm_{si}")
                    stage['structure_mass_kg']  = s_c8.number_input("Structure Mass (kg)", 1.0, 50000.0, float(stage['structure_mass_kg']), key=f"ssm_{si}")
                    stage['separation']         = s_c9.checkbox("Stage Separates", bool(stage['separation']), key=f"ssep_{si}")

                    # Tsiolkovsky Δv for this stage
                    try:
                        m0     = float(stage['propellant_mass_kg']) + float(stage['structure_mass_kg'])
                        mf     = float(stage['structure_mass_kg'])
                        isp    = float(stage['isp'])
                        if m0 > mf > 0 and isp > 0:
                            dv_stage = isp * 9.80665 * math.log(m0 / mf)
                            dv_total += dv_stage
                            st.metric(f"Stage {si+1} Δv", f"{dv_stage:.0f} m/s")
                    except Exception:
                        pass

            if n_stages > 1 and dv_total > 0:
                st.success(f"🚀 **Total Multistage Δv: {dv_total:.0f} m/s** (Tsiolkovsky, each stage independent)")

        # ════════════════════════════════════════════════════════
        # SECTION 2D: LAUNCH VEHICLE
        # ════════════════════════════════════════════════════════
        with st.expander("SECTION 2D: LAUNCH VEHICLE 🚀", expanded=False):
            if 'launch_vehicle' not in sim.specs.configuration:
                sim.specs.configuration['launch_vehicle'] = {}
            lv = sim.specs.configuration['launch_vehicle']

            # Launch vehicle database (name → {LEO, GTO, TLI, C3, cost, country})
            LV_DB = {
                "PSLV-C (standard)":         {"LEO":3800, "GTO":1300, "TLI":None, "cost_m":25, "country":"ISRO 🇮🇳"},
                "PSLV-XL":                    {"LEO":5000, "GTO":1800, "TLI":None, "cost_m":30, "country":"ISRO 🇮🇳"},
                "GSLV Mk II":                 {"LEO":5000, "GTO":2700, "TLI":None, "cost_m":45, "country":"ISRO 🇮🇳"},
                "GSLV Mk III (LVM3)":         {"LEO":10000,"GTO":4000, "TLI":None, "cost_m":60, "country":"ISRO 🇮🇳"},
                "Falcon 9 (Expendable)":      {"LEO":22800,"GTO":8300, "TLI":3500, "cost_m":67, "country":"SpaceX 🇺🇸"},
                "Falcon 9 (Reused)":          {"LEO":17000,"GTO":5500, "TLI":None, "cost_m":50, "country":"SpaceX 🇺🇸"},
                "Falcon Heavy (Expendable)":  {"LEO":63800,"GTO":26700,"TLI":16800,"cost_m":130,"country":"SpaceX 🇺🇸"},
                "Starship (orbit)":           {"LEO":150000,"GTO":None,"TLI":100000,"cost_m":10, "country":"SpaceX 🇺🇸"},
                "Atlas V 401":                {"LEO":9800, "GTO":4750, "TLI":2800, "cost_m":110,"country":"ULA 🇺🇸"},
                "Atlas V 551":                {"LEO":18850,"GTO":8900, "TLI":5100, "cost_m":145,"country":"ULA 🇺🇸"},
                "Vulcan Centaur VC2S":        {"LEO":27200,"GTO":9000, "TLI":None, "cost_m":100,"country":"ULA 🇺🇸"},
                "Ariane 5 ECA":               {"LEO":20000,"GTO":10865,"TLI":6600, "cost_m":145,"country":"ArianeGroup 🇪🇺"},
                "Ariane 6 (A62)":             {"LEO":10300,"GTO":4500, "TLI":None, "cost_m":75, "country":"ArianeGroup 🇪🇺"},
                "Ariane 6 (A64)":             {"LEO":21600,"GTO":11500,"TLI":None, "cost_m":115,"country":"ArianeGroup 🇪🇺"},
                "Vega (standard)":            {"LEO":1500, "GTO":None, "TLI":None, "cost_m":35, "country":"ArianeGroup 🇪🇺"},
                "Vega-C":                     {"LEO":2350, "GTO":None, "TLI":None, "cost_m":40, "country":"ArianeGroup 🇪🇺"},
                "Soyuz-2.1a":                 {"LEO":7500, "GTO":2800, "TLI":None, "cost_m":50, "country":"Roscosmos 🇷🇺"},
                "Proton-M":                   {"LEO":23000,"GTO":6920, "TLI":5500, "cost_m":80, "country":"Roscosmos 🇷🇺"},
                "Long March 2C":              {"LEO":3850, "GTO":None, "TLI":None, "cost_m":30, "country":"CASC 🇨🇳"},
                "Long March 5B":              {"LEO":25000,"GTO":None, "TLI":None, "cost_m":75, "country":"CASC 🇨🇳"},
                "Long March 9":               {"LEO":150000,"GTO":None,"TLI":53000,"cost_m":500,"country":"CASC 🇨🇳"},
                "H-IIA (202)":                {"LEO":10000,"GTO":4100, "TLI":None, "cost_m":90, "country":"JAXA 🇯🇵"},
                "H3-24":                      {"LEO":6500, "GTO":4000, "TLI":None, "cost_m":50, "country":"JAXA 🇯🇵"},
                "New Glenn":                  {"LEO":45000,"GTO":13000,"TLI":None, "cost_m":70, "country":"Blue Origin 🇺🇸"},
                "Electron (Rocket Lab)":      {"LEO":300,  "GTO":None, "TLI":None, "cost_m":7.5,"country":"Rocket Lab 🇬🇧"},
                "LauncherOne":                {"LEO":500,  "GTO":None, "TLI":None, "cost_m":12, "country":"Virgin Orbit 🇺🇸"},
                "SSLV (ISRO)":                {"LEO":500,  "GTO":None, "TLI":None, "cost_m":15, "country":"ISRO 🇮🇳"},
                "Custom / TBD":               {"LEO":None, "GTO":None, "TLI":None, "cost_m":None,"country":"Custom"},
            }

            lv_name = st.selectbox("Launch Vehicle", list(LV_DB.keys()),
                                   index=list(LV_DB.keys()).index(lv.get('name', 'PSLV-C (standard)'))
                                   if lv.get('name') in LV_DB else 0,
                                   key="lv_name")
            lv['name'] = lv_name
            specs_db   = LV_DB[lv_name]

            # Show specs
            lv_c1, lv_c2, lv_c3, lv_c4 = st.columns(4)
            lv_c1.metric("Provider", specs_db['country'])
            lv_c2.metric("LEO Cap.", f"{specs_db['LEO']:,} kg" if specs_db['LEO'] else "—")
            lv_c3.metric("GTO Cap.", f"{specs_db['GTO']:,} kg" if specs_db['GTO'] else "—")
            lv_c4.metric("Est. Cost", f"${specs_db['cost_m']}M" if specs_db['cost_m'] else "TBD")

            # Feasibility check
            wet_mass = float(sim.specs.configuration['physical']['mass_wet'])
            leo_cap  = specs_db.get('LEO')
            if leo_cap is not None:
                if wet_mass <= leo_cap:
                    st.success(f"✅ **Feasible for LEO** — wet mass {wet_mass:.0f} kg ≤ {leo_cap:,} kg capacity")
                else:
                    st.error(f"❌ **Overmass for LEO** — wet mass {wet_mass:.0f} kg > {leo_cap:,} kg capacity. Reduce mass or choose a heavier lift vehicle.")

            lv_r1, lv_r2, lv_r3 = st.columns(3)
            lv['launch_site']  = lv_r1.selectbox("Launch Site", [
                "Satish Dhawan (ISRO, India)",
                "Kennedy Space Center (NASA, USA)",
                "Cape Canaveral (USAF, USA)",
                "Vandenberg SFB (USAF, USA)",
                "Kourou (ESA/ArianeGroup, French Guiana)",
                "Baikonur (Roscosmos, Kazakhstan)",
                "Plesetsk (Roscosmos, Russia)",
                "Tanegashima (JAXA, Japan)",
                "Jiuquan (CASC, China)",
                "Mahia Peninsula (Rocket Lab, New Zealand)",
                "Custom / TBD",
            ])
            lv['fairing_dia_m'] = lv_r2.selectbox("Fairing Diameter", [
                "0.97 m (PSLV SSPO)", "1.5 m (Electron)",
                "2.6 m (PSLV-XL)", "3.7 m (Falcon 9)",
                "4.5 m (Atlas V) / (GSLV Mk III)",
                "5.4 m (Falcon Heavy)", "7.0 m (Starship)",
                "Custom",
            ])
            lv['orbit_regime']  = lv_r3.selectbox("Target Regime for This Launch", [
                "LEO (200–2000 km)", "SSO (~600 km, 97–98°)",
                "GTO (200 × 35786 km)", "GEO (35786 km)",
                "MEO (2000–35786 km)", "TLI (Trans-Lunar)", "TMI (Trans-Mars)",
                "Escape (C3 > 0)",
            ])

            lv['rideshare'] = st.checkbox("Rideshare / Secondary Payload Mission",
                                           bool(lv.get('rideshare', False)))
            lv['notes']     = st.text_area("Launch Vehicle Notes", lv.get('notes', ''),
                                            placeholder="Specific launch window constraints, range safety requirements, RAAN targeting…",
                                            height=60)
            lv['cost_m']    = specs_db['cost_m'] or 0.0
            sim.specs.configuration['launch_vehicle'] = lv

        # ════════════════════════════════════════════════════════
        # SECTION 3: ORBITAL PARAMETERS
        # ════════════════════════════════════════════════════════
        with st.expander("SECTION 3: ORBITAL PARAMETERS"):
            st.markdown("**3.1 Initial Orbit**")
            c1, c2 = st.columns(2)
            sim.specs.orbit['initial']['method'] = c1.selectbox(
                "Definition Method", ["Keplerian Elements","Cartesian","TLE"])
            method = sim.specs.orbit['initial']['method']

            if method == "TLE":
                sim.specs.orbit['initial']['tle_line1'] = st.text_input(
                    "TLE Line 1", sim.specs.orbit['initial'].get('tle_line1',''))
                sim.specs.orbit['initial']['tle_line2'] = st.text_input(
                    "TLE Line 2", sim.specs.orbit['initial'].get('tle_line2',''))
            elif method == "Keplerian Elements":
                c3, c4, c5, c6, c7, c8 = st.columns(6)
                sim.specs.orbit['initial']['a']    = c3.number_input("SMA (km)", 6000.0, 1000000.0,
                    float(sim.specs.orbit['initial']['a']))
                sim.specs.orbit['initial']['e']    = c4.number_input("Eccentricity", 0.0, 0.99,
                    float(sim.specs.orbit['initial']['e']), format="%.4f")
                sim.specs.orbit['initial']['i']    = c5.number_input("Inclination (°)", 0.0, 180.0,
                    float(sim.specs.orbit['initial']['i']))
                sim.specs.orbit['initial']['raan'] = c6.number_input("RAAN (°)", 0.0, 360.0,
                    float(sim.specs.orbit['initial'].get('raan', 0.0)))
                sim.specs.orbit['initial']['arg_p']= c7.number_input("Arg of Perigee (°)", 0.0, 360.0,
                    float(sim.specs.orbit['initial'].get('arg_p', 0.0)))
                sim.specs.orbit['initial']['nu']   = c8.number_input("True Anomaly (°)", 0.0, 360.0,
                    float(sim.specs.orbit['initial'].get('nu', 0.0)))

            st.markdown("**3.2 Target / Destination Orbit**")
            c9, c10, c11 = st.columns(3)
            sim.specs.orbit['target']['type'] = c9.selectbox("Target Orbit/Body",
                ["LEO","MEO","GEO","GSO","SSO","Lunar Orbit","Moon",
                 "Mars","Venus","Jupiter","Saturn","Mercury",
                 "Europa","Titan","Enceladus","Interplanetary"])
            sim.specs.orbit['target']['description']   = c10.text_input(
                "Orbit Description", sim.specs.orbit['target'].get('description',''))
            sim.specs.orbit['target']['arrival_body']  = c11.selectbox(
                "Arrival Central Body",
                ["Earth","Moon","Mars","Sun","Jupiter","Saturn","Venus","Mercury"])

            if st.button("🔍 Review Section 3", key="r3"):
                verdict, transcript = sim.review_section("ORBIT", sim.specs.orbit)
                st.session_state.section_verdicts['s3'] = {"v": verdict, "t": transcript[-1]['text']}
            if 's3' in st.session_state.section_verdicts:
                v = st.session_state.section_verdicts['s3']
                st.markdown(f"**{v['v']}** — {v['t'][:300]}…")

        # ════════════════════════════════════════════════════════
        # SECTION 4: MISSION CONSTRAINTS
        # ════════════════════════════════════════════════════════
        with st.expander("SECTION 4: MISSION CONSTRAINTS"):
            st.markdown("**4.1 Trajectory Constraints**")
            c1, c2, c3, c4 = st.columns(4)
            sim.specs.constraints['trajectory']['max_delta_v']   = c1.number_input(
                "Max Δv (m/s)", 0.0, 50000.0,
                float(sim.specs.constraints['trajectory']['max_delta_v']))
            sim.specs.constraints['trajectory']['max_duration_days'] = c2.number_input(
                "Max Duration (days)", 1, 36500,
                int(sim.specs.constraints['trajectory']['max_duration_days']))
            sim.specs.constraints['trajectory']['maneuver_type'] = c3.selectbox(
                "Maneuver Type", ["Hohmann","Bi-Elliptic","Low-Thrust Spiral",
                                   "Gravity Assist","Lambert Arc","Hybrid"])
            sim.specs.constraints['trajectory']['transfer_type'] = c4.selectbox(
                "Transfer Type", ["Hohmann","Bi-Elliptic","Low-Thrust","Ballistic Capture","Custom"])

            st.markdown("**4.2 Safety Constraints**")
            c5, c6, c7, c8 = st.columns(4)
            sim.specs.constraints['safety']['min_altitude_km']  = c5.number_input(
                "Min Altitude (km)", 100.0, 40000.0,
                float(sim.specs.constraints['safety']['min_altitude_km']))
            sim.specs.constraints['safety']['max_altitude_km']  = c6.number_input(
                "Max Altitude (km)", 100.0, 2000000.0,
                float(sim.specs.constraints['safety']['max_altitude_km']))
            sim.specs.constraints['safety']['collision_avoidance'] = c7.checkbox(
                "Collision Avoidance Required",
                bool(sim.specs.constraints['safety']['collision_avoidance']))
            sim.specs.constraints['safety']['radiation_limit']  = c8.selectbox(
                "Radiation Limit",
                ["Minimize Exposure","< 10 krad TID","< 50 krad TID",
                 "< 100 krad TID","No Limit"])

            st.markdown("**4.3 Operational Constraints**")
            c9, c10, c11, c12 = st.columns(4)
            sim.specs.constraints['operational']['ground_contact_required'] = c9.checkbox(
                "Ground Contact Required",
                bool(sim.specs.constraints['operational']['ground_contact_required']))
            sim.specs.constraints['operational']['sun_exclusion_angle'] = c10.number_input(
                "Sun Exclusion Angle (°)", 0.0, 90.0,
                float(sim.specs.constraints['operational']['sun_exclusion_angle']))
            sim.specs.constraints['operational']['thermal_min'] = c11.number_input(
                "Thermal Min Op (°C)", -200.0, 0.0,
                float(sim.specs.constraints['operational']['thermal_min']))
            sim.specs.constraints['operational']['thermal_max'] = c12.number_input(
                "Thermal Max Op (°C)", 0.0, 200.0,
                float(sim.specs.constraints['operational']['thermal_max']))

            st.markdown("**4.4 Regulatory**")
            c13, c14 = st.columns(2)
            sim.specs.constraints['regulatory']['license'] = c13.text_input(
                "Regulatory License / Authority",
                sim.specs.constraints['regulatory'].get('license',''))
            sim.specs.constraints['regulatory']['debris_mitigation'] = c14.selectbox(
                "Debris Mitigation Plan",
                ["25-Year Deorbit Required","GEO Graveyard (+300 km)",
                 "Active Deorbit System (ADR)","Passivation Only","TBD"])

            if st.button("🔍 Review Section 4", key="r4"):
                verdict, transcript = sim.review_section("CONSTRAINTS", sim.specs.constraints)
                st.session_state.section_verdicts['s4'] = {"v": verdict, "t": transcript[-1]['text']}
            if 's4' in st.session_state.section_verdicts:
                v = st.session_state.section_verdicts['s4']
                st.markdown(f"**{v['v']}** — {v['t'][:300]}…")

        # ════════════════════════════════════════════════════════
        # SECTION 5: ENVIRONMENTAL CONDITIONS
        # ════════════════════════════════════════════════════════
        with st.expander("SECTION 5: ENVIRONMENTAL CONDITIONS"):
            c1, c2, c3 = st.columns(3)
            sim.specs.environment['space_weather']['solar_activity'] = c1.select_slider(
                "Solar Activity", ["Minimum","Average","Maximum"],
                value=sim.specs.environment['space_weather']['solar_activity'])
            sim.specs.environment['space_weather']['kp_index'] = c2.selectbox(
                "Kp Index Assumption", ["Use Real-Time","Kp = 3 (quiet)","Kp = 5 (moderate)","Kp = 8 (storm)"])
            sim.specs.environment['environment'] = c3.selectbox(
                "Drag Model", ["NRLMSISE-00","JB2008","GMAT","Exponential Atmosphere"])

            c4, c5, c6 = st.columns(3)
            sim.specs.environment['perturbations']['j2'] = c4.checkbox(
                "J2 Oblateness", bool(sim.specs.environment['perturbations']['j2']))
            sim.specs.environment['perturbations']['higher_order_gravity'] = c5.checkbox(
                "Higher-Order Gravity (J3–J6)",
                bool(sim.specs.environment['perturbations']['higher_order_gravity']))
            sim.specs.environment['perturbations']['solar_pressure'] = c6.checkbox(
                "Solar Radiation Pressure",
                bool(sim.specs.environment['perturbations']['solar_pressure']))
            sim.specs.environment['perturbations']['third_body'] = st.multiselect(
                "Third-Body Perturbations", ["Moon","Sun","Jupiter","Venus","Mars"],
                default=sim.specs.environment['perturbations']['third_body'])
            sim.specs.environment['debris']['track'] = st.checkbox(
                "Enable Debris Tracking",
                bool(sim.specs.environment['debris']['track']))

        # ════════════════════════════════════════════════════════
        # SECTION 6: OPTIMIZATION
        # ════════════════════════════════════════════════════════
        with st.expander("SECTION 6: OPTIMIZATION PREFERENCES"):
            c1, c2 = st.columns(2)
            sim.specs.optimization['goal'] = c1.radio(
                "Primary Goal", ["Minimum Fuel","Minimum Time","Balanced","Maximum Safety","Custom Weights"])
            sim.specs.optimization['planning']['autonomy_level'] = c2.selectbox(
                "Autonomy Level", ["Minimal","Standard","Full"])

            if sim.specs.optimization['goal'] == "Custom Weights":
                st.markdown("**Custom Weight Sliders (must sum to 100)**")
                c3, c4, c5 = st.columns(3)
                w_fuel   = c3.slider("Fuel Weight",   0, 100,
                    int(sim.specs.optimization['custom_weights']['fuel']))
                w_time   = c4.slider("Time Weight",   0, 100,
                    int(sim.specs.optimization['custom_weights']['time']))
                w_safety = c5.slider("Safety Weight", 0, 100,
                    int(sim.specs.optimization['custom_weights']['safety']))
                sim.specs.optimization['custom_weights'] = {
                    "fuel": w_fuel, "time": w_time, "safety": w_safety}
                total_w = w_fuel + w_time + w_safety
                if total_w != 100:
                    st.warning(f"⚠️ Weights sum to {total_w}, not 100. Normalize before submission.")

            c6, c7 = st.columns(2)
            sim.specs.optimization['planning']['horizon_days'] = c6.number_input(
                "Planning Horizon (days)", 1, 3650,
                int(sim.specs.optimization['planning']['horizon_days']))
            sim.specs.optimization['planning']['replanning_freq'] = c7.number_input(
                "Replanning Frequency (hours)", 1, 720,
                int(sim.specs.optimization['planning']['replanning_freq']))

        # ════════════════════════════════════════════════════════
        # SECTION 7: TARGETS & OBJECTIVES
        # ════════════════════════════════════════════════════════
        with st.expander("SECTION 7: TARGETS & OBJECTIVES"):
            c1, c2, c3, c4 = st.columns(4)
            sim.specs.targets['definitions']['type']           = c1.selectbox(
                "Target Type", ["Satellite","Space Station","Asteroid","Planet",
                                  "Moon","Ground Target","Deep Space Point"])
            sim.specs.targets['definitions']['id']             = c2.text_input(
                "Target Identifier", sim.specs.targets['definitions']['id'])
            sim.specs.targets['definitions']['geometry']       = c3.selectbox(
                "Approach Geometry", ["Direct Rendezvous","Formation Flying",
                                        "Observation","Fly-by","Orbital Insertion"])
            sim.specs.targets['definitions']['approach_speed'] = c4.number_input(
                "Approach Speed (m/s)", 0.0, 100.0,
                float(sim.specs.targets['definitions']['approach_speed']))

            st.markdown("**Ground Track Coverage**")
            sim.specs.targets['ground_track']['coverage'] = st.selectbox(
                "Coverage Requirement",
                ["Global","Regional","Single Ground Station","Polar","Equatorial","Custom"])

        # ════════════════════════════════════════════════════════
        # SECTION 8: COST BREAKDOWN & CONTINGENCY
        # ════════════════════════════════════════════════════════
        with st.expander("SECTION 8: COST BREAKDOWN & CONTINGENCY 💰", expanded=False):
            st.caption("Fill known line items. Check **AI estimates** to let the council compute unknowns using NASA NICM CERs.")
            LINE_ITEMS = [
                ("spacecraft_bus",  "🛰 Spacecraft Bus ($M)",        "Structure, ACS, propulsion, harness"),
                ("payload",         "🔭 Payload / Instruments ($M)", "Cameras, spectrometers, science instruments"),
                ("launch_vehicle",  "🚀 Launch Vehicle ($M)",        "Falcon 9 ~$70M, Falcon Heavy ~$130M"),
                ("ground_segment",  "📡 Ground Segment ($M)",        "Mission control, ground stations, software"),
                ("operations",      "🖥 Operations ($M/yr × yrs)",   "Ops team, DSN tracking, data analysis"),
            ]
            known_vals = {}
            for key, label, tip in LINE_ITEMS:
                ca, cb = st.columns([3, 1])
                na_checked = cb.checkbox("AI estimates", value=st.session_state.cost_na.get(key, True),
                                         key=f"na_{key}", help=tip)
                st.session_state.cost_na[key] = na_checked
                if na_checked:
                    ca.markdown(f"**{label}** &nbsp; `AI will estimate`")
                    known_vals[key] = "UNKNOWN"
                else:
                    val = ca.number_input(label, min_value=0.0, max_value=100000.0,
                                          value=float(st.session_state.cost_breakdown.get(key) or 0.0),
                                          step=1.0, format="%.1f", help=tip, key=f"val_{key}")
                    st.session_state.cost_breakdown[key] = val
                    known_vals[key] = val
            sim.specs.cost_breakdown = known_vals

            # Live cost estimate pie chart
            try:
                from agent_tools import AgentTools as _AT
                _dry   = float(sim.specs.configuration['physical']['mass_dry'])
                _orbit = str(sim.specs.orbit['target'].get('type', 'LEO'))
                _dur   = float(sim.specs.overview['duration_value'])
                _risk  = sim.specs.overview['priority']
                _est   = _AT.cost_estimation_parametric(_dry, _orbit, _dur, _risk, known_vals)
                _items = _est['line_items_usd_m']
                _total = float(_est['estimated_total_m'])
                if not math.isfinite(_total): _total = 0.0
                _total = min(_total, 1_000_000.0)
                fig_cost = go.Figure(go.Pie(
                    labels=list(_items.keys()),
                    values=[min(float(v), 1e6) for v in _items.values()],
                    hole=0.42, textinfo="label+percent",
                    marker=dict(colors=["#1a6aff","#00e5ff","#1aff88","#ffcc00","#ff6644","#aa44ff","#ff4488"]),
                ))
                fig_cost.update_layout(
                    title=f"Budget Allocation — Total: ${_total:.1f}M (est.)",
                    height=320, margin=dict(t=40, b=0, l=0, r=0),
                    paper_bgcolor="rgba(0,0,0,0)", font_color="#c0d8ff",
                )
                st.plotly_chart(fig_cost, use_container_width=True)
                if _est['ai_estimated_items']:
                    st.caption(f"🤖 AI-estimated: {', '.join(_est['ai_estimated_items'])}")
                sim.specs.financials['cost_estimate_m'] = _total
            except Exception as _e:
                st.caption(f"Cost preview unavailable: {_e}")

            st.markdown("**Contingency & Abort**")
            c_ab1, c_ab2 = st.columns(2)
            sim.specs.contingency['abort']['destination'] = c_ab1.selectbox(
                "Abort Destination", ["Safe Parking Orbit","Controlled Deorbit","Return to Origin"])
            sim.specs.contingency['responses']['comm_loss'] = c_ab2.number_input(
                "Comm-Loss Autonomy (hours)", 1, 336,
                int(sim.specs.contingency['responses'].get('comm_loss', 24)))

        # ════════════════════════════════════════════════════════
        # SECTION 9: SIMULATION SETTINGS
        # ════════════════════════════════════════════════════════
        with st.expander("SECTION 9: SIMULATION SETTINGS"):
            c1, c2, c3 = st.columns(3)
            sim.specs.simulation['params']['step_size'] = c1.number_input(
                "Time Step (s)", 1, 3600, int(sim.specs.simulation['params']['step_size']))
            sim.specs.simulation['params']['integrator'] = c2.selectbox(
                "Integrator", ["RK4","RK45","Dormand-Prince","Adams-Bashforth","Verlet"])
            sim.specs.simulation['params']['monte_carlo'] = c3.checkbox(
                "Enable Monte Carlo", bool(sim.specs.simulation['params'].get('monte_carlo', False)))
            if sim.specs.simulation['params']['monte_carlo']:
                sim.specs.simulation['params']['mc_runs'] = st.number_input(
                    "Monte Carlo Runs", 10, 10000,
                    int(sim.specs.simulation['params'].get('mc_runs', 1000)))
            _sim_output_options = ["Timeline","Delta-V Budget","3D Visualisation","Ground Track",
                                   "Link Budget","Thermal Profile","Eclipse Analysis","Porkchop Plot"]
            _sim_output_default = [v for v in sim.specs.simulation.get('outputs', [])
                                   if v in _sim_output_options] or ["Timeline","Delta-V Budget"]
            sim.specs.simulation['outputs'] = st.multiselect(
                "Simulation Outputs", _sim_output_options, default=_sim_output_default)

        # ════════════════════════════════════════════════════════
        # SECTION 10: ADVANCED OPTIONS
        # ════════════════════════════════════════════════════════
        with st.expander("SECTION 10: ADVANCED OPTIONS"):
            c1, c2, c3 = st.columns(3)
            sim.specs.advanced['expert']['custom_propagator']          = c1.checkbox(
                "Use Custom Propagator", bool(sim.specs.advanced['expert']['custom_propagator']))
            sim.specs.advanced['interplanetary']['use_gravity_assist'] = c2.checkbox(
                "Allow Gravity Assists", bool(sim.specs.advanced['interplanetary']['use_gravity_assist']))
            sim.specs.advanced['formation']['inter_sat_link']          = c3.checkbox(
                "Inter-Satellite Links", bool(sim.specs.advanced['formation']['inter_sat_link']))
            c4, c5 = st.columns(2)
            sim.specs.advanced['formation']['type'] = c4.selectbox(
                "Formation Type",
                ["None","Leader-Follower","Pearls on a String","Wheel","Helix","Custom"])
            sim.specs.advanced['interplanetary']['departure_body'] = c5.selectbox(
                "Departure Body", ["Earth","Moon","Mars","Venus","Jupiter","Saturn"])
            flyby_str = st.text_input("Flyby Bodies (comma-separated)",
                ", ".join(sim.specs.advanced['interplanetary'].get('flybys', [])))
            sim.specs.advanced['interplanetary']['flybys'] = [
                f.strip() for f in flyby_str.split(",") if f.strip()]

        # ════════════════════════════════════════════════════════
        # NEW: 20 ADVANCED ENGINEERING MODULES
        # ════════════════════════════════════════════════════════
        try:
            from advanced_inputs import render_advanced_inputs
            render_advanced_inputs(sim)
        except Exception as e:
            st.error(f"Failed to load advanced modules: {e}")

        # ════════════════════════════════════════════════════════
        # SECTION 11: SUBMISSION
        # ════════════════════════════════════════════════════════
        st.markdown("---")
        st.subheader("SECTION 11: SUBMISSION")

        SAFE_MAX = 50_000.0
        try:
            raw_cap = float(sim.specs.financials.get('budget_cap_m', 500.0))
            if not math.isfinite(raw_cap) or raw_cap < 0: raw_cap = 500.0
            raw_cap = min(raw_cap, SAFE_MAX)
        except Exception:
            raw_cap = 500.0

        new_cap = st.number_input("Final Budget Cap ($M)", min_value=1.0,
                                  max_value=SAFE_MAX, value=raw_cap, step=10.0, format="%.1f")
        sim.specs.financials['budget_cap_m'] = new_cap
        try:
            sim.specs.budget_cap_m = new_cap
        except Exception:
            pass

        btn_text = ("➡️ SUBMIT FOR FINAL VALIDATION"
                    if st.session_state.mission_stage != "REVIEW" else "🔄 UPDATE MISSION PLAN")
        if st.button(btn_text, type="primary"):
            sim.recalculate_budgets()
            cost_v   = min(float(sim.specs.financials.get('cost_estimate_m', 0.0)), SAFE_MAX)
            budget_v = min(float(sim.specs.financials.get('budget_cap_m', 500.0)), SAFE_MAX)
            st.session_state.mrd_summary = f"""
## MISSION SPECIFICATION SUMMARY
**Mission:** {sim.specs.overview['name']} ({sim.specs.overview['type']})
**Target:** {sim.specs.orbit['target']['type']}
**Wet Mass:** {sim.specs.configuration['physical']['mass_wet']:.0f} kg
**Propulsion:** {sim.specs.configuration['propulsion']['type']}
**Cost Est.:** ${cost_v:.1f}M  |  **Budget Cap:** ${budget_v:.1f}M
"""
            st.session_state.mission_stage = "REVIEW"
            st.rerun()

    elif st.session_state.mission_stage == "APPROVED":
        st.success("✅ Configuration Locked. Proceed to the Execution Tab.")


# ═══════════════════════════════════════════════════════════
# TAB 2 — MULTI-AGENT COUNCIL
# ═══════════════════════════════════════════════════════════
with tab2:
    if st.session_state.mission_stage in ["REVIEW", "APPROVED"]:
        st.header("📢 The Grand Council of Experts")
        c1, c2 = st.columns([2, 1])
        c1.info("The Council verifies your plan against Physics, Regulations, and Costs.")
        c1.markdown(st.session_state.mrd_summary)

        if c2.button("📢 CONVENE COUNCIL", type="primary"):
            st.session_state.debate_transcript = []
            st.session_state.final_verdict     = "PASS"
            st.markdown("### 🔄 Council in Progress…")
            progress_bar = st.progress(0, text="Starting council…")

            from aerofleet.agents.council import CouncilOfExperts
            
            council = CouncilOfExperts()
            mission_plan = sim.specs.__dict__
            
            progress_bar.progress(50, text="⚙️ Running 17-Agent Council Debate (Iterative ACO)...")
            try:
                final_plan, transcript = council.run_grand_debate(mission_plan)
                st.session_state.debate_transcript = transcript
                
                # Render results
                st.markdown("### 🧑‍🔬 Agent Critiques")
                for entry in transcript:
                    if entry["role"] == "SYSTEM":
                        continue
                    if entry["role"] == "Chief Planner & Moderator":
                        continue
                    
                    verdict = entry.get("verdict", "GREEN")
                    icon  = "🟢" if verdict == "GREEN" else "🔴" if verdict == "RED" else "🟡"
                    label = "APPROVED" if verdict == "GREEN" else "OBJECTION" if verdict == "RED" else "CAUTION"
                    dur = entry.get("duration_s", 0)
                    model = entry.get("model", "—")
                    
                    with st.container(border=True):
                        st.markdown(f"**{icon} {entry['name']}** — *{entry.get('role', 'Specialist')}* &nbsp;&nbsp;"
                                    f"`{model}` &nbsp; ⏱ {dur}s")
                        st.markdown(f"**{label}**")
                        with st.expander("Read Feedback"):
                            st.markdown(entry["text"])
                
                progress_bar.progress(100, text="✅ Council complete!")
                st.markdown("### 🏛️ Mission Architect's Final Decision")
                
                # Calculate actual RED flags
                non_sys = [t for t in transcript if t.get("role") not in ["SYSTEM", "Chief Planner & Moderator"]]
                red_count = sum(1 for t in non_sys if t.get("verdict") == "RED")

                # Find architect
                architect_entry = next((t for t in reversed(transcript) if t.get("role") == "Chief Planner & Moderator"), None)
                if architect_entry:
                    st.info(architect_entry["text"])
                    # Strictly enforce the 2+ RED rule, overriding the LLM if it hallucinates an approval
                    if red_count >= 2 or "MODIFICATION REQUIRED" in architect_entry["text"].upper():
                        st.session_state.final_verdict = "FAIL"
                    else:
                        st.session_state.final_verdict = "PASS"
                else:
                    st.info("No architect synthesis found.")
                    st.session_state.final_verdict = "FAIL" if red_count >= 2 else "PASS"
                    
            except Exception as e:
                st.error(f"Debate failed: {e}")
                progress_bar.progress(100, text="❌ Council failed")

        # Show previous results
        if st.session_state.debate_transcript:
            non_sys = [t for t in st.session_state.debate_transcript
                       if t.get("role") not in ["SYSTEM","Chief Planner & Moderator"]]
            green = sum(1 for t in non_sys if t.get("verdict") == "GREEN")
            red   = sum(1 for t in non_sys if t.get("verdict") == "RED")
            total = max(len(non_sys), 1)
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("Approval Rate", f"{green}/{total}")
            m2.metric("RED Flags", red)
            m3.metric("Final Verdict",
                      "✅ GREENLIT" if st.session_state.get("final_verdict") == "PASS" else "❌ BLOCKED")
            st.subheader("Council Results")
            for t in non_sys:
                icon = "🟢" if t.get("verdict") == "GREEN" else "🔴" if t.get("verdict") == "RED" else "🟡"
                with st.container(border=True):
                    st.markdown(f"**{icon} {t['name']}**")
                    with st.expander("Read Feedback"):
                        st.markdown(t.get("text", ""))
            arch_prev = next((t for t in st.session_state.debate_transcript
                               if t.get("role") == "Chief Planner & Moderator"), None)
            if arch_prev:
                st.markdown("### 🏛️ Mission Architect's Final Decision")
                st.info(arch_prev["text"])

        if st.session_state.get("final_verdict") == "PASS" and st.session_state.debate_transcript:
            if st.button("✅ LOCK CONFIGURATION"):
                st.session_state.mission_stage = "APPROVED"
                st.balloons()
                st.rerun()
        elif st.session_state.get("final_verdict") == "FAIL" and st.session_state.debate_transcript:
            st.warning("⚠️ Critical issues found. Return to Tab 1 to modify specs.")
    else:
        st.warning("Submit mission specifications (Tab 1) before convening the Council.")


# ═══════════════════════════════════════════════════════════
# TAB 3 — EXECUTION  (Trajectory + Porkchop + VR)
# ═══════════════════════════════════════════════════════════
with tab3:
    if st.session_state.mission_stage == "APPROVED":
        st.subheader("🚀 Mission Execution")
        col_run, col_pdf = st.columns(2)
        if col_run.button("▶️ Run Trajectory Simulation"):
            with st.spinner("Propagating orbit…"):
                sim.generate_flight_plan(sim.specs.orbit['target']['type'],
                                         sim.specs.overview['launch_date'])
                st.success("✅ Orbit propagated.")
        if col_pdf.button("📄 Generate Report PDF"):
            generate_pdf(sim, st.session_state.mrd_summary)
            st.success("✅ Report Generated.")

        st.divider()

        # ── Porkchop Plot ──────────────────────────────────────────────────
        with st.expander("🌶️ Porkchop Plot — Launch Window Analysis", expanded=True):
            st.caption("Delta-V heatmap across departure date × time-of-flight. Find the optimal launch window.")
            pc_c1, pc_c2, pc_c3 = st.columns(3)
            origin_body = pc_c1.selectbox("Origin Body", ["EARTH","MARS","VENUS"], key="pc_origin")
            target_body = pc_c2.selectbox("Destination",
                ["MARS","MOON","VENUS","JUPITER","SATURN","MERCURY","EARTH"], key="pc_target")
            span_days   = pc_c3.slider("Window Span (days)", 60, 730, 360)

            launch_base = sim.specs.overview['launch_date']
            span_start  = launch_base - timedelta(days=span_days // 2)
            span_end    = launch_base + timedelta(days=span_days // 2)

            if st.button("🌶️ Generate Porkchop Plot", type="primary"):
                with st.spinner("Computing Δv grid…"):
                    try:
                        from trajectory_engine import TrajectoryEngine
                        from data_loader import MissionDataLoader
                        _root   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        _loader = MissionDataLoader(_root)
                        _te     = TrajectoryEngine(_loader)
                        pc_data = _te.generate_porkchop_data(origin_body, target_body, span_start, span_end)
                        st.session_state.porkchop_data = pc_data
                        st.success("✅ Porkchop computed.")
                    except Exception as e:
                        st.error(f"Porkchop error: {e}")
                        st.session_state.porkchop_data = None

            if st.session_state.porkchop_data:
                pd_data = st.session_state.porkchop_data
                x_dates = pd_data['x_dates']
                y_tof   = pd_data['y_tof']
                z_vals  = np.array(pd_data['z_values'])
                min_idx = np.unravel_index(np.argmin(z_vals), z_vals.shape)
                min_dv  = round(float(z_vals[min_idx]), 2)
                best_dep = x_dates[min_idx[1]] if min_idx[1] < len(x_dates) else "?"
                best_tof = y_tof[min_idx[0]]   if min_idx[0] < len(y_tof) else "?"

                st.success(
                    f"⭐ Optimal window: Depart **{best_dep}**, TOF **{best_tof} days**, Δv = **{min_dv} km/s**")

                fig_pc = go.Figure(go.Contour(
                    x=x_dates, y=y_tof, z=z_vals,
                    colorscale=[
                        [0.00, "#001a33"],[0.20, "#003d80"],[0.40, "#0066cc"],
                        [0.55, "#00cc88"],[0.70, "#aaff00"],[0.82, "#ffcc00"],
                        [0.92, "#ff6600"],[1.00, "#cc0000"],
                    ],
                    contours=dict(coloring="heatmap", showlabels=True,
                                  labelfont=dict(size=9, color="white")),
                    colorbar=dict(title="Δv (km/s)",
                                  titlefont=dict(color="#c0d8ff"),
                                  tickfont=dict(color="#c0d8ff")),
                    hovertemplate="Departure: %{x}<br>TOF: %{y} days<br>Δv: %{z:.2f} km/s<extra></extra>",
                ))
                fig_pc.add_trace(go.Scatter(
                    x=[best_dep], y=[best_tof],
                    mode="markers+text",
                    marker=dict(symbol="star", size=16, color="#ffff00",
                                line=dict(color="white", width=1)),
                    text=["Min Δv"], textposition="top center",
                    textfont=dict(color="white", size=10),
                    name=f"Min Δv ({min_dv} km/s)",
                ))
                fig_pc.update_layout(
                    title=dict(
                        text=f"<b>🌶️ Porkchop Plot — {origin_body} → {target_body}</b>",
                        font=dict(color="#e0e8ff", size=18), x=0.5),
                    xaxis=dict(title="Departure Date", tickangle=45,
                               tickfont=dict(color="#c0d8ff"), titlefont=dict(color="#c0d8ff"),
                               gridcolor="#1e3050"),
                    yaxis=dict(title="Time of Flight (days)",
                               tickfont=dict(color="#c0d8ff"), titlefont=dict(color="#c0d8ff"),
                               gridcolor="#1e3050"),
                    paper_bgcolor="#060e1a", plot_bgcolor="#0a1520",
                    font_color="#c0d8ff", height=520,
                    margin=dict(t=60, b=80, l=60, r=40),
                )
                st.plotly_chart(fig_pc, use_container_width=True)
                st.info(f"**X-axis:** Departure date from {origin_body}  \n"
                        f"**Y-axis:** Time of flight to {target_body} (days)  \n"
                        "**Colour:** Total Δv (km/s) — cooler = cheaper  \n"
                        "**⭐:** Minimum-energy (optimal) launch window")

        st.divider()
        with st.expander("🥽 VR / AR Scene Export"):
            if st.button("🌐 Export VR Scene JSON"):
                try:
                    from vr_bridge import get_vr_scene_data, export_vr_json
                    traj  = st.session_state.get('trajectory_data')
                    scene = get_vr_scene_data(sim.specs, traj)
                    mname = sim.specs.overview.get('name', 'Mission')
                    saved_path = export_vr_json(scene, mname)
                    st.success(f"✅ VR scene saved: `{saved_path}`")
                    st.download_button("⬇️ Download VR JSON",
                                       data=open(saved_path, 'rb').read(),
                                       file_name=os.path.basename(saved_path),
                                       mime="application/json")
                except Exception as e:
                    st.error(f"VR export failed: {e}")
    else:
        st.warning("Mission must be APPROVED by the Council before accessing Execution.")


# ═══════════════════════════════════════════════════════════
# TAB 4 — LIVE SATELLITE TRACKER
# ═══════════════════════════════════════════════════════════
with tab4:
    st.header("🌍 Live Satellite Tracker")
    st.caption("Real-time positions of satellites — CelesTrak public TLE feeds, SGP4 propagation, orthographic globe.")

    try:
        from satellite_tracker import (
            CONFIRMED_GROUPS, get_cached_satellites,
            build_satellite_globe, build_altitude_histogram,
        )
        _tracker_ok = True
    except Exception as _te:
        st.error(f"Satellite tracker module error: {_te}")
        st.code(str(_te))
        _tracker_ok = False

    if _tracker_ok:
        sat_c1, sat_c2, sat_c3, sat_c4 = st.columns([2, 1, 1, 1])
        group_label = sat_c1.selectbox("Satellite Group", list(CONFIRMED_GROUPS.keys()),
                                       key="sat_group")
        # group_label is directly the key for get_cached_satellites
        max_sats    = sat_c2.slider("Max Satellites", 50, 5000, 2000, step=100)
        alt_min     = sat_c3.number_input("Min Alt (km)", 0, 10000, 0)
        alt_max     = sat_c4.number_input("Max Alt (km)", 100, 200000, 200000)

        col_fetch, col_auto = st.columns([1, 3])
        fetch_btn    = col_fetch.button("🔄 Fetch / Refresh", type="primary")
        auto_refresh = col_auto.checkbox("Auto-refresh every 5 min")

        now_ts = _time.time()
        if auto_refresh and (now_ts - st.session_state.sat_fetch_ts) > 300:
            fetch_btn = True

        if fetch_btn or not st.session_state.sat_positions:
            with st.spinner(f"Fetching TLEs from CelesTrak — {group_label}…"):
                _positions = get_cached_satellites(group=group_label, limit=max_sats)
                if _positions:
                    st.session_state.sat_positions = _positions
                    st.session_state.sat_fetch_ts  = _time.time()
                    st.success(f"✅ Loaded {len(_positions):,} satellites from {group_label}")
                else:
                    st.warning("⚠️ No data returned. CelesTrak may be temporarily unavailable. Try a different group or retry in a moment.")

        positions = st.session_state.sat_positions

        if positions:
            filtered = [p for p in positions
                        if alt_min <= p.get("alt_km", 0) <= alt_max]
            alts_f   = [p["alt_km"] for p in filtered]

            # Metrics row
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("🛰 Satellites", f"{len(filtered):,}")
            m2.metric("⬆️ Max Alt",   f"{max(alts_f):.0f} km" if alts_f else "—")
            m3.metric("⬇️ Min Alt",   f"{min(alts_f):.0f} km" if alts_f else "—")
            m4.metric("📊 Avg Alt",   f"{float(np.mean(alts_f)):.0f} km" if alts_f else "—")
            m5.metric("⏱ Data Age",  f"{int(now_ts - st.session_state.sat_fetch_ts)}s ago")

            # ── Orthographic globe ──────────────────────────────────────
            fig_globe = build_satellite_globe(filtered,
                                              title=f"{group_label}")
            # Globe controls hint
            st.caption("💡 **Drag** to rotate the globe · **Scroll** to zoom · **Hover** over a dot for satellite details")
            st.plotly_chart(fig_globe, use_container_width=True)

            # Colour legend
            st.markdown(
                '<div style="display:flex;gap:18px;flex-wrap:wrap;font-size:0.83rem;padding:4px 0;">'
                '<span><span style="color:#00ff88;font-size:1.1rem">●</span> &lt;450 km VLEO</span>'
                '<span><span style="color:#00e5ff;font-size:1.1rem">●</span> 450–800 km LEO</span>'
                '<span><span style="color:#4d9fff;font-size:1.1rem">●</span> 800–2000 km</span>'
                '<span><span style="color:#aa44ff;font-size:1.1rem">●</span> 2–5 Mm MEO-low</span>'
                '<span><span style="color:#ff44cc;font-size:1.1rem">●</span> 5–20 Mm MEO</span>'
                '<span><span style="color:#ffaa00;font-size:1.1rem">●</span> &gt;20 Mm GEO</span>'
                '</div>', unsafe_allow_html=True)

            st.divider()
            # Histogram + data table
            h_col, t_col = st.columns([1, 1])
            with h_col:
                st.plotly_chart(build_altitude_histogram(filtered),
                                use_container_width=True)
            with t_col:
                st.subheader("📋 Satellite List")
                df_sat = pd.DataFrame(filtered)
                if not df_sat.empty:
                    _show = [c for c in ["name","norad_id","alt_km","inclination",
                                         "period_min","velocity_km_s"] if c in df_sat.columns]
                    df_sat = df_sat[_show].rename(columns={
                        "name":"Name","norad_id":"NORAD","alt_km":"Alt (km)",
                        "inclination":"Incl (°)","period_min":"Period (min)",
                        "velocity_km_s":"Speed (km/s)"}).head(500)
                    st.dataframe(df_sat, use_container_width=True, height=300)

            # Search
            st.subheader("🔍 Search")
            sq = st.text_input("Search by name or NORAD ID", key="sat_search")
            if sq:
                hits = [p for p in filtered
                        if sq.lower() in p["name"].lower()
                        or sq in str(p.get("norad_id",""))]
                if hits:
                    for r in hits[:8]:
                        with st.container(border=True):
                            ca, cb, cc, cd, ce = st.columns(5)
                            ca.metric("Name",    r["name"][:20])
                            cb.metric("NORAD",   r.get("norad_id",""))
                            cc.metric("Alt",     f"{r['alt_km']:.0f} km")
                            cd.metric("Incl",    f"{r.get('inclination',0):.1f}°")
                            ce.metric("Speed",   f"{r.get('velocity_km_s',0):.2f} km/s")
                else:
                    st.info("No match found.")
        else:
            st.info("👆 Click **Fetch / Refresh** to load live satellite positions.")
            st.markdown("""
**How It Works:**
1. Downloads TLE (Two-Line Element) data from **[CelesTrak](https://celestrak.org/pub/TLE/)** — completely free, no login
2. Propagates each satellite to the **exact current UTC time** using the SGP4/SDP4 model (same algorithm used by NORAD/US Space Force)
3. Converts ECI (Earth-Centred Inertial) → geodetic lat/lon/altitude (WGS84)
4. Renders positions on an **interactive orthographic globe** — drag to rotate, scroll to zoom

**Available Groups:** Space Stations · Starlink · GPS · GLONASS · Galileo · Weather · Scientific · CubeSats · Active GEO · NOAA
            """)


