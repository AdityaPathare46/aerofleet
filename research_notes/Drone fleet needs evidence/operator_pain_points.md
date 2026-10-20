# Operational pain points of commercial drone fleet operators (India first, global second)

Research date: 20 Oct 2026. About 20 search/fetch calls. "Verified" means I read the page itself. "Snippet" means the claim came only from a search-result summary and the page itself was not read.

## 1. Indian market size and fleet structure

### Takeaway
India has roughly 29.5k registered drones (official figure, Jan 2025), rising to about 38.5k–39k by mid-2026 (press figure), and about 44k remote pilot certificates. Agriculture dominates the type certificates. The government-funded fleets are much smaller than their headline targets: about 1,094 Drone Didi drones and about 544 subsidised Kisan drones, against a 15,000 target. I found no public evidence of which autopilot stack (ArduPilot, PX4 or proprietary) the major Indian operators use.

### Cited Findings
- Official count, Rajya Sabha answer of 10 Feb 2025: as of 29 Jan 2025, 29,501 UINs had been issued on Digital Sky, and DGCA-authorised RPTOs had issued 22,466 Remote Pilot Certificates. [RS PQ 10-02-2025](https://rsdebate.nic.in/bitstream/123456789/758334/1/PQ_267_10022025_U646_p134_p136.pdf). (Snippet, but the figures match ETV Bharat.) DGCA had issued 96 type certificates, 65 of them for agricultural UAS. [ETV Bharat, Feb 2025](https://www.etvbharat.com/en/!bharat/india-has-over-29500-registered-drones-dgca-enn25021704844)
- Earlier baseline, July 2024 Rajya Sabha reply reported by PTI: about 16,000 RPCs and 116 DGCA-approved RPTOs. [Deccan Herald](https://www.deccanherald.com/amp/story/india%2Fcentre-says-16000-remote-pilot-certificates-issued-for-operating-drones-3116118) (snippet)
- Mid-2026: "over 39,000 drones registered" and "more than 44,000 pilot certificates". This comes from an Indian Express p.7 item of 15 Jun 2026, as summarised by SuperKalam. It is not a primary government source. [SuperKalam](https://superkalam.com/current-affairs/15-06-2026/drone-ecosystem-39000-drones-registered-and-44-000-pilot-certificates-issued-pg7-28efe8f5-fca1-4c5b-a184-4730d0242f2e)
- Khaleej Times and Policybazaar give "over 38,500 registered drones, nearly 40,000 DGCA-certified remote pilots and 244 approved training organisations", dated Feb 2026. [Khaleej Times](https://www.khaleejtimes.com/world/asia/how-nearly-40000-strong-drone-network-reaches-indias-congested-cities-villages); [Policybazaar](https://www.policybazaar.com/corporate-insurance/articles/how-to-become-a-drone-pilot-in-india/). Other 2026 guides say "over 40" RPTOs, which conflicts badly. **The RPTO count is unverified (somewhere between 116 and 244).**
- Namo Drone Didi: the target is 15,000 drones and the outlay is ₹1,261 crore (2023-24 to 2025-26). Lead Fertilizer Companies distributed 1,094 drones to SHG drone didis in 2023-24, of which about 500 came under the scheme itself. Karnataka (145), UP (128) and AP (108) received the most. [PIB doc Feb 2026](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/feb/doc2026217793801.pdf); [Medianama Dec 2024](https://www.medianama.com/2024/12/223-centre-deploys-500-drones-namo-drone-didi-scheme-reports-zero-expenditure/) (snippets; the sources word the 500-of-1,094 split differently). Medianama reported "zero expenditure" under the scheme as of Dec 2024.
- Madhya Pradesh: 1,066 drones allocated, 89 distributed. [Ground Report, 30 May 2026](https://www.groundreport.in/states-madhya-pradesh/namo-drone-didi-struggling-with-battery-and-servicing-issues-ground-report/) (verified)
- Kisan drones under SMAM, from a parliamentary reply of Mar/Apr 2025: 544 drones supplied to farmers on subsidy, 1,595 Kisan Drone Custom Hiring Centres, and ₹141.39 crore released up to 31 Mar 2025. [RS PQ 04-04-2025](https://rsdebate.nic.in/bitstream/123456789/756793/1/PQ_267_04042025_U3841_p61_p65.pdf) (snippet)
- Operators:
  - Garuda Aerospace claims its agri fleet logged 1 million flight hours in a year. [The Machine Maker](https://themachinemaker.com/news/garuda-aerospace-achieves-1-million-flight-hours-with-agri-drones/) (company claim)
  - Marut Drones claims a fleet of over 750 drones plus trained pilots. [Dealroom](https://app.dealroom.co/companies/marut_drones) (company claim)
  - Skye Air claims more than 20 lakh (2 million) deliveries in 2025, operating in Gurugram. [Flapone](https://www.flapone.com/news/skye-air-crosses-20-lakh-drone-deliveries-in-2025-hyperlocal-push) (company claim)
  - IoTechWorld AGRIBOT is described as "India's first Government approved Agri-Spray Drone". [Crustdata](https://crustdata.com/profiles/company/iotechworld-avigation-pvt-ltd)

### Inferences
- These are smallholder-style fleets. Assuming about 1,000 Drone Didi SHGs with one drone each, plus 1,595 custom hiring centres, most "operators" run between 1 and a few drones. The multi-hundred-drone fleets belong to a handful of OEM/service companies (Garuda, Marut, Skye Air). This matters for who would buy fleet software. The large operators have the configuration-drift problem. The small ones have record-keeping and service problems.
- Registrations (about 39k) and pilots (about 44k) are close to one-to-one, which suggests most drones are not in large fleets. This is weak inference.

### Gaps
- No primary 2026 DGCA or Digital Sky figure. I found no public Digital Sky dashboard.
- **Autopilot stack:** I found nothing public that ties Garuda, IoTechWorld, Marut, Skye Air, TSAW or Redwing to ArduPilot, PX4 or Cube hardware. DGCA type-certificate documents or teardown posts on ArduPilot Discourse would be the place to look. I did not check them. This should not be assumed.
- I did not locate ideaForge customer fleet composition, TSAW or Redwing fleet sizes, or a FICCI/EY/Drone Federation India fleet-operations report.

## 2. Problems reported by Indian agri-spraying and delivery operators

### Takeaway
The documented Indian pain points are batteries, slow repair and service, transport and logistics, and thin training. Record-keeping, firmware and compliance paperwork do not appear in any field report I found. Downtime is real but measured only in anecdotes; nobody has published a downtime rate.

### Cited Findings
Source for this group: [Ground Report, 30 May 2026](https://www.groundreport.in/states-madhya-pradesh/namo-drone-didi-struggling-with-battery-and-servicing-issues-ground-report/) (verified). It reports from Madhya Pradesh (Sehore and Raisen).
- Battery and charging:
  - A battery cycle is about 16–17 minutes including calibration, with only 8–9 minutes of actual spraying.
  - Recharging takes about 2 hours, plus about 30 minutes of cooling first.
  - A replacement battery costs ₹40–50k once the warranty has expired.
- Downtime and service:
  - One operator's drone has been unused since Dec 2025 after a battery failure.
  - An earlier GPS fault took 10–15 days for technicians to arrive.
- Transport (the article cites a study it does not name): 42.68% of Drone Didis faced transport issues, 78.82% in the South, and 68.66% said hiring vehicles was expensive. **I could not trace the underlying study, so treat these figures as unverified.**
- Kit: the scheme kit includes 4 spare battery sets, one propeller set and a fast charger. Training is 15 days for the pilot plus 5 days for an assistant. Generators and vehicles are often not provided.
- A local official calls the phase one of "learning by doing".

Other sources:
- Battery degradation, MP farmers (Oct 2024): batteries rated for about 30 minutes now deliver 10–15 minutes, and a charge takes more than an hour for about 15 minutes of flight. [MavDrones](https://www.mavdrones.com/drone-didis-battery-woes-drone-news/) (snippet)
- Repair logistics: repairs can mean travelling 40–50 km, and blade replacement can take up to 10 days. [InsideFPV](https://insidefpv.com/blogs/blogs/battery-issues-stall-madhya-pradeshs-drone-didis) (snippet, about 2024)
- On paper, the scheme provides a 2-year AMC and 1-year comprehensive insurance, with Lead Fertilizer Companies responsible for repair and maintenance. [PIB guidelines, Nov 2024](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2024/nov/doc2024114428601.pdf) (snippet)
- Policy commentary notes that recharging cycles and maintenance create recurring downtime, that there are no local repair hubs ("drone clinics"), and that 15-day training may be insufficient. [IMPRI](https://www.impriindia.com/?p=73541) (analysis, not field data)
- Older adoption study: maintenance, piloting skill and service costs are major concerns, and contracting out is the usual workaround. [DroneVideos summary](https://dronevideos.com/?p=6706) (secondary)
- Delivery: Skye Air's CEO names regulatory approvals and weather pauses during heavy rain. Redwing names infrastructure and community acceptance. [Business Today, Jun 2024](https://www.businesstoday.in/amp/technology/news/story/from-sky-to-doorstep-discussing-the-future-of-drone-delivery-in-urban-india-with-skye-air-ceo-ankit-kumar-432833-2024-06-11) (snippet)

### Inferences
- Ground software could address only some of this.
  - **Battery health and cycle tracking:** batteries lose capacity, and operators find out only when flight time collapses. A battery log could show the drop earlier.
  - **Service-ticket and fault records:** a log with timestamps would help prove AMC response times. The 10–15 day wait shows the lack of an accountability trail.
  - **Insurance and AMC documentation:** the AMC and insurance exist only on paper, and nobody tracks claims.
- Software cannot fix the main constraints: battery chemistry, charging power, vehicles and technician density.
- The users are SHG women with 15 days of training. Any tool would have to work offline, in a local language, and be very simple. Firmware and parameter management would mostly fall to the OEM or the fertilizer company (IFFCO and others), not the operator.

### Gaps
- No government evaluation report on Namo Drone Didi or Kisan drone utilisation and downtime was found. The scheme only began in earnest in 2024-26.
- There is no crash or incident rate for Indian agri drones, and I found no DGCA incident statistics for UAS.
- No FICCI, EY or Drone Federation India report on operator pain points was found in this pass.

## 3. Global: what large and enterprise operators say about fleet management, configuration, updates and post-flight review

### Takeaway
The quantified evidence is old or thin. The only hard survey number is from 2019: about 40% of public-safety programmes check firmware updates monthly at best. Newer evidence is qualitative and mostly comes from vendors (AirData, fleet-software blogs). The best government example is the NTSB's own drone programme: 12 drones were tracked in spreadsheets it called "archaic".

### Cited Findings
- DRONERESPONDERS Fall 2019 Public Safety UAS Survey (Aug–Sep 2019, 223–274 respondents per question, ±5%). [PDF](https://www.droneresponders.org/_files/ugd/ef6978_19517dfe38b34fad94d29c2b0c908491.pdf) (verified, text extracted)
  - Only about 60% of agencies check for firmware updates weekly or more often, and about 40% monthly at best. The report calls this neglect of regimented firmware checks a "potential safety risk".
  - It notes that updates can eat into launch time.
  - More than 60% of programmes fly 5 or fewer missions a month in total.
  - Nearly 40% have 6 or more remote pilots.
  - Under 40% use formal qualification tools (PTB/PQS).
  - Only 8% rate external training vendors as extremely well qualified.
- NTSB (Sep 2024): the agency's UAS programme grew from 5 drones, 4 crew and 1 lead to 12 drones and 15 staff. Fleet and personnel records sat in spreadsheets and databases it called "archaic" and "inefficient", which made it hard to keep a robust safety management system. It sought cloud fleet-management software for aircraft and personnel tracking. [AvWeb, 19 Sep 2024](https://avweb.com/aviation-news/ntsb-works-to-streamline-drone-program/) (verified)
- Menlo Park Fire Protection District (DFR programme, flying since 2014), from an AirData case study (May 2026):
  - Its stated priorities are proactive aircraft and battery health management and structured data for reporting and accountability.
  - It needed records for training, maintenance and operational reviews.
  - The article gives no fleet size, downtime figures or firmware data.
  - It is vendor-sourced. [DroneLife, 29 May 2026](https://dronelife.com/?p=109937) (verified)
- Industry survey, Drone Industry Insights *Global State of Drones 2025*: regulatory obstacles (certification, BVLOS) were the top challenge for the third year running, followed by client acquisition and funding. Fleet operations do not appear among the top challenges. [Heliguy summary](https://www.heliguy.com/blogs/posts/global-state-of-drones-2025-industry-whitepaper/) (snippet)
- DroneDeploy's State of the Drone Industry reports (2021: more than 600 users) and its later "State of Reality Capture" (1,447 respondents, AEC-skewed) are not focused on fleet management. I found no pain-point percentage in them. [GeoWeek](https://www.geoweeknews.com/articles/dronedeploy-state-of-reality-capture-report/) (snippet)
- The rest is vendor marketing and does not measure how common these problems are:
  - Spreadsheet maintenance tracking failing as fleets grow. [dronedesk](https://dronedesk.io/drone-fleet-management-guide)
  - An anecdote about a state agency that missed inspections because flight hours were kept in a personal spreadsheet. [Oxmaint](https://oxmaint.com/industries/government/drone-fleet-maintenance-government-aerial-surveys)

### Inferences
- Large public-sector and enterprise programmes do report record-keeping, maintenance-tracking and firmware-discipline problems, but the numbers are thin. The commercial "fleet management" category exists, with AirData, DroneLogbook and Dronedesk as incumbents, mostly built on DJI log ingestion. That shows demand, but it also means the space is not empty.
- Survey respondents put regulation and customers ahead of fleet operations. Fleet tooling is a secondary pain, felt mainly by organisations above roughly 10 aircraft or with a regulator or insurer asking for records.

### Gaps
- I found no public statements from Zipline, Wing or Manna on configuration control or update processes in this pass. Their fleet tooling is built in-house and proprietary.
- There is no recent (2023–2026) survey putting a number on firmware or configuration pain. Commercial UAV News and DRONELIFE surveys were not located with numbers.

## 4. Documented cases of inconsistent settings or firmware across drones

### Takeaway
There are a few real investigation-grade cases where a wrong or missing file or configuration caused a multi-drone or fleet-type accident. None comes from India. The evidence is case-based, not statistical.

### Cited Findings
- Orlando drone show (Dec 2024), from the NTSB preliminary report: the launch parameter file holding the final flight paths had not been sent to the drones, and a 7° misalignment showed in the aircraft logs. Multiple drones fell into the crowd and a child was injured. [WKMG, 16 Jan 2025](https://gmg-wkmg-prod.cdn.arcpublishing.com/news/local/2025/01/16/crashed-drones-in-orlando-christmas-show-were-not-getting-data-minutes-before-show-ntsb-report-finds); [WCJB](https://www.wcjb.com/2025/01/16/orlando-drone-crash-report-details-operator-errors-resulting-collisions) (snippet). The investigation was still open when these reports appeared. The child injury detail is from general press memory and was **not verified** in this pass.
- Swiss STSB safety recommendation 588 (about 2023), from the search snippet only (the PDF returned 404):
  - The flight controller was running ArduCopter 3.5.0-rc5, a release candidate, which could use only 2 of its 3 IMUs.
  - Only firmware 3.6.12 or later, with the matching safety-critical parameter set, would have given that redundancy.
  - Source: [STSB av_se_588](https://www.sust.admin.ch/en/safety-recommendations/aviation/av_se_588.pdf). This is a direct example of firmware-version and parameter configuration being a safety finding on an ArduPilot aircraft. **The operator and aircraft details are unverified.**
- Freefly Astro (Feb 2023): a single-aircraft crash traced to an SD-card hardware fault exposing software bugs, fixed by a firmware update. It shows that the firmware version is a key fact in any investigation. [DroneDJ](https://dronedj.com/2023/02/20/freefly-astro-crash-firmware-update/) (snippet)

### Inferences
- These cases support a narrow value claim: "prove which firmware, parameters and mission file each aircraft actually had at launch". They are rare, high-consequence events, not a daily pain reported in surveys.
- For Indian agri fleets running ArduPilot-derived controllers (unconfirmed), the STSB case is the closest analogue.

### Gaps
- No Indian case was found. DGCA does not appear to publish UAS incident reports in a searchable form.
- I did not get the full STSB 588 text or the NTSB final report on Orlando.
