# Drone operator obligations that ground-side software could help satisfy (records, checks, conformance, reporting)

Researched 20 Oct 2026. Status labels: **IN FORCE**, **PROPOSED**, **UNVERIFIED** (secondary source only or text not seen). Several primary PDFs (egazette, federalregister.gov, faa.gov NPRM PDF, EUR-Lex HTML) blocked or returned empty pages to the fetch tool. Where that happened, a secondary source is cited and marked.

---

## 1. India: Drone Rules 2021, QCI certification scheme, Digital Sky, NPNT, draft Bill 2025, agri-spraying SOP

### Takeaway
India's Drone Rules 2021 put very few explicit record-keeping duties on operators. The firm ones are a 48-hour accident report via Digital Sky (Rule 30), a mandatory Digital Sky airspace check before each flight (Rule 21), zone permission (Rule 22), and type-certificate conformance (Rule 14(3)). NPNT, real-time tracking and geofencing are only *enabled* by Rule 12 ("may, in future ... specify"). I found no official evidence that flight-log upload to Digital Sky is mandated or enforced today. The strongest record-type duty for Indian agri-spray operators is the CIB&RC requirement to submit spray-monitoring data within 7 days (secondary source only).

### Cited Findings
- **Rule 30 (IN FORCE):** The remote pilot must report an accident to the Director General through the Digital Sky platform "no later than forty-eight hours" after it occurs. — [Drone Rules 2021 text, legitquest](https://www.legitquest.com/act/drone-rules-2021/8A40)
- **Rule 3(1)(b) (IN FORCE):** "Accident" includes cases where the UAS sustains significant damage, goes missing or is completely inaccessible. So a lost or fly-away drone is reportable. — [legitquest](https://www.legitquest.com/act/drone-rules-2021/8A40)
- **Rule 21 (IN FORCE):** Before starting an operation, the remote pilot "shall mandatorily verify the digital sky platform" for notifications or restrictions in the intended area. — [legitquest](https://www.legitquest.com/act/drone-rules-2021/8A40)
- **Rules 19, 20 and 22(1) (IN FORCE):**
  - Rule 19: Government may publish a red/yellow/green airspace map on Digital Sky at 10 m or finer resolution.
  - Rule 20: The map must be machine-readable through an API so pilots can plot flight plans against it.
  - Rule 22(1): No operation in a red or yellow zone without prior permission.
  - This is the closest India gets to a "conformance to approved area" obligation. — [legitquest](https://www.legitquest.com/act/drone-rules-2021/8A40)
- **Rule 12 (enabling only):** Central Government "may, in future, by notification" specify safety features. These are (a) NPNT hardware and firmware, (b) a real-time tracking beacon (location, altitude, speed, UIN) and (c) geofencing. Rule 12(2) requires owners to adopt notified features, and Rule 12(3) gives at least 6 months to comply. Flight-data logging is not listed. — [legitquest](https://www.legitquest.com/act/drone-rules-2021/8A40)
- **Type certificate (IN FORCE):**
  - Rule 6: No operation unless the UAS conforms to a type certificate or is exempt.
  - Rule 14(3): The operator must ensure the UAS "conforms to a valid type certificate".
  - Form D-1 (type certificate application), items 43 and 44: asks for manufacturer maintenance guidelines and the maintenance inspection schedule / overhaul interval.
  - There is no standalone operator maintenance-record rule in the Rules text reviewed. — [legitquest](https://www.legitquest.com/act/drone-rules-2021/8A40)
- **Penalties (IN FORCE):**
  - Rule 50: penalty up to ₹1 lakh.
  - Rule 49(2): breaches of Rules 22 (zones) and 27 are cognisable and non-compoundable.
  - Rule 53: DGCA may suspend or cancel licences and approvals. — [legitquest](https://www.legitquest.com/act/drone-rules-2021/8A40)
- **QCI Certification Scheme for UAS (Gazette, 26 Jan 2022) (IN FORCE, partly UNVERIFIED):**
  - QCI is the scheme owner and DGCA issues type certificates.
  - A truncated excerpt says flight logs are "witnessed and submitted" during certification.
  - The same excerpt says a firmware update should be allowed only if signed with the manufacturer's digital certificate, and the UAS should be able to verify that signature.
  - I could not read the full text, so whether this binds operators (or only manufacturers at certification) is unverified. — [Gazette notification copy, sarinlaw.com](https://sarinlaw.com/wp-content/uploads/2022/01/Gazette-Notification-Certification-Scheme-for-UAS-26.01.2022.pdf)
- **Certification-body documents:** A QCI-scheme certification body's application form asks for maintenance manuals or procedures, and for the names of personnel competent to fly and maintain the UAS. — [MS Certification form](https://mscertification.net/wp-content/uploads/2026/02/3.PRC_.F03-UAS-information_or_application_rev_00-as-per-QCI-scheme.pdf)
- **Platform split (UNVERIFIED, blog sources):** Since July 2025, registration and certification reportedly moved to eGCA, while Digital Sky keeps flight permissions and NPNT. Sources conflict on whether NPNT is enforced for all non-nano drones or under a grace period. — [Kodainya](https://www.kodainya.com/blogs/indias-digitalsky); [Zbotic](https://zbotic.in/drone-regulations-india-2026-dgca-rules-for-hobbyists/)
- **Draft Civil Drone (Promotion and Regulation) Bill 2025 (PROPOSED):**
  - Released by MoCA for consultation on 16 Sep 2025, with comments due 30 Sep 2025.
  - It would be a standalone Act for civil drones under 500 kg, and rules under it would replace the Drone Rules 2021. DGCA stays the regulator.
  - It includes mandatory UIN registration, type certificates, mandatory third-party insurance, criminal offences for weaponised or dangerous-goods misuse, and victim compensation.
  - No source I found describes specific operator record-keeping clauses. — [Ikigai Law summary, vLex](https://vlex.com/vid/summary-the-civil-drone-1092216594); [MediaNama](https://www.medianama.com/2025/10/223-draft-civil-drone-promotion-and-regulation-bill-2025/); [CAM blog](https://corporate.cyrilamarchandblogs.com/2025/10/draft-civil-drone-promotion-and-regulation-bill-2025-regulation-curtailing-industry-growth/)
- **Agri spraying (IN FORCE as interim regime, details from secondary sources):**
  - The CIB&RC interim approval (Apr 2022, 2 years) allowed pesticides already approved for knapsack spraying to be applied by drone while drone-specific data was generated.
  - Operators must "electronically submit spray monitoring data to the CIB&RC within seven days of spraying".
  - Operators must follow the MoA&FW SOP and use only approved products at approved concentrations and heights. Marking the treated area is the operator's responsibility.
  - I did not read the primary memo or SOP. — [CropLife India SOP summary](https://croplifeindia.org/wp-content/uploads/2022/04/Drone-SOP-India.pdf); [CropLife India SOP](http://croplifeindia.org/wp-content/uploads/2022/03/Drone-SOP-Final.pdf)

### Inferences
- In India, the auditable evidence a ground tool can produce today is narrow:
  - proof of the pre-flight Digital Sky zone/NOTAM check (Rule 21);
  - proof of the zone permission and that the flight stayed inside it (Rule 22);
  - an accident report filed within 48 h (Rule 30);
  - a record that the airframe and firmware match the type-certified configuration (Rule 14(3) plus the QCI signed-update clause);
  - for agri operators, a spray-monitoring record submitted within 7 days.
- "Flight log upload to Digital Sky is required" should **not** be claimed. Rule 12 is only enabling, and I found no gazette notification of mandatory safety features or log upload.

### Gaps
- Rule 27's subject was not confirmed (Rule 49(2) refers to it).
- I could not read Drone (Amendment) Rules 2022 and 2023 (Feb 2022 removed the drone pilot licence in favour of the Remote Pilot Certificate, per my background knowledge, UNVERIFIED here).
- I found no gazette notification under Rule 12. Current NPNT enforcement status is unresolved.
- I did not see the full QCI scheme text, including whether it imposes operator-side log retention or continued-airworthiness duties.
- I did not read the primary text of the CIB&RC interim SOP or the MoA&FW SOP (log fields, retention).
- I found no Indian enforcement or audit cases.

---

## 2. EU / UK: Reg (EU) 2019/947 specific category, SORA 2.5 OSOs, LUC, occurrence reporting

### Takeaway
The specific category has the most explicit and software-friendly requirements:
- UAS.SPEC.050(1)(g) requires records of personnel training, maintenance, and operations including "unusual technical or operational occurrences", each kept for at least 3 years.
- UAS.SPEC.050(1)(i) requires maintenance instructions and qualified maintenance staff.
- Article 19(2) requires occurrence reporting under Reg 376/2014.
- The UK CAA AMC lists the exact technical-logbook fields and requires records to be protected from alteration.

SORA 2.5 became EASA's reference methodology via ED Decision 2025/018/R.

### Cited Findings
- **UAS.SPEC.050(1)(g) (IN FORCE; text read from the UK-retained version, Sep 2026, which mirrors the EU text).** The operator must keep an up-to-date record of:
  - (i) qualifications and training of remote pilots, other essential personnel and maintenance staff, for at least 3 years after they leave or change role;
  - (ii) "the maintenance activities conducted on the UAS for a minimum of 3 years";
  - (iii) "information on UAS operations, including any unusual technical or operational occurrences and other data as required by the operational authorisation for a minimum of 3 years". — [CAA UK Reg 2019/947 consolidated (Sep 2026)](https://regulatorylibrary.caa.co.uk/2019-947-pdf/PDF.pdf)
- **Other UAS.SPEC.050 duties:**
  - (f): operate within the limitations, conditions and mitigations of the operational authorisation (conformance).
  - (h): use UAS designed so that a failure will not take them outside the operation volume (containment).
  - (i): maintain the UAS by defining maintenance instructions and employing trained maintenance staff.
  - (j) and (k): keep up-to-date lists of designated remote pilots per flight and of maintenance staff.
  - (l): green flashing light and active direct remote ID (dated application). — [CAA UK 2019/947](https://regulatorylibrary.caa.co.uk/2019-947-pdf/PDF.pdf)
- **UK AMC1 UAS.SPEC.050(1)(g), "Logging of flight activities and record-keeping":**
  - Operations must be logged in an electronic technical logbook per aircraft.
  - Required fields: UAS identification and serial; date, time and location of take-off and landing; duration; cumulative hours and cycles; responsible remote pilot; activity and OA number, VLOS or BVLOS; significant incidents or accidents; "a completed pre-flight inspection"; site risk assessments and RF surveys; defects and rectifications; "any repairs and changes to the UAS configuration"; UAS.SPEC.100 data.
  - "Records must be stored for 3 years in a manner that ensures their protection from unauthorised access, damage, alteration, and theft." — [CAA UK 2019/947](https://regulatorylibrary.caa.co.uk/2019-947-pdf/PDF.pdf)
- **UK OSO#03 maintenance AMC:**
  - A maintenance programme with scheduled preventive maintenance derived from the designer's requirements.
  - Maintenance and releases to service recorded in a maintenance log system.
  - Release only by personnel holding release authorisation for that model.
  - The log records the work and the reason for it (defect, modification, scheduled). It "may be requested for inspection/audit by the CAA during oversight activities". — [CAA UK 2019/947](https://regulatorylibrary.caa.co.uk/2019-947-pdf/PDF.pdf)
- **UAS.SPEC.060 / UAS.OPEN.060 pre-flight (IN FORCE).** The remote pilot must:
  - check that the UAS configuration complies with the manufacturer's manual;
  - "make sure that the software installed on the UAS and in the command unit is the latest version published by the UAS manufacturer";
  - check battery state;
  - "update the geo-awareness system";
  - set the height limit;
  - check weather, obstacles and restricted zones. — [CAA UK 2019/947](https://regulatorylibrary.caa.co.uk/2019-947-pdf/PDF.pdf)
- **Article 19(2) (IN FORCE):** "Each UAS operator shall report ... any safety-related occurrence ... in compliance with Regulation (EU) No 376/2014." The UK AMC routes reports through MOR on the ECCAIRS 2 portal, with the Operator ID. The UK guidance says mandatory UA reporting is limited to occurrences with fatal or serious injury or involving a manned aircraft. — [CAA UK 2019/947](https://regulatorylibrary.caa.co.uk/2019-947-pdf/PDF.pdf); [EUR-Lex 2019/947](https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX%3A32019R0947&from=PL); [legislation.gov.uk Art 19](https://www.legislation.gov.uk/eur/2019/947/article/19)
- **SORA 2.5 (IN FORCE as AMC):** EASA released the SORA 2.5 methodology on 29 Sep 2025 and integrated it into the AMC/GM to 2019/947 via ED Decision 2025/018/R. Containment is now Step #8 and comes before OSO identification in Step #9. — [BCN Drone Center](https://barcelonadronecenter.com/blog/2025/09/29/sora-2.5/); [EASA SORA 2.5 material](https://easa.europa.eu/fi/downloads/137616/en)
- **OSO titles relevant to ground software** (from the Swedish Transport Agency SORA documentation template; which SORA version it follows is not confirmed):
  - OSO#03: UAS maintained by competent and/or proven entity.
  - OSO#05: UAS designed considering system safety and reliability.
  - OSO#06: C3 link characteristics appropriate.
  - OSO#07: Inspection of the UAS (product inspection) to ensure consistency with the ConOps.
  - OSO#08/#14: Operational procedures defined, validated and adhered to.
  - OSO#09/#15: Remote crew trained and current.
  - OSO#13: External services adequate.
  - OSO#18: Automatic protection of the flight envelope from human error.
  - OSO#23: Environmental conditions defined. — [Transportstyrelsen SORA template](https://www.transportstyrelsen.se/globalassets/global/blanketter/luftfart/dronare/tsl7863t-sora-documentation-references.pdf)
- **Current consolidated text:** EASA Easy Access Rules for UAS, June 2026 revision. — [EASA](https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-unmanned-aircraft-systems-regulations-eu)

### Inferences
- OSO#07 (product inspection against the ConOps), OSO#03 (maintenance log) and the "configuration changes" field in the technical log together are an explicit configuration-conformance obligation. A ground tool that compares as-flown configuration and firmware to the authorised baseline maps onto these directly.
- An auditor would ask for:
  - the technical logbook per airframe, with all AMC fields, 3 years, tamper-protected;
  - the maintenance log and release-to-service records;
  - training records;
  - evidence of the pre-flight inspection and the software-version check;
  - occurrence reports in ECCAIRS;
  - evidence that flights stayed within the OA's operational volume (UAS.SPEC.050(1)(f) and (h)).
- "Protection from alteration" in the UK AMC is a direct hook for append-only or hash-chained logs.

### Gaps
- I did not verify the EU (EASA) AMC wording for UAS.SPEC.050(1)(g). The fields quoted are UK CAA AMC. The EU original has the same 3-year rule text (UK retained law is derived from it), but EASA's AMC may list different fields.
- I did not extract the exact SORA 2.5 OSO list and robustness criteria for OSO#03, #07 and #23 or the containment requirements. SORA 2.5 consolidated the OSO list; confirm against JARUS SORA 2.5 Annex E.
- I did not read the LUC requirements (UAS.LUC.030 safety management system, UAS.LUC.040 LUC manual).
- I did not confirm the Reg 376/2014 72-hour reporting deadline (Art. 4) in this session.

---

## 3. US: FAA Part 107, Part 135, proposed Part 108 BVLOS

### Takeaway
- **Part 107 (IN FORCE)** has a 10-day accident report (§107.9), pre-flight checks (§107.15, §107.49), and a duty to produce required records on request (§107.7). It sets no general log-retention period. The exceptions are Category 4 maintenance records (§107.140) and declarant records (§107.165).
- **Part 108 (PROPOSED, NPRM 7 Aug 2025)** is the first US rule with broad drone recordkeeping: §108.760 retention (life of aircraft or 24 months), §108.40 personnel records, manufacturer flight-data collection and configuration control. As of late Aug 2026 it was reportedly still at OIRA with no final rule.

### Cited Findings
- **§107.9 (IN FORCE):** report "no later than 10 calendar days after an operation" if there is a serious injury, loss of consciousness, or property damage over $500 (excluding the UA). — [eCFR Part 107](https://www.ecfr.gov/current/title-14/part-107)
- **§107.15:** no operation unless in a condition for safe operation; the remote pilot must check before each flight. **§107.49:** before flight, assess weather, airspace and ground hazards, brief participants, check control links, check power, and secure payloads. — [eCFR Part 107](https://www.ecfr.gov/current/title-14/part-107)
- **§107.7(a)(3):** make available on request "any document, record, or report required to be kept". **§107.7(b):** allow FAA tests and inspections. **§107.65:** 24-month knowledge recency. — [eCFR Part 107](https://www.ecfr.gov/current/title-14/part-107)
- **§107.140(c)(4) and §107.165:**
  - Category 4 (airworthiness-certificated) maintenance records kept for 1 year or until the work is repeated or superseded; life-limited part and AD status records transfer with the aircraft.
  - Category 2 and 3 declarants keep supporting data for 2 years. — [eCFR Part 107](https://www.ecfr.gov/current/title-14/part-107)
- **Part 108 NPRM, FAA-2025-14992 (PROPOSED):**
  - Proposed §108.760 "Record Retention": UA records, mechanical-irregularity records and maintenance records kept for the life of the aircraft or for 24 months, as applicable.
  - Proposed §108.40: personnel records kept through employment plus 12 months (the NYC Bar commented this should be longer).
  - Federal Register text not read directly (blocked). — [Federal Register NPRM](https://www.federalregister.gov/documents/2025/08/07/2025-14992/normalizing-unmanned-aircraft-systems-beyond-visual-line-of-sight-operations); [NYC Bar comments](https://www.nycbar.org/reports/unmanned-aircraft-bvlos-faa-comments/); [Pilot Institute](https://pilotinstitute.com/part-108-explained/)
- **Part 108 scope (secondary):** Operators would keep records on aircraft, flight information, mechanical issues, maintenance and alteration inspections, and personnel training. Manufacturers would provide operating, maintenance and configuration-control documentation. — [ABA Air & Space Lawyer, Winter 2026](https://www.americanbar.org/groups/air_space/resources/air-space-lawyer/2026-winter/bvlos-regulation-era-autonomous-drones/)
- **§108.725 (UNVERIFIED):** manufacturers would run a flight-data collection system and retain flight data for at least 2 years. — [Dronebundle](https://dronebundle.com/blog/part-108)
- **Proposed §108.600 (UNVERIFIED, vendor claim):** a vendor maps it to version monitoring, maintenance scheduling and operational data recording. — [Unmanned Airspace / ResilienX](https://www.unmannedairspace.info/uncategorized/reslienx-white-paper-shows-its-technology-alignment-with-faa-parts-108146/)
- **Status:** "29 Aug 2026 — Still under OIRA review. No final rule." — [UAS Dashboard](https://uasdashboard.com/guides/part-108-guide); see also [USI guide](https://www.flyusi.org/guides/get-108-ready)
- **Vendor activity:** Aloft has launched maintenance scheduling and logging aimed at future Part 108 operators, a signal that vendors see this recordkeeping as a market. — [Unmanned Airspace](https://www.unmannedairspace.info/uncategorized/aloft-releases-maintenance-scheduling-tool/)

### Inferences
- Under Part 107, flight logs are good practice, not a legal requirement (apart from the cases above). The legal evidence an auditor wants is the §107.9 report, proof of the §107.49 pre-flight, and the waiver's conditions (BVLOS waivers commonly impose their own recordkeeping; not verified here).
- If Part 108 is finalised as proposed, 24-month or life-of-aircraft maintenance and mechanical-irregularity records become mandatory. That is the clearest US demand signal for ground-side record software.

### Gaps
- I did not read the Part 108 NPRM regulatory text directly (federalregister.gov and faa.gov returned 403).
- Not confirmed: section numbers for maintenance and inspection, configuration and software change control, conformance monitoring, and occurrence reporting timelines. I also did not confirm the comment deadline (about 6 Oct 2025, from background knowledge, UNVERIFIED).
- I did not research Part 135 drone operators (e.g. Wing, Zipline): §135.63 recordkeeping, the §135.65 mechanical-irregularity log, and the Part 5 SMS. Not verified in this session.

---

## 4. UK CAP 722 and Australia CASA ReOC (brief)

### Takeaway
UK requirements come from UK-retained 2019/947 plus CAA AMC (above). The CAP 722 series carries the same technical-logbook and maintenance-log expectations. CASA has a dedicated ReOC record-keeping page, but it timed out, so the Australian details are unverified.

### Cited Findings
- **UK (Sep 2026 consolidated text):**
  - technical logbook per UA, electronic, 3-year retention, protected from alteration (AMC1 UAS.SPEC.050(1)(g));
  - maintenance log and release to service (OSO#03 AMC);
  - remote pilot logbook separate from the technical log;
  - MOR occurrence reporting via ECCAIRS 2. — [CAA UK 2019/947](https://regulatorylibrary.caa.co.uk/2019-947-pdf/PDF.pdf); [CAA UAS occurrence reporting](https://www.caa.co.uk/drones/reporting-concerns-about-safety-privacy-and-illegal-flying/uas-occurrence-reporting/)
- **Australia:** ReOC record-keeping requirements are published by CASA (page not retrieved). Reporting duties to the ATSB changed from 30 Sep 2021. — [CASA ReOC record keeping](https://www.casa.gov.au/drones/remotely-piloted-aircraft-operators-certificate/record-keeping); [Unmanned Airspace](https://www.unmannedairspace.info/uncategorized/australias-new-drone-safety-reporting-requirements-reflect-growing-importance-of-remotely-piloted-aircraft/)

### Inferences
- The UK is the jurisdiction where a tamper-evident electronic technical log is most explicitly required. It is a good reference market for "evidence pack" positioning.

### Gaps
- I did not check CAP 722 section numbers individually.
- Not confirmed for Australia: CASR Part 101 regulation numbers, the Part 101 Manual of Standards (Chapter 10, records, from background knowledge, UNVERIFIED) and retention periods.

---

## 5. Which obligations show up in enforcement or audits?

### Takeaway
I found no reliable public dataset tying drone enforcement actions to specific record-keeping clauses in any of these jurisdictions. The only direct "auditor will ask" statement found is the UK CAA's note that the maintenance log "may be requested for inspection/audit by the CAA during oversight activities".

### Cited Findings
- UK CAA: maintenance log subject to inspection/audit during oversight. — [CAA UK 2019/947](https://regulatorylibrary.caa.co.uk/2019-947-pdf/PDF.pdf)
- US: §107.7 obliges production of required records and allows FAA inspection on request. — [eCFR Part 107](https://www.ecfr.gov/current/title-14/part-107)
- India: Rule 49(2) makes zone violations (Rule 22) cognisable and non-compoundable, the most severe category. Rule 50 penalties go up to ₹1 lakh. — [legitquest](https://www.legitquest.com/act/drone-rules-2021/8A40)
- A FOIA request for the FAA's sUAS accident report database exists, which suggests §107.9 reports are collected centrally. I did not see its outcome. — [MuckRock](https://www.muckrock.com/foi/united-states-of-america-10/database-of-suas-drone-accident-reports-132824/)

### Inferences
- Zone or airspace violations (India Rule 22, EU UAS.SPEC.050(1)(f)) and failure to report accidents (India Rule 30, FAA §107.9) are the obligations with the clearest penalty hooks. Record-keeping failures are more likely found during oversight audits (UK, EU LUC) than in published enforcement.

### Gaps
- I found no FAA enforcement statistics by Part 107 section, no DGCA drone enforcement orders, and no EASA or NAA audit-finding summaries for UAS operators. This is the biggest open question for a "data-backed use case". Possible next sources: FAA Compliance and Enforcement data releases, DGCA enforcement circulars, UK CAA oversight reports.
