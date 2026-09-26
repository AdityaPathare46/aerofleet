using System.Collections;
using System.Collections.Generic;
using AeroFleet.VR.Data;
using AeroFleet.VR.Geo;
using AeroFleet.VR.Interaction;
using AeroFleet.VR.View;
using UnityEngine;
using UnityEngine.XR;

namespace AeroFleet.VR
{
    /// <summary>
    /// The headset viewer's entry point. Connects to the AeroFleet backend (the same API the desktop
    /// app uses), builds the tabletop for the chosen city, and either follows the live swarm
    /// (/safety/live-margins every 1.5 s) or replays a frozen CBF rejection with its claim check.
    /// Works in a headset (Quest 3 over Link, or standalone) and, without one, as a desktop window
    /// with mouse orbit and picking — the same scene either way.
    ///
    /// Three ways to start:
    ///   launched by the desktop (Quest Link) — follows the desktop's view right away;
    ///   a config file (development/tests) — runs standalone exactly as before;
    ///   a fresh headset — listens for an AeroFleet desktop on the Wi-Fi and pairs with it.
    /// While paired it follows the scenario the desktop pushes (city, live/replay, incident,
    /// selected drone, range) and reports what it shows. See Pairing.cs, aerofleet/vr/.
    /// </summary>
    public class AeroFleetApp : MonoBehaviour
    {
        const float PollSeconds = 1.5f;
        const float LinkLostAfterS = 8f;
        const float TableHalf = 0.7f, ColumnHeight = 0.32f;
        static readonly Vector3 TableHome = new Vector3(0f, 0.82f, 0.85f);

        // ── state the boards read ──────────────────────────────────────────
        public ViewMode Mode { get; private set; } = ViewMode.Live;
        public int RangeKm { get; private set; } = 4;
        public bool DetailAll { get; private set; }
        public string Selected { get; private set; }
        public LiveMarginsDto Live { get; private set; }
        public List<IncidentSummaryDto> Incidents { get; private set; } = new List<IncidentSummaryDto>();
        public int IncidentIndex { get; private set; }
        public VrSceneDto Scene { get; private set; }
        public Diorama Diorama { get; private set; }
        public string StatusLine => (Following ? $"following {FollowingHost} · " : "") + statusText;
        string statusText = "connecting…";
        public bool Following { get; private set; }
        public string FollowingHost { get; private set; }
        public bool StatusIsError { get; private set; }
        public bool InHeadset { get; private set; }
        public bool ShowBuildings { get; private set; } = true;
        public BuildingsDto Buildings { get; private set; }
        public int BuildingsDrawn => buildingsView != null ? buildingsView.Drawn : 0;
        public int BuildingsDrawnMeasured => buildingsView != null ? buildingsView.DrawnMeasured : 0;
        public string CitySlug => city?.Slug ?? cfg?.city;
        public string CityName => city?.Name?.Split(',')[0] ?? cfg?.city;

        LaunchConfig cfg;
        ApiClient api;
        CityDto city;
        Vector2d center;
        RoadsDto roads;
        List<ZoneDto> zones = new List<ZoneDto>();
        List<DepotDto> depots = new List<DepotDto>();
        List<CityDto> cities = new List<CityDto>();
        Vector2 focus;
        float lastLiveAt = -1f, nextBoardRefresh;
        string builtDioramaKey;
        Coroutine poller;

        enum Stage { Starting, Home, Standalone, Following }
        Stage stage = Stage.Starting;
        BeaconListener beacons;
        ConnectBoard connectBoard;
        string boardState;          // null | home | prompt | code | error
        string homeMessage, autoPairedSession, dismissedSession, followingSession;
        bool pairing, stopPolling;
        int scenarioVersion = -1;
        float nextBeaconCheck;

        Transform workspace, tableRoot, tableSpin;
        TableView table;
        BuildingsView buildingsView;
        SwarmView swarm;
        ReplayView replay;
        FleetBoard fleetBoard;
        ContextBoard contextBoard;

        // ── lifecycle ──────────────────────────────────────────────────────

        IEnumerator Start()
        {
            cfg = LaunchConfig.Resolve();
            api = new ApiClient(cfg.apiUrl, cfg.token);
            Mode = cfg.mode;
            Debug.Log($"[AeroFleet] API {cfg.apiUrl} · city {cfg.city} · mode {cfg.mode} · config from {cfg.source}");

            BuildWorkspace();

            // OpenXR starts before the first scene loads; give the runtime a moment to report a device.
            float until = Time.realtimeSinceStartup + 1.5f;
            while (!XRSettings.isDeviceActive && Time.realtimeSinceStartup < until) yield return null;
            InHeadset = XRSettings.isDeviceActive;
            if (!InHeadset) EnableDesktopMode();
            PlaceBoards();

            beacons = new BeaconListener();
            beacons.Start();

            if (cfg.source == "launched by AeroFleet" && api.HasToken)
            {
                yield return Follow(cfg.apiUrl, cfg.token, "this PC");
                if (Following) yield break;
            }
            if (cfg.source == "config file" || api.HasToken)
            {
                yield return RunStandaloneCo();
                yield break;
            }
            stage = Stage.Home;
            SetStatus("waiting for the AeroFleet desktop app…");
        }

        public void RunStandalone()
        {
            boardState = null;
            connectBoard.Hide();
            StartCoroutine(RunStandaloneCo());
        }

        IEnumerator RunStandaloneCo()
        {
            stage = Stage.Standalone;
            api = new ApiClient(cfg.apiUrl, cfg.token);
            if (!api.HasToken && !string.IsNullOrEmpty(cfg.username))
            {
                SetStatus("signing in…");
                string err = null;
                yield return api.Login(cfg.username, cfg.password, null, e => err = e);
                if (err != null) { SetStatus($"Sign-in failed: {err}", true); yield break; }
            }

            yield return LoadCity();
            if (city == null) yield break;

            if (Mode == ViewMode.Replay) yield return EnterReplay(cfg.incidentId);
            else EnterLive();
        }

        void Update()
        {
            if (Time.unscaledTime >= nextBeaconCheck && beacons != null && !pairing)
            {
                nextBeaconCheck = Time.unscaledTime + 0.5f;
                UpdateConnectBoard();
            }
            if (Time.unscaledTime < nextBoardRefresh) return;
            nextBoardRefresh = Time.unscaledTime + 0.25f;
            if (Mode == ViewMode.Live && lastLiveAt > 0 && !StatusIsError)
            {
                float age = Time.unscaledTime - lastLiveAt;
                statusText = $"{CityName} · live · {Live?.DroneCount ?? 0} airborne · updated {age:0.0} s ago" +
                             (age > 6 ? "  —  backend not responding" : "");
            }
            fleetBoard?.Refresh(this);
            contextBoard?.Refresh(this);
        }

        void OnDestroy() => beacons?.Dispose();

        string DeviceName
        {
            get
            {
                string n = SystemInfo.deviceModel != null && SystemInfo.deviceModel.Contains("Quest") ? SystemInfo.deviceModel : SystemInfo.deviceName;
                if (!InHeadset) n += " (no headset)";
                return n.Length > 40 ? n.Substring(0, 40) : n;
            }
        }

        // ── pairing with the desktop ───────────────────────────────────────

        void UpdateConnectBoard()
        {
            if (boardState == "code" || boardState == "error") return;
            var desktops = beacons.Current();
            if (stage == Stage.Home)
            {
                boardState = "home";
                connectBoard.ShowHome(desktops, homeMessage, cfg.source == "config file", beacons.Error);
                // A fresh headset that hears exactly one desktop asks it straight away — the operator
                // still has to allow it there.
                if (desktops.Count == 1 && desktops[0].Session != autoPairedSession)
                {
                    autoPairedSession = desktops[0].Session;
                    PairWith(desktops[0]);
                }
            }
            else if (stage == Stage.Standalone)
            {
                var offer = desktops.Find(d => d.Session != dismissedSession);
                if (offer != null) { boardState = "prompt"; connectBoard.ShowPrompt(offer); }
                else if (boardState == "prompt") { boardState = null; connectBoard.Hide(); }
            }
        }

        public void PairWith(DesktopBeacon desk)
        {
            if (pairing) return;
            pairing = true;
            string url = desk.GatewayUrl;
            StartCoroutine(PairingClient.Pair(url, DeviceName,
                code => { boardState = "code"; connectBoard.ShowCode(desk.Host, code); },
                token => { pairing = false; followingSession = desk.Session; StartCoroutine(Follow(url, token, desk.Host)); },
                err =>
                {
                    pairing = false;
                    // The desktop closed its session between announcing it and our request: nothing to
                    // report, keep looking.
                    if (err.StartsWith("409")) { boardState = null; return; }
                    boardState = "error";
                    connectBoard.ShowError(err, RetryConnect);
                }));
        }

        public void DismissPrompt(string session)
        {
            dismissedSession = session;
            boardState = null;
            connectBoard.Hide();
        }

        void RetryConnect()
        {
            boardState = null;
            autoPairedSession = null;
            connectBoard.Hide();
        }

        IEnumerator Follow(string url, string token, string host)
        {
            var link = new ApiClient(url, token);
            ScenarioEnvelope env = null;
            string err = null;
            yield return link.Get<ScenarioEnvelope>("/api/v1/vr/device/scenario", true, e => env = e, (_, e) => err = e);
            if (env == null)
            {
                boardState = "error";
                connectBoard.ShowError($"Paired, but the desktop didn't answer: {err}", RetryConnect);
                yield break;
            }

            api = link;
            cfg.apiUrl = url;
            Following = true;
            FollowingHost = host;
            stage = Stage.Following;
            stopPolling = false;
            boardState = null;
            connectBoard.Hide();
            Debug.Log($"[AeroFleet] Paired with {host} — following its view");

            if (city == null || city.Slug != env.Scenario.City)
            {
                cfg.city = env.Scenario.City;
                yield return SwitchCityQuiet();
                if (city == null) yield break;
            }
            yield return ApplyScenario(env);
            StartCoroutine(FollowLoop());
        }

        IEnumerator FollowLoop()
        {
            float nextBeat = 0f, lastHeard = Time.realtimeSinceStartup;
            while (Following)
            {
                ScenarioEnvelope env = null;
                long code = 0;
                yield return api.Get<ScenarioEnvelope>("/api/v1/vr/device/scenario", true, e => env = e, (c, _) => code = c);
                if (code == 401) { EndFollowing("The desktop ended the VR session."); yield break; }
                if (env != null) lastHeard = Time.realtimeSinceStartup;
                // Ending the session also stops the desktop's gateway, so usually there's no 401 to read —
                // just silence. Treat a few seconds of it as the session being over.
                else if (Time.realtimeSinceStartup - lastHeard > LinkLostAfterS)
                {
                    EndFollowing($"Lost the connection to {FollowingHost} — the VR session ended or the Wi-Fi dropped.");
                    yield break;
                }
                if (env != null && env.Version != scenarioVersion) yield return ApplyScenario(env);
                if (Time.realtimeSinceStartup >= nextBeat)
                {
                    nextBeat = Time.realtimeSinceStartup + 3f;
                    string status = Newtonsoft.Json.JsonConvert.SerializeObject(new
                    {
                        mode = Mode == ViewMode.Replay ? "replay" : "live", city = CitySlug,
                        incident_id = Scene?.IncidentId, selected = Selected, in_headset = InHeadset,
                    });
                    yield return PairingClient.Send("POST", api.BaseUrl + "/api/v1/vr/device/heartbeat", status, api.Token, null, null);
                }
                yield return new WaitForSeconds(1f);
            }
        }

        void EndFollowing(string message)
        {
            Following = false;
            stopPolling = true;
            stage = Stage.Home;
            homeMessage = message;
            // Its beacon may still be cached for a few seconds — don't pair straight back into the
            // session that just ended.
            autoPairedSession = dismissedSession = followingSession;
            boardState = null;
            SetStatus(message, true);
        }

        /// <summary>Make the table show what the desktop shows. Only runs when the desktop's scenario changes,
        /// so the operator can still look around locally in between.</summary>
        IEnumerator ApplyScenario(ScenarioEnvelope env)
        {
            scenarioVersion = env.Version;
            var s = env.Scenario;
            if (city == null || s.City != city.Slug)
            {
                cfg.city = s.City;
                yield return SwitchCityQuiet();
                if (city == null || city.Slug != s.City)
                {
                    SetStatus($"Couldn't load {s.City} from the desktop — {statusText}", true);
                    yield break;
                }
            }
            DetailAll = s.DetailAll;
            if (ShowBuildings != s.ShowBuildings)
            {
                ShowBuildings = s.ShowBuildings;
                if (Diorama != null) buildingsView.Build(Diorama, center, ShowBuildings ? Buildings : null);
            }
            if (s.Mode == "replay")
            {
                int i = Incidents.FindIndex(x => x.IncidentId == s.IncidentId);
                if (Mode != ViewMode.Replay || i < 0) yield return EnterReplay(s.IncidentId);
                else if (i != IncidentIndex || Scene == null) { IncidentIndex = i; yield return LoadScene(); }
            }
            else
            {
                if (Mode != ViewMode.Live || poller == null) { Scene = null; EnterLive(); }
                Selected = s.SelectedDrone;
            }
            SetRange(s.RangeKm);
        }

        void SetStatus(string text, bool error = false)
        {
            statusText = text;
            StatusIsError = error;
            if (error) Debug.LogWarning("[AeroFleet] " + text);
        }

        // ── scene construction ─────────────────────────────────────────────

        void BuildWorkspace()
        {
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
            RenderSettings.ambientLight = Palette.Hex("3A4C66");

            workspace = new GameObject("Workspace").transform;
            workspace.SetParent(transform, false);
            var floor = Draw.Prim(PrimitiveType.Quad, workspace, new Vector3(0, 0, 0.5f), new Vector3(24, 24, 1), Draw.Lit(Palette.Floor), "Floor");
            floor.transform.localRotation = Quaternion.Euler(90, 0, 0);
            Draw.Line(workspace, Draw.Circle(1.6f, 96, 0.002f), 0.004f, Palette.WithAlpha(Palette.TableEdge, 0.6f), loop: true, name: "WorkArea");

            tableRoot = new GameObject("Table").transform;
            tableRoot.SetParent(workspace, false);
            tableRoot.localPosition = TableHome;
            tableSpin = new GameObject("Map").transform; // rotates with ROTATE; everything geographic lives under it
            tableSpin.SetParent(tableRoot, false);
            table = new GameObject("Airspace").AddComponent<TableView>();
            table.transform.SetParent(tableSpin, false);
            buildingsView = new GameObject("Buildings").AddComponent<BuildingsView>();
            buildingsView.transform.SetParent(tableSpin, false);
            swarm = new GameObject("Swarm").AddComponent<SwarmView>();
            swarm.transform.SetParent(tableSpin, false);
            swarm.OnSelect = Select;
            replay = new GameObject("Replay").AddComponent<ReplayView>();
            replay.transform.SetParent(tableSpin, false);

            fleetBoard = FleetBoard.Create(workspace, this);
            contextBoard = ContextBoard.Create(workspace);
            connectBoard = ConnectBoard.Create(workspace, this);
        }

        void PlaceBoards()
        {
            if (InHeadset)
            {
                // Standing operator at the origin: boards flank the table at reading distance.
                var eye = new Vector3(0, 1.55f, 0);
                fleetBoard.GetComponent<Panel>().Face(workspace.TransformPoint(new Vector3(-1.08f, 1.32f, 0.72f)), workspace.TransformPoint(eye));
                contextBoard.GetComponent<Panel>().Face(workspace.TransformPoint(new Vector3(1.08f, 1.32f, 0.72f)), workspace.TransformPoint(eye));
                connectBoard.GetComponent<Panel>().Face(workspace.TransformPoint(new Vector3(0f, 1.42f, 0.62f)), workspace.TransformPoint(eye));
            }
            else
            {
                // Desktop: both boards stand behind the table so one camera frames everything.
                var eye = new Vector3(0, 1.4f, -1.2f);
                fleetBoard.GetComponent<Panel>().Face(workspace.TransformPoint(new Vector3(-0.46f, 1.66f, 1.8f)), workspace.TransformPoint(eye));
                contextBoard.GetComponent<Panel>().Face(workspace.TransformPoint(new Vector3(0.46f, 1.66f, 1.8f)), workspace.TransformPoint(eye));
                connectBoard.GetComponent<Panel>().Face(workspace.TransformPoint(new Vector3(0f, 1.5f, 0.35f)), workspace.TransformPoint(eye));
            }
        }

        void EnableDesktopMode()
        {
            var cam = Camera.main;
            if (cam == null)
            {
                cam = new GameObject("Desktop Camera") { tag = "MainCamera" }.AddComponent<Camera>();
            }
            // Head tracking would pin the camera at the floor origin with no headset; hand it to the mouse.
            foreach (var b in cam.GetComponents<Behaviour>())
                if (b.GetType().Name.Contains("TrackedPoseDriver")) b.enabled = false;
            cam.nearClipPlane = 0.01f;
            cam.fieldOfView = 50f;
            var orbit = cam.gameObject.AddComponent<DesktopOrbit>();
            orbit.target = TableHome + new Vector3(0, 0.36f, 0.3f);
            orbit.distance = 2.75f;
            orbit.pitch = 24f;
            cam.gameObject.AddComponent<DesktopPointer>();
            Debug.Log("[AeroFleet] No XR device — desktop mode (right-drag orbit, scroll zoom, click to select).");
        }

        // ── data ───────────────────────────────────────────────────────────

        IEnumerator LoadCity()
        {
            SetStatus($"loading {cfg.city} from {cfg.apiUrl}…");
            string err = null;
            cities = null;
            yield return api.Get<List<CityDto>>("/api/v1/cities/", false, c => cities = c, (_, e) => err = e);
            if (cities == null)
            {
                SetStatus($"Can't reach the AeroFleet backend at {cfg.apiUrl} ({err}). Start it, then relaunch.", true);
                yield break;
            }
            city = cities.Find(c => c.Slug == cfg.city) ?? (cities.Count > 0 ? cities[0] : null);
            if (city == null) { SetStatus("Backend has no cities configured.", true); yield break; }
            center = new Vector2d(city.Center[0], city.Center[1]);

            yield return api.Get<List<ZoneDto>>($"/api/v1/geofence/zones?city={city.Slug}", false, z => zones = z);
            yield return api.Get<List<DepotDto>>($"/api/v1/fleet/depots?city={city.Slug}", false, d => depots = d);
            roads = null;
            yield return api.Get<RoadsDto>($"/api/v1/cities/{city.Slug}/roads", false, r => roads = r,
                (_, e) => Debug.LogWarning("[AeroFleet] No street map: " + e));
            SetStatus($"loading {CityName} buildings…");
            Buildings = null;
            yield return api.Get<BuildingsDto>($"/api/v1/cities/{city.Slug}/buildings", false, b => Buildings = b,
                (_, e) => Debug.LogWarning("[AeroFleet] No 3D buildings: " + e));
        }

        void EnterLive()
        {
            Mode = ViewMode.Live;
            replay.Hide();
            swarm.gameObject.SetActive(true);
            RebuildDiorama();
            if (poller == null) poller = StartCoroutine(PollLive());
        }

        IEnumerator PollLive()
        {
            while (Mode == ViewMode.Live && !stopPolling)
            {
                long code = 0;
                string err = null;
                yield return api.Get<LiveMarginsDto>($"/api/v1/safety/live-margins?city={city.Slug}", true, OnLive, (c, e) => { code = c; err = e; });
                if (err != null)
                    SetStatus(code == 401
                        ? "Not signed in (or the token expired). Launch from the AeroFleet app, or set a test account in aerofleet_config.json."
                        : $"Live feed error: {err}", true);
                yield return new WaitForSeconds(PollSeconds);
            }
            poller = null;
        }

        void OnLive(LiveMarginsDto data)
        {
            if (Mode != ViewMode.Live || switching || data.City != city?.Slug) return;
            Live = data;
            lastLiveAt = Time.unscaledTime;
            StatusIsError = false;
            if (Selected != null && !data.Drones.ContainsKey(Selected)) Selected = null;
            RebuildDiorama(); // no-op unless the ceiling constant changed
            swarm.Apply(data, Diorama, center, Selected, DetailAll);
        }

        IEnumerator EnterReplay(string preferredIncident)
        {
            Mode = ViewMode.Replay;
            swarm.Clear();
            swarm.gameObject.SetActive(false);
            SetStatus($"{CityName} · replay · loading incidents…");
            List<IncidentSummaryDto> list = null;
            long code = 0;
            yield return api.Get<List<IncidentSummaryDto>>($"/api/v1/incidents/?city={city.Slug}&trigger_type=CBF_REJECTION", true,
                l => list = l, (c, e) => { code = c; SetStatus(c == 401 ? "Not signed in — replay needs an operator token." : $"Incidents: {e}", true); });
            if (Mode != ViewMode.Replay || list == null) yield break;
            Incidents = list;
            IncidentIndex = Mathf.Max(0, list.FindIndex(i => i.IncidentId == preferredIncident));
            yield return LoadScene();
        }

        IEnumerator LoadScene()
        {
            Scene = null;
            replay.Hide();
            if (Incidents.Count == 0)
            {
                SetStatus($"{CityName} · replay · no CBF rejections recorded yet");
                RebuildDiorama();
                yield break;
            }
            string id = Incidents[IncidentIndex].IncidentId;
            SetStatus($"{CityName} · replay · loading {Vocab.ShortId(id)}…");
            VrSceneDto s = null;
            yield return api.Get<VrSceneDto>($"/api/v1/incidents/{id}/vr-scene", true, x => s = x, (_, e) => SetStatus($"Incident: {e}", true));
            if (Mode != ViewMode.Replay || s == null) yield break;
            Scene = s;
            SetStatus($"{CityName} · replay · incident {IncidentIndex + 1} of {Incidents.Count} · {ReplayView.GroupViolations(Scene.Violations).Count} violated constraint(s)");
            RebuildDiorama();
            replay.Show(Scene, Diorama, center);
        }

        void RebuildDiorama()
        {
            float legal = (float)(Live?.Constants.LegalCeilingM ?? 120);
            float e = focus.x, n = focus.y, extent = RangeKm * 1000f;
            if (Mode == ViewMode.Replay && Scene != null)
            {
                var f = ReplayView.Frame(Scene, center);
                if (f != null) (e, n, extent) = f.Value;
            }
            string key = $"{Mode}|{e:0}|{n:0}|{extent:0}|{legal:0}";
            if (key == builtDioramaKey) return;
            builtDioramaKey = key;
            Diorama = new Diorama(e, n, extent, TableHalf, ColumnHeight, legal);
            table.Build(Diorama, center, roads, zones, depots, Live?.Constants ?? new LiveConstants(), showPlinth: true);
            buildingsView.Build(Diorama, center, ShowBuildings ? Buildings : null);
            if (Mode == ViewMode.Live && Live != null) swarm.Apply(Live, Diorama, center, Selected, DetailAll);
        }

        // ── controls (board buttons) ───────────────────────────────────────

        public void SetMode(ViewMode m)
        {
            if (city == null || m == Mode) return;
            if (m == ViewMode.Live) { Scene = null; EnterLive(); }
            else StartCoroutine(EnterReplay(Scene?.IncidentId));
        }

        public void SetRange(int km)
        {
            RangeKm = km;
            focus = km < 4 && Selected != null && Live != null && Live.Drones.TryGetValue(Selected, out var d)
                ? GeoMath.ToLocal(d.Lat, d.Lon, center.x, center.y) : Vector2.zero;
            RebuildDiorama();
        }

        public void Select(string id)
        {
            Selected = Selected == id ? null : id;
            if (Selected != null && RangeKm < 4 && Live != null && Live.Drones.TryGetValue(Selected, out var d))
            {
                focus = GeoMath.ToLocal(d.Lat, d.Lon, center.x, center.y);
                RebuildDiorama();
            }
            if (Live != null) swarm.Apply(Live, Diorama, center, Selected, DetailAll);
        }

        public void ToggleDetailAll()
        {
            DetailAll = !DetailAll;
            if (Live != null) swarm.Apply(Live, Diorama, center, Selected, DetailAll);
        }

        public void StepIncident(int delta)
        {
            if (Mode != ViewMode.Replay || Incidents.Count < 2) return;
            IncidentIndex = (IncidentIndex + delta + Incidents.Count) % Incidents.Count;
            StartCoroutine(LoadScene());
        }

        public void ToggleBuildings()
        {
            ShowBuildings = !ShowBuildings;
            buildingsView.Build(Diorama, center, ShowBuildings ? Buildings : null);
        }

        /// <summary>Next city in the backend's registry (Pune ⇄ Mumbai): reload map, zones, depots, buildings, feed.</summary>
        public void NextCity()
        {
            if (city == null || cities == null || cities.Count < 2 || switching) return;
            int i = cities.FindIndex(c => c.Slug == city.Slug);
            cfg.city = cities[(i + 1) % cities.Count].Slug;
            StartCoroutine(SwitchCity());
        }

        bool switching;

        IEnumerator SwitchCity()
        {
            var mode = Mode;
            Mode = ViewMode.Live; // stops the poller loop on its next tick
            yield return SwitchCityQuiet();
            if (city == null) yield break;
            if (mode == ViewMode.Replay) yield return EnterReplay(null); else EnterLive();
        }

        /// <summary>Load cfg.city's map, zones, depots and buildings, clearing the old city's state.</summary>
        IEnumerator SwitchCityQuiet()
        {
            switching = true;
            Live = null; Scene = null; Selected = null; focus = Vector2.zero;
            Incidents = new List<IncidentSummaryDto>();
            swarm.Clear();
            replay.Hide();
            builtDioramaKey = null;
            yield return LoadCity();
            switching = false;
        }

        public void RotateTable() => tableSpin.localRotation *= Quaternion.Euler(0, 90, 0);

        public void NudgeTable(float dy)
        {
            var p = tableRoot.localPosition;
            p.y = Mathf.Clamp(p.y + dy, 0.5f, 1.3f);
            tableRoot.localPosition = p;
        }

        /// <summary>Put the table and boards in front of wherever the operator is now standing.</summary>
        public void Recenter()
        {
            var cam = Camera.main;
            tableRoot.localPosition = TableHome;
            tableSpin.localRotation = Quaternion.identity;
            if (!InHeadset || cam == null) return;
            Vector3 fwd = cam.transform.forward;
            fwd.y = 0;
            if (fwd.sqrMagnitude < 1e-4f) return;
            Vector3 head = cam.transform.position;
            workspace.SetPositionAndRotation(new Vector3(head.x, 0, head.z), Quaternion.LookRotation(fwd.normalized, Vector3.up));
            PlaceBoards();
        }
    }
}
