# What accident and incident data says causes civil drone (UAS) incidents

Scope note: this was about 20 tool calls of research, so coverage is uneven. Several sources (MDPI full texts, ATSB report PDF, Coverdrone blog) were blocked or timed out. Anything not opened directly is marked **[snippet only]** or **[unverified]**. No figure here is invented. Where no number exists, I say so.

## 1. What official investigators (AAIB, NTSB, ATSB, BEA, EASA, ASRS) show about cause categories

### Takeaway
Official bodies classify drone events by **what happened** (loss of control in flight, system/component failure, loss of data link, collision). They do not classify by **why** at the level of "wrong parameter" or "bad config change". The UK AAIB says loss of control in flight (LOC-I) is the main UAS accident category, usually because the drone stopped responding or behaved erratically. None of the official sources I found publishes a share for configuration, parameter or firmware causes.

### Cited Findings
- **UK AAIB, Annual Safety Review 2023 (published 2024):**
  - The text says: "The predominant cause of UAS accidents, was LOC-I usually resulting from the UAS becoming unresponsive to control inputs or displaying erratic or uncommanded responses."
  - The occurrence categories charted for UAS are LOC-I, SCF-NP (system/component failure, non-powerplant), SCF-PP (powerplant failure), CTOL (collision with obstacle during take-off/landing) and U-LINK (UAS loss of data link).
  - Counts are only in the charts and could not be extracted as text.
  - A small number of UAS cases were left out of the dataset.
  - [AAIB ASR 2023 PDF (mirror)](https://www.suasnews.com/wp-content/uploads/2024/03/AAIB-Annual-Safety-Review-2023.pdf)
- **AAIB ASR 2023, drone case summaries.** These are the safety actions of the year:
  - **Tekever AR5:** a fault in the Satcom antenna caused a loss of the C2 link. As a fix, the operator will make future variants enable Satcom backup automatically when fewer than 2 C2 links are available. This is a design/configuration fix.
  - **Tekever AR3:** a low-pressure fuel pump failed and tripped a fuse that also fed the high-pressure pump. This is a design issue.
  - **Evolve Dynamics Sky Mantis:** a 20 m fall caused by thermal damage to the battery and drone connectors. Damage was also found on the batteries used in the 3 previous flights. The fix was a pre-flight connector check, so this is a maintenance/inspection issue.
  - **DJI Mavic 2 Enterprise (police):** the battery probably disconnected in flight, either because it was not fully latched or because the latch was worn. The fix was pre-flight check discipline.
  - **DJI Inspire 2 film shoot:** a person deviated from the briefed path and ran into a propeller.
  - [same source](https://www.suasnews.com/wp-content/uploads/2024/03/AAIB-Annual-Safety-Review-2023.pdf)
- **AAIB ASR 2025:**
  - In 2025 there were 783 occurrence notifications, 131 record-only investigations opened and 198 final reports.
  - The landing page has no UAS-specific breakdown. The full PDF was not reviewed.
  - [GOV.UK AAIB ASR 2025](https://www.gov.uk/aaib-reports/aaib-annual-safety-review-2025); PDF: https://assets.publishing.service.gov.uk/media/6a21991a8e85b4e5346abf75/AAIB_Annual_Safety_Review_2025.pdf
- **AAIB record-only UAS bulletins (Dec 2025 to Jan 2026):**
  - The bulletin has only 2 occurrences.
  - **DJI M30T:** low battery triggered return-to-home (RTH). The pilot cancelled it, flew manually and hit a power line.
  - **DJI M30:** flew unintentionally into a tree.
  - Neither mentions settings, firmware or calibration. The reports rely on what the pilot told the AAIB.
  - [GOV.UK](https://www.gov.uk/government/publications/aaib-record-only-uas-investigations-reviewed-december-2025-january-2026/aaib-record-only-uas-investigations-reviewed-december-2025-january-2026)
- **Third-party tally of AAIB record-only UAS cases (Dronedesk):**
  - Covers 415 incidents in 39 bulletins, Jul-2019 to Oct-2026.
  - Root cause is coded by Dronedesk "based on the textual content of the report" and is called a "work in progress".
  - The cause breakdown table did not render, so no shares are available.
  - [aaib.dronedesk.io](https://aaib.dronedesk.io/)
- **ATSB (Australia), *A safety analysis of RPAS 2012–2017* (AR-2017-016a):**
  - About half of the 180 occurrences in 2012–2016 were proximity encounters with manned aircraft.
  - This came from the [BeefCentral summary](https://www.beefcentral.com/?p=129296) **[snippet only]**. The ATSB page timed out. [ATSB](https://www.atsb.gov.au/node/2308)
  - I found no ATSB publication called "A safer path".
- **ATSB aviation statistics:** RPAs had become the second most common aircraft type in reported accidents, with no collisions, fatalities or serious injuries involving RPAs. [ATSB AR-2018-030](https://www.atsb.gov.au/sites/default/files/media/5776642/ar-2018-030_final.pdf) **[snippet only]**
- **CASA RPAS sector safety profile (ATSB data 2015–2024):**
  - 939 "Encounter with RPA" occurrences since 2015.
  - RPAS make up about 1% of all reported occurrences.
  - New RPA reporting requirements started on 30 Sep 2021.
  - [CASA](https://www.casa.gov.au/operations-safety-and-travel/safety-management-systems/sector-safety-risk-profiles/remotely-piloted-aircraft-systems-sector-safety-risk-profile/sector-safety-performance-remotely-piloted-aircraft-systems) **[snippet only]**
- **EASA ASR 2025 (2024 data):**
  - No fatal accidents or serious injuries involving UAS.
  - 7 occurrences involved manned aircraft: 1 accident and 6 serious incidents. The 6 serious incidents were 5 airprox and 1 LOC-I.
  - The size and origin of the UAS were mostly not coded.
  - [Unmanned Airspace summary of EASA ASR](https://www.unmannedairspace.info/uncategorized/easa-no-fatal-accidents-involving-drones-in-2024/); [EASA](https://www.easa.europa.eu/en/newsroom-and-events/news/easa-publishes-annual-safety-review-2025) **[snippet only]**
- **EASA drone risk portfolio (older data, 2010 to May 2016):** most of the 42 accidents were drone crashes "for either technical reasons or due to loss of control". [Aerossurance](https://aerossurance.com/safety-management/easa-drone-risk-portfolio/) **[snippet only; pre-2018]**
- **NASA ASRS / FAA, Cardosi & Lennertz 2017:**
  - 220 relevant UAS events.
  - Reporters were manned-aircraft pilots (68%), controllers (17%) and UAS pilots (15%).
  - The data is mostly about airspace encounters, not technical cause.
  - [ROSAP dot/12500](https://rosap.ntl.bts.gov/view/dot/12500) **[snippet only]**

### Inferences
- The official frameworks (ICAO ADREP-style categories) cannot show "misconfigured parameter" as a cause. That cause would be hidden inside LOC-I, SCF-NP or "unresponsive/erratic". So the absence of a number is not evidence that the cause is absent.
- Manned-aviation agencies (EASA, ATSB, CASA, ASRS) see drones mainly as an **airspace-encounter** hazard to manned aircraft. Investigations of the drone itself are concentrated in the UK AAIB record-only bulletins.
- The AAIB drone cases with real lessons often involve **pre-flight check/maintenance** issues (battery latching, connector damage) and **RTH/automation behaviour**. A pre-flight assurance tool would touch these.

### Gaps
- No NTSB CAROL UAS breakdown was retrieved. NTSB investigates few small-UAS events.
- No BEA drone statistics were found.
- The breakdown in the EASA ASR drone chapter was not obtained.
- The AAIB UAS cause chart counts are only in images.

## 2. What academic analyses find on technical vs human vs organisational shares

### Takeaway
The split depends heavily on the dataset and coding method:
- Studies of Australian/international occurrence data find **equipment/technical problems are the largest category (about 64%)**.
- An HFACS coding of NASA ASRS reports finds **human factors about 78% and hardware/software about 20%**.
- Broken C2 (command-and-control) links are the most-cited technical failure mode.

I found no academic study that gives a share for operator configuration or parameter errors.

### Cited Findings
- **Wild, Murray, Baxter et al. (Aerospace 2016; JATM 2017):**
  - 152 civil RPAS accidents/incidents from 2006–2015.
  - The majority involved system/component failures from equipment problems.
  - Human factors was the second most common contributing factor. LOC-I was the second most common occurrence category.
  - [ECU](https://ro.ecu.edu.au/ecuworkspost2013/2410); [JATM/DOAJ](https://doaj.org/article/68abe85554984c5e9c99ef0b66929f6c)
  - The **64% technical** figure and "broken communications links in most cases" come from press coverage ([Asian Scientist 2016](https://www.asianscientist.com/2016/08/tech/tech-issues-drone-accidents/)). These are **not verified in the paper text**. The data is pre-2018.
- **Murray, Richardson, Molloy, Wild (AIAA Aviation 2022):**
  - 429 ATSB RPAS occurrences from May 2008 to Jul 2021.
  - Accidents are more than 75% of occurrences, which suggests incidents are under-reported.
  - Collisions with terrain are about 90% of occurrences.
  - About 90% happened during maneuvering.
  - The abstract has no human/technical split.
  - [ECU](https://ro.ecu.edu.au/ecuworks2022-2026/1108)
- **Davis & Majumdar (Univ. of Arkansas, 2025 student poster):**
  - HFACS coding of NASA ASRS UAS reports.
  - Human factors (decision errors, violations) were 78%. Hardware/software malfunctions were 20%. Environmental factors were rare.
  - Sample size is not stated, and the shares add up to 98%. This is low-weight evidence.
  - [ScholarWorks](https://scholarworks.uark.edu/hnrcsturpc25/29)
- **Aerospace 2025 paper (MDPI 12(3):206):** says technical failures have been the largest cause of RPAS accident occurrences (2008–2019 database). [MDPI](https://www.mdpi.com/2226-4310/12/3/206) **[snippet only; full text 403]**
- **Ghasri & Maghrebi (ATRF 2019):**
  - Exploratory factor analysis of Australian drone occurrences.
  - "Equipment issues" and "lack of coordination between aerial activities" emerge as main categories.
  - The authors recommend regular safety inspections and integrated monitoring.
  - [ATRF](https://australasiantransportresearchforum.org.au/factors-affecting-unmanned-aerial-vehicles-safety-a-post-occurrence-exploratory-data-analysis-of-drones-accidents-and-incidents-in-australia/) **[snippet only]**
- **UAV loss-of-control framework (Aeronautical Journal):** design and manufacturing errors were the dominant causal factor (22 events, 34%). [Cambridge](https://resolve.cambridge.org/core/journals/aeronautical-journal/article/human-factors-accident-analysis-framework-for-uav-loss-of-control-in-flight/7B119869818CB1A5C07EF0ABA8A89417) **[snippet only; year and sample (military vs civil) not confirmed]**
- **Drones 2025, "UAV Accident Forensics via HFACS-LLM Reasoning":** 847 small-UAS reports from ASRS and NTSB, 2010 to May 2025. The breakdown could not be retrieved (403). [doi:10.3390/drones9100704](https://doi.org/10.3390/drones9100704)

### Inferences
- Occurrence databases (ATSB, AAIB) lean **technical**. Voluntary self-reports (ASRS) lean **human**. The reason is who reports and how coding works, not necessarily the true causes.
- Within technical causes, the sources consistently mention **C2 link loss**, **power/battery** (latching, connectors, low battery) and **GNSS/compass** errors.
- "Software/configuration" does not appear as its own coded category in any dataset I found.

### Gaps
- I could not find or verify Johnson's or Grindley's quantified UAS studies.
- Full-text sub-category shares within technical causes (battery vs GNSS vs propulsion vs software) were not obtained from any 2018+ study.

## 3. Documented cases and counts of wrong parameters, failsafes, geofences, firmware, calibration or configuration changes

### Takeaway
There are **individual cases** where RTH, home point, failsafe or automation set-up mattered. There are also **software-engineering studies** showing that parameter handling is a known bug class in PX4 and ArduPilot. I found **no count or share** of real incidents caused by operator misconfiguration in any official or academic dataset.

### Cited Findings
- **AAIB field investigation, DJI M600 Pro, Wallsend, 13 Dec 2019 (Bulletin 7/2020):**
  - The drone was doing an automated survey. A GPS-compass error made it revert to a manual mode.
  - It did not respond to RTH, drifted beyond line of sight and hit a house roof.
  - Both pilots "had relied predominantly on the automated flight capability" and had not practised emergencies since 2018.
  - 1 safety recommendation was made to the CAA.
  - The cause was sensor error plus automation dependence and lack of training, **not a wrong setting**.
  - [AAIB PDF](https://assets.publishing.service.gov.uk/media/5f1ae9f8d3bf7f596648297e/DJI_M600_Pro_UAS_reg_na_07-20.pdf)
- **AAIB, DJI Inspire 2, London, Feb 2020:** the drone did not correctly set its home point, although it looked correct on the pilot's screen. Poor GPS and compass readings at take-off then led to erratic manoeuvring. [AAIB](https://www.gov.uk/aaib-reports/aaib-investigation-to-dji-inspire-2-uas-registration-n-a-080220)
- **AAIB record-only, DJI Mavic 2 Enterprise, Dudley, Mar 2021:** automatic RTH started but the drone did not climb to its pre-programmed 80 m height and hit a tree. [AAIB RO bulletin Jun–Jul 2021](https://www.gov.uk/government/publications/aaib-record-only-uas-investigations-reviewed-june-july-2021/aaib-record-only-uas-investigations-reviewed-june-july-2021.) **[snippet only]**
- **AAIB record-only, DJI Mavic 3 Enterprise, Elmbridge, Nov 2024:** the drone did not respond to the RTH command. Logs suggest it hit something while climbing to its RTH altitude, possibly a powerline. **[snippet only; this is an RTH altitude vs obstacle issue]**
- **AAIB record-only battery-latching cases (2020):**
  - **Yuneec H520:** the battery moved in its holder.
  - **Aeryon SkyRanger:** the battery was not correctly latched before flight.
  - [suasnews AAIB RO summaries](https://www.suasnews.com/2025/01/aaib-record-only-uas-investigations-reviewed-october-november-2024/) **[snippet only]**
- **AAIB ASR 2023, Tekever AR5:** the fix for the C2 loss was a **configuration/design change**: automatic Satcom backup when fewer than 2 C2 links are available. [AAIB ASR 2023](https://www.suasnews.com/wp-content/uploads/2024/03/AAIB-Annual-Safety-Review-2023.pdf)
- **Wang et al., FSE 2021 (PX4 and ArduPilot bug study):**
  - 569 bugs studied, of which 168 were UAV-specific.
  - These were classified into 8 root causes: limit, math, inconsistency, priority, **parameter**, hardware support, correction, initialization.
  - "Parameter" covers parameter missing and parameter misuse. One example is a PX4 landing parameter misuse.
  - "Limit" bugs come from improper parameter limits. PX4 has 1,306 limits and more than 1,000 parameters.
  - The per-category counts are in Fig. 2 and were not extracted.
  - These are **developer code bugs, not operator misconfiguration**.
  - [FSE'21 PDF](https://yuleisui.github.io/publications/fse21.pdf)
- **Kim et al., USENIX Security 2020 (MayDay):** describes drone crashes whose root cause was the ArduPilot control program failing to validate an operator-set control gain. These are research reproductions, not field incident statistics. [USENIX](https://www.usenix.org/system/files/sec20-kim.pdf)
- **"Control Parameters Considered Harmful" (arXiv 2112.03511):** finds range-specification bugs in drone configuration modules, where parameter values allowed by the software still lead to crashes. [arXiv](https://arxiv.org/pdf/2112.03511)
- **Iowa State, "Self-Adaptive Mechanisms for Misconfigurations in sUAS":** traces intermittent take-off failures on a real sUAS to a flight-controller parameter error. No frequency is given. [PDF](https://faculty.sites.iastate.edu/mcohen/files/inline-files/cicada-seams.pdf) **[snippet only]**
- **RisConFix (arXiv 2512.07122, 2025):** LLM-based repair of "risk-prone drone configurations". It shows research interest, not incident frequency. [arXiv](https://www.arxiv.org/pdf/2512.07122)
- **ArduPilot documentation:**
  - Setting FS_EKF_THRESH=0 disables the EKF failsafe.
  - Raising it lets a flyaway from a bad compass or GPS glitch go further before the drone lands.
  - This is a concrete example of a setting that a pre-flight checker could flag.
  - [ArduPilot docs](https://ardupilot.org/copter/docs/common-ekf-inav-failsafe.html)
- **ArduPilot forum, Copter 4.6:** a crash where the radio failsafe did not engage. This is user-reported and not investigated. [Discourse](https://discuss.ardupilot.org/t/arducopter-radio-failsafe-not-engaging-resulting-in-a-crash/137519)

### Inferences
- Misconfiguration is a **plausible and documented mechanism**, especially in the open-source PX4/ArduPilot world with 1,000+ parameters. But **no investigation dataset quantifies how often it causes real incidents**.
- In the public UK record, the drone fleet is mostly DJI. DJI exposes few parameters, so "wrong parameter" cases are rare there. The relevant DJI analogues are RTH altitude, home point and low-battery RTH behaviour.
- The causes that investigators repeatedly cite and that are adjacent to what a ground tool could check are:
  - pre-flight condition: battery latching, connector damage, battery health
  - RTH/failsafe set-up and behaviour
  - GNSS/compass health at take-off
- A tool pitched as a "parameter checker" is weakly supported by incident data. A tool covering **pre-flight readiness (battery, sensor health, RTH and failsafe set-up)** is better supported.
- For **plan conformance / flight-path deviation**, I found no incident data counting deviation from the approved flight path as a cause. The only "deviated from the briefed path" case was a *person* on a film set.

### Gaps
- I found no count of firmware-update-induced incidents in any official dataset.
- I found no geofence-setting incident cases.
- I found no AAIB or NTSB report attributing an accident to a wrong ArduPilot or PX4 parameter. A targeted search of AAIB bulletins for "ArduPilot", "Pixhawk" and "parameter" is recommended.

## 4. Drone insurer claims data and India DGCA data

### Takeaway
The only quantified insurer data found is Coverdrone (UK), where pilot error is the top cause of claims. Flyaway, loss of data link, mechanical failure and loss of power rank lower. I found no public DGCA drone incident statistics.

### Cited Findings
- **Coverdrone 2021 claims:**
  - Pilot error was **33% of claims** in 2021, down from **49% in 2020**. Coverdrone credits the A2 CofC training and regulation.
  - The 2021 top 10 in order: pilot error, accidental damage, loss of data link, flyaway, accidental loss, mechanical failure, bird strike, loss of power, weather, theft from a vehicle.
  - Flyaway rose from 6th (2020) to 4th (2021).
  - 98.2% of claims were settled.
  - Sources: [DroneXL](https://dronexl.co/2022/02/02/drone-pilot-error-insurance-claim/); [DroneDJ](https://dronedj.com/2022/02/04/coverdrone-drone-insurance-claims/); [ARPAS-UK](https://arpas.uk/?p=2692). These are secondary summaries; the original Coverdrone post returned 404.
  - The data covers a single insurer's book, with no percentages beyond pilot error.
- **Flock, SkyWatch, Global Aerospace:** no quantified claims-cause data found.
- **India DGCA:**
  - No drone accident or incident counts were found.
  - Drone Rules 2021 require reporting a drone accident to DGCA via Digital Sky within 48 hours. [Mondaq](https://mondaq.com/india/aviation/1162664/safety-investigations-of-accidents-incidents-involving-drones-addressing-the-gaps-in-drone-rules-in-india)
  - The Aircraft (Investigation of Accidents and Incidents) Rules 2025 cover UAS, with 24-hour reporting. [Lawrbit](https://www.lawrbit.com/?p=9707) **[snippet only]**
  - The draft Civil Drone (Promotion and Regulation) Bill 2025 is noted in a Jan 2026 law-firm roundup. [AMS Shardul](https://www.amsshardul.com/wp-content/uploads/2026/01/Update-Annual-India-Aviation-Roundup-2025.pdf) **[snippet only]**

### Inferences
- Insurer data puts **operator error** on top. "Loss of data link" and "flyaway" (often the end result of compass, GPS or config problems) are mid-ranked. A settings/readiness tool targets a slice of these, not the top category.
- India has a reporting duty but no public dataset. A pitch to Indian operators cannot rely on local incident statistics.

### Gaps
- Coverdrone 2022–2025 data was not found.
- No other insurer has published shares.
- No DGCA/Digital Sky occurrence counts are public as far as I found. Parliamentary questions (Lok/Rajya Sabha) are the likely route.
