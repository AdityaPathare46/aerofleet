# AeroFleet: Project Summary

This document summarizes the pivot from Space Mission Architect (space mission planning) to
AeroFleet (city-scale drone fleet dispatch), what was built, and what still needs verification
on your own machine.

## 1. Why the Pivot

Faculty feedback on the original project raised two issues:

1. **Precision**: orbital trajectory calculations require ~10-digit precision that no LLM can
   guarantee. The project's core safety mechanism — a Control Barrier Function (CBF) gate that
   makes deterministic, non-LLM safety determinations — already existed to address exactly this
   class of problem. The pivot keeps that mechanism and applies it to a domain where the
   precision requirements are more forgiving (metres and watt-hours, not sub-metre orbital
   mechanics) while remaining the actual safety authority.
2. **Model provenance**: the original model roster included Qwen and DeepSeek (Chinese-origin).
   The new roster (Llama 3.3, Mistral Small, Gemma 2, Phi-4) is entirely open-weight and
   non-Chinese.

The HOD's suggested redirect — city-scale drone traffic management & fleet delivery — fits this
architecture well: a multi-agent council reasoning over operational tradeoffs, gated by a formal
safety layer, is directly applicable to drone dispatch.

## 2. What Was Built

### Reused as-is (already domain-agnostic)
- `agents/council.py`'s orchestration loop (pre-screen -> iterative pheromone-weighted debate ->
  CBF gate), `agents/local_agent.py` (Ollama client), `agents/base_agent.py`
- `event_bus/async_bus.py`, `explainability/decision_trace.py`
- `data/database.py` engine setup, `scenario_engine/` harness (registry/runner/reporter)
- `tauri-app`'s WebSocket debate hook pattern

### Rewritten for the drone domain
- **`aerofleet/city/`** (new) — `graph.py` wraps `osmnx` to fetch and cache the real street graph
  for a configurable city (default Pune, India), with an automatic synthetic-grid fallback if
  OSM/network access is unavailable. `airspace.py` models DGCA Red/Yellow/Green zones and
  altitude-banded corridors.
- **`aerofleet/fleet/`** (new) — `models.py` (Drone/Depot/Battery/DeliveryOrder dataclasses),
  `dispatch.py` (deterministic candidate generation: nearest feasible drone by battery/payload/
  ETA), `digital_twin.py` (live fleet state shadow + what-if simulation), `state.py`
  (process-wide in-memory fleet singleton, seeded with demo depots/drones).
- **`aerofleet/safety/cbf_gate.py`** — rewritten with 11 drone constraints (min separation,
  geofence exclusion, battery reserve margin, altitude ceiling, wind limit, payload limit, noise
  limit, collision probability, comms link margin, depot capacity, visibility).
- **`aerofleet/safety/conflict_screening.py`** (new) — deterministic pre-screen for inter-drone
  conflict probability and geofence flags, replacing the old space-conjunction-screening module,
  gating whether the full council debate is even invoked.
- **`aerofleet/safety/emergency_landing.py`** (new) — implements the "Contingency Management"
  requirement: automated diversion to the nearest pre-mapped safe zone on a flight-critical fault.
- **`aerofleet/fault_tolerance/multi_fault_handler.py`** — rewritten `FaultType` enum (MOTOR,
  GPS_LOSS, BATTERY_CRITICAL, COMMS_LOSS, WEATHER_ABORT, PAYLOAD_RELEASE_FAIL, GEOFENCE_BREACH)
  with the same priority/conflict-resolution pattern as the original.
- **`aerofleet/agents/factory.py`, `tools.py`, `specialist_agents.py`, `council.py`** — full
  11-agent roster swap (Dispatcher, Route, Battery, Airspace Safety, Weather, Comms, Cost, Ops,
  Compliance, Autonomy Validator, Payload) plus 5 specialists, non-Chinese model map, new tool
  functions (route feasibility, battery margin, geofence, weather, DGCA compliance, cost).
- **`aerofleet/agents/mock_agent.py`** (new) — deterministic rule-based LLM backend so the whole
  pipeline can be exercised without a reachable Ollama server (`USE_MOCK_AGENTS=true`).
- **`aerofleet/api/`** — new `orders.py` (create/dispatch delivery orders), `routes.py`
  (route/ETA calculation over the city graph), `fleet.py` (live drone/depot state), `geofence.py`
  (zones); `agents.py`/`safety.py`/`ws_debate.py`/`pomdp.py` updated in place; `missions.py` and
  `trajectories.py` removed (directly superseded).
- **`aerofleet/data/models/models.py`** — new SQLAlchemy schema: `Drone`, `Depot`, `Order`,
  `Delivery`, `BatterySwap`, `Geofence`, `AgentInteraction`, `RouteCalculation` (replacing
  `Mission`/`Simulation`/`Component`/`TrajectoryCalculation`).
- **`scenario_engine/`** — `schemas.py`/`evaluator.py` metrics changed to ETA, battery margin,
  delivery cost, noise, comms link margin, CBF pass, DGCA compliance, safety flags. Seven new
  scenario YAMLs replacing the Apollo/Voyager/JWST set: standard delivery, rush-hour conflict,
  depot-outage reroute, storm/wind abort (negative test), battery-swap bottleneck, geofence
  incursion (negative test), motor-failure emergency landing.
- **`docs/PATENT_NOVELTY.md`** (new) — the patent claims draft (see that file for the full text).
- **`README.md`**, **`.env` / `.env.example`**, **`pyproject.toml`**, **`Dockerfile`**,
  **`docker-compose.yml`**, **`k8s/deployment.yaml`**, **`config/default.yaml`** — renamed and
  updated for the new package (`space_mission_architect` -> `aerofleet`) and model roster.

### Left untouched (legacy, out of scope for this pivot) — since removed
This section originally listed `src/` (v1 Streamlit monolith) and every deep-space-specific
`aerofleet/` subpackage (`ssa/`, `rl_trajectory/`, `planning/`, `robotics/`, `knowledge/`,
`evaluation/`, `cislunar/`, `core/`, `digital_twin/`, `explainability/`, `simulation/`, `stm/`,
`ui/`) as untouched legacy. **Update, Phase AJ**: every `aerofleet/` subpackage in that list was
deleted outright (see §14c below for the live-import-trace method used to confirm each was truly
unreferenced before removal, not just assumed dead). **Update, follow-up to Phase AJ**: `src/`
(~20 files, never wired into Docker/pyproject, confirmed by the same grep-based check as the
`aerofleet/` subpackages) was deleted too — nothing legacy remains in the repo.

## 3. Verification Status

This pivot was actually run end-to-end during this session, not just written and assumed to
work. What was found and fixed along the way:

- **`.venv` was corrupted** (pip bound to a phantom Python 3.14 install with broken package
  metadata) — rebuilt from `python3.10`, all dependencies installed and verified importable.
- **Real OSM data confirmed working**: fetching the *whole* city of Pune via `osmnx.graph_from_place`
  hung indefinitely against the public Overpass API. Fixed by bounding the fetch to a configurable
  radius (default 4km, realistic for drone delivery range) around a geocoded centre point via
  `graph_from_point` instead — this pulled a real 7,916-node street graph for Pune in well under
  a minute, and caches to disk after the first fetch.
- **`osmnx.distance.nearest_nodes` needs `scikit-learn`** for lat/lon graphs — was missing from
  requirements, now added.
- **A real, pre-existing bug in `utils/config.py`**: `get_config()` loaded `.env` with
  `load_dotenv(override=True)`, which silently overwrote shell-exported environment variables
  (including the new `USE_MOCK_AGENTS` flag) with the `.env` file's defaults — the opposite of
  the code's own comment ("so env vars take priority"). This caused the live API's council-debate
  endpoint to hang trying to reach the unreachable Tailscale-only Ollama server even with
  `USE_MOCK_AGENTS=true` exported. Fixed by changing to `override=False`.
- **Scenario ground-truth bugs**: two of the seven scenario YAMLs had invented expected values
  that didn't match what the deterministic tools actually compute (comms link margin, a
  conflict-detection timing edge case, a depot-reroute scenario that assumed unimplemented
  auto-rerouting logic). Fixed by deriving ground truth from the real tool output and rewriting
  the depot scenario as a CBF-rejection negative test instead.
- **The Tauri desktop app never actually rendered, even before this pivot**: no `tsconfig.json`
  existed at all (so `npm run build` was broken), five files imported the Zustand store via the
  wrong relative path (`../../store/appStore` instead of `../store/appStore` / `./store/appStore`),
  and — the one that actually blanked the whole app — `appStore.ts` referenced `DEFAULT_AGENTS`
  inside `create()` (which runs synchronously at module-import time) *before* `DEFAULT_AGENTS` was
  declared later in the file, a temporal-dead-zone `ReferenceError` that crashed the module before
  React ever rendered a single node, with no error surfacing through any console/error-boundary
  channel. Found this by running the actual dev server in a browser and bisecting `main.tsx` down
  to a single hook call. All fixed; the CORS allow-list was also missing the Tauri dev port 1420.

**Confirmed working end-to-end** (mock LLM backend, since the real Ollama GPU server is
Tailscale-only and unreachable from this sandbox):
- `pytest tests/` — 43/45 pass (2 pre-existing failures in `test_config.py`, unrelated to this
  pivot — a `DatabaseConfig` env-var double-prefixing bug and a test-isolation issue).
- `python -m scenario_engine.runner --type all` — **7/7 scenarios pass**, including two negative
  tests (high wind correctly triggers a CBF wind-limit rejection; a route crossing a DGCA Red
  Zone correctly triggers a CBF geofence rejection) and one that requires the Conflict Avoidance
  specialist agent to actually fire.
- Live FastAPI server: register → login → create order (against a real OSM-geocoded destination)
  → dispatch (CBF-gated, real street-graph distances) → drone state updates to `EN_ROUTE` →
  fleet digital twin correctly tracks battery/distance consumed. Full agent council debate via
  `/api/v1/agents/debate` also confirmed working against the mock backend.
- **Tauri desktop app, in a real browser via the dev server**: `npx tsc --noEmit` clean (zero
  errors), app renders correctly with AeroFleet branding and the renamed nav (Dispatch Designer,
  Fleet Map, Depot Directory, etc.), and the new Fleet Map page live-fetches from the running API
  and correctly displays "Pune, Maharashtra, India · 7916 street-graph nodes (real OSM data) —
  18 drones · 6 depots". Right panel telemetry gauges (ETA, Battery Margin, Delivery Cost, Peak
  Noise, CBF/DGCA flags) render with the new drone fields.

**Not verified in this session**: a live run against the *real* Ollama models (only the
deterministic mock backend was exercised, by necessity — the GPU server is Tailscale-only) and
the native Tauri desktop window (`npm run tauri dev`, which needs Rust) — only the web dev server
was verified, in a browser. Run these yourself:
```bash
export USE_MOCK_AGENTS=true   # or point OLLAMA_HOST at your reachable Ollama server
uvicorn aerofleet.api.app:app --reload
# see API_TEST_GUIDE.md for the full register -> order -> dispatch flow
python -m scenario_engine.runner --type all
cd tauri-app && npm run dev
```

## 4. Production Pass — Multi-City Map, Visual Redesign, Native Build

A follow-up session took the demo from "web dev server with a schematic SVG map" to a real
desktop app:

- **Multi-city backend**: `aerofleet/city/registry.py` now registers Pune and Mumbai (each with
  real airport coordinates seeding a DGCA Red Zone), `fleet/state.py` keeps one `FleetState` per
  city, and every fleet/geofence/routing/order endpoint takes a `?city=` param. Confirmed both
  cities fetch real bounded-radius OSM graphs (Pune: 7,916 nodes; Mumbai: 6,731 nodes).
- **Real satellite mapping**: the Airspace Map page was rewritten from a schematic SVG to
  MapLibre GL JS with Esri World Imagery raster tiles (no API key) — confirmed via 172 real tile
  fetches and a direct `fetch()` of a tile URL returning a genuine JPEG. Depot/drone positions now
  use real lat/lon (added to the `/fleet/drones` and `/fleet/depots` API responses, computed from
  the OSM graph — they only exposed graph node IDs before). A 3D toggle extrudes depots, drones,
  and geofence zones into their actual altitude bands using `fill-extrusion` layers.
- **Visual identity redesign**: `globals.css` was rewritten top to bottom — graphite background,
  signal-amber accent (was electric blue), sharp 2-6px radii (was 8-16px + glow/blur), no
  gradients or glassmorphism. All decorative emoji were removed app-wide (kept only functional
  glyphs like &#10003;/&#10005;/&#8635;). Pages were renamed around the fleet-dispatch/council
  identity (Ops Center, Dispatch Console, Council Room, Airspace Map, Scenario Lab, Depot
  Network) rather than flight-planner language.
- **Real bugs found fixing the native desktop build** (none of these had ever been exercised
  before this session): `Cargo.toml` declared a `[lib]` target (`aerofleet_lib`) with no
  corresponding `src/lib.rs` — removed, since this is a desktop-only app with all logic in
  `main.rs`. `build.rs` was entirely missing despite `tauri-build` being a declared
  build-dependency — added. The `icons/` directory referenced in `tauri.conf.json` didn't exist
  at all — generated a full icon set via `npx tauri icon` from a new brand SVG matching the
  in-app logo.
- **Tauri native build — confirmed working.** One more real bug turned up during the actual
  build: this project lives on an external drive without native macOS extended-attribute
  support, so the OS transparently shadow-writes a `._<name>` AppleDouble file next to almost
  everything written to it — including Tauri's own build-script output. Tauri's `build.rs` scans
  its output directory for `.toml` files and doesn't filter these out, so it tried to parse a
  binary `._default.toml` as UTF-8 TOML and panicked. Fixed by pointing `CARGO_TARGET_DIR` at a
  path on the native filesystem (e.g. `/tmp`) instead of the project's own external-drive path —
  after that, all 354 crates compiled clean in ~36s (incremental) and the native `aerofleet`
  binary launched and ran stably for 2+ minutes with no crash or panic. **If you hit the same
  `stream did not contain valid UTF-8` panic**, run:
  `CARGO_TARGET_DIR=/tmp/aerofleet-tauri-target npm run tauri dev` (or `tauri build`) instead of
  the bare command — this is an environment quirk of this specific drive, not a code bug, so it
  isn't baked into the repo's config by default.

## 5. Real Drone Hardware Integration + Deployment Hardening

A follow-up session made AeroFleet capable of commanding real ArduPilot/PX4 hardware over
MAVLink, not just simulated drones, and hardened the Docker deployment path. Everything below was
actually run and observed, not just written — see the honesty note at the top of this document
for what that standard means here.

- **`aerofleet/hardware/mavlink_link.py`** — `MAVLinkVehicle`, one connection per real/SITL
  vehicle, built on `pymavlink` (chosen over MAVSDK for full ArduPilot+PX4 protocol coverage).
  Connect/telemetry-decode (HEARTBEAT, GLOBAL_POSITION_INT, SYS_STATUS, GPS_RAW_INT,
  BATTERY_STATUS), arm/disarm, autopilot-aware `set_mode()` (reads the vehicle's own
  `mode_mapping()` rather than hand-rolling per-autopilot tables), takeoff, guided-mode `goto()`,
  full MAVLink mission-protocol upload, return-to-launch, emergency land, and a best-effort
  onboard circular geofence push via ArduPilot `FENCE_*` parameters.
- **`aerofleet/hardware/telemetry_service.py`** — `DroneLinkRegistry`: connection lifecycle
  (register/unregister flips a `Drone`'s `link_mode` between `SIMULATED`/`LIVE`), a 2 Hz async
  poll loop that writes live telemetry onto the *same* in-memory `Drone` object the rest of the
  system already reads and publishes `telemetry.update` events on the existing `AsyncEventBus`,
  and the `emergency_stop_all()` kill switch (RTL every LIVE vehicle, independent of the normal
  dispatch path).
- **Safety-critical wiring, not just plumbing**: `orders.py`'s `dispatch_order` gained exactly one
  new branch — after the CBF gate has already approved a dispatch, *if and only if* the assigned
  drone is LIVE, it arms/takeoffs/gotos the real vehicle. No code path sends a hardware command
  without CBF approval first; this was a hard constraint from the start, not a retrofit.
- **`aerofleet/api/routes/hardware.py`** — connect/disconnect, manual arm/disarm override, list
  LIVE vehicles, the emergency-stop-all kill switch, and a live telemetry WebSocket
  (`/api/v1/hardware/ws/telemetry`), wired into `app.py` with the poll loop started/stopped from
  the FastAPI startup/shutdown hooks.
- **`tools/mock_mavlink_vehicle.py`** — a real (if physics-free) MAVLink vehicle over UDP, used to
  verify all of the above **actually round-trips real MAVLink messages**, not just imports
  cleanly: connect → telemetry decode → arm → takeoff → goto → mission upload (full
  COUNT/REQUEST/ITEM_INT/ACK handshake) → mode change → RTL → disarm, then separately the full
  `DroneLinkRegistry` lifecycle (register → poll loop mutating the live `Drone` → event bus
  broadcast → emergency-stop-all → unregister), and finally the entire stack through the actual
  running FastAPI server and the actual Tauri desktop UI (new **Hardware** panel) via real HTTP/
  WebSocket calls with a real auth token — every one of these passed. The Airspace Map gives LIVE
  drones a distinct amber-ring marker.
- **Docker hardening**: `docker-compose.yml`'s `dashboard` and `nginx` services referenced files
  that never existed (`aerofleet/ui/dashboard.py`, `nginx.conf`) and have been removed; `Dockerfile`
  bumped `python:3.9-slim` → `python:3.10-slim` to match the actually-tested venv; a commented
  `devices:` block documents USB/serial passthrough for real hardware. **Real bug found verifying
  this**: this repo's external, non-APFS drive shadow-writes macOS AppleDouble `._*` files, and
  Docker BuildKit's context walker calls `xattr` on every file — including those — before
  `.dockerignore` filtering even applies, so `docker compose build` failed outright with
  `failed to xattr .../._.claude: operation not permitted`. Added a `.dockerignore` anyway (good
  practice, but doesn't fix this specific failure), and the actual fix is building with the legacy
  builder: `DOCKER_BUILDKIT=0 docker compose build` — confirmed this gets past the xattr error and
  the entire dependency set installs successfully inside the container. The build then failed for
  an unrelated reason in this environment: the host disk was nearly full (570MB free of 228GB),
  and `torch`'s multi-gigabyte CUDA toolkit pull (`nvidia-cudnn-cu13`, `nvidia-nccl-cu13`,
  `triton`, etc.) exhausted it mid-write. `torch` is not imported anywhere in the active
  `aerofleet` package — it's unused dead weight left over from the original project's `robotics/`/
  `rl_trajectory/` subpackages, which are themselves confirmed unwired from the drone-dispatch API
  (see the "Legacy, not part of the active pipeline" note in the README) — removed it from
  `requirements.txt`. **Full `docker compose up` could not be verified in this environment**: even
  without `torch`, the host's APFS container (245GB capacity) has well under 1GB actually free
  system-wide, and the failed build's partial write left Docker Desktop's own daemon in a broken
  state (`meta.db: input/output error` on every subsequent command, including `docker system
  prune`). This is a host disk-capacity issue outside the project — commonly caused by macOS Time
  Machine local snapshots silently consuming tens of GB — not a bug in `docker-compose.yml` or the
  `Dockerfile`. What *is* confirmed: `docker compose config` validates cleanly (no more broken
  `dashboard`/`nginx` references), the AppleDouble/xattr context-transfer issue is solved
  (`DOCKER_BUILDKIT=0 docker compose build`), and the entire pip dependency set installed
  successfully inside the container before the disk was exhausted. Free host disk space and
  restart Docker Desktop, then `docker compose up --build` should complete — this wasn't re-run
  after the `torch` removal because the daemon was already wedged.
- **Regression**: `pytest tests/` re-run after every phase in this pass — same 43 passed / 2
  pre-existing failures throughout (both in `tests/unit/test_config.py`, environment-assertion
  tests unrelated to any of this work; see their own failure output for detail). Nothing this pass
  touched broke anything that was passing before it.

See [`docs/HARDWARE_SETUP.md`](docs/HARDWARE_SETUP.md) for how to actually connect a vehicle,
including the safety disclaimer that governs all of this.

## 6. Map Scoping, Model Roster Refresh, VR Safety View, 3-Tier LLM Deployment, Patent Extension

A follow-up pass covering five requested changes together, since they interact. Same honesty
standard as above — every claim below was actually run and observed.

- **Map scoping**: the Airspace Map's MapLibre instance had no `maxBounds`/zoom limits, so
  panning/zooming pulled Esri satellite tiles for the whole globe. Added a `bounds_radius_km`
  field to `CityConfig` (`aerofleet/city/registry.py`), exposed via `/api/v1/cities/`, and
  `minZoom`/`maxZoom`/`maxBounds` (re-tightened per city on switch, cleared during the `flyTo`
  transition so it doesn't clip the animation) in `TrajectoryViewer.tsx`. Confirmed in-browser:
  zooming out 15x now stops at the city boundary instead of revealing the globe.
- **Model roster refresh**: researched current OpenRouter/Ollama rankings (Aug 2026) and replaced
  the stale roster (`llama3.3:70b`, `mistral-small:24b-instruct`, `phi4:14b`, `gemma2:27b-it`)
  with `llama4:scout`, `mistral-small3.2`/`mistral-large-3`, `gemma4:12b`, `phi4-reasoning:plus` —
  all confirmed real/pullable tags, all non-Chinese-origin per the constraint established at the
  original pivot. The old tags were hardcoded in **six** separate places, not just
  `factory.py`'s `DEFAULT_MODEL_MAP` — `council.py`'s separate complexity-tier routing table,
  5 hardcoded model attributes in `specialist_agents.py`, a docstring example in `ws_debate.py`,
  `.env.example`, and the frontend's `appStore.ts` display array all needed updating together, or
  the roster would look upgraded in some views and stale in others. Verified with a full-repo
  grep sweep for the old tags (zero hits) plus a live Python import check of every updated value.
- **3-tier LLM connection architecture**: new `aerofleet/agents/runtime_settings.py`
  (`RuntimeLLMSettings` singleton, same getter-singleton idiom as `fleet/state.py`'s
  `get_fleet_state`), rewired `llm_backend.py` to read it instead of raw env vars, new
  `aerofleet/agents/openrouter_agent.py` (third mode — hosted API — with its own
  Ollama-tag→OpenRouter-model-id translation table, since OpenRouter doesn't have Mistral Large 3
  or Gemma 4 listed yet and falls back to the previous generation for those two, documented
  rather than hidden), and new `aerofleet/api/routes/settings.py` (`GET`/`PUT`/`POST .../test`).
  **Real bug found and fixed while testing**: `LocalMissionAgent`'s Ollama client had no
  connection timeout at all, so a bad Tailscale IP entered in the Settings UI would hang the
  "Test Connection" button for a minute-plus on the OS's own TCP timeout; added an explicit
  `connect_timeout` param, 5s for the test path. Verified live: connect/switch/test all three
  modes through the actual running Settings page in the browser, including watching the fix turn
  a 60+ second hang into a clean ~6 second failure.
- **Windows/macOS Ollama installer automation** (`tauri-app/src-tauri/src/ollama_installer.rs`,
  new Rust module) — `check_ollama_status`, `install_ollama` (download the official installer,
  verify its SHA-256 against `sha256sum.txt` fetched from the same GitHub release, only then
  execute it), `pull_model` (roster-tag-validated), `get_linux_install_command` (Linux is
  deliberately **not** automated — piping a fetched script into a shell unattended was judged a
  bigger trust surface than a checksum-verified installer binary, so it just returns the official
  `curl | sh` command for the user to run themselves). Deliberately doesn't use
  `tauri-plugin-shell`'s JS-invokable command API at all — these are narrow, purpose-built Rust
  commands, so the frontend can only ever call these four specific operations, which is a tighter
  security boundary than ACL-scoping a general shell-execute permission would have been.
  **Real bug found by a deliberately-written live test**: `sha256sum.txt`'s real content prefixes
  every filename with `./` (e.g. `./Ollama-darwin.zip`), which the initial checksum parser didn't
  strip, so it would have silently failed to find a match for every real release. Caught by a
  `#[tokio::test] #[ignore]` test that hits the actual GitHub Releases API rather than only
  synthetic fixtures — 6 fast unit tests plus that one live test all pass (`cargo test --bin
  aerofleet -- --include-ignored`). Compiles clean, zero warnings; the actual native binary was
  built and launched successfully via `cargo run` (confirmed via the dev-mode `tauri dev` log,
  separate from Vite's own port conflict which was an unrelated leftover process, not a bug in
  this code).
- **VR Safety View** (`tauri-app/src/pages/VRSafetyView.tsx`, new) — renders each in-flight
  drone's live CBF constraint margins as literal 3D geometry (translucent separation sphere,
  altitude-ceiling plane, battery-reserve gauge, HUD labels for the remaining constraints) in a
  WebXR scene via `@react-three/fiber` + `@react-three/xr` (both previously-installed
  dependencies that were completely unused until now). Backed by a new
  `GET /api/v1/safety/live-margins` endpoint that re-evaluates the *same* CBF gate
  `dispatch_order` already uses, read-only, against live fleet telemetry — filtered to only
  actually-flying drones, since depot-parked idle drones are legitimately within the 15m
  separation constraint's threshold without that meaning anything unsafe, which was confirmed by
  running it before the filter and seeing exactly that false-positive violation. **This took a
  long, honestly-documented debugging pass**: the scene appeared black by default because the
  camera started too far from where a real dispatched drone (several km from the depot) actually
  was, plus every WebXR/error-boundary interaction ended up being a red herring chased down one at
  a time (stale console-message buffering, a genuine-but-unrelated `OrbitControls`
  stale-spherical-offset bug in an intermediate design, a suspected-but-ruled-out
  duplicate-Three.js-instance issue, a suspected-but-ruled-out exhausted-WebGL-context theory) —
  the actual fix was just tuning the default camera distance and confirming via a fresh browser
  tab that the render pipeline had been correct all along. Confirmed rendering with a real
  dispatched drone showing the correct green (safety-passed) marker color and position.
- **Patent doc extension**: added Independent Claim 4 (immersive VR rendering of CBF margins) and
  Claim 5 (deployment-flexible LLM architecture with a safety boundary independent of connection
  mode) to `docs/PATENT_NOVELTY.md`, plus a dependent claim giving AR breadth without having
  built it. Added a one-line "superseded" header to `docs/PATENT_CLAIMS.md` (the original
  orbital-mechanics patent draft) rather than deleting it.
- **Regression**: `pytest tests/` and `tsc --noEmit` re-run after every phase — same 43 passed / 2
  pre-existing failures throughout on the Python side; TypeScript clean throughout.

## 7. Correctness & Reliability Hardening

A follow-up pass, explicitly scoped by the user to "correctness and reliability" over deeper
research novelty or UI polish. Started with a real audit (three parallel Explore passes over the
codebase) rather than a generic checklist, and found concrete problems — each item below states
what was actually found and actually fixed, same honesty standard as every phase before it.

- **Multi-worker correctness/safety bug, found and fixed**: `Dockerfile`'s production `CMD` ran
  `uvicorn ... --workers 4`, but `FleetState` (`aerofleet/fleet/state.py`), `DroneLinkRegistry`
  (`aerofleet/hardware/telemetry_service.py`), and `AsyncEventBus` (module-level in
  `aerofleet/api/routes/hardware.py`) are all plain module-level singletons — one independent copy
  per OS process, not shared across uvicorn workers. Traced the actual consequence: every one of
  the 4 workers runs FastAPI's startup hook, so every worker would independently call
  `start_background_polling()` and spin up its own `DroneLinkRegistry.run_forever()` loop — meaning
  4 separate MAVLink connections opening to, and independently commanding, the same real vehicle.
  For software that arms and flies real aircraft, that's not just a consistency bug. Fixed by
  pinning `--workers 1` with an inline comment explaining why it's an intentional architectural
  choice at this project's scale, not an oversight — and documenting what a real fix would actually
  require: Redis for the small, already-`to_dict()`-ready mutable drone/depot/order state (the easy
  part), plus a genuine redesign of MAVLink-link ownership (which worker owns which live socket)
  and pub/sub-based WebSocket fan-out (so telemetry reaches clients connected to *other* workers) —
  neither of which is implemented, and a partial fix (Redis for state alone) would leave the
  hardware layer worse off than today, not better. This was never caught earlier because the
  project has only ever actually been run and demoed with a single process
  (`uvicorn --reload`/`python -m uvicorn ... --port 8000`, no `--workers` flag) — the bug was real
  but latent, only reachable through the Docker path specifically.
- **Security audit findings, fixed**: `aerofleet/api/routes/settings.py` (accepts an OpenRouter API
  key) had zero authentication on all three routes — now gated by `get_current_active_user`. Any
  registered user could arm/disarm/emergency-stop-all real hardware — added a minimal `is_operator`
  boolean to the `User` model (not a full permissions system) and a `get_current_operator_user`
  dependency, applied only to hardware's control endpoints (connect/disconnect/arm/disarm/
  emergency-stop-all), not the read-only `GET /vehicles`. Both WebSockets
  (`hardware.py`'s `/ws/telemetry`, `ws_debate.py`'s `/debate`) accepted any connection with no
  token check — both now require `?token=<jwt>`, validated via a new `get_user_from_token()` helper
  factored out of `auth.py`'s existing decode logic. `/auth/login` had no brute-force protection and
  no endpoint anywhere had rate limiting (a `rate_limit_per_minute` config field existed but was
  never wired to anything) — added `slowapi`, applied to login (5/min), register (10/min), dispatch,
  and hardware control endpoints. `safety.py`'s `verify_route` accepted a raw, unvalidated dict body
  despite feeding the CBF gate directly — added a proper `VerifyRouteRequest`/`TrajectoryPoint`
  Pydantic schema. Removed `passlib` (declared but never used; auth uses `bcrypt` directly).
- **A real bug found live-testing the WebSocket auth, not by inspection**: the first version closed
  the DB session (`with get_db_session() as db: user = get_user_from_token(...)`) and then accessed
  `user.is_active` *after* the `with` block exited — SQLAlchemy had already detached the ORM
  instance from its session, so every WebSocket connection attempt with a *valid* token crashed with
  `DetachedInstanceError` and a 500, while only the reject-path (no/bad token) worked. Only caught by
  actually connecting a real WebSocket client with a real token, not by the no-token rejection test
  alone — fixed by reading `user.is_active` while the session is still open, confirmed by re-running
  both the reject and accept paths against the live server afterward.
- **All of the above verified live**, not just unit-level: ran the actual API, registered a normal
  user and an operator user, flipped `is_operator` via direct SQL (no admin UI exists yet — documented
  as the known way to do this today), and confirmed: settings/safety endpoints 401 without a token;
  hardware control 403s for a non-operator and succeeds end-to-end (through a real mock MAVLink
  vehicle) for an operator; 6 rapid login attempts against a wrong password correctly return
  401×5 then 429; both WebSockets reject with no token and connect cleanly with a valid one.
- **Regression**: `pytest tests/` — same 43 passed / 2 pre-existing failures throughout.
- **Test coverage on every previously-untested safety-critical path**: the entire pre-existing
  `tests/` suite was a holdover from the original orbital-mechanics project — real, passing, but
  zero coverage on `aerofleet/safety/cbf_gate.py`, `aerofleet/fleet/dispatch.py`, `orders.py`'s
  `dispatch_order`, or anything in `aerofleet/hardware/`. Added, additively (no legacy fixture or
  test touched):
  - `tests/unit/test_cbf_gate.py` — all 11 named constraints individually pass and violate,
    multi-point/multi-violation aggregation, the ASIF-QP near-violation correction path, config-
    driven thresholds. `cbf_gate.py`: 0% → 92% covered.
  - `tests/unit/test_dispatch.py` — `DispatchEngine` candidate ranking/exclusion (payload,
    battery, availability) against a stubbed `CityGraph` (no OSM network dependency). `dispatch.py`:
    0% → 100% covered.
  - `tests/unit/test_mavlink_link.py` — `MAVLinkVehicle`'s pure telemetry-decode logic
    (HEARTBEAT/GLOBAL_POSITION_INT/SYS_STATUS field mapping, sentinel-value handling) and the
    `MAV_CMD_*` constant resolver, against synthetic message objects — no live socket needed.
  - `tests/integration/test_dispatch_order_api.py` — the real `POST /orders/{id}/dispatch`
    endpoint via `TestClient`, `use_council=false` (no LLM dependency): CBF-approved vs
    CBF-rejected paths, that drone state actually mutates (not just the response body), and —
    mocking only the `MAVLinkVehicle` methods, not the real dispatch logic — that a LIVE-linked
    drone's `arm()/takeoff()/goto()` are called if and only if the CBF gate approved. `orders.py`:
    0% → 67% covered (the `dispatch_order` path specifically; plain CRUD endpoints remain
    untested and are lower-stakes).
  - `tests/hardware/test_mock_vehicle_integration.py` — the one test that exercises the *real*
    MAVLink wire protocol: spawns `tools/mock_mavlink_vehicle.py` as a subprocess, drives a real
    `MAVLinkVehicle` over a real UDP socket through connect→arm→takeoff→mission-upload→RTL→disarm,
    codifying the same sequence manually verified during the original hardware-integration phase.
    Marked with a new `hardware` pytest marker, excluded from the default run via
    `-m "not hardware"` in `pytest.ini`/`pyproject.toml` (subprocess + real socket timing isn't
    appropriate for the fast default suite) — run explicitly with `pytest tests/ -m hardware`.
  - New `tests/conftest.py` fixtures (additive): `api_client` (real `TestClient`, triggers
    startup/shutdown lifecycle), `fresh_fleet_state` (clears the `FleetState` singleton between
    tests), `auth_headers` (registers a throwaway user, returns a bearer token).
  - **Two real test-isolation bugs found and fixed while writing these, not by inspection**: (1)
    the rate limiter added in this same pass is a per-process singleton
    (`aerofleet/api/rate_limit.py`) — without resetting it, whichever test happened to be the 6th
    in a run to hit `/auth/login` got a spurious 429 caused by an *earlier* test's login calls, not
    its own; added an autouse `reset_rate_limiter` fixture calling `limiter.reset()`. (2) `get_config()`
    calls `load_dotenv()`, which — the first time any test boots the real app — writes this repo's
    `.env` values (`OLLAMA_HOST`, etc.) into `os.environ` as a process-wide side effect that then
    silently leaked into every later test in the same pytest run, including the pre-existing
    `test_config.py::test_default_values`; extended the already-existing autouse
    `reset_singletons` fixture to snapshot/restore `os.environ` around every test. Confirmed fixed
    by running the full suite both with and without `OLLAMA_HOST` set in the ambient shell.
  - **Result**: 43 → 95 tests passing (2 deselected `hardware`-marked, run separately and
    confirmed passing on their own), same 2 pre-existing environment-sensitive failures in
    `test_config.py` (unrelated to any of this work — confirmed by reproducing them with a clean
    `env -u OLLAMA_HOST`, which restores the original 2-failure baseline). Overall coverage:
    ~25% → 42%.

## 8. CI Pipeline — Fixed and Locally Verified

`.github/workflows/ci-cd.yml` had never been confirmed to pass a single run: it pinned Python 3.9
(the Dockerfile has been 3.10 since Phase O), and its `build`/`deploy` jobs pushed an image named
`spacemission-api` and ran `kubectl apply`/`kubectl rollout status` against a
`space-mission-architect` k8s namespace — fossils of the pre-pivot project name — requiring
registry/kubeconfig secrets that were never configured and a `k8s/deployment.yaml` that doesn't
exist. Verified every step locally rather than assuming the YAML is correct:

- **Python version**: bumped the `test` job to 3.10.
- **`build`/`deploy` jobs**: gated behind `workflow_dispatch` (manual-only) with a comment stating
  they need real secrets before use, rather than left silently broken on every push.
- **flake8**: split into two steps. The syntax-error-only check
  (`--select=E9,F63,F7,F82`) is the real hard gate — confirmed clean locally (0 errors). The
  broader style check (`--max-line-length=100`) found **718 pre-existing violations** (mostly line
  length and blank-line spacing) predating this entire project's pivot — made informational
  (`continue-on-error: true`) rather than either silently dropped or used to block merges on debt
  this pipeline was never actually clean of. Confirmed none of this pass's own new/touched files
  meaningfully move that number.
- **mypy**: found **185 pre-existing type errors**, the large majority SQLAlchemy `Column[T]` vs
  `T` false positives from not having the SQLAlchemy mypy plugin configured (every ORM model field
  access in `orders.py` trips this). One real-but-pre-existing finding worth noting for later:
  `settings.py`'s `test_llm_settings` assigns either an `OpenRouterAgent` or a `LocalMissionAgent`
  to the same local variable across two branches, which mypy correctly flags as a type-narrowing
  issue — not introduced by this pass's auth changes, not fixed here either. Made informational
  for the same reason as the style check.
- **Frontend step added**: `npx tsc --noEmit` — confirmed clean (0 errors) against the actual
  current `tauri-app/` source.
- **Rust step added**: `cargo test` in `src-tauri/` — confirmed all 6 non-ignored tests in
  `ollama_installer.rs` pass (the 7th, hitting the real GitHub API, stays `#[ignore]`-marked for
  the default run, same as before).
- **A real dependency-conflict bug found while verifying, unrelated to the CI YAML itself**: an
  ad-hoc `pip install` earlier in this pass (for `slowapi`) silently pulled `pytest-asyncio` up to
  `1.4.0` in the local dev venv, incompatible with the pinned `pytest==7.4.3`
  (`ImportError: cannot import name 'FixtureDef' from 'pytest'`) — broke the *entire* test suite,
  not just async tests, since pytest auto-loads every installed plugin at startup. This is a local
  venv-drift artifact from many ad-hoc installs across a long session, not something a clean CI
  install of `requirements-dev.txt` would hit — but real and worth recording since it silently
  wiped out every test result for a while before being caught. Fixed by reinstalling the exact
  pin (`pytest-asyncio==0.21.1`).
- **A real, unrelated bug found purely by hitting it while re-verifying**: this repo lives on a
  non-APFS external drive, and ongoing filesystem activity (cargo/pip installs running
  concurrently) kept regenerating macOS AppleDouble shadow files inside `.venv` — one of them,
  a corrupted copy of a matplotlib bundled style file, made `osmnx`'s import path throw a
  UTF-8 decode error, which `aerofleet/city/graph.py`'s broad exception handler correctly caught
  and treated as "OSM unavailable," triggering the documented synthetic-grid offline fallback —
  exactly the scenario that fallback exists for. But the fallback itself was broken:
  `_build_synthetic_grid()` builds a plain `networkx.Graph`, while `path_length_km()` unconditionally
  assumed the OSM-only `MultiDiGraph` shape of `get_edge_data()` (`{parallel_key: {attrs}}` vs a
  plain Graph's `{attrs}` directly), crashing with `AttributeError: 'float' object has no attribute
  'get'` on every route-distance calculation. This means the offline fallback — a documented,
  load-bearing feature ("the rest of the system still runs fully offline") — has likely never
  actually worked for anything that computes a route distance, since whatever originally triggered
  it (network unavailability) was never exercised end-to-end. Fixed by detecting the actual edge-data
  shape at the point of use instead of assuming one; confirmed by forcing the fallback path and
  computing a real route distance successfully (`2.4 km`) with no crash.
- **Regression**: full suite re-run after all of the above — 95 passed, same 2 pre-existing
  environment-sensitive failures.

## 9. Restructuring the LLM's Role — Decouple Council from Dispatch

Direct faculty feedback from a project review meeting: **LLMs cannot be used for real-time
decision-making or taking action, because inference latency is fundamentally incompatible with
it — a different use case for the multi-agent LLM system needed to be found.** Investigating this
turned up a real, active bug, not just a design smell worth preempting:

- **The actual bug**: `aerofleet/api/routes/orders.py`'s `dispatch_order` had a `use_council=True`
  branch that called `CouncilOfExperts().run_grand_debate(dispatch_plan)` — a plain `def`, not
  `async def`, making up to 80 sequential LLM calls (≤10 core agents + ≤5 specialists + 1
  dispatcher synthesis, × up to 5 debate rounds) — **synchronously, with no `await`, inside an
  `async def` FastAPI handler**. Because nothing in that call chain ever yielded control back to
  the event loop, this didn't just make the one calling client wait tens of seconds to minutes —
  it blocked the single-threaded asyncio event loop that serves *every* concurrent request on the
  server for the entire duration of the debate. `aerofleet/api/routes/agents.py`'s `/debate`
  endpoint had the identical problem, unconditionally, with no CBF gate at all.
- **Dead code found alongside it**: `aerofleet/api/routes/ws_debate.py`'s `broadcast()`, which the
  frontend's "watch the council deliberate live" UI assumed was streaming messages in real time,
  had **zero callers anywhere in the codebase** — grepped the whole package to confirm. The "live
  debate" experience never actually worked; the frontend got total silence for the whole debate,
  then everything at once, if it ever got a response at all.
- **A second, unrelated bug found the same way**: `tauri-app/src/pages/MissionDesigner.tsx`'s
  "Create & Dispatch Order" button only ever called `POST /orders/` (order creation) — it never
  called `POST /orders/{id}/dispatch` at all, so no live dispatch had ever actually been exercised
  through the UI before this pass.

**The fix was architectural, not a patch.** Dispatch is now unconditionally deterministic and
instant: the `use_council` flag and its entire branch were deleted from `dispatch_order`, not
gated off — candidate generation → CBF gate → execute/reject is the *only* path left, and it's
the same deterministic path already covered by Phase Y's tests. The council was fully decoupled
into an optional, human-triggered, asynchronous **post-hoc explanation** step:

- New `aerofleet/agents/explanation_worker.py`, following the exact background-worker idiom
  already established by `aerofleet/hardware/telemetry_service.py` (module-level
  `Optional[asyncio.Task]`, idempotent `start_background_explanation_worker()`/`stop_...()` wired
  into `app.py`'s startup/shutdown events, an internal `asyncio.Queue`, a cooperative
  `while self._running` loop) — pulls jobs off the queue and calls the council via
  `loop.run_in_executor(None, ...)`, which is the detail that actually matters: since
  `run_grand_debate`'s LLM calls are themselves synchronous, wrapping the call in a plain
  `asyncio.create_task` without `run_in_executor` would **not** have fixed the blocking — only
  offloading it to a real OS thread does.
- `council.py`'s `run_grand_debate` gained an optional `precomputed_cbf_certificate` parameter —
  when generating an explanation for a decision that already happened, the council uses the real
  certificate that was actually enforced rather than silently re-deriving a second, possibly
  different (if fleet state moved on) verdict that would never be shown to anyone.
- New `POST /orders/{id}/request-explanation` enqueues a job; existing `GET /orders/{id}` was
  extended with `council_explanation_status`/`council_transcript` fields, polled for exactly like
  every other async status in this app — no new streaming mechanism introduced.
- `ws_debate.py` was deleted outright, along with the frontend's `useDebateWebSocket.ts` hook —
  it was dead code with nothing to stream live under the new model, not a working feature that got
  removed.
- `agents.py`'s `/debate` endpoint (used for standalone, order-less debate testing/demos) was
  converted to the same async-job pattern: returns a `job_id` immediately (202), polled via a new
  `GET /debate/{job_id}`.
- Frontend: `MissionDesigner.tsx` now actually calls `/dispatch` and shows the instant result
  (verdict, assigned drone, CBF certificate) inline, with an explicit "Request Explanation" button
  that makes the async/optional nature of the LLM step visible rather than implied.
  `CouncilViewer.tsx` was redesigned from a (non-functional) live transcript view into a simple
  history browser — pick a past order, see its decision and, if requested, its explanation —
  polling only while a request is `PENDING`/`RUNNING`, same pattern as every other page.

**A real, unrelated bug found while verifying this, not by inspection**: `tests/conftest.py` sets
`os.environ["DATABASE_URL"] = "sqlite:///:memory:"`, and this had silently never worked.
`DatabaseConfig` (`aerofleet/utils/config.py`) declares `model_config =
SettingsConfigDict(env_prefix="DATABASE_")` with a field literally named `database_url` —
pydantic-settings therefore actually reads `DATABASE_DATABASE_URL`, not `DATABASE_URL`. Every test
run had, in fact, been hitting a real file (`sqlite:///./aerofleet.db` in the repo root) instead
of an isolated in-memory DB — invisible until this pass added new `Order` columns
(`dispatch_plan`, `council_explanation_status`, etc.), since `Base.metadata.create_all()` doesn't
alter existing tables, and the stale on-disk schema then failed every dispatch test with
`OperationalError: table orders has no column named council_explanation_status`. This bug wasn't
scoped to tests either: `docker-compose.yml` and `k8s/deployment.yaml` both set plain
`DATABASE_URL=postgresql://...`, meaning a real deployment following either of those files would
have silently ignored its configured Postgres URL and fallen back to a local SQLite file. Fixed at
the source — `database_url: str = Field(..., validation_alias="DATABASE_URL")` plus
`populate_by_name=True` (so direct dict/kwarg construction, e.g. in `DatabaseConfig(database_url=...)`
test calls and YAML config loading, still works alongside the alias) — rather than worked around
in `conftest.py`, since the same bug would otherwise still be silently live in production. Deleted
the stale `aerofleet.db`/`._aerofleet.db`/`space_missions.db` files this bug had accumulated
(already `.gitignore`d, never committed).

Fixing that one bug immediately surfaced **two more layered underneath it** — each was masking
the next, so `DATABASE_URL=sqlite:///:memory:` had, in fact, never once actually taken effect in
this codebase's history until all three were fixed together:

- `config/default.yaml` (used by both the `development` and `test` environments, neither of which
  has its own YAML file) explicitly pinned `database:.database_url: sqlite:///./aerofleet.db` —
  redundant with the field's own default, but because `Config.load_from_yaml()` passes YAML values
  as constructor kwargs, and constructor kwargs outrank env vars in pydantic-settings' source
  priority, this explicit line silently shadowed the `validation_alias` fix above for exactly the
  two environments tests and local dev actually run under. Fixed by removing the redundant line
  (with a comment explaining why it must stay removed) so the field default — the same effective
  value — applies only when `DATABASE_URL` isn't set, letting the env var win when it is.
- With both of the above fixed, `DATABASE_URL=sqlite:///:memory:` finally reached
  `aerofleet/data/database.py`'s `init_db()` for the first time — which unconditionally passes
  `pool_size`/`max_overflow` to `create_engine()`. SQLAlchemy's correct default pool for
  `sqlite:///:memory:` is `SingletonThreadPool`, which doesn't accept those kwargs at all —
  `TypeError: Invalid argument(s) 'max_overflow' sent to create_engine()`. Fixed by branching:
  `sqlite:///:memory:` now gets `StaticPool` (so every session shares the one connection that
  actually has the schema — `SingletonThreadPool` alone ties connections to a thread, which
  FastAPI's `TestClient` can cross), everything else keeps the original `pool_size`/`max_overflow`
  path unchanged.

All three fixed together, the test suite now gets genuine in-memory isolation for the first time —
confirmed by the fact that no `aerofleet.db` file gets created by a test run at all anymore
(previously, `pytest tests/` silently wrote real order rows to a real file in the repo root, every
run, forever, undetected because no test asserted anything about row *count*).

- **Regression**: `pytest tests/` — 96 passed, 2 deselected (`hardware`-marked), 1 failing —
  `test_config.py::TestConfig::test_load_default_config`, which asserts `Config().environment ==
  "development"` but sees `"test"` because `conftest.py` sets `ENVIRONMENT=test` at module import
  time for the whole session; unrelated to this phase's changes and already failing before it
  (confirmed by checking the failure was present in the very first full-suite run of this pass,
  prior to any edit). This replaces the previous baseline of "2 pre-existing environment-sensitive
  failures" — one of the two (`test_postgres_url`) was the `DATABASE_URL` bug above and is now
  fixed for real; the other remains, still unrelated to dispatch/council behavior.
- **Live manual verification, against a real running server** (`USE_MOCK_AGENTS=true`, no live
  Ollama reachable from this environment — same limitation noted throughout this project's history
  for anything LLM-dependent): registered a user, created an order, dispatched it — response
  returned in **14ms** (a second run: 21ms), containing the CBF certificate and
  `"explanation_status": "NOT_REQUESTED"`, no council transcript, confirming the council is not
  touched at all on this path. Called `request-explanation` — returned `PENDING` immediately, then
  fired 3-5 concurrent unrelated `GET` requests (`/fleet/drones`) in parallel with the background
  job actually running (confirmed by interleaved log lines: the explanation worker's council
  initialization and debate-round logging appear *between* the concurrent requests' own log lines,
  not before or after them) — every concurrent request returned in 2-6ms, unaffected. Polling
  `GET /orders/{id}` afterward showed `council_explanation_status` transition to `READY` with a
  populated 26-entry `council_transcript`. Full production-scale timing (a real multi-second, up-to
  -80-call debate against live Ollama) wasn't reproduced live in this pass for the same reason nothing
  else Ollama-dependent has been in this project's history — but the mechanism verified here
  (`run_in_executor`-backed background worker, confirmed via interleaved logging to genuinely run
  concurrently with request handling) is exactly what makes debate duration irrelevant to the event
  loop regardless of how long any individual debate takes.
- **A real bug found by this live pass, not by inspection or by the test suite** (the existing
  `test_dispatch_order_api.py` assertions never check the explanation fields, so this was invisible
  to `pytest`): `orders.py`'s `_to_response()` helper — which builds every `OrderResponse` returned
  by `GET /orders/{id}` and `GET /orders/` — was never updated when `OrderResponse` gained
  `council_explanation_status`/`council_transcript`/two timestamp fields earlier in this phase.
  Since those fields aren't passed as constructor kwargs, Pydantic silently fell back to the
  schema's own defaults (`"NOT_REQUESTED"`, `None`) on every response, regardless of what was
  actually in the database — confirmed by querying `verify.db` directly with `sqlite3` and seeing
  `council_explanation_status=READY` with a 9,946-character transcript already committed, while the
  API kept reporting `NOT_REQUESTED` with zero transcript entries for the same order. Fixed by
  passing all four fields through in `_to_response()`; re-ran the full live sequence above after the
  fix and confirmed the API now reports the same state as the database at every step.
- `docs/PATENT_NOVELTY.md`'s Claim 1 was rewritten to match: the council is no longer described as
  "outranked by the gate" but as **architecturally excluded** from the decision/action path
  entirely — a strictly stronger claim, with a dated restructuring note citing this exact fix as
  its concrete embodiment. Claim 2 (the deterministic pre-screen) was re-scoped from "gates whether
  the full debate runs before dispatch" to "gates whether the full agent set runs for the
  now-async explanation," since nothing gates dispatch anymore except the CBF check itself.

## 10. Phase AC — Fleet-Level Policy Tuning

The third, and final, legitimate use of the multi-agent LLM council identified when its role was
restructured in Phase AB (async explanation, and per-order pre-screening were the other two):
reasoning about whether CBF safety-threshold *defaults* should be adjusted, on a slow cadence
(hours, not per-order), from aggregate fleet statistics — never per-decision, and never applied
without an explicit human approval.

- New `PolicyProposal` DB model (`aerofleet/data/models/models.py`): city, proposed threshold
  changes (JSON), rationale, a snapshot of the stats the council was shown, status
  (`PENDING_REVIEW`/`APPROVED`/`REJECTED`), reviewed_by/reviewed_at.
- New `aerofleet/safety/policy_store.py`: `get_active_policy(city)` returns the latest *approved*
  proposal's threshold overrides for a city (or `{}` if none), cached in-process (invalidated only
  on approve/reject — a DB read on every dispatch would reintroduce exactly the kind of per-request
  latency Phase AB's whole effort was about removing).
- `aerofleet/safety/cbf_gate.py`'s `build_cbf_gate()` gained an optional `city` parameter and now
  resolves each threshold as `dispatch_plan value > approved policy overlay > hardcoded default` —
  additive; passing no `city` (or a city with nothing approved) reproduces the exact prior behavior,
  confirmed by a dedicated test (`test_no_city_reproduces_prior_hardcoded_default`).
- New `aerofleet/agents/policy_review_worker.py`, following the exact background-worker idiom
  established by `explanation_worker.py`/`telemetry_service.py`: a slow-cadence loop (default 6h,
  `POLICY_REVIEW_INTERVAL_S`-configurable), a single-shot (not multi-round debate — this doesn't
  need ACO convergence) council consultation via the shared `build_llm_backend()` factory, run
  through `run_in_executor` to stay off the event loop exactly like the explanation worker. The
  council is instructed to propose *no* change unless recent stats (near-misses, CBF interventions,
  faults — pulled from the already-existing `FleetState.twin`, `aerofleet/fleet/digital_twin.py`)
  actually support one, and to respond with a fenced JSON block the worker parses defensively (a
  malformed/missing block is treated as "no change," never as an error that could halt the cycle).
- New `aerofleet/api/routes/policy.py`: `GET /policy/proposals` (any authenticated user, read-only),
  `POST /policy/proposals/{id}/approve` / `/reject` and `POST /policy/trigger-review` (all gated by
  the existing `get_current_operator_user` dependency from Phase X — changing a threshold every
  future dispatch in a city gets checked against carries the same authority bar as arming a drone).
- Minimal frontend: new **Fleet Policy** page (`tauri-app/src/pages/PolicyProposals.tsx`) — a
  pending-review list with inline approve/reject, a history section, and a manual "Trigger Review
  Now" button so this is actually demoable without waiting 6 hours. Added to the sidebar nav.

**A real, pre-existing gap found and fixed while building this**: `FleetDigitalTwin`
(`aerofleet/fleet/digital_twin.py`) has had a `CBF_INTERVENTION` event type since Phase B, but
nothing anywhere ever called `.twin.update({"type": "CBF_INTERVENTION"})` — the field has silently
read zero for every city, always, regardless of how many times the CBF gate actually rejected a
dispatch. Fixed by adding that call to `orders.py`'s `dispatch_order` in the `REJECTED_BY_CBF_GATE`
branch — the one place a rejection actually happens. This wasn't found by inspection; it was found
because the policy-review worker's mock-agent gating logic needed a real signal to react to, and
manually tracing why `cbf_interventions` always read 0 led straight to it.

**A real test-isolation bug found and fixed**: `policy_store._cache` is a module-level dict by
design (the whole point is avoiding a DB read on every dispatch) — but that means it's also a
process-wide singleton across an entire `pytest` run, and one test's `approve` call was leaking a
cached overlay into a later, unrelated test for the same city. Fixed by extending the already-
existing autouse `reset_singletons` fixture (added in Phase Y for exactly this class of problem)
to also call `policy_store.invalidate_policy_cache()` between every test.

- **Tests**: `tests/unit/test_policy_store.py` (overlay resolution order, cache behavior,
  invalidation), `tests/unit/test_policy_review_worker.py` (JSON-block extraction, mock
  policy-analyst response shape), `tests/integration/test_policy_api.py` (auth/operator gating on
  every endpoint, the full trigger→approve→overlay-takes-effect and trigger→reject→no-overlay
  round trips, 409 on double-approval, 404 on an unknown proposal). New `operator_headers` fixture
  added to `tests/conftest.py` (flips `is_operator` directly via the DB — same documented approach
  used to manually verify hardware-control auth in Phase X — since no admin UI grants this yet).
  **Result**: 127 tests passing (up from 96), same single pre-existing unrelated failure.
- **Live verification**: ran the real API and the real Tauri dev frontend together, registered an
  operator user, confirmed the Fleet Policy page's empty state renders correctly, and that
  `POST /policy/trigger-review` and `GET /policy/proposals` both round-trip with `200 OK` against
  the live server (confirmed via the browser's network log, not just visually). Deliberately did
  *not* try to force a real CBF rejection through the live HTTP API to populate a live proposal —
  the default demo fleet's dispatch inputs can't reach `payload`/`wind`/`noise`/etc. thresholds
  through the exposed order-creation fields alone (confirmed by dispatching 8 orders at the
  drone-capacity payload ceiling; all 8 approved) — so that specific path is covered by the
  automated integration tests instead, which manipulate the fleet twin directly and are a more
  reliable way to exercise it deterministically than trying to coax a rare edge case out of the
  demo fleet's defaults.

## 11. Phase AD — Decentralized Drone-to-Drone (D2D) Safety Mesh

Prompted by the user relaying that their guide/mentor flagged India's incoming Vehicle-to-Vehicle
(V2V) communication mandate as worth researching and connecting to this project. Investigated the
actual mandate first rather than assuming relevance: MoRTH's draft notification (Aug 2026) requires
factory-fitted On-Board Units conforming to a new standard (AIS-230), using 3GPP C-V2X in the
5.875-5.925 GHz band (DoT license-exempted June 2026 specifically for this), broadcasting
speed/position/heading for collision warnings — phased mandatory fitment for new vehicles from
October 2028. Full citations in `docs/D2D_MESH_RESEARCH_DESIGN.md`.

**The honest scoping call, made explicit up front**: the 5.9 GHz band is licensed for road
vehicles, not drones, and DGCA hasn't authorized UAV use of it. What actually transfers is the
*architectural pattern* — standardized periodic broadcast of kinematic state enabling
peer-to-peer hazard awareness without a central coordinator — applied to the regulatory basis that
genuinely does cover Indian UAVs: DGCA's Digital Sky / Remote ID mandate, which already requires
drones to broadcast identity and position. `docs/D2D_MESH_RESEARCH_DESIGN.md` states this
distinction explicitly rather than implying spectrum-level relevance that doesn't exist.

**System design review before writing any code**: `aerofleet/safety/cbf_gate.py`'s
`evaluate_trajectory()` was already discovered to be a pure function of trajectory-point dicts,
with zero dependency on `FleetState`, the database, or any network call — meaning the exact same,
unmodified safety-critical gate can evaluate decentralized peer-broadcast data with no changes to
the gate itself. And `aerofleet/planning/communication_resilience.py` — a complete DTN link-state
machine built for the *original* satellite inter-satellite-link project, never ported to drones —
turned out to map almost directly onto a drone-to-drone link-health state machine. Both were real
discoveries from reading the actual codebase, not assumptions.

**What was built**:
- `aerofleet/safety/d2d_mesh.py`: `D2DBasicSafetyMessage` (position/velocity/heading, modeled on
  AIS-230's broadcast content and DGCA's Remote ID), `D2DLinkStateMachine`
  (`NOMINAL → DEGRADED → STORE_FORWARD → ISOLATED`, UTM-appropriate timeouts — seconds, not the
  original module's "1 orbit period"), `D2DTransceiver` (peer table with TTL eviction,
  `to_trajectory_points()` feeding `cbf_gate.py`'s gate unmodified). Verified live: a smoke test
  constructing a peer message and feeding it through the real `ControlBarrierFunctionGate` produced
  a correct `PASSED` result on the first run.
- `tools/mock_mavlink_vehicle.py` gained periodic D2D-BSM broadcast over local UDP multicast
  (`239.192.42.99:14650`) plus a receive loop maintaining a live `D2DTransceiver`. **Verified live,
  not just by code review**: ran two separate OS processes (`--drone-id DRONE-A` / `DRONE-B`) and
  confirmed each discovered the other via real multicast — `D2D link=NOMINAL peers=['DRONE-B']` and
  the mirror image, printed from two independently-running processes.
- `tests/unit/test_d2d_mesh.py` (21 tests): link-state transitions, peer TTL eviction, trajectory-
  point projection, and — the actual novel claim this design rests on — **verdict-parity tests**
  proving a CBF verdict computed from D2D peer broadcasts is bit-for-bit identical to one computed
  centrally for the same geometry, because both paths call the same unmodified gate.
- `scenario_engine/d2d_degradation_study.py`: a Monte Carlo empirical study (explicitly *not*
  shoehorned into the existing YAML/tolerance-band scenario schema, which is built for a different
  job — single-mission regression checks against a known-good value, not statistical sampling).
  Simulates two drones over time with configurable D2D-BSM packet loss and broadcast interval,
  measuring: (1) verdict-equivalence rate between D2D-derived and centralized CBF verdicts, (2)
  degradation-response latency (closed-form from tested constants, not sampled), (3) undetected-
  conflict rate during a simulated central-link outage, D2D-backstop vs. a no-D2D baseline.
  **A real logic bug found and fixed while building this**: the first version evaluated every
  trial at a fixed end-of-trial instant, making "does this trial land inside the outage window" a
  constant across every trial (always false) rather than something that could actually vary —
  caught by inspecting a degenerate first-run result (`trials_landing_in_outage_window: 0`) rather
  than trusting the code. Fixed by sampling a random evaluation instant per trial. Real run at 5,000
  trials, seed 42, 20% packet loss, 1s broadcast interval (`scenario_reports/
  d2d_degradation_study_20260809_171005.json`): **99.68% verdict-equivalence rate** (16/5000
  disagreements, mean staleness at disagreement 0.675s), and during the simulated outage window, 8
  true conflicts occurred, of which **D2D caught 7 (87.5%) versus 0 for the no-D2D baseline** (the
  baseline's zero is true by construction — no central link and no D2D means no conflict-awareness
  data of any kind — the point of the metric is putting an actual number on that failure mode, not
  questioning the baseline). Honestly noted: n=8 true-conflict events is a small sample; a larger
  or adversarially-sampled trial set would be needed for a tighter confidence interval, which is
  exactly the kind of thing to do before a real journal submission, not before this snapshot.
  **Update, Phase AL**: exactly this fix — adversarial/importance-sampled trials — is now built into
  `scenario_engine/d2d_degradation_study.py` (`--stress-fraction`); see §14e below for the real
  re-run and its numbers.
- Minimal frontend: `d2d_link_state` surfaced on `GET /fleet/drones` and shown as a badge next to a
  LIVE drone's status in `tauri-app/src/pages/HardwarePanel.tsx` (only rendered when non-NOMINAL,
  keeping the UI quiet in the common case).
- `docs/PATENT_NOVELTY.md`'s new Independent Claim 10, drafted around the specific novel property
  the tests and study above actually establish — *evaluation-routine identity* between the
  centralized and decentralized safety paths, with a measured (not merely asserted) divergence rate
  under realistic packet loss — rather than a generic "drones can also talk to each other" claim,
  which decentralized-UAV-avoidance prior art already covers.

**A real integration bug found and fixed while wiring the live indicator, not by inspection**:
`aerofleet/hardware/mavlink_link.py`'s `MAVLinkVehicle.poll()` never raises just because a UDP peer
died — UDP has no disconnect signal, so `poll()` was unconditionally returning the last cached
telemetry snapshot forever, meaning the originally-wired "missed heartbeat = exception from poll()"
logic would never actually detect a dead real drone link. Caught by literally killing a running mock
vehicle process mid-verification and watching the API keep reporting `NOMINAL` indefinitely instead
of degrading. Fixed at the root: added `MAVLinkVehicle.last_message_at`, set only inside
`_handle_message()` (i.e., only when a real message is decoded), and switched
`telemetry_service.py`'s `_poll_one()` to key off staleness of that timestamp rather than
`poll()`'s return value. Re-verified live end to end: registered a real (killable) mock vehicle as
LIVE, confirmed `NOMINAL`, killed the process, and polled `GET /fleet/drones` every 2 seconds —
transitioned `NOMINAL → DEGRADED → ISOLATED` on schedule (never `STORE_FORWARD`, correctly, since
the server never records D2D peer contact by design — see `d2d_mesh.py`'s module docstring on why
the server doesn't participate in the mesh itself).

- **Regression**: `pytest tests/` — 161 passed (up from 96 at the start of this session), 2
  deselected (`hardware`-marked), same single pre-existing unrelated failure throughout
  (`test_config.py::test_load_default_config`).
- **Target venue research** (grounded via web search, not recalled from memory): **Drones** (MDPI,
  IF 4.8, Q1 in Aerospace Engineering) recommended as the realistic primary submission target —
  exact topical fit, calibrated to simulation-validated architecture work rather than requiring
  flight-test data this capstone doesn't have. IEEE Transactions on Intelligent Transportation
  Systems (IF 9.1, Q1) and Transportation Research Part C: Emerging Technologies (IF 7.3, CiteScore
  14.7, Q1) noted as stretch/follow-up targets once real two-drone hardware validation exists —
  stated as a limitation in `docs/D2D_MESH_RESEARCH_DESIGN.md` itself, not glossed over.

## 12. Phase AE — Real DGCA Airspace Data for Pune and Mumbai

Prompted by the user asking to "refine and make accurate the airspace map, the restriction
zones and all for the Pune and Mumbai region, also include the height at which the drones
should fly — make it production level." Investigated the actual prior implementation before
changing anything: `aerofleet/city/airspace.py`'s `build_default_airspace()` generated exactly
one made-up Red Zone circle (3 km, not the DGCA-stated 5 km) around each city's real airport
coordinate, plus a fabricated "dense urban core" Yellow zone around city center that isn't how
DGCA's rule actually works (the real Yellow zone is an airport-proximity lateral band, 8-12 km
from the *same* airport, not an independent urban-density concept) — and a hand-picked, unnamed
set of "safe zone" offsets with no basis in real geography.

**A far more consequential gap found while reading the dispatch code, not assumed**:
`orders.py`'s `dispatch_order` hardcoded `"in_red_zone": False` unconditionally — the entire
zone-classification system existed and was even exposed via other endpoints
(`GET /geofence/check`), but dispatch itself never once called it. A delivery to real airport
coordinates has always been silently approved, regardless of what the map showed. This was the
actual highest-value fix in this phase, not merely "more accurate circles."

**Research** (verified via web search, not recalled from memory): DGCA Drone Rules 2021's actual
zone/altitude figures — Red Zone = 5 km from an active airport perimeter, Yellow Zone = 8-12 km
lateral band (cited as reduced from 45 km in the 2021 amendment), Green Zone ceiling 120 m
(400 ft) AGL generally, reduced to 60 m (200 ft) within that Yellow band; plus real, named,
publicly-known restricted sites: Pune Airport/Lohegaon (joint civil + Indian Air Force Station),
Pune Cantonment (Southern Command HQ), Chhatrapati Shivaji Maharaj International Airport, Juhu
Aerodrome, Naval Dockyard Mumbai and INS Hamla (the Indian Navy's own published 3 km Mumbai
no-fly perimeter, explicitly naming both), and BARC Trombay (nuclear/strategic installation).
Sources: [Kodainya airspace zone map](https://www.kodainya.com/blogs/drone-airspace-zone-map),
[FlapOne no-fly zones](https://www.flapone.com/blog/india-no-fly-zones-for-drones-what-you-need-to-know),
[Deccan Herald — Navy Mumbai no-fly notice](https://www.deccanherald.com/national/west/indian-navy-to-neutralise-drones-near-its-mumbai-installation-1010828.html),
[Mumbai Live — Navy 3km zone](https://www.mumbailive.com/en/civic/navy-marks-3-km-area-in-mumbai-as-no-fly-zone-for-drones-66785),
[Transcontinental Times — INS Hamla](https://www.transcontinentaltimes.com/drones-prohibited-from-flying-within-3-kms-of-ins-hamla-in-mumbai/),
[Zbotic — DGCA weight/zone categories](https://zbotic.in/dgca-drone-weight-categories-in-india-green-yellow-red-category-explained-2026/).

**Honesty note, stated explicitly in the new module's docstring**: this is rule-grounded, not a
scrape of DGCA's live Digital Sky platform (not publicly queryable by automated means). Radii
follow DGCA's stated figures where the rule gives an explicit number; where it doesn't (military
cantonments, strategic sites), a conservative, clearly-labeled estimate is used instead of a
fabricated precise one.

**What was built**:
- New `aerofleet/city/restricted_sites.py`: `RestrictedSite`/`NamedSafeZone` dataclasses, and
  curated real-site lists — 2 for Pune, 5 for Mumbai — plus real named public open grounds
  (Saras Baug, Shivaji Park, etc.) replacing the old arbitrary lat/lon offsets.
- `aerofleet/city/airspace.py`: `DGCA_LEGAL_CEILING_M`/`DEFAULT_OPERATIONAL_CEILING_M`/
  `REDUCED_CEILING_NEAR_AIRPORT_M` constants (100 m operational ceiling kept as a deliberate
  margin below DGCA's 120 m legal limit — the same "reserve below the hard limit" pattern
  already used for battery reserve margin); new `altitude_ceiling_m_at(lat, lon)` (60 m inside a
  Yellow band, 100 m otherwise); `assign_altitude_band()` now takes optional lat/lon and demotes
  to the highest band that still fits the local ceiling, backward-compatible when omitted; new
  `build_airspace_from_sites()` building a Red disc (+ a Yellow ring for AIRPORT-category sites
  only, matching DGCA's rule text) per real site.
- `aerofleet/city/registry.py`/`fleet/state.py`: `CityConfig` now carries each city's curated
  site list; `FleetState` builds real site-based airspace for Pune/Mumbai, falling back to the
  old single-circle builder (also corrected to the real 5 km/12 km figures) for any future city
  added without a curated list.
- `orders.py`'s `dispatch_order`: now looks up the destination's real lat/lon
  (`graph.node_lat_lon`), classifies it against the real zones, and passes both the real
  `in_red_zone`/`in_yellow_zone` flags and a location-derived `max_altitude_m` into the CBF gate
  — replacing the hardcoded `False` and the fixed, non-location-aware altitude assignment.

**A second real, pre-existing bug found while wiring this, exposed by making altitude
location-aware**: `dispatch_plan`'s `"altitude_m": altitude_band.floor_m or 60.0` treated the
LOW band's legitimate `0.0` m floor as falsy and silently substituted `60.0` — meaning every
STANDARD-priority dispatch had always reported the wrong cruise altitude (by coincidence
matching LOW's ceiling, which is why it went unnoticed: the bug canceled out for the one
constant altitude ceiling that existed before this phase, but broke as soon as the ceiling
became variable). Fixed by cruising at the assigned band's midpoint instead of its floor —
correct for every band and priority, not just the one that happened to hide the bug, and
verified via a test asserting the exact resulting CBF margin (30.0 in a Yellow band, 70.0
elsewhere, not the same fallback value in both cases).

- **Tests**: `tests/unit/test_restricted_sites.py` (16 tests — real airport/military/nuclear
  coordinates classify RED, a control point classifies GREEN, altitude ceiling and band
  clamping), 3 new tests in `tests/integration/test_dispatch_order_api.py`
  (`TestDispatchRejectsRealRedZoneDestination`) proving a destination actually inside a real Red
  Zone gets `REJECTED_BY_CBF_GATE` through the live dispatch endpoint (not a mocked gate — the
  real `geofence_exclusion` constraint firing on real coordinates), a Yellow-band destination
  still approves but with the reduced-ceiling margin, and a control destination gets the full
  operational margin. **Result**: 181 tests passing (up from 161), same single pre-existing
  unrelated failure.
- **Live verification**: ran the real API and Tauri dev frontend together; confirmed
  `GET /geofence/zones` returns the correct real zone counts (3 for Pune, 7 for Mumbai) with
  correct radii; confirmed visually in the browser that the Red/Yellow circles render on the
  actual satellite map at the real airport/site locations for both cities (screenshots showed
  the Red disc correctly positioned over Lohegaon's real location, and Mumbai's denser
  7-zone overlap). Did not attempt to force a live curl-based dispatch into a real red zone in
  this sandbox specifically, since this environment's known, pre-existing OSM-fetch failure
  (documented in earlier phases — an external-drive filesystem issue with a matplotlib style
  file, unrelated to this change) falls back to a synthetic street grid that doesn't extend out
  to the real airport coordinates; the automated integration tests cover this deterministically
  instead by patching `graph.node_lat_lon` directly, which is what actually proves the wiring
  works regardless of which environment runs it.

## 13. Phase AF — Fleet Incident Forensics Council

Prompted by pointed, external critique of this project's own framing (relayed by the user,
verbatim, not softened before acting on it): the honest answer to "what does the AI decide" was
"whether to write an explanation paragraph on request, and whether to nudge a safety margin every
6 hours" — a much smaller claim than the project's title suggests, and a real gap between what's
built and what's presented. The user's direct instruction: "find out an actual usecase for our
LLM multi agent architecture that justifies and is actually usable in our case."

**Research, not assumption**: searched for real precedent before designing anything. Found two
directly relevant, recent papers: **"UAV Accident Forensics via HFACS-LLM Reasoning"**
(*Drones* 9(10):704, 2025 — the exact journal already recommended as this project's target venue)
— single-LLM, HFACS (Human Factors Analysis and Classification System — the real, standard
aviation-accident taxonomy)-guided structured prompting over UAV incident narratives, evaluated
against ASRS-report ground truth (macro-F1 0.58–0.76 across 18 categories, 7 models — an honestly
mid-range, real number, not an inflated one). Separately, the SRE/microservices literature
("Flow-of-Action," RCACopilot-style systems) has the multi-agent, domain-specialist root-cause
architecture — which turns out to already be almost exactly what this project's 11-agent roster
is, just never pointed at incident investigation. Nothing found combines both for a UAV fleet
specifically — that gap is where this phase's actual novelty claim sits, not a generic "we added
AI reasoning" claim.

**Design**: the Fleet Incident Forensics Council, auto-triggered (never manually requested) the
instant the CBF gate rejects a dispatch. `aerofleet/agents/incident_taxonomy.py` defines a
4-tier taxonomy (Immediate Trigger, Contributing Domain Factors, Systemic/Policy Factors,
Regulatory) methodologically inspired by, but explicitly not identical to, HFACS — HFACS
classifies *human* pilot error, and AeroFleet has no pilot in the loop, so the taxonomy is stated
honestly as an adaptation, not a port. 7 of the 11 existing domain agents (excluding Cost, which
has nothing to say about a safety incident) each independently assess whether their domain
contributed, citing the actual frozen CBF certificate and dispatch plan from the moment of the
incident — never re-derived state, same principle as `explanation_worker.py`'s
`precomputed_cbf_certificate`. A synthesis agent (the Dispatcher) combines their findings into a
structured report and, only when the evidence supports it, a proposed policy-threshold change
that an operator must explicitly promote into the *same* `PolicyProposal` review queue Phase AC
already built — not a second, parallel way for a threshold to change.

**What was built**: `aerofleet/data/models/models.py`'s `IncidentReport`;
`aerofleet/agents/incident_forensics_worker.py` (same background-worker idiom as
`explanation_worker.py`/`policy_review_worker.py`); `aerofleet/agents/mock_agent.py` extended with
three new deterministic mock response types (domain assessment, regulatory assessment, synthesis)
so the whole pipeline is testable/demoable without live Ollama; `aerofleet/api/routes/incidents.py`
(list, get, `promote-to-policy-proposal`); the auto-trigger wired into `orders.py`'s
`dispatch_order` on `REJECTED_BY_CBF_GATE` (the only trigger that's actually live today — fault
events and emergency landings are implemented in the taxonomy/worker but not yet wired to a live
signal, since `aerofleet/fault_tolerance/multi_fault_handler.py` and
`aerofleet/safety/emergency_landing.py` turned out to be dead code, never connected to the live
dispatch/telemetry path at all, confirmed by grep before claiming otherwise — a real, pre-existing
gap this phase didn't have scope to also close); a new **Incident Forensics** page in the desktop
app; a new Claim 11 in `docs/PATENT_NOVELTY.md`; `scenario_engine/incident_forensics_evaluation.py`,
a labeled-evaluation harness mirroring the precedent paper's macro-F1-across-categories
methodology (12 labeled synthetic incidents, 5 of 7 categories scorable against a CBF-margin-based
ground truth — `routing_navigation` and `cross_check_anomaly` require genuine narrative reasoning
a regex can't fake, honestly excluded from mock-mode scoring rather than assigned a fabricated
result).

**A real, systemic bug found and fixed while building this — the most significant one, affecting
three modules, not one**: `explanation_worker.py`, `policy_review_worker.py`, and this phase's own
`incident_forensics_worker.py` all shared the identical pattern —
`if _task is None: _task = asyncio.create_task(...)` on start, but `stop_background_..._worker()`
never reset `_task` back to `None`. The first `TestClient` context in any pytest session created a
real task tied to that context's event loop; every subsequent test's `stop`/`start` cycle saw
`_task is not None` and silently did nothing, leaving later tests' enqueued jobs pointed at a
`Task` object whose underlying `asyncio.Queue` was bound to a now-closed loop. Discovered because
this phase's own tests were the first to synchronously wait for a job to reach `READY` inside a
tight timeout across multiple test functions — `explanation_worker`/`policy_review_worker` tests
never had, so the same failure mode had been silently swallowing background-task exceptions
("Task exception was never retrieved") in every prior phase's test run this session, without ever
causing a wrong assertion. Fixed by resetting both `_task = None` and `_worker = None` on stop, so
a fresh worker (and fresh, correctly-loop-bound `Queue`) gets built on the next start. Confirmed
fixed suite-wide: zero "bound to a different event loop" errors anywhere in the full run after the
fix, versus a reproducible failure before it.

**A second real bug found via live, not automated, testing**: dispatching to a real Red Zone
(Pune Cantonment, close enough to city center to actually be reachable through this sandbox's
synthetic-grid fallback — see Phase AE's note on the external-drive OSM-fetch limitation) produced
a correct per-factor assessment (`airspace_conflict: CONTRIBUTED`, `battery_energy:
NOT_CONTRIBUTED`, matching the real certificate exactly) but an *incorrect* synthesis summary
naming `battery_energy` as the cause. Root cause: the mock synthesis's factor-attribution regex
matched `"factor": "X"` and `"contributed": "CONTRIBUTED"` independently across the whole prompt
text with a non-greedy `.*?`, so it could pair one factor's name with a *different* factor's
verdict later in the same JSON array — invisible in every unit/automated test written so far,
since none of them exercised a multi-factor case where the first-listed factor's own verdict
differed from a later one's. Fixed by scoping the regex to match within one JSON object at a time.
Re-verified live after the fix: same real rejection, correct `airspace_conflict` attribution.

- **Tests**: `tests/unit/test_incident_taxonomy.py`-equivalent coverage folded into
  `tests/unit/test_incident_forensics_worker.py` (12 tests: JSON extraction, per-domain
  correctness against a known violation, transcript completeness, synthesis attribution),
  `tests/integration/test_incidents_api.py` (9 tests: real auto-trigger through the live dispatch
  endpoint, not a unit-level call into the worker; list/get auth; promote-to-policy-proposal
  operator-gating, double-promotion rejection, and confirming the promoted proposal actually
  appears in Phase AC's existing queue), `tests/unit/test_incident_forensics_evaluation.py` (4
  tests). **Result**: 204 tests passing (up from 181 at the start of this phase), same single
  pre-existing unrelated failure throughout.
- **Live verification**: ran the real API and Tauri dev frontend together; dispatched to a real
  Red Zone destination through the live server (no mocking — an actual geofence rejection), watched
  the incident auto-create and reach `READY` within seconds, confirmed the Incident Forensics page
  correctly renders the root cause, contributing-factor list, proposed policy change, and
  regulatory citation exactly matching the API response. Did not exercise the promote-to-proposal
  button live in the browser (covered by 4 passing automated tests instead) given time; did not
  attempt a live fault-event or emergency-landing trigger, since neither has a live signal to
  trigger from yet, stated directly above rather than glossed over.

## 14a. Phase AG — Wiring the Emergency-Safety Modules Into the Live Telemetry Path

**Why**: an external review of the project flagged that `aerofleet/fault_tolerance/multi_fault_handler.py`
and `aerofleet/safety/emergency_landing.py` were fully built and unit-tested in isolation but never
called from anywhere in the live telemetry/dispatch path — confirmed true by grep before this phase
started. The system could not actually trigger an automated emergency landing during a real flight,
no matter how good the two modules were on their own. This phase closes that gap.

**What changed**: `aerofleet/hardware/telemetry_service.py`'s `DroneLinkRegistry` now owns one
`MultiFaultHandler` per LIVE drone (created in `register()`, dropped in `unregister()`). Every poll
tick (`_poll_one`) now also calls `_detect_faults()`, which derives real fault conditions from the
same `VehicleTelemetry` fields the poll loop already reads — no new sensors, no fabricated signals:

- `COMMS_LOSS` — a poll() exception, or a stale `last_message_at` (the same signal the D2D link-state
  machine, Phase AD, already used).
- `BATTERY_CRITICAL` — `battery_remaining_pct` below 15%.
- `GPS_LOSS` — `gps_fix_type` below a 3D fix while armed.
- `MOTOR` — `system_status` in `{CRITICAL, EMERGENCY, FLIGHT_TERMINATION}`. Documented explicitly as
  an approximation — MAVLink's `SYS_STATUS`/`HEARTBEAT` messages don't expose a dedicated per-motor
  fault field in this project's telemetry surface, so this is the closest honest proxy, not a claim
  of true motor diagnostics.
- `GEOFENCE_BREACH` — `fleet.airspace.is_no_fly(lat, lon)`, reusing Phase AE's real, DGCA-grounded
  restricted-site data (no synthetic/demo zones).

Each condition is registered/resolved idempotently (`_sync_fault`) so a persisting condition doesn't
spam duplicate `ActiveFault` entries across poll ticks. `_finalize_faults()` then calls
`MultiFaultHandler.generate_recovery_plan()` for real conflict resolution and priority ordering
across any simultaneous faults on that drone, hands the top-priority fault to
`EmergencyLandingPlanner.plan()` (Phase C's original module — nearest pre-mapped safe zone, or
return-to-home, or hold-position depending on fault type), and — the step that had never been
reached before — calls the *already-existing* `DroneLinkRegistry.execute_emergency_action()` to send
the real MAVLink command (`goto`, `return_to_launch`, or a mode change) to the vehicle. A new
`Drone.active_fault_types` field (surfaced through `to_dict()`) exposes the live fault list to the
API/UI, and `Drone.state` flips to `EMERGENCY_LANDING` when a divert/RTH is in flight.

**What's still honestly out of scope**: `WEATHER_ABORT` and `PAYLOAD_RELEASE_FAIL` aren't wired,
because there is no live telemetry signal in this project to detect either from — wiring them would
mean fabricating a trigger, which this project has consistently avoided. A live GPS-denied or
motor-failure trigger has also only been exercised via a mocked `MAVLinkVehicle` in unit tests
(`tests/unit/test_telemetry_service_faults.py`, 10 tests covering each fault type, idempotent
resolve-on-recovery, and a MOTOR-vs-BATTERY_CRITICAL simultaneous-fault priority test), not against
the real `tools/mock_mavlink_vehicle.py` UDP harness or real GPU-PC hardware — the mock vehicle has
no external control surface to force a battery/GPS/motor fault condition on demand, so a true
live-hardware trigger of this path remains a next step, not something claimed as done here.

**Verification**: `pytest tests/` → 214 passed, the same 1 pre-existing unrelated `test_config.py`
failure, 2 hardware-marked deselected. New tests confirm the real vehicle mock methods
(`return_to_launch`, `goto`) are actually called, not just that a status field changes.

## 14b. Phase AH — Optional Redis-Backed State for Multi-Worker Scaling

**Why**: the same review flagged that `FleetState`, `DroneLinkRegistry`, and `AsyncEventBus` are
module-level singletons, so the backend has always run `--workers 1` — spinning up a second worker
would mean two processes each opening their own duplicate MAVLink connection to the same physical
drone, with two independently-mutating, never-synchronized copies of fleet state.

**The real constraint this design has to respect**: no amount of shared state fixes the duplicate-
MAVLink-connection problem, because a MAVLink link is inherently a single-owner resource — two
processes both writing setpoints to the same serial/UDP link race each other regardless of what's in
Redis. The correct fix is therefore not "make every worker fully symmetric," it's "give exactly one
process ownership of real hardware links and FleetState mutation, and let every other worker read a
synchronized view." That's what this phase ships, additively and env-gated
(`AEROFLEET_REDIS_URL`) — unset, behavior is byte-for-byte the same single-process model as before.

See `aerofleet/event_bus/redis_bus.py` and `docs/MULTI_WORKER_ARCHITECTURE.md` for the concrete
design, what's implemented vs. documented-as-future-work, and how to verify it.

## 14b2. Phase AI — Admin Panel for Operator/Admin Grants

**Why**: the same review flagged that granting a user `is_operator` (hardware-control authority)
required raw SQL directly against the database — no admin UI existed. True: `get_current_operator_user`
in `aerofleet/api/routes/auth.py` had said exactly that in its own docstring since the endpoint was
first built.

**What changed**: added a genuine second privilege tier, `User.is_admin`, deliberately kept separate
from `is_operator` — flying a drone and managing other users' permissions are different privilege
types, and reusing one flag for both would let any operator silently mint more operators. New
`aerofleet/api/routes/admin.py`: `GET /admin/users` (list all users, no password hashes) and
`PATCH /admin/users/{id}` (set `is_operator`/`is_admin`/`is_active`), both gated by a new
`get_current_admin_user` dependency. A safety check blocks an admin from revoking their own
`is_admin` — there's no recovery path from an empty admin table short of raw SQL again, so this is
blocked outright rather than trying to detect "are you the last admin" races.

**The bootstrapping problem, solved honestly**: every admin system needs *some* way to mint the
very first admin. The safe answer is `AEROFLEET_BOOTSTRAP_ADMIN_USERNAME` — an env var read once at
startup (`auth.ensure_bootstrap_admin()`), idempotent, granting `is_admin=True` to that username if
it's already registered. This is the one deliberate, narrow exception to "no more raw SQL for
privileges" — an env var set by whoever controls the deployment, not an unauthenticated
"make me admin" endpoint, which would be a real vulnerability. Confirmed live: registered a user,
restarted the API with `AEROFLEET_BOOTSTRAP_ADMIN_USERNAME` set to that username, confirmed the log
line `Bootstrap admin granted to '<user>'`, and confirmed a second restart correctly logs nothing
(idempotent — `is_admin` was already `True`).

**Frontend**: `tauri-app/src/pages/Settings.tsx` gained a fourth "Admin" tab, visible only to users
whose `/auth/me` response has `is_admin: true`. Shows every registered user with per-row
Operator/Admin toggle buttons; the current admin's own Admin button is disabled with a
`"You can't revoke your own admin access"` tooltip, mirroring the backend's block.

**Verification**: `tests/integration/test_admin_api.py` (13 tests) — anonymous/regular-user/
operator-without-admin all correctly rejected (403), admin can list/grant/revoke, self-revocation
blocked, unknown-user 404, and three bootstrap-flow tests. Live end-to-end: started a real API
process with a bootstrap admin, logged into the actual Tauri dev UI, confirmed the Admin tab
appears only for that account, clicked "Grant" on the Operator column, watched it flip to a filled
"Operator" badge in the browser, and independently confirmed via a direct API call that
`is_operator: true` actually persisted server-side.

## 14c. Phase AJ — Removing the Legacy Deep-Space Subpackages

**Why**: the same review called out `ssa/`, `rl_trajectory/`, and `robotics/` by name as "bloated
legacy code" that risks confusing a reviewer. Rather than delete exactly those three and stop,
this phase traced the *actual* live import graph of the running FastAPI app
(`sys.modules` after `import aerofleet.api.app`, cross-checked with a repo-wide grep for every
remaining reference) to find every `aerofleet/` subpackage with zero live callers — not just the
three named ones.

**What was confirmed dead and removed**: `aerofleet/ssa/`, `rl_trajectory/`, `robotics/`,
`cislunar/`, `core/`, `digital_twin/` (the top-level orbital-mechanics package — not to be confused
with the live, unrelated `aerofleet/fleet/digital_twin.py`, which was kept), `evaluation/`
(the old `SpacePlanBench100` orbital benchmark, already flagged as inapplicable in §15 below),
`explainability/`, `knowledge/`, `planning/`, `simulation/`, `stm/`, and `ui/` — plus three
API route files that imported them but were never mounted in `app.py`'s `include_router()` calls
in the first place (`routes/stm.py`, `routes/evaluation.py`, `routes/visualization.py` — the last
was a WebXR *solar-system* planet-texture endpoint, not drone-related at all), and
`tests/integration/test_v2_pipeline.py`, whose 12 test classes covered exclusively this now-deleted
code.

**Deliberately left alone at the time**: `src/` (the original v1 Streamlit monolith at the repo
root, ~20 files) was a much larger, separate legacy codebase than what was named — flagged to the
user rather than deleted unilaterally in this phase, since it was a bigger blast radius than the
request scoped. **Update, follow-up**: the user asked for it explicitly after being flagged, and it
was confirmed still fully unreferenced (same grep-based check) and removed — see §14f below. The
`fault_tolerance/` package's other v2.0-era siblings (`predictive_diagnostics.py`,
`xai_fault_analysis.py`, `ppo_fault_recovery.py`, `distributed_recovery.py`, `edge_ai_optimizer.py`,
`sim2real.py`, `online_adaptation.py`) are equally unreferenced by the live app, but they live
inside the same package as `multi_fault_handler.py`, which Phase AG just finished wiring into the
safety-critical path — touching that directory's `__init__.py` and re-export surface right after
was judged a separate, riskier decision than the clean whole-package deletions here, so they were
left in place and flagged instead of removed.

**Verification**: live-import trace (`sys.modules` after booting the real app) cross-checked
against a static grep before any deletion — every removed package showed zero live-app references
by both methods, not just one. `pytest tests/` after deletion → 196 passed (214 minus the 18
now-removed dead-code tests), the same 1 pre-existing unrelated `test_config.py` failure, 2
hardware-marked deselected. `python -c "import aerofleet.api.app"` confirmed the app still boots
cleanly with nothing missing.

## 14d. Phase AK — Synthetic-Grid Geofence Fallback Now Reaches Real Restricted Sites

**Why**: the same review flagged that `aerofleet/city/graph.py`'s offline synthetic-grid fallback
(used whenever `osmnx`/network access is unavailable — the case throughout this whole sandboxed
session) didn't extend to real airport coordinates, so DGCA Red Zone geofencing (Phase AE) could
never be exercised through a normal simulated dispatch offline.

**What was actually found, which is worse than described**: `_build_synthetic_grid()` was hardcoded
to `base_lat, base_lon = 18.5204, 73.8567` (Pune) **regardless of which city was being built** — a
real, previously-undetected bug. An offline Mumbai `FleetState` was silently generating drone/depot
positions anchored at Pune's coordinates, not Mumbai's, because the fallback ignored `self.city_name`
entirely. On top of that, the grid was a fixed 12×12 / 200 m-spacing patch (~2.4 km span) — even for
Pune itself, nowhere near reaching Pune Airport, ~7 km from the anchor point.

**The fix**: `_build_synthetic_grid()` now looks up the requested city in `CITY_REGISTRY` by
`osm_name`, anchors at *that* city's real center, and sizes the grid to comfortably contain every
one of that city's real restricted sites and safe zones (`aerofleet/city/restricted_sites.py`) —
computed as 2.4× the haversine distance from center to the farthest real site, with a 3 km floor so
a city with few sites still gets a reasonable demo area. The grid is also now centered on the city
point (previously grew from one corner), so sites in any direction from downtown are covered, not
just one quadrant. An unrecognized `city_name` still falls back to the old Pune-anchored behavior,
but now logs a warning instead of silently mislocating a different city.

**Verification**: new `tests/unit/test_city_graph_synthetic_fallback.py` (7 tests) — per-city
anchoring for every `CITY_REGISTRY` entry, an explicit regression test that Mumbai's grid is not
placed near Pune's coordinates, every real restricted site/safe zone falling inside the grid's
bounding box for both cities, an end-to-end chain (`nearest_node()` → `node_lat_lon()` →
`is_no_fly()`) confirming a real graph node near Pune Airport is actually flagged no-fly, and an
unrecognized-city-name fallback sanity check. Also manually confirmed live: Pune's synthetic grid's
lat range now spans 18.42–18.62° (previously ~18.52–18.54°) and correctly contains both Pune Airport
and Pune Cantonment; Mumbai's grid is centered near 19.08°N/72.88°E (Mumbai's real coordinates), not
18.52°N (Pune's). `pytest tests/` → 203 passed, the same 1 pre-existing unrelated failure.

## 14e. Phase AL — D2D Sample-Size Fix and Regulatory-Framing Audit

**Sample size**: `scenario_engine/d2d_degradation_study.py` gained a `stress_fraction` parameter
(default `0.0` — reproduces Phase AD's original numbers bit-for-bit for the same seed, verified by
a dedicated regression test). When set, that fraction of trials use *importance sampling*: instead
of the original random-walk peer placement (which naturally produces a true conflict only rarely —
honestly, this is real drone behavior, not a simulation bug), an adversarial trial directly draws a
target true-separation biased toward small values and back-solves the peer's start position so a
straight-line constant-velocity track reaches exactly that separation at the trial's evaluation
instant. This is standard rare-event/importance-sampling practice, not cherry-picking: every trial —
adversarial or not — still runs through the exact same unmodified `ControlBarrierFunctionGate`, and
the two results are reported as **separate, labeled numbers** (`metric_3` natural-rate,
`metric_3b_stress` importance-sampled) rather than blended into one misleadingly-precise rate. Added
a Wilson score interval (`_wilson_ci`) for both — the right choice over a normal approximation for a
small-n or near-0/1 proportion, both of which describe the original n=8 sample.

A real re-run (`--trials 5000 --seed 42 --stress-fraction 0.5`) confirms the honest scarcity problem
is real (natural rate: **5 true conflicts** out of 2,534 non-adversarial trials, 60% catch rate, 95%
Wilson CI **[0.23, 0.88]** — genuinely too wide to defend) and that the fix works (stress rate: **454
true conflicts** out of 2,466 adversarial trials, 79.5% catch rate, 95% Wilson CI **[0.76, 0.83]** —
comfortably tight). `tests/unit/test_d2d_degradation_study.py` gained 6 new tests covering exactly
this: bit-for-bit reproduction at `stress_fraction=0.0`, the stress mode producing far more
conflicts than natural, CI presence/tightness, `None` CI on zero conflicts, determinism given a
seed, and natural+stress trial counts summing to the total. `README.md` and `docs/PATENT_NOVELTY.md`
updated to cite both figures instead of the old single 87.5%/n=8 number.

**Regulatory framing**: audited every V2V/5.9GHz/C-V2X mention across `docs/D2D_MESH_RESEARCH_DESIGN.md`,
`docs/PATENT_NOVELTY.md`, and `README.md`. Finding: **this was already correctly hedged**, dated
2026-08-09 (Phase AD) — `docs/D2D_MESH_RESEARCH_DESIGN.md` has an explicit "Honesty note on scope"
paragraph stating DGCA has not authorized UAV use of the 5.9 GHz C-V2X band, that AeroFleet does not
propose transmitting on it, and that what's actually borrowed from the V2V mandate is the
*architectural pattern* (periodic kinematic broadcast enabling peer-local hazard detection), applied
to the regulatory basis that genuinely does apply to Indian UAVs — DGCA's Digital Sky/Remote ID
mandate. `docs/PATENT_NOVELTY.md`'s Claim 10 and `README.md`'s D2D section both already carry the
same "architectural, not spectral" caveat. No changes were needed here beyond the sample-size-driven
number updates above — reported as a negative finding rather than fabricating a fix for a problem
that, on inspection, didn't exist in the form described.

## 14f. Follow-Up — Removing `src/` and Closing the Mutation-Routing Gap

Two items were flagged (not built) at the end of the AG-AL batch, then fixed on request rather than
left as permanent caveats:

**`src/` removal**: the original v1 Streamlit monolith (~20 files: `mission_agent.py`,
`council.py`, `trajectory_engine.py`, a `pages/` subdirectory, etc.) was confirmed still fully
unreferenced by the live app — the same grep-based check used for the `aerofleet/` subpackages in
Phase AJ (`aerofleet/`, `tauri-app/`, `tests/`, `scenario_engine/`, `tools/`, every shell/config
file) — then deleted. `pytest.ini`'s `testpaths = tests` and `pyproject.toml` never referenced it
either. Nothing legacy remains in the repository root.

**Mutation-routing gap**: Phase AH's own documentation flagged that dispatch/hardware mutations on
a non-owner worker relied on deployment-level routing alone, with no in-app check — a follow-up "if
this were taken further." Built now: `require_hardware_owner()`
(`aerofleet/api/routes/hardware.py`), a dependency raising `HTTPException(503, ...)` whenever
`hardware_owner_enabled()` is false, applied to `connect_vehicle`, `disconnect_vehicle`,
`arm_vehicle`, `disarm_vehicle`, `emergency_stop_all`, and called directly inside `orders.py`'s
`dispatch_order`. Deliberately includes `emergency_stop_all` — the kill switch — because the failure
mode without the guard is worse than with it: a non-owner worker's `registry._links` is always
empty, so an unguarded emergency-stop call would return a 200 while silently RTLing zero vehicles,
which is more dangerous than a loud 503 telling the operator to hit the actual owner worker.
Read-only endpoints (`GET /hardware/vehicles`) are deliberately NOT gated — that's the separate,
still-open "no cross-worker FleetState read-mirror" gap, unaffected by this fix.

**Verification**: `tests/integration/test_hardware_owner_gate.py` (11 tests) — every mutating
endpoint 503s under `AEROFLEET_HARDWARE_OWNER=0` and works normally when unset/`"1"`; the read-only
endpoint is confirmed unguarded; a non-operator request against a non-owner worker is confirmed to
never return 200 (403 or 503 only), so the new gate can't be used to bypass the existing operator
auth check. `pytest tests/` → 248 passed, the same 1 pre-existing unrelated failure, 2
hardware-marked deselected.

## 15. Suggested Next Steps

- Run the full scenario suite against live Ollama models and record real pass/fail numbers —
  do **not** reuse any numbers from the old README's SpacePlanBench-100 table, they were
  measured against the orbital system and do not apply here.
- Decide whether to delete the still-unwired `fault_tolerance/` v2.0 siblings
  (`predictive_diagnostics.py`, `xai_fault_analysis.py`, etc. — see §14c) or keep them for
  architecture history. (`src/` itself was removed — see §14f.)
- Add more cities by extending `CITY_REGISTRY` in `aerofleet/city/registry.py`.
- If pursuing the patent angle, take `docs/PATENT_NOVELTY.md` to your institution's TTO or a
  patent professional before filing anything.
- Test the Windows Ollama installer path on an actual Windows machine — it was written against
  documented Inno-Setup silent-install conventions and unit-tested for its checksum/parsing
  logic, but the installer-execution step itself could only be verified on macOS in this pass.
