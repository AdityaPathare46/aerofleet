# Critical review of AeroFleet 2.0, 27 November 2026

Scope: the seven commits after the dossier (`24c814f..8928782`: safety-audit fixes, SA1/FA3, RFC 3161 timestamps,
36-airport airspace, spray acreage, the `pune-agri` fleet, DGCA compliance and the accident dossier, the hi/mr
translation change). 44 files, +3,264 / -284 lines. Read as a sceptical examiner would.

## Verdict

The engineering is better than before: real silent passes are closed, and all 769 tests pass. But two new features do
not do what the docs say. **Today's fleet now marks almost every stock PX4 drone "Check first"**. **A forged timestamp
passes as "attested"**. Three claims made in these commits do not survive a check: FA3 is called held out, SA1 is called
a test, and the translations are called "native-speaker reviewed". Fix those five before the viva. Everything else is
medium or low.

## What was checked

| Check | Result |
|---|---|
| `pytest tests/unit tests/integration` | **769 passed** (the docs say 765 in one place and 752 in another) |
| `npx tsc --noEmit` (tauri-app) | clean |
| `docs/paper/check_numbers.py` | 30 of 30 agree |
| New "failsafe or safety check off" rule run on 200 random public PX4 logs | 199 of 200 flagged (C1) |
| RFC 3161 verifier read line by line, plus its own unit test | a token from a self-made CA passes (C2) |
| SA1/FA3 declaration (`e9c4ebc`) and results (`ffd0f27`) against FA2's declaration | see H1, H2 |
| Drone Rules 2021 rule numbers and the 2021 airspace map, against public sources | see H4, H5 |

## What is solid

- Real silent passes are now closed:
  - a drone with no baseline (NO_REFERENCE) gets "Check first";
  - so does a CSV/GPX-only last flight;
  - a grounded drone gets "Do not fly";
  - ArduPilot `ARMING_CHECK=0` is caught.
- The ordering bug in `reconcile.py` is fixed. The no-AI import guard now also covers `spray.py` and `vr_study.py`.
- The accident dossier HTML escapes every user and file string. It states plainly that it assigns no blame.
- The timestamp request sends only a 32-byte hash. Verification fails closed when the receipt or the token is edited.
- SA1/FA3 was declared before it ran. It reports vehicle-clustered intervals, which fixes a real weakness of FA1/FA2.
  It also reports the crash-flight numbers that do not flatter the product.

---

## Critical: fix before the viva

### C1. The "failsafe or safety check off" rule flags 199 of 200 stock PX4 drones

**Evidence.** `failsafes_off()` was run on the initial parameters of 200 randomly chosen public PX4 logs from
`AeroFleet_px4_data` (the script is at the end of this file).

| Parameter flagged | Logs (of 200) | Why |
|---|---|---|
| `CBRK_FLIGHTTERM = 121212` | **199** | PX4's own default; flight termination is off unless deliberately enabled |
| `COM_LOW_BAT_ACT = 0` | 145 | the default "warning only" action; this rule predates these commits |
| `CBRK_IO_SAFETY = 22027` | 142 | the safety switch is bypassed by default on recent PX4 |
| `CBRK_SUPPLY_CHK = 894281` | 32 | a deliberate bypass: a real finding |
| `NAV_RCL_ACT = 0` | 22 | RC-loss failsafe off: a real finding |
| `GF_ACTION = 0` | 8 | geofence action off: a real finding |

**Why it matters.**
- Once a PX4 drone's settings are uploaded, it can never show "Ready". The board reads "Check first" for everyone.
- That is the alarm fatigue the project argues against.
- FA3's 14.2% does not show this, because FA3 scores only the flight-log reasons (`last_flight_summary`), not the
  settings reasons. The board's real false-alarm rate on PX4 settings is therefore unmeasured, and on this sample it is
  close to 100%.

**Fix.**
1. Flag a breaker only when it differs from that firmware version's default. Do not flag `CBRK_FLIGHTTERM` at all.
2. Treat `COM_LOW_BAT_ACT = 0` and `CBRK_IO_SAFETY` as notices unless the approved baseline differs.
3. Then declare and run FA4: the whole board, settings reasons included, on the held-out vehicles' first logs.

Effort: half a day.

**Status: fixed the same day, not yet committed.**

What changed in `readiness.py`:
- `CBRK_FLIGHTTERM` is no longer checked at all.
- `CBRK_IO_SAFETY = 22027` is now a *setting note*, shown on Today's fleet in en/hi/mr. It is never a reason.
- `CBRK_SUPPLY_CHK`, `NAV_RCL_ACT`, `GF_ACTION` and `COM_LOW_BAT_ACT` stay reasons.
- Values are now read as numbers even when stored as text ("0.0").

Rerun on the same 200 logs: **152 of 200** flagged, down from 199. The remainder:

| Parameter | Logs (of 200) |
|---|---|
| `COM_LOW_BAT_ACT = 0` | 145 |
| `CBRK_SUPPLY_CHK` | 32 |
| `NAV_RCL_ACT` | 22 |
| `GF_ACTION` | 8 |

**Deviation from point 2, on purpose.** `COM_LOW_BAT_ACT = 0` is kept as a reason. It means the drone only warns on low
battery and does not return or land. That is the same hazard as ArduPilot's battery failsafe being off by default,
which the board already flags (and which SITL v2 S1 depends on). So most public PX4 drones really do have it off, and
saying so is correct. An approved spraying baseline sets it to 2 or 3.

New strings (`settingNote` in Hindi and Marathi) have not been read by anyone else. Both demo boards were checked from
the app database: `demo` is still 3/2/3. **FA4 has not been declared or run yet.**

### C2. A forged RFC 3161 timestamp passes as "attested"

**Evidence.**
- Without `ca_pem`, `verify_tsr` takes the signing certificate from inside the token itself. It checks only that the
  certificate carries the timeStamping key usage and was valid at the token's own `genTime`.
- The project's own test proves this. In `tests/unit/test_assurance_tsa.py:97`, a token from a CA made inside the test
  returns `ok: True` with no CA supplied.
- `check_receipt` then prints *"RFC 3161 TSA (…) attested this receipt at … (independent of this computer's clock)"*.
- The app's "Check a receipt" button sends no CA, so this is the path that actually runs.
- VIVA Q44 says this "eliminates trust in the operator's local computer clock".

**Why it matters.** An operator can make a CA and a "TSA" certificate in a few lines of Python, then backdate any
receipt. The feature exists to stop exactly that, and today it accepts it.

**Fix.**
1. Ship the DigiCert and FreeTSA root certificates in the repo and always verify the chain.
2. Report `ok: true` for the timestamp only when `ca_verified` is true. Otherwise say "timestamp present but not
   verified".
3. Check the ESS signing-certificate attribute.
4. Add a test where a self-made CA must fail.

Also, `GET /ledger/receipt?tsa_url=` lets any logged-in user make the backend POST to any URL (SSRF). Restrict it to
an allow-list.

Effort: half a day.

**Status: fixed the same day, not yet committed.**

What `tsa.py` now requires before it accepts a token:
1. The chain reaches the **pinned root** `aerofleet/assurance/data/tsa_roots.pem` (DigiCert Trusted Root G4, copied
   from the certifi/Mozilla store, fingerprint recorded in the file).
2. Every intermediate is a CA and was valid at `genTime`.
3. The signed attributes are present: content-type is TSTInfo, and the ESS signing-certificate attribute names the
   signer.
4. The signer is matched by issuer *and* serial.
5. The nonce is present when one was requested.

`ok` is true only when all of this holds.

Other changes:
- `/ledger/check-receipt` no longer accepts a CA from the caller. That was a second way to trust a self-made CA.
- `tsa_url` must be on `ALLOWED_TSA_URLS`, which is DigiCert only; anything else gets a 422. FreeTSA was dropped,
  because adding its root needs a download.

Tests added:
- a backdated token from a self-made CA is rejected, both offline and through the API;
- a missing or wrong ESS attribute is rejected;
- a missing nonce is rejected;
- a disallowed URL is rejected.

Live check: a real DigiCert token for a random hash verifies against the pinned root, and a wrong hash is rejected.
773 tests pass. VIVA Q44, HANDOFF and Proof.tsx are reworded.

---

## High: wording and test design an examiner will find

### H1. FA3 is not a held-out test

**What happened.**
- FA2's declaration (`measure_fa2.py`) says: *"the rule is not changed again on the basis of this result without a
  new declaration on new data."*
- The rule was then changed in `dbc45d3`: airborne by speed, and in-flight battery.
- FA3 re-ran on the same held-out half H.
- H was no longer untouched: FA2 had already published its per-reason counts.

**Why it matters.** The paper's own checklist forbids exactly this. FA3 is a re-measurement of the revised rule, not
an independent confirmation.

**Also note:**
- The change made false alarms worse on H: 11.1% (FA2) → 14.2% (FA3).
- FA3's vehicle-cluster interval reaches **20.7%**, above the 20% pass mark. "Met" is true only for the point estimate.

**Fix.** In the docs, call FA3 "re-measured on H after a further change (not held out)". Quote the cluster interval
next to "met". Treat the next declared test (FA4, C1) as the clean one: run it on new data, for example the ArduPilot
SITL fleet plus PX4 logs never used before.

### H2. SA1's pass mark was set after its answer was known

**What happened.**
- `develop_on_D.py` had already shown RflyMAD sensor faults flagged at **53.8%** and fault-free flights at 0%.
- SA1 then declared a pass mark of "sensor faults ≥ 50% and fault-free ≤ 5%" on the same RflyMAD flights.
- The result was again 53.8% (106/197) and 0/50.

**Why it matters.** A bar set 3.8 points under a known value is not a test.

**What the data actually says** (worth saying in the viva):

| Group | Flagged |
|---|---|
| Archive crash flights | 36.8% |
| Crashed drones' earlier, normal flights | 26.5% |
| Ordinary H flights | 27.3% |

So the board flags a crash flight about 1.35 times as often as a normal one. It is a records tool, not a crash
detector.

**Fix.** Relabel SA1-RflyMAD as descriptive and state why. Put the 36.8% / 26.5% / 27.3% figures in the report as
they are.

### H3. "Native-speaker reviewed" Hindi and Marathi is a self-review

**What happened.**
- `readinessText.ts` sets `REVIEWED = { hi: true, mr: true }`. Its comment names the project owner as the reviewer.
- The commit came 20 minutes after the previous one.
- `HANDOFF.md:250` still says the translations are unchecked. `HANDOFF.md:193` says they are approved.

**Why it matters.** Review by the person who wrote and shipped the text is not the independent check the flag was
created for. Hindi native-speaker status is also not shown.

**Fix.** Either get one outside reader per language (a classmate or a KVK contact will do) and record their initials
and the date, or set the wording to "read by a team member (Marathi native); Hindi not independently checked". Fix the
HANDOFF contradiction.

### H4. The accident dossier cites "Rule 45"; the 48-hour duty is probably Rule 29

**What happened.**
- `accident_report.py` and the routes call it the "DGCA Drone Rules 2021 Rule 45 48-hour dossier".
- Public summaries of the Drone Rules 2021 put the 48-hour Digital Sky accident report in **Rule 29**, and
  insurance in Rule 44, which matches the code.
- These are secondary sources. Check the gazette text (G.S.R. 589(E), 25 Aug 2021) before printing anything.
- Check "Rule 13" (type certificate), "Rule 14" (UIN) and "Rule 34" (RPC) the same way.

**Why it matters.** A wrong rule number on a printout headed "DGCA" is the easiest point a panel can take.

**Fix.**
1. Correct the numbers.
2. Rename the printout "Accident record prepared for a Digital Sky report", so it does not look like an official DGCA
   form.

### H5. Airport zones: wrong reference point, and agricultural flights are over-restricted

The 2021 airspace map measures distances **from the airport perimeter**:
- 5-8 km is yellow at any height;
- 8-12 km is yellow only **above 200 ft (about 60 m)**, and green below that.

The code differs in three ways:

| Problem | Effect |
|---|---|
| Uses one point per airport, not the perimeter | Zones are up to about 2 km too small along the runway: **under**-restrictive near the red edge |
| Marks all of 5-12 km yellow at every height | A 4 m spraying run 10 km from Pune airport, which is green, is shown "needs permission": **over**-restrictive for exactly the target user |
| 3 km / 8 km radii for "smaller aerodromes" | No source cited |
| 36 airports listed | Smaller aerodromes in farming districts are missing (check Baramati) |

**Fix.**
1. Apply the 60 m height rule in the 8-12 km band.
2. Add a runway-length allowance (or the perimeter) and say so.
3. Cite a source for every radius, or drop the smaller-aerodrome class.
4. Keep "UNCHECKED, verify on Digital Sky", which is right.

---

## Medium

| # | Finding | Evidence | Fix |
|---|---|---|---|
| M1 | The stored-records check in `/ledger/verify` misses swaps and deletions | `verify_stored_records` checks only that a review's hash is *somewhere* in the ledger. Swapping two reviews' reports passes. Deleting a review row passes. A spray form whose review was deleted is skipped (`continue`). | Record `review_id` in the ledger payload. Compare entry to row by key, and compare counts. |
| M2 | `pune-agri` is a simulated fleet, but the screens don't say so | It is seeded from ArduPilot SITL `.bin` files. DEMO.md calls them "6 real ArduCopter SITL flights", and the commit says "a true Indian agricultural fleet". FleetPicker, Today's fleet, Spray register and Trends show no "simulated" label. | Add "Simulated (ArduPilot SITL)" to the fleet name or picker, and to every printout made from it. |
| M3 | "Airborne by speed" uses raw fix-to-fix GPS speed | `_airborne_spans` computes speed from consecutive track points with no smoothing. On the ground, GPS jitter at 5-10 Hz easily exceeds 1.5 m/s, so ground complaints come back as warnings. This fits FA3 rising from 11.1% to 14.2%. | Use the speed over at least 1-2 s, or require it to last, and say which. |
| M4 | Compliance rules apply only if someone filled the form | No insurance record gives a silent pass, yet Rule 44 insurance is mandatory and no UIN gives "Do not fly". The pilot's RPC is stored per drone, but a pilot flies many drones. Expiry is compared with the **UTC** date, so between 00:00 and 05:30 IST it is a day late. | Make "insurance not recorded" "Check first". Store the RPC per pilot. Use the IST date. |
| M5 | The docs have drifted | The dossier says 752 tests and has no SA1/FA3/TSA. The commit says 765; the real count is 769. HANDOFF contradicts itself on the translations. | Fix the counts, then rebuild with `python tools/build_dossier.py` before sending it to the reviewing model. |

## Low

- **L1. AI attribution changed tool.** The new commits are co-authored by "Antigravity", the earlier ones by Claude. The
  paper and the report must name every AI tool used.
- **L2. Spray acreage is an upper bound.** The `area` value comes from moving distance × track spacing, so it includes
  turns. The code says so. The printed Annexure-I should say "upper bound" next to the number, because farmers may be
  billed by it.
- **L3. An operator can clear their own grounding.** It is signed, which is fine. The board should show who cleared it
  and when.
- **L4. RSA-PSS timestamp tokens are rejected.** The verifier uses PKCS#1 v1.5 only. It fails closed, so this is a
  robustness issue, not a security one.

---

## Recommended order, with about three days left

1. **C1** failsafe defaults, then declare and run **FA4** on new data (1 day).
2. **C2** pin the TSA roots, and remove the "attested" wording when the chain is not verified (half a day).
3. **H1-H4** wording fixes in VIVA, HANDOFF, DEMO and the code strings: FA3 not held out, SA1 descriptive, translation
   reviewer, rule numbers (2-3 hours, once Rule 29 is confirmed from the gazette).
4. **H5** the 60 m rule in the 8-12 km band (2 hours), then **M2** the simulated label (30 minutes).
5. **M1, M3, M4** if time allows. Rebuild the dossier last (M5).

## Reproducing C1

```python
import glob, random, collections
from pyulog import ULog
from aerofleet.assurance.readiness import failsafes_off
files = [f for f in glob.glob("/Volumes/One Touch/AeroFleet_px4_data/**/*.ulg", recursive=True)
         if "/._" not in f and "/external" not in f and "/sitl" not in f]
random.Random(1).shuffle(files)
c, n, flagged = collections.Counter(), 0, 0
for f in files[:200]:
    try:
        p = ULog(f, ["vehicle_status"]).initial_parameters
    except Exception:
        continue
    n += 1; out = failsafes_off(p); flagged += bool(out); c.update(o["name"] for o in out)
print(n, flagged, c.most_common())   # 27 Nov 2026: 200 199 [('CBRK_FLIGHTTERM', 199), ('COM_LOW_BAT_ACT', 145), ...]
```

## Sources for H4 and H5

- [Khaitan & Co, Drone Rules 2021 summary (rule numbers)](https://www.khaitanco.com/sites/default/files/2021-09/Ergo_06092021.pdf)
- [Mondaq, Drone Rules 2021 summary and key takeaways](https://www.mondaq.com/india/aviation/1114708/the-drone-rules-2021-summary-and-key-takeaways)
- [PIB, Ministry of Civil Aviation, airspace map release, 24 Sep 2021](https://pib.gov.in/PressReleasePage.aspx?PRID=1757850)
- [Drishti IAS, Airspace Map of India (zone distances)](https://www.drishtiias.com/daily-updates/daily-news-analysis/airspace-map-of-india/print_manually)
