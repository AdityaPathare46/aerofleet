# Using the VR Safety View on a Meta Quest 3

The AeroFleet desktop app (Windows or Mac) and the **AeroFleet VR** app pair with each other: the
headset shows exactly what you're looking at on the desktop — city, live swarm or incident,
selected drone, range — and follows as you change it. Without a desktop, the VR app still runs on
its own as before.

| path | runs on | how it connects |
|---|---|---|
| **A. Quest 3 app over Wi-Fi** (recommended) | Windows or Mac + a standalone Quest 3 | pairs with the desktop over the local network |
| **B. PC-VR over Quest Link** | Windows PC + Quest 3 on Link / Air Link | the desktop launches the viewer on the PC |
| C. Quest Browser (WebXR) | the Quest itself | the in-app web view, no install |

## A. Quest 3 over Wi-Fi — pair with the desktop

1. Install **AeroFleet VR** on the Quest (**AeroFleet ▸ Build ▸ Quest APK**, then
   `adb install -r AeroFleetVR.apk`). Put the Quest on the same Wi-Fi as the computer.
2. In the desktop app open **VR Safety View**. The first time, a **View this in VR** window opens
   (later: the **Connect headset** button in the header). Click **Connect a headset**.
3. Open **AeroFleet VR** on the Quest. It finds the computer by itself and asks to connect; a
   4-digit code appears in the headset.
4. The same code appears on the desktop — click **Allow** if they match (**Deny** otherwise).
5. The headset now shows your current view and follows every change on the desktop. The desktop's
   header shows *Quest 3 connected*, and the window shows what the headset is displaying.
6. **Disconnect headset** or **End VR session** in the same window stops it; the headset goes back
   to its connect screen.

If the headset was already running on its own when you click *Connect a headset*, it shows
"<computer> is sharing a view — Connect / Not now" instead.

**What is exposed on the network, and when.** The AeroFleet backend itself only ever listens on
this computer (127.0.0.1). While a VR session is open — and only then — it also opens a small
**VR gateway on port 8765** and announces itself on **UDP port 47800**. The gateway accepts:
the pairing handshake (which does nothing until you click Allow), and, with the paired headset's
session token, read-only requests for exactly what the VR view draws. It refuses every other
endpoint and never accepts desktop login tokens. Ending the session (or leaving the desktop app
for 90 s) closes both. The first time, the OS firewall may ask whether to allow incoming
connections for Python — allow it on private networks.

**Troubleshooting**
- *Headset says "Looking for AeroFleet on this Wi-Fi…" forever:* both devices on the same network?
  Guest/enterprise Wi-Fi often blocks device-to-device traffic (client isolation) — use a home
  network or a phone hotspot. Check the firewall prompt above.
- *"Your AeroFleet sign-in has expired":* sign in again on the desktop, then Connect a headset.

## B. PC-VR over Quest Link (Windows)

1. **On the PC:** install the *Meta Quest Link* app. Open it, then go to Settings ▸ General ▸
   OpenXR Runtime and set Meta Quest Link as active.
2. **On the Quest 3:** connect a USB-C cable (Link) or enable Air Link from Quick Settings ▸ Quest
   Link. You should now be in the Link home environment.
3. **Get the viewer:** build it from the Unity project (**AeroFleet ▸ Build ▸ Windows PC-VR** →
   `Builds/Windows/AeroFleetVR.exe`) and either
   - place the `AeroFleetVR` build folder next to `AeroFleet.exe`,
   - set `AEROFLEET_VR_VIEWER` to the exe path, or
   - put it in the checkout at `unity/AeroFleetVR/Builds/Windows/`.
4. **In AeroFleet:** open *VR Safety View* ▸ **Connect headset**. Under *This PC over Quest Link*
   the window says whether the OpenXR runtime, Link/SteamVR and the viewer are ready; click
   **Launch on this PC**.
5. The viewer opens in the headset already paired (no code needed — you're at this PC) and
   follows the desktop exactly like the Wi-Fi path. The table is in front of you, with the fleet
   board on the left and the claim-check / legend board on the right.
   - Point a controller at a drone or a button and pull the trigger.
   - **RECENTER** re-centres the table on where you are standing.
   - **TABLE ▲/▼** changes its height.
   - **CITY ►** switches between Pune and Mumbai.
   - **3D CITY** toggles buildings.

## C. Quest Browser (WebXR)

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

## Running the VR app without a desktop (development, tests)

With an `aerofleet_config.json` in the app's persistent data folder (in the Unity editor:
**AeroFleet ▸ Dev ▸ Write Local Test Config**), the VR app starts on its own against that backend,
exactly as before pairing existed, and only offers *Connect* if a desktop starts sharing. On a
headset it can reach the backend through `adb reverse tcp:8000 tcp:8000` with the default
`http://localhost:8000`.

## What you are looking at

- **Drones:** green = within limits, amber = inside a watch band, red = CBF violation.
  - The drop-line to the ground is the altitude, read against the ruler (LOW 0–60, MID 60–80,
    HIGH 80–100 m).
  - Separation beams are labelled with horizontal ↔ and vertical ↕ distance.
- **Trajectories:** every simulated drone flies a known plan: climb over the depot at 3 m/s,
  cruise the road route at 12 m/s, descend at 2 m/s, land. A selected drone (or one needing
  attention) shows its path ahead as a bright line, with ticks at +30/+60/+90/+120 s and "lands
  in m:ss" at touchdown. The part already flown is faint.
- **Predicted conflicts:** the backend projects every pair's planned trajectories 2 minutes ahead,
  using the gate's horizontal separation rule. A red ring pair marks where two drones *will* be
  closer than 15 m, labelled "PREDICTED CONFLICT in 42 s". The board's PREDICTED tile counts
  them. Amber means a near miss inside the watch band. Drones on live MAVLink telemetry have no
  plan and aren't forecast.
- **Replay:** a rejection from after this change is drawn along the exact route the gate checked,
  waypoint by waypoint at each waypoint's altitude. It turns red where a waypoint is in a no-fly
  zone, over the ceiling, or past the battery reserve, and the first failure is labelled. Older
  incidents show a straight line and say so.
- **Red column:** DGCA no-fly zone, all altitudes. **Yellow column:** airport permission zone,
  60 m ceiling.
- **Buildings:** OpenStreetMap footprints. Light buildings have a tagged height. Dark ones are
  drawn at an assumed 9 m, and the board states how many of each.
- **Vertical scale:** exaggerated (×15 at 4 km) for drones and buildings alike. The factor is shown
  on the ruler.
- **ASSUMED:** marks a constraint with no live per-drone sensor yet, where the dispatch-time
  default is used.
