import streamlit as st

def render_advanced_inputs(sim):
    st.markdown("---")
    st.header("🔬 ADVANCED ENGINEERING MODULES")
    
    with st.expander("1️⃣ LAUNCH & ASCENT PROFILE"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('launch_ascent', {})
        la = sim.specs.advanced['launch_ascent']
        la['launch_site'] = c1.text_input("Launch Site", "Kennedy Space Center")
        la['complex_pad'] = c2.text_input("Complex / Pad", "LC-39A")
        la['lat_lon'] = c3.text_input("Lat / Lon", "28.57, -80.65")
        la['country'] = c1.text_input("Country", "USA")
        la['range_safety'] = c2.text_input("Range Safety Zone", "Eastern Range")
        la['launch_window'] = c3.selectbox("Launch Window", ["Instantaneous", "Multi-hour"])
        la['backup_windows'] = c1.number_input("Backup Windows", 0, 10, 2)
        la['daily_opps'] = c2.number_input("Daily Opportunities", 1, 5, 1)
        la['parking_orbit'] = c3.number_input("Parking Orbit Alt (km)", 100, 1000, 200)
        la['inj_accuracy'] = c1.number_input("Injection Accuracy (%)", 0.0, 10.0, 99.9)
        la['c3_energy'] = c2.number_input("Injection Energy C3 (km^2/s^2)", -100.0, 200.0, 0.0)
        la['max_q'] = c3.number_input("Max-Q (kPa)", 10, 200, 35)
        la['max_g'] = c1.number_input("Max Acceleration (g)", 1.0, 15.0, 4.5)
        la['fairing_jettison'] = c2.number_input("Fairing Jettison (s)", 50, 500, 180)
        la['stage_sep'] = c3.number_input("Stage Separation (s)", 100, 1000, 210)
        la['wind_limits'] = c1.number_input("Wind Limits (m/s)", 0, 100, 15)
        la['lightning'] = c2.checkbox("Lightning Constraint Active", True)
        la['sea_state'] = c3.number_input("Sea State Limit", 0, 10, 3)
        la['booster_landing'] = c1.text_input("Booster Landing Site", "LZ-1")
        la['recovery_mode'] = c2.selectbox("Recovery Mode", ["RTLS", "ASDS", "Expendable"])
        la['entry_burn_fuel'] = c3.number_input("Entry Burn Fuel Reserve (%)", 0.0, 50.0, 10.0)

    with st.expander("2️⃣ DETAILED PROPULSION SYSTEM DESIGN"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('propulsion_detailed', {})
        pd = sim.specs.advanced['propulsion_detailed']
        pd['chamber_pressure'] = c1.number_input("Chamber Pressure (bar)", 1.0, 500.0, 100.0)
        pd['mixture_ratio'] = c2.number_input("Mixture Ratio (O/F)", 1.0, 10.0, 2.5)
        pd['expansion_ratio'] = c3.number_input("Expansion Ratio", 1.0, 500.0, 40.0)
        pd['nozzle_type'] = c1.selectbox("Nozzle Type", ["Bell", "Aerospike", "Extendable"])
        pd['restart_cap'] = c2.number_input("Restart Capability", 0, 50, 3)
        pd['ignition_sys'] = c3.selectbox("Ignition System", ["Pyrotechnic", "Spark", "Hypergolic", "Laser"])
        pd['fuel_type'] = c1.selectbox("Fuel Type", ["RP-1", "LH2", "Methane", "Hydrazine"])
        pd['ox_type'] = c2.selectbox("Oxidizer Type", ["LOX", "NTO", "Hydrogen Peroxide"])
        pd['density'] = c3.number_input("Propellant Density (kg/m^3)", 100, 2000, 1000)
        pd['boil_off'] = c1.number_input("Boil-off Rate (%/day)", 0.0, 10.0, 0.1)
        pd['tank_material'] = c2.selectbox("Tank Material", ["Aluminum", "Composite COPV", "Steel"])
        pd['pressurization'] = c3.selectbox("Pressurization", ["Helium", "Autogenous", "Blowdown"])
        pd['ullage'] = c1.number_input("Ullage Volume (%)", 1.0, 20.0, 5.0)
        pd['ppu_eff'] = c2.number_input("PPU Efficiency (%)", 50.0, 100.0, 95.0)
        pd['thruster_eff'] = c3.number_input("Thruster Efficiency (%)", 10.0, 100.0, 60.0)
        pd['ep_pressure'] = c1.number_input("Xenon/Krypton Pressure (bar)", 10, 500, 150)
        pd['redundancy'] = c2.selectbox("Engine Redundancy", ["None", "1-Fault Tolerant", "2-Fault Tolerant"])
        pd['fail_prob'] = c3.number_input("Failure Probability (%)", 0.0, 10.0, 0.1)
        pd['burn_margin'] = c1.number_input("Burn Margin (%)", 0.0, 50.0, 5.0)

    with st.expander("3️⃣ ATTITUDE DETERMINATION & CONTROL SYSTEM (ADCS)"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('adcs_detailed', {})
        adcs = sim.specs.advanced['adcs_detailed']
        adcs['star_trackers'] = c1.number_input("Star Tracker Count", 0, 5, 2)
        adcs['sun_sensors'] = c2.number_input("Sun Sensors", 0, 10, 4)
        adcs['magnetometers'] = c3.number_input("Magnetometers", 0, 5, 2)
        adcs['imus'] = c1.number_input("IMUs", 0, 5, 2)
        adcs['gyro_drift'] = c2.number_input("Gyroscope Drift Rate (deg/hr)", 0.0, 10.0, 0.1)
        adcs['reaction_wheels'] = c3.number_input("Reaction Wheel Count", 0, 8, 4)
        adcs['rw_sat_limit'] = c1.number_input("Wheel Saturation Limit (Nms)", 0.1, 100.0, 15.0)
        adcs['magnetorquer'] = c2.number_input("Magnetorquer Strength (Am^2)", 0.0, 500.0, 50.0)
        adcs['ctrl_thrusters'] = c3.number_input("Control Thrusters", 0, 24, 12)
        adcs['ctrl_algo'] = c1.selectbox("Control Algorithms", ["PID", "LQR", "MPC", "AI-based"])
        adcs['fault_tolerant'] = c2.checkbox("Fault-tolerant control", True)
        adcs['gg_torque'] = c3.number_input("Gravity gradient torque (Nm)", 0.0, 0.1, 1e-4, format="%e")
        adcs['aero_torque'] = c1.number_input("Aerodynamic torque (Nm)", 0.0, 0.1, 1e-5, format="%e")
        adcs['solar_torque'] = c2.number_input("Solar torque (Nm)", 0.0, 0.1, 1e-5, format="%e")

    with st.expander("4️⃣ THERMAL ENGINEERING INPUTS"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('thermal', {})
        th = sim.specs.advanced['thermal']
        th['radiator_area'] = c1.number_input("Radiator Area (m^2)", 0.0, 100.0, 5.0)
        th['mli_layers'] = c2.number_input("MLI Layers", 1, 50, 15)
        th['heat_pipes'] = c3.checkbox("Heat Pipe Presence", True)
        th['coating'] = c1.selectbox("Thermal Coating Type", ["White Paint", "Black Paint", "Silver Teflon", "Gold"])
        th['internal_heat'] = c2.number_input("Internal heat generation (W)", 0.0, 5000.0, 250.0)
        th['eclipse_dur'] = c3.number_input("Eclipse duration (min)", 0.0, 500.0, 35.0)
        th['solar_flux'] = c1.number_input("Solar flux assumptions (W/m^2)", 0.0, 3000.0, 1361.0)
        th['survival_temp'] = c2.number_input("Survival mode temperature (°C)", -200.0, 100.0, -20.0)
        th['heater_power'] = c3.number_input("Heater power budget (W)", 0.0, 1000.0, 50.0)
        th['payload_thermal_min'] = c1.number_input("Payload thermal min (°C)", -200.0, 100.0, -10.0)
        th['payload_thermal_max'] = c2.number_input("Payload thermal max (°C)", -100.0, 200.0, 40.0)
        th['battery_temp_min'] = c3.number_input("Battery temp min (°C)", -50.0, 50.0, 0.0)

    with st.expander("5️⃣ STRUCTURAL & MECHANICAL DESIGN"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('structural', {})
        st_ = sim.specs.advanced['structural']
        st_['primary_mat'] = c1.selectbox("Primary Material", ["Aluminum 6061", "Carbon Composite", "Titanium"])
        st_['safety_factor'] = c2.number_input("Safety Factor", 1.0, 5.0, 1.25)
        st_['natural_freq'] = c3.number_input("Natural Frequency (Hz)", 5.0, 100.0, 35.0)
        st_['max_vib'] = c1.number_input("Max launch vibration (Grms)", 0.0, 50.0, 14.0)
        st_['acoustic'] = c2.number_input("Acoustic load tolerance (dB)", 100.0, 200.0, 140.0)
        st_['shock'] = c3.number_input("Shock tolerance (g)", 100.0, 5000.0, 1000.0)
        st_['solar_deploy'] = c1.selectbox("Solar panel deployment", ["Spring-loaded", "Motorized", "Fixed"])
        st_['antenna_deploy'] = c2.selectbox("Antenna deployment type", ["Spring", "Motor", "Inflatable", "Fixed"])
        st_['deploy_timing'] = c3.number_input("Deployment timing (s)", 1, 3600, 600)
        st_['bus_mass'] = c1.number_input("Bus structure mass (kg)", 10.0, 5000.0, 200.0)
        st_['payload_mass'] = c2.number_input("Payload structure mass (kg)", 1.0, 5000.0, 50.0)
        st_['margin_alloc'] = c3.number_input("Margin allocation (%)", 0.0, 50.0, 20.0)

    with st.expander("6️⃣ POWER SYSTEM ENGINEERING"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('power_detailed', {})
        pw = sim.specs.advanced['power_detailed']
        pw['cell_type'] = c1.selectbox("Cell Type", ["GaAs", "Silicon", "Perovskite", "Multi-junction"])
        pw['degradation'] = c2.number_input("Degradation Rate (%/yr)", 0.0, 10.0, 2.5)
        pw['sun_angle'] = c3.number_input("Sun incidence angle (deg)", 0.0, 90.0, 0.0)
        pw['batt_chem'] = c1.selectbox("Battery Chemistry", ["Li-Ion", "NiH2", "Li-Po", "Solid State"])
        pw['dod'] = c2.number_input("Depth of Discharge (%)", 10.0, 100.0, 30.0)
        pw['cycle_life'] = c3.number_input("Cycle Life", 100, 100000, 30000)
        pw['charge_eff'] = c1.number_input("Charging efficiency (%)", 50.0, 100.0, 90.0)
        pw['bus_voltage'] = c2.number_input("Bus voltage (V)", 5.0, 300.0, 28.0)
        pw['bus_type'] = c3.selectbox("Bus Type", ["Regulated", "Unregulated"])
        pw['redundant_bus'] = c1.checkbox("Redundant buses", True)
        pw['eclipse_margin'] = c2.number_input("Eclipse power margin (%)", 0.0, 100.0, 20.0)
        pw['contingency'] = c3.number_input("Contingency reserve (%)", 0.0, 100.0, 10.0)

    with st.expander("7️⃣ COMMUNICATION SYSTEMS"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('comms_detailed', {})
        cm = sim.specs.advanced['comms_detailed']
        cm['eirp'] = c1.number_input("EIRP (dBW)", 0.0, 100.0, 40.0)
        cm['ant_gain'] = c2.number_input("Antenna Gain (dBi)", 0.0, 100.0, 30.0)
        cm['point_loss'] = c3.number_input("Pointing Loss (dB)", 0.0, 10.0, 1.0)
        cm['atm_loss'] = c1.number_input("Atmospheric Loss (dB)", 0.0, 20.0, 0.5)
        cm['ber'] = c2.number_input("Bit Error Rate (10^-x)", 1, 15, 6)
        cm['relay_sats'] = c3.checkbox("Relay satellites (TDRSS/EDRS)", False)
        cm['dsn_usage'] = c1.checkbox("DSN usage", False)
        cm['ground_net'] = c2.text_input("Ground station network", "KSAT, AWS Ground Station")
        cm['modulation'] = c3.selectbox("Modulation", ["QPSK", "BPSK", "QAM", "FSK"])
        cm['coding'] = c1.selectbox("Coding scheme", ["LDPC", "Reed-Solomon", "Turbo", "Convolutional"])
        cm['light_time'] = c2.number_input("One-way light time (s)", 0.0, 20000.0, 0.1)
        cm['delay_tol'] = c3.number_input("Signal delay tolerance (s)", 0.0, 10000.0, 5.0)

    with st.expander("8️⃣ PAYLOAD-SPECIFIC ENGINEERING"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('payload_detailed', {})
        pl = sim.specs.advanced['payload_detailed']
        pl['type'] = c1.selectbox("Payload Type", ["Camera", "SAR", "Spectrometer", "Science", "Robotics"])
        pl['resolution'] = c2.number_input("Resolution (m)", 0.01, 1000.0, 1.0)
        pl['swath'] = c3.number_input("Swath width (km)", 1.0, 5000.0, 15.0)
        pl['fov'] = c1.number_input("Field of view (deg)", 0.1, 180.0, 2.5)
        pl['accuracy'] = c2.number_input("Instrument accuracy (%)", 0.01, 100.0, 99.0)
        pl['cal_freq'] = c3.number_input("Calibration freq (days)", 1, 365, 30)
        pl['cal_targets'] = c1.text_input("Calibration targets", "Moon, Deep Space")
        pl['obs_sched'] = c2.selectbox("Observation scheduling", ["Autonomous", "Ground-commanded"])
        pl['dwell_time'] = c3.number_input("Target dwell time (s)", 1.0, 3600.0, 60.0)

    with st.expander("9️⃣ ORBITAL MECHANICS & TRAJECTORY DESIGN"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('orbit_detailed', {})
        ob = sim.specs.advanced['orbit_detailed']
        ob['epoch'] = c1.text_input("Epoch Time (UTC)", "2028-01-01T00:00:00Z")
        ob['ref_frame'] = c2.selectbox("Reference Frame", ["J2000", "ITRF", "EME2000"])
        ob['elements'] = c3.selectbox("Elements Type", ["Mean", "Osculating"])
        ob['burn_type'] = c1.selectbox("Maneuver Planning", ["Impulsive", "Finite burns"])
        ob['burn_dur'] = c2.number_input("Burn duration (s)", 1.0, 50000.0, 300.0)
        ob['grav_assist'] = c3.text_input("Gravity assist sequence", "E-V-V-E-J")
        ob['lambert'] = c1.checkbox("Lambert solver constraints", True)
        ob['dsm'] = c2.checkbox("Deep Space Maneuvers (DSM)", False)
        ob['sk_freq'] = c3.number_input("Station-Keeping freq (days)", 1, 365, 14)
        ob['drift_tol'] = c1.number_input("Drift tolerance (deg)", 0.01, 5.0, 0.1)
        ob['edl_alt'] = c2.number_input("Entry interface altitude (km)", 10.0, 1000.0, 120.0)
        ob['edl_shield'] = c3.text_input("Heat shield parameters", "PICA-X, 5cm")
        ob['landing_ellipse'] = c1.text_input("Landing ellipse (km)", "10x5")

    with st.expander("🔟 GUIDANCE, NAVIGATION & AUTONOMY"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('gnc_detailed', {})
        gn = sim.specs.advanced['gnc_detailed']
        gn['gnss'] = c1.checkbox("GPS/GNSS usage", True)
        gn['optical_nav'] = c2.checkbox("Optical navigation", False)
        gn['trn'] = c3.checkbox("Terrain-relative navigation", False)
        gn['auto_traj'] = c1.checkbox("Autonomous trajectory correction", False)
        gn['docking'] = c2.checkbox("Docking guidance", False)
        gn['safe_mode'] = c3.checkbox("Autonomous safe mode", True)
        gn['fdir'] = c1.selectbox("FDIR Level", ["Basic", "Advanced AI-driven", "Hardware-only"])
        gn['ai_thresh'] = c2.number_input("Autonomous decision threshold (%)", 50.0, 99.9, 95.0)
        gn['ai_margins'] = c3.number_input("AI confidence margins (%)", 1.0, 50.0, 10.0)

    with st.expander("1️⃣1️⃣ SPACE ENVIRONMENT & RADIATION"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('env_detailed', {})
        en = sim.specs.advanced['env_detailed']
        en['tid'] = c1.number_input("Total Ionizing Dose (krad)", 1.0, 1000.0, 50.0)
        en['see_tol'] = c2.selectbox("SEE tolerance", ["High", "Medium", "Low (COTS)"])
        en['shield_thick'] = c3.number_input("Shielding thickness (mm Al)", 1.0, 50.0, 5.0)
        en['impact_prob'] = c1.number_input("Micrometeoroid Impact Prob (%)", 0.01, 10.0, 1.0)
        en['shield_mat'] = c2.selectbox("Shielding material", ["Aluminum", "Kevlar/Nextel", "Titanium"])
        en['solar_storm'] = c3.checkbox("Solar storm tolerance", True)
        en['sep_event'] = c1.checkbox("SEP event assumptions active", True)

    with st.expander("1️⃣2️⃣ RELIABILITY & REDUNDANCY ENGINEERING"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('rel_detailed', {})
        rl = sim.specs.advanced['rel_detailed']
        rl['target'] = c1.number_input("Mission reliability target (%)", 50.0, 99.999, 99.0)
        rl['mtbf'] = c2.number_input("MTBF (hours)", 1000, 1000000, 50000)
        rl['fta'] = c3.checkbox("Failure tree analysis required", True)
        rl['cold_red'] = c1.checkbox("Cold redundancy", True)
        rl['hot_red'] = c2.checkbox("Hot redundancy", False)
        rl['cross_strap'] = c3.checkbox("Cross-strapping", True)
        rl['mass_marg'] = c1.number_input("Mass margin (%)", 0.0, 50.0, 20.0)
        rl['power_marg'] = c2.number_input("Power margin (%)", 0.0, 50.0, 20.0)
        rl['fuel_res'] = c3.number_input("Fuel reserve (%)", 0.0, 50.0, 10.0)

    with st.expander("1️⃣3️⃣ OPERATIONS & GROUND SEGMENT"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('ops_detailed', {})
        op = sim.specs.advanced['ops_detailed']
        op['team_size'] = c1.number_input("Operations team size", 1, 500, 20)
        op['contact_sched'] = c2.selectbox("Contact schedule", ["Continuous", "Intermittent", "Autonomous"])
        op['shift_plan'] = c3.selectbox("Shift planning", ["24/7", "8/5", "On-call"])
        op['gs_loc'] = c1.text_input("Ground station locations", "Goldstone, Madrid, Canberra")
        op['ant_diam'] = c2.number_input("Antenna diameter (m)", 1.0, 70.0, 34.0)
        op['cloud_backup'] = c3.checkbox("Cloud backup", True)
        op['tlm_rate'] = c1.number_input("Telemetry packet rate (Hz)", 1, 1000, 10)
        op['hk_freq'] = c2.number_input("Housekeeping frequency (Hz)", 0.1, 10.0, 1.0)
        op['leop'] = c3.checkbox("LEOP dedicated team", True)

    with st.expander("1️⃣4️⃣ HUMAN SPACEFLIGHT INPUTS"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('human_flight', {})
        hf = sim.specs.advanced['human_flight']
        hf['crew_size'] = c1.number_input("Crew size", 0, 20, 0)
        hf['life_support'] = c2.number_input("Life support duration (days)", 0, 1000, 0)
        hf['eva'] = c3.checkbox("EVA capability", False)
        hf['hab'] = c1.number_input("Habitable Volume (m^3)", 0.0, 1000.0, 0.0)
        hf['o2_res'] = c2.number_input("Oxygen reserve (days)", 0, 100, 0)
        hf['co2'] = c3.selectbox("CO2 scrubbing", ["None", "LiOH", "Amine Swingbed"])
        hf['rad_shelter'] = c1.checkbox("Radiation shelter", False)

    with st.expander("1️⃣5️⃣ SAFETY & REGULATORY COMPLIANCE"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('safety_detailed', {})
        sf = sim.specs.advanced['safety_detailed']
        sf['fTS'] = c1.checkbox("Range safety destruct system (FTS)", True)
        sf['haz_class'] = c2.selectbox("Hazard classification", ["Low", "Medium", "High"])
        sf['abort_modes'] = c3.text_input("Abort modes", "RTLS, TAL, ATO")
        sf['itu'] = c1.checkbox("ITU frequency licensing", True)
        sf['fcc'] = c2.checkbox("FCC/IN-SPACe approvals", True)
        sf['plan_prot'] = c3.selectbox("Planetary protection category", ["I", "II", "III", "IVa", "IVb", "V"])

    with st.expander("1️⃣6️⃣ AI/OPTIMIZATION ENGINE MISSING INPUTS"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('ai_opt_detailed', {})
        ai = sim.specs.advanced['ai_opt_detailed']
        ai['algo'] = c1.selectbox("Optimization Algorithms", ["Genetic algorithm", "PSO", "Reinforcement learning", "MILP solver"])
        ai['conf_thresh'] = c2.number_input("Confidence threshold (%)", 50.0, 99.9, 90.0)
        ai['constraint_prio'] = c3.selectbox("Constraint priority", ["Safety First", "Cost First", "Science First"])
        ai['pareto'] = c1.selectbox("Pareto frontier resolution", ["Low", "Medium", "High"])
        ai['cost_weight'] = c2.selectbox("Cost-function weighting", ["Linear", "Exponential", "Dynamic"])

    with st.expander("1️⃣7️⃣ DIGITAL TWIN & SIMULATION VALIDATION"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('sim_detailed', {})
        sm = sim.specs.advanced['sim_detailed']
        sm['fidelity'] = c1.selectbox("Simulation Fidelity", ["Low", "Medium", "High"])
        sm['real_time'] = c2.checkbox("Real-time simulation mode", False)
        sm['hitl'] = c3.checkbox("Hardware-in-the-loop", False)
        sm['sensor_emu'] = c1.checkbox("Sensor emulation", True)
        sm['fc_int'] = c2.checkbox("Flight computer integration", False)
        sm['heritage'] = c3.checkbox("Correlation with heritage missions", True)
        sm['mc_conv'] = c1.number_input("Monte Carlo convergence criteria (%)", 0.1, 10.0, 1.0)

    with st.expander("1️⃣8️⃣ CYBERSECURITY"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('cyber', {})
        cy = sim.specs.advanced['cyber']
        cy['encryption'] = c1.selectbox("Encryption type", ["AES-256", "ChaCha20", "None"])
        cy['secure_uplink'] = c2.checkbox("Secure uplink required", True)
        cy['anti_jam'] = c3.checkbox("Anti-jamming systems", False)
        cy['auth'] = c1.selectbox("Authentication protocols", ["RSA", "ECDSA", "HMAC"])

    with st.expander("1️⃣9️⃣ SPACECRAFT SOFTWARE SYSTEMS"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('sw_detailed', {})
        sw = sim.specs.advanced['sw_detailed']
        sw['rtos'] = c1.selectbox("RTOS type", ["VxWorks", "RTEMS", "FreeRTOS", "Linux"])
        sw['update_cap'] = c2.checkbox("OTA Update capability", True)
        sw['autonomy_lvl'] = c3.selectbox("Autonomy software level", ["ECSS E-1", "ECSS E-2", "ECSS E-3", "ECSS E-4"])
        sw['watchdog'] = c1.checkbox("Watchdog timers", True)
        sw['mem_scrub'] = c2.checkbox("Memory scrubbing", True)

    with st.expander("2️⃣0️⃣ SCIENCE & MISSION VALUE METRICS"):
        c1, c2, c3 = st.columns(3)
        sim.specs.advanced.setdefault('sci_detailed', {})
        sc = sim.specs.advanced['sci_detailed']
        sc['sci_return'] = c1.text_area("Expected science return", "High-resolution mapping of target")
        sc['obs_prio'] = c2.selectbox("Observation priority", ["Time-critical", "Target-of-opportunity", "Background"])
        sc['coverage_pct'] = c3.number_input("Coverage percentage target (%)", 1.0, 100.0, 80.0)
        sc['roi'] = c1.number_input("Commercial ROI expectation (%)", 0.0, 1000.0, 15.0)
        sc['strat_imp'] = c2.selectbox("Strategic importance", ["Low", "Medium", "High", "Critical"])
        sc['tech_demo'] = c3.text_area("Technology demonstration goals", "Test new Hall thruster in deep space")
