# Using the VR Safety View on a Meta Quest 3

There are three ways to put the AeroFleet tabletop in a headset. All three show the same data from
the same backend: the live swarm or an incident replay, real Pune/Mumbai streets and OSM
buildings, DGCA zones, and ceilings.

| path | runs on | best for |
|---|---|---|
| **A. PC-VR with the native viewer** (recommended) | Windows PC + Quest 3 over Quest Link / Air Link | the desktop app: one click from the VR view |
| B. Quest Browser (WebXR) | the Quest itself, page served from your PC | no install on the PC, quick demos |
| C. Standalone Quest app (APK) | the Quest itself | a headset without a PC nearby |

## A. PC-VR — "Launch in headset" from the desktop app

1. **On the PC:** install the *Meta Quest Link* app. Open it, then go to Settings ▸ General ▸
   OpenXR Runtime and set Meta Quest Link as active.
2. **On the Quest 3:** connect a USB-C cable (Link) or enable Air Link from Quick Settings ▸ Quest
   Link. You should now be in the Link home environment.
3. **Get the viewer:** build it from the Unity project (**AeroFleet ▸ Build ▸ Windows PC-VR** →
   `Builds/Windows/AeroFleetVR.exe`) and either
   - place the `AeroFleetVR` build folder next to `AeroFleet.exe`,
   - set `AEROFLEET_VR_VIEWER` to the exe path, or
   - use **Locate viewer…** in the Headset panel once. The path is remembered.
4. **In AeroFleet:** open *VR Safety View* and sign in. Choose the city and either *Live swarm* or
   an incident, then click **Headset ▾**. The panel checks four things:
   - Windows
   - the OpenXR runtime
   - Link or SteamVR is running
   - the viewer was found

   When all four are green, click **Launch … in headset**.
5. The viewer opens in the headset. It uses the same API URL, city, mode and incident you had
   selected, and the session is passed securely through an environment variable. The table is in
   front of you, with the fleet board on the left and the claim-check / legend board on the right.
   - Point a controller at a drone or a button and pull the trigger.
   - **RECENTER** re-centres the table on where you are standing.
   - **TABLE ▲/▼** changes its height.
   - **CITY ►** switches between Pune and Mumbai.
   - **3D CITY** toggles buildings.

If the viewer can't reach the backend, its board says so. It needs the backend reachable from the
PC (the default `http://127.0.0.1:8000` works when both run on the same machine).

## B. Quest Browser (WebXR)

The in-app view is a WebXR page, and the Quest Browser supports it natively.

1. Run the desktop app's dev server or the web build on your PC, plus the backend.
2. Connect the Quest by USB with developer mode on, and forward the ports:

   ```bash
   adb reverse tcp:1420 tcp:1420
   ```

   ```bash
   adb reverse tcp:8000 tcp:8000
   ```

3. In the Quest Browser, open `http://localhost:1420` and go to *VR Safety View*. Sign in, then
   choose **Enter VR**, or **Enter MR** to see the table in your real room with passthrough.

Using `localhost` through `adb reverse` matters: WebXR needs a secure context, and localhost counts
as one, whereas a LAN IP over plain http does not.

## C. Standalone APK

**AeroFleet ▸ Build ▸ Quest APK**, then install with `adb install -r AeroFleetVR.apk`. Point it at
the backend in one of two ways:

- `adb reverse tcp:8000 tcp:8000`, which keeps the default `http://localhost:8000`, or
- put an `aerofleet_config.json` in the app's persistent data folder with the PC's LAN address
  (`apiUrl`).

## What you are looking at

- **Drones:** green = within limits, amber = inside a watch band, red = CBF violation.
  - The drop-line to the ground is the altitude, read against the ruler (LOW 0–60, MID 60–80,
    HIGH 80–100 m).
  - Separation beams are labelled with horizontal ↔ and vertical ↕ distance.
- **Red column:** DGCA no-fly zone, all altitudes. **Yellow column:** airport permission zone,
  60 m ceiling.
- **Buildings:** OpenStreetMap footprints. Light buildings have a tagged height. Dark ones are
  drawn at an assumed 9 m, and the board states how many of each.
- **Vertical scale:** exaggerated (×15 at 4 km) for drones and buildings alike. The factor is shown
  on the ruler.
- **ASSUMED:** marks a constraint with no live per-drone sensor yet, where the dispatch-time
  default is used.
