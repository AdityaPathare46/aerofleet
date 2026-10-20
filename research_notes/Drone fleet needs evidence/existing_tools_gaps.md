# Existing drone fleet-ops / compliance / log-analysis tools and gaps (ArduPilot/PX4, India)

Research date: 20 Oct 2026. Already-known items (Airdata, FlyFreely, Auterion Suite, Mission Planner Compare Params, Parachute CLI) were not re-researched. About 19 tool calls were used, so coverage is partial. See Gaps.

## What other tools exist, what do they do, and what do they cost?

### Takeaway
Commercial fleet-ops tools cluster around logbooks, pilots/jobs, checklists, risk assessments, airspace and maintenance schedules. Log auto-sync is mostly DJI-first. None of the vendor pages I checked mention parameter or firmware consistency across a fleet, or checking a flight against its plan, for ArduPilot/PX4. Indian tools focus on spraying operations, booking and invoicing, and type-certified GCS software. None of them, as described publicly, does post-flight diagnosis or configuration auditing.

### Cited Findings
**Dronedesk (UK)**
- Plans are Startup (1 user, 3 jobs/month, flight logging, checklists, risk assessments), Pro (unlimited jobs, "Flight log auto-sync (DJI)", SORA add-on), Unlimited (unlimited users, annual invoiced) and Specialist (contact sales, white label). The official page did not render the prices. Its only log import is DJI auto-sync, and the page does not mention ArduPilot/PX4, maintenance or parameter tracking. — [Dronedesk pricing](https://www.dronedesk.io/pricing)
- A third-party aggregator lists the prices as Startup $14/mo, Pro $28/mo (+$10/user), and Unlimited $700/mo billed annually. **Unverified against the vendor.** — [Spendbase](https://test.spendbase.co/de/?p=32865)

**DroneLogbook**
- A listing says it imports logs from many systems, including "Ardupilot (Mission Planner)". It covers compliance reports, maintenance tracking and battery cycles. — [ForConstructionPros listing](https://www.forconstructionpros.com/equipment/equipment-technology/drones-and-unmanned-aerial-vehicles/product/22899931/drone-logbook-drone-logbook)
- Price "from $6.95/user/month". An Agriculture Edition Gold plan is $79.95/month/user. Private label is a custom quote. **Aggregator, unverified.** — [Fitgap](https://us.fitgap.com/products/034561/dronelogbook)
- It is a Parrot enterprise fleet-management partner. — [Parrot newsroom](https://www.parrot.com/en/newsroom/parrot-dronelogbook)

**Skyward (Verizon)**
- **Discontinued.** Verizon announced the closure in May 2022 and support ended 30 June 2022. — [DroneLife](https://dronelife.com/2022/05/05/verizon-skyward-closed-drone-software-business-yesterday/); [DroneDJ](https://dronedj.com/2022/05/06/verizon-is-closing-its-skyward-drone-management-company/)
- Some 2025 vendor-blog roundups still list Skyward as an option, so those roundups are stale. — [Dronedesk blog](https://blog.dronedesk.io/drone-fleet-management-software/)

**Aloft (formerly Kittyhawk), Air Control**
- It is free for individual operators for basic tasks (LAANC, mission planning). Enterprise is a tiered subscription with no published price. — [Gartner listing](https://www.gartner.com/reviews/product/aloft-air-control)
- It claims to be "drone agnostic" with logs from "dozens of manufacturers". The June 2024 blog names no ArduPilot or PX4 formats. Its log features are playback and record-keeping, not analysis. — [Aloft blog, 10 Jun 2024](https://www.aloft.ai/blog/flight-logging-import-with-aloft-whats-next-after-dji-sync/)
- Context: DJI ended flight sync for U.S. users on 12 June 2024. That is a DJI-dependency risk for logbook tools that relied on it. — same source
- An aggregator lists "Maintenance Scheduling" as a feature, but no vendor documentation confirms it. — [SoftwareSuggest](https://www.softwaresuggest.com/aloft)

**FlytBase (dock and BVLOS autonomy, DJI Dock-centric)**
- Tiers are Zero ($0/dock), Pro (about $999/yr per reseller and aggregator listings) and Enterprise. Resellers list Enterprise at $4,499/yr for one DJI Dock 3 and $3,999/yr for Dock 2. Official Enterprise pricing is contact-sales. — [FlytBase pricing](https://flytbase.com/pricing); [Dronefly reseller](https://www.dronefly.com/products/flytbase-enterprise-base-package-for-dji-dock-3-m4d-m4td-1-year); [Fitgap](https://us.fitgap.com/products/flytbase)

**AirHub (Netherlands, Drone Operations Center)**
- Its features are flight planning, multi-aircraft live streaming, airspace compliance, maintenance scheduling, fleet tracking, incident reporting, checklists and on-premise deployment. It has apps for iOS, Android and the DJI Smart Controller. Customers include Dubai Police and the Belgian Federal Police. — [TNW, 8 Apr 2026](https://thenextweb.com/news/airhub-4-4m-drone-operations)

**India**
- **PDRL AeroGCS** comes in GREEN (agri spraying), ORANGE (survey), ENTERPRISE (project management/analytics) and CONFIG (tuning) editions. — [Brandfetch](https://brandfetch.com/aerogcs.com.md)
- A 2021 report says AeroGCS talks to DGCA Digital Sky for NPNT permission artefacts and enforces geofence, altitude and time. — [sUAS News](https://www.suasnews.com/2021/09/pdrls-aerogcs-to-prevent-misuse-of-indian-drones-through-npnt-solution/)
- **Company claim:** about 50% of Indian manufacturers type-certified with AeroGCS, and 75% of Indian agri drones type-certified with AeroGCS Green. A different source puts agri share at 60%, so the figures conflict and are unverified. — [The Week, Mar 2024](https://www.theweek.in/wire-updates/business/2024/03/12/dcm8-pdrl.html); [Brandfetch](https://brandfetch.com/aerogcs.com.md)
- AeroGCS GREEN was certified to DO-278A AL5 (Nov 2023), and PDRL has an order for 500 licences from AVPL International. — [The Week, Nov 2023](https://www.theweek.in/wire-updates/business/2023/11/21/dcm21-pdrl.html); [The Machine Maker](https://themachinemaker.com/news/pdrl-lands-major-order-for-500-aerogcs-software-licenses-from-avpl-international/)
- **Skylark Drones DMO-AG** launched 19 Feb 2025. It offers fleet management, crop recommendations, "automated health monitoring" and local-language UI. It claims to be "DGCA-compliant" and "compatible with all major autopilot-enabled controllers", without naming ArduPilot or PX4. It does not mention maintenance, logs or pricing. — [BioVoice News](https://biovoicenews.com/skylark-drones-launches-indias-first-software-for-spray-management/)
- **BhuMeet** is an agri-drone ops SaaS listed on Product Hunt in Nov 2025. Its modules are orders, fleet and pilot tracking, spray analytics and invoicing. Vendor description only. — [Product Hunt](https://www.producthunt.com/p/bhumeet)

**Other log viewers**
- MD-DRONE is a forensic log tool for DJI, Parrot and Pixhawk logs, aimed at investigators. Vendor-blog roundup only. — [Dronedesk blog](https://blog.dronedesk.io/uav-log-viewer/)

### Inferences
- **Covered by many tools:** pilot and aircraft logbooks, checklists, risk assessments, airspace authorisation (US/EU), scheduled maintenance by hours or cycles, and job management.
- **Covered weakly or not at all (from public pages):**
  - fleet-wide parameter and firmware drift for ArduPilot/PX4
  - checking a flight against its plan (beyond FlyFreely's basic limits)
  - automated root-cause diagnosis of ArduPilot/PX4 logs
  - DGCA-specific post-flight records that tie together Digital Sky permission artefacts, logs and maintenance
- DJI-first log sync is a structural weakness. DJI cutting U.S. sync in 2024 shows that logbook vendors depend on one OEM's API.
- Indian agri software competes on bookings, invoicing, spray analytics and type certification, not on engineering assurance. AeroGCS is the incumbent at the GCS and type-certification layer, so any Indian tool would likely need to coexist with it.

### Gaps
- The open ArduPilot/PX4 tools (UAV Log Viewer, PX4 Flight Review, plot.ardupilot.org, Mission Planner auto analysis, LogAnalyzer, MAVExplorer) were **not verified this session**. From prior knowledge only (unverified): they are single-log viewers or plotters, mostly free and open-source. The old LogAnalyzer / MP "auto analysis" ran simple rule checks. None manages a fleet, and none tracks parameter changes across aircraft or flights.
- Not researched for lack of budget: DroneDeploy fleet features, DroneSense, Measure (largely acquired/pivoted, unverified), Hammer Missions, UgCS, Skye Air UTM, Garuda Aerospace software, Digital Sky partner apps.
- Official prices for Dronedesk, DroneLogbook and Aloft enterprise could not be confirmed. The Dronedesk page did not render its numbers.

## What do users complain about?

### Takeaway
I found little direct review evidence. The clearest documented pain points are dependence on DJI log sync, and for ArduPilot users the need for expert humans to read logs. G2, Capterra and Reddit complaint threads were not retrieved.

### Cited Findings
- DJI ended flight-log sync for U.S. users on 12 June 2024, which forced logbook vendors such as Aloft to build workarounds. — [Aloft blog](https://www.aloft.ai/blog/flight-logging-import-with-aloft-whats-next-after-dji-sync/)
- Skyward's 2022 shutdown was described as a surprise to customers and partners, which is a vendor-continuity risk. — [DroneLife](https://dronelife.com/2022/05/05/verizon-skyward-closed-drone-software-business-yesterday/); [Inside Towers](https://insidetowers.com/?p=49990)
- An ArduPilot forum discussion says that fully understanding logs requires familiarity with ArduPilot's internal code. — [ArduPilot Discourse, seminar request](https://discuss.ardupilot.org/t/request-for-seminar-on-analysis-of-flight-logs)
- In help threads, users often post the Mission Planner summary instead of the raw .bin, and helpers have to ask for the real file. — [ArduPilot Discourse example](https://discuss.ardupilot.org/t/crash-log-analysis-help/4643)
- Search did not find any Reddit thread recommending non-DJI or ArduPilot fleet software. Vendor roundups are DJI-weighted. — search result summary; sources: [Dronedesk blog](https://blog.dronedesk.io/alternative-to-drone-logbook/)

### Inferences
- The lack of ArduPilot/PX4 mentions on commercial pricing pages, apart from DroneLogbook's import list, suggests open-autopilot fleets are a secondary market for these vendors.

### Gaps
- No G2 or Capterra review text was retrieved, and no Reddit (r/drones, r/UAVmapping) complaint threads were found. **Treat "users complain about X" claims as unsupported** until those are pulled.

## Is there demand for automated crash diagnosis from ArduPilot/PX4 logs?

### Takeaway
"Please analyse my crash log" threads are a long-running, recurring genre on ArduPilot Discourse, but I could not get a count. The one 2026 attempt at an automated (ML) diagnoser was publicly criticised by experienced log readers for wrong diagnoses. That shows both the demand and how high the accuracy bar is. Academic work on PX4/ArduPilot log anomaly detection is active, and a real-log PX4 dataset exists.

### Cited Findings
- Crash and log-help threads go back years, for example "Crash log analysis help", "Crash in loiter, need help with analysing the log file" and "Drone crashed, trying to figure out why". — [thread 4643](https://discuss.ardupilot.org/t/crash-log-analysis-help/4643); [thread 733](https://discuss.ardupilot.org/t/crash-in-loiter-need-help-with-analysing-the-log-file/733); [thread 92345](https://discuss.ardupilot.org/t/drone-crashed-trying-to-figure-out-why/92345)
- **AI-assisted log diagnosis engine** (ArduPilot Discourse, posted 1 Mar 2026):
  - It is a rule engine plus XGBoost over more than 150 features and 9 failure classes. It was run blind on 34 crash logs taken from forum threads.
  - The output was skewed toward compass interference (16 of 34) and motor imbalance (12 of 34).
  - Experienced members (dkemxr, Yuri_Rage, Allister, Juergen-Fahlbusch) said several diagnoses were wrong. For example, log 1 was thrust loss from an underpowered craft, not compass. They also pointed out that several of the logs were tuning requests, not crashes.
  - The code is not public.
  - The author noted that the symptom in a thread title is rarely the physical root cause.
  — [ArduPilot Discourse thread 142646](https://discuss.ardupilot.org/t/introducing-an-ai-assisted-log-diagnosis-engine-tracing-root-causes-in-bin-files/142646)
- **UAV-SEAD (arXiv 2602.13900, Feb 2026):** 1,396 real PX4 flight logs (over 52 h) with 4 classes of state-estimation anomaly. — [papers.cool summary](https://papers.cool/arxiv/2602.13900)
- **AeroTSBoost (arXiv 2605.25639):** a LightGBM detector over statistical window features, reported as best AUPRC on UAV-SEAD. — [arXiv](https://arxiv.org/pdf/2605.25639)
- **ICSE 2024:** an empirical study of 178 real abnormal PX4 and ArduPilot logs caused by software bugs. — [ICSE 2024](https://conf.researchr.org/details/icse-2024/icse-2024-research-track/186/An-Exploratory-Investigation-of-Log-Anomalies-in-Unmanned-Aerial-Vehicles)
- **DronLomaly (APSEC 2022):** an LSTM over DJI, ArduPilot and PX4 logs, reporting 0.968 recall and 0.963 precision (abstract figures, not independently checked). — [SMU repository](https://ink.library.smu.edu.sg/sis_research/7519)
- A University of Bologna thesis describes a hybrid PX4 log analyser (rule-based plus unsupervised). — [AMS Laurea](https://amslaurea.unibo.it/id/eprint/36251/)

### Inferences
- There is demand for log diagnosis, but expert forum helpers are the de facto competition and the quality bar. A tool that gives confident wrong root causes gets rejected publicly. That fits a design built on deterministic, evidence-backed checks (thrust margin, vibration, EKF, power, configuration) rather than ML classification.
- The 34-log exercise also shows forum "crash" threads are noisy labels: many are tuning or setup questions, not crashes.

### Gaps
- **No count** of log-help threads was obtained. The Discourse category URL I tried returned 404. A count could be made with the Discourse search API (e.g. `discuss.ardupilot.org/search.json?q=crash log`) or category topic counts.
- PX4 Discourse volume was not checked.

## Startups funded in this space, 2022–2026

### Takeaway
Funding in pure fleet-ops / compliance software is small and sparse. The one clear recent round I found is AirHub's €4.4M Series A (Apr 2026), aimed at police and DFR use rather than open-autopilot engineering assurance. Skyward's closure in 2022 is a counter-signal.

### Cited Findings
- **AirHub:**
  - €4.4M Series A, April 2026, led by Keen Venture Partners and Runway FBU, with LUMO Labs and Lumaux participating.
  - It followed a €1M seed in April 2024.
  - The money goes to DFR and police expansion, plus defence (MilHub) and security (SecHub) products.
  — [TNW](https://thenextweb.com/news/airhub-4-4m-drone-operations); [DroneLife](https://dronelife.com/2026/04/08/drone-operations-software-company-airhub-closes-e4-4m-series-a/)
- **vHive:** an earlier $5.5M round (2019) and a reported $25M Series B led by PSG. The Series B date was not confirmed in the results. — [Calcalist](https://www.calcalistech.com/ctech/articles/0,7340,L-3770147,00.html)
- **Skyward:** closed by Verizon in 2022. — [DroneDJ](https://dronedj.com/2022/05/06/verizon-is-closing-its-skyward-drone-management-company/)
- **Skylark Drones** (India) cites more than 10M autonomous flights and 120+ enterprise customers. No funding figure was in the source. — [BioVoice News](https://biovoicenews.com/skylark-drones-launches-indias-first-software-for-spray-management/)

### Inferences
- Investors are funding ops platforms for public safety and DFR, and dock autonomy (FlytBase). I found no funded startup whose main product is ArduPilot/PX4 configuration and log assurance, which suggests this is either an open niche or one too small to fund.

### Gaps
- Funding for Aloft, Airdata, FlyFreely, DroneLogbook, FlytBase, PDRL and Indian agri-SaaS in 2022–2026 was not researched. Crunchbase was not accessed.
- vHive's Series B date is unverified.
