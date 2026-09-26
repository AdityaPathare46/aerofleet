# AeroFleet VR — native headset viewer (Unity)

A walk-around tabletop of the live AeroFleet airspace for Meta Quest 3: the real street map and
OpenStreetMap buildings of Pune or Mumbai, DGCA no-fly and permission zones as exact volumes, the
100 m ops and 120 m legal ceilings, and every airborne drone with its altitude, battery,
separation and route — fed live from the same backend the desktop app uses. A replay mode puts a
frozen CBF rejection on the table and checks the AI council's causal claims against the violated
constraints.

This folder mirrors `Assets/AeroFleet/` of the Unity project (the project itself lives outside the
repo at `/Volumes/UnityWork/UnityProjects/Aerofleet`, Unity 6000.6.0f1, URP, XR Interaction
Toolkit 3.6.1, OpenXR 1.18, Newtonsoft JSON). `.meta` files are included so GUIDs, and therefore
the scene's script references, survive a copy back. Sync after editing in Unity:

```bash
rsync -a --exclude '._*' --exclude .DS_Store /Volumes/UnityWork/UnityProjects/Aerofleet/Assets/AeroFleet /Volumes/UnityWork/UnityProjects/Aerofleet/Assets/AeroFleet.meta unity/AeroFleetVR/Assets/
```

## Status

| | |
|---|---|
| Compiles in Unity 6000.6.0f1 (0 errors, 0 warnings) | verified |
| Runs in the editor without a headset (desktop mode) against a live local backend: Pune and Mumbai, live swarm, boards, 3D buildings, drone selection, 1/2/4 km range | verified, screenshots taken |
| Inside a Quest 3 (Link or standalone) | **not yet run** — needs a Windows PC with Quest Link, or an Android build |
| Windows PC-VR build | needs *Windows Build Support (Mono)* for this editor (not installed on the Mac), or build on the PC |

## Layout

```
Assets/AeroFleet/
  Scripts/Core/AeroFleetApp.cs     entry point: config → sign-in → city data → live poll / replay
  Scripts/Core/LaunchConfig.cs     config file < CLI args < AEROFLEET_TOKEN env var
  Scripts/Data/                    ApiClient (UnityWebRequest + bearer) and DTOs mirroring the API
  Scripts/Geo/Diorama.cs           real metres → table metres (east=+x, north=+z, vertical ×VExag)
  Scripts/View/TableView.cs        surface, streets, zone prisms, ceilings, altitude ruler, scale, depots
  Scripts/View/BuildingsView.cs    OSM footprints extruded; tagged heights light, assumed heights dark
  Scripts/View/SwarmView.cs        drones, separation beams / awareness links, predicted conflicts, tag stacking
  Scripts/View/DroneView.cs        glyph, drop-line, ground ring, 4D trajectory (+30 s ticks, touchdown), data tag
  Scripts/View/DataTag.cs          labelled rows with bars and limit ticks (no unlabelled bars)
  Scripts/View/ReplayView.cs       frozen rejection: the exact route the gate checked, failing waypoints in red
  Scripts/View/FleetBoard.cs       KPIs, worst-case margin per CBF constraint (LIVE/ASSUMED), controls
  Scripts/View/ContextBoard.cs     replay: claim check · live: how to read the table + selected drone
  Scripts/Interaction/             Clickable (XRI ray or mouse), desktop orbit/picking
  Editor/AeroFleetSetup.cs         AeroFleet ▸ Setup / Dev / Build menus
```

Same data contract, palette, thresholds and wording as the in-app web view
(`tauri-app/src/components/vr/`), so the headset and the desktop never describe a number differently.

## Set up (once)

In the Unity project: **AeroFleet ▸ Setup ▸ Run All**. It creates the theme and materials
(`Resources/`), builds `Scenes/AeroFleetVR.unity` (XRI *XR Origin (XR Rig)*, interaction manager,
ground collider, app), makes it the only build scene, assigns the OpenXR loader for Standalone with
the Oculus Touch / Quest Touch Plus / Touch Pro profiles, and allows plain-HTTP to the backend.

## Run

**Editor, no headset:** start the backend and seed it (from the repo root), then press Play.

```bash
.venv/bin/python -m uvicorn aerofleet.api.app:app --host 127.0.0.1 --port 8000
```

```bash
.venv/bin/python tools/seed_demo_swarm.py --orders 14 --rejections 6
```

For a local test sign-in, use **AeroFleet ▸ Dev ▸ Write Local Test Config**. It writes
`aerofleet_config.json` to `Application.persistentDataPath` with the local demo account. That
account is for a local backend only. Right-drag orbits, scroll zooms, and click selects.

**PC-VR (Quest 3 over Link / Air Link):** build **AeroFleet ▸ Build ▸ Windows PC-VR** on a machine
with Windows Build Support, then launch with:

```
AeroFleetVR.exe --aerofleet-api http://127.0.0.1:8000 --aerofleet-city pune --aerofleet-mode live
```

and the operator token in the `AEROFLEET_TOKEN` environment variable (never on the command line —
process arguments are visible to every other process on the PC). `--aerofleet-mode replay
--aerofleet-incident <id>` opens a specific rejection.

**Quest standalone:** **AeroFleet ▸ Build ▸ Quest APK**; put an `aerofleet_config.json` with the
backend's LAN address in the app's persistent data folder, or `adb reverse tcp:8000 tcp:8000` and
keep `http://localhost:8000`.

## Honesty notes

- Building heights come from OSM tags; in Pune and Mumbai only ~2–3% of buildings have one. The
  rest are drawn at the stated assumed height (9 m) in a darker colour, and the board says how many.
- Vertical is exaggerated (×15 at the 4 km range) for both drones and buildings; the ruler and
  board state the factor.
- Constraints without a live per-drone sensor are labelled ASSUMED (dispatch-time default).
- The previous version of this app displayed fabricated data (the same telemetry for every case,
  random failures, arbitrary depot positions, invented "replay" curves). That code is kept, compiled
  out, in the Unity project's `Assets/_Legacy/` with a README listing each problem.
