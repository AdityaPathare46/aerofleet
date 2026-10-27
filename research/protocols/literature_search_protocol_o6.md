# Documented Literature Search Protocol and Prior Work Verification (O6)

**Protocol Date:** 26 October 2026  
**Search Period:** 2016 – 2026  
**Target Query Databases:**
1. IEEE Xplore Digital Library
2. ACM Digital Library
3. Elsevier ScienceDirect / Forensic Science International
4. arXiv Computer Science & Robotics (cs.RO, cs.LG, cs.SE)
5. Google Scholar & Crossref Metadata API

---

## 1. Query Strings and Inclusion Rules

### Query Strings:
- `("UAV" OR "drone" OR "PX4" OR "ArduPilot") AND ("crash log" OR "flight log") AND ("root cause" OR "attribution" OR "fault diagnosis")`
- `("UAV" OR "unmanned aircraft") AND ("leakage" OR "cross-validation") AND ("anomaly detection")`
- `("drone" OR "multirotor") AND ("vibration" OR "condition monitoring") AND ("preventive maintenance" OR "prognostics")`

### Inclusion Rules:
1. Empirical evaluation of UAV / drone autopilot logs or telemetry from real hardware or high-fidelity simulation.
2. Models or rules attempting fault detection, accident attribution, anomaly classification, or maintenance screening.
3. Peer-reviewed conference, journal, or indexed technical report.

### Exclusion Rules:
1. Purely theoretical control laws without flight telemetry analysis.
2. Vision-only obstacle avoidance without autopilot telemetry.
3. Studies lacking reproducible dataset or baseline descriptions.

---

## 2. Table of Closest Prior Work and Verification Status

| Citation | Domain & Contribution | Empirical Scope & Baseline | Comparison with Present Study | Verification Status & URL |
|---|---|---|---|---|
| **Kose et al. (2026)** *Sensors* 26(10):3188 | Hardware vulnerability testbed; sim-to-real discrepancies in PX4 logs | Laboratory benchmark testbed; 10 scripted flight experiments | Focuses on sim-to-real divergence; does not evaluate retrospective crash archives, pilot attribution, or leakage. | **Verified** [doi:10.3390/s26103188](https://doi.org/10.3390/s26103188) |
| **Silalahi et al. (2026)** *Forensic Sci. Int. Digit. Investig.* 56:302051 | DroPTC: Sentence-level log message classification for drone forensics | 3 drone models; log text message NLP parsing | Classifies textual console log strings, not numerical continuous flight dynamics; does not attempt binary pilot-vs-aircraft attribution. | **Verified** [doi:10.1016/j.fsidi.2026.302051](https://doi.org/10.1016/j.fsidi.2026.302051) |
| **Duvvuru et al. (2025)** *ICSE 2025*, pp. 385–397 | LLM-agent automated simulation testing and log analytics for sUAS | PX4 SITL simulation runs; prompt-engineered agents | Focuses on synthetic simulation testing; present paper evaluates local LLMs against real-world expert ground truth and discovers voting manipulation. | **Verified** [doi:10.1109/ICSE55347.2025.00223](https://doi.org/10.1109/ICSE55347.2025.00223) |
| **Zibaei & Borth (2024)** *Front. Robot. AI* 11:1123762 | Causal models for actual causes of UAV failures | ArduPilot documentation NLP mining; synthetic fault injection | Traces constructed causal DAGs in simulation; does not evaluate real uncurated public flight archives or binary responsibility labels. | **Verified** [doi:10.3389/frobt.2024.1123762](https://doi.org/10.3389/frobt.2024.1123762) |
| **Wild et al. (2016)** *Aerospace* 3(3):22 | Analysis of 152 civil drone accidents | Regulatory incident reports (FAA, ATSB); human vs. technical factors | Analyzes written accident prose reports; finds equipment failure dominates human error (matching our expert findings); no flight telemetry analyzed. | **Verified** [doi:10.3390/aerospace3030022](https://doi.org/10.3390/aerospace3030022) |
| **Wang et al. (2021)** *ESEC/FSE 2021*, pp. 20–31 | Taxonomy of 569 bugs in PX4 and ArduPilot | Source code commit logs and bug tracker issues | Code-level software bug study; complementary to our finding that configuration/tuning and parameter errors dominate physical hardware failures. | **Verified** [doi:10.1145/3468264.3468559](https://doi.org/10.1145/3468264.3468559) |
| **AAIB (2026)** *Annual Safety Review 2025* | UK official drone accident investigations | 84 investigated UAS occurrences in 2024–2025 | Official government investigation reports; emphasizes lost-link and motor failure modes; no telemetry models evaluated. | **Verified** [gov.uk/aaib](https://www.gov.uk/government/organisations/air-accidents-investigation-branch) |
| **EASA (2026)** *Easy Access Rules for UAS* | European drone regulatory framework | Revision of Regulations (EU) 2019/947 and 2019/945 | Regulatory specifications for incident reporting and flight data logging standards. | **Verified** [easa.europa.eu](https://www.easa.europa.eu) |

---

## 3. Addendum (27 October 2026): studies missed by the search

Peer Review Round 15 named four closely related studies that the queries above did not return. Each was verified
(Crossref, USENIX or arXiv) and added to the manuscript. The search was done by one author and is not a systematic review.

| Citation | Contribution | Relation to the present study | Verification |
|---|---|---|---|
| **Kim et al. (2020)** USENIX Security, MAYDAY | Flight logs hold only high-level control states; adds program-level logging; traces 10 ArduPilot accidents to control-semantic bugs | Mechanistic counterpart of our statistical finding that logs cannot attribute crashes | [usenix.org](https://www.usenix.org/conference/usenixsecurity20/presentation/kim) |
| **Mantas & Patsakis (2019)** LNCS, GRYPHON | Six-step forensic method for ArduPilot Dataflash logs ending in a timeline | Overlaps AeroFleet's evidence timeline; no attribution | [doi:10.1007/978-3-030-26834-3_22](https://doi.org/10.1007/978-3-030-26834-3_22) |
| **Wang et al. (2024)** ICSE | 178 abnormal PX4/ArduPilot logs from real software-bug incidents | Possible external labelled set; not yet opened | [doi:10.1145/3597503.3639186](https://doi.org/10.1145/3597503.3639186) |
| **Vieira et al. (2025)** arXiv 2509.22267 | Segment-wise splits leak in bearing fault diagnosis; bearing-wise partitioning proposed | Unit-wise splitting is not new; we measure its effect on crash logs | [arXiv:2509.22267](https://arxiv.org/abs/2509.22267) |

Kose et al. (2026), previously unconfirmed by a reviewer's search, was re-checked against Crossref on 27 October 2026
(Sensors 26(10):3188, issued 18 May 2026; title and authors match).
