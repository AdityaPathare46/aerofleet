using System;
using System.Collections;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using Newtonsoft.Json;
using UnityEngine;
using UnityEngine.Networking;

namespace AeroFleet.VR
{
    /// <summary>What an AeroFleet desktop announces on the LAN while a VR session is open (aerofleet/vr/beacon.py).</summary>
    public class DesktopBeacon
    {
        [JsonProperty("aerofleet_vr")] public int Version;
        [JsonProperty("host")] public string Host;
        [JsonProperty("gateway_port")] public int GatewayPort;
        [JsonProperty("addrs")] public List<string> Addrs = new List<string>();
        [JsonProperty("session")] public string Session;
        [JsonIgnore] public string SourceIp;
        [JsonIgnore] public float LastSeen;

        /// <summary>Prefer the address the datagram actually came from — it's the one that routes back.</summary>
        public string GatewayUrl
        {
            get
            {
                string ip = !string.IsNullOrEmpty(SourceIp) && SourceIp != "127.0.0.1" ? SourceIp
                    : Addrs.Count > 0 ? Addrs[0] : "127.0.0.1";
                return $"http://{ip}:{GatewayPort}";
            }
        }
    }

    /// <summary>The scenario the desktop pushes: what the operator is looking at right now.</summary>
    public class DesktopScenario
    {
        [JsonProperty("city")] public string City = "pune";
        [JsonProperty("mode")] public string Mode = "live";
        [JsonProperty("incident_id")] public string IncidentId;
        [JsonProperty("selected_drone")] public string SelectedDrone;
        [JsonProperty("range_km")] public int RangeKm = 4;
        [JsonProperty("detail_all")] public bool DetailAll;
        [JsonProperty("show_buildings")] public bool ShowBuildings = true;
    }

    public class ScenarioEnvelope
    {
        [JsonProperty("scenario_version")] public int Version;
        [JsonProperty("scenario")] public DesktopScenario Scenario;
        [JsonProperty("owner")] public string Owner;
    }

    /// <summary>
    /// Listens on the beacon port for AeroFleet desktops (background thread; results are read on the
    /// main thread). Datagrams are small JSON; anything else is ignored.
    /// </summary>
    public class BeaconListener : IDisposable
    {
        public const int Port = 47800;
        readonly ConcurrentQueue<DesktopBeacon> inbox = new ConcurrentQueue<DesktopBeacon>();
        readonly Dictionary<string, DesktopBeacon> known = new Dictionary<string, DesktopBeacon>();
        UdpClient udp;
        Thread thread;
        volatile bool running;
        public string Error { get; private set; }

        public void Start()
        {
            try
            {
                udp = new UdpClient();
                udp.Client.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, true);
                udp.EnableBroadcast = true;
                udp.Client.Bind(new IPEndPoint(IPAddress.Any, Port));
                running = true;
                thread = new Thread(Loop) { IsBackground = true, Name = "AeroFleet beacon listener" };
                thread.Start();
            }
            catch (Exception e)
            {
                Error = e.Message;
                Debug.LogWarning($"[AeroFleet] Can't listen for desktops on UDP {Port}: {e.Message}");
            }
        }

        void Loop()
        {
            var from = new IPEndPoint(IPAddress.Any, 0);
            while (running)
            {
                try
                {
                    byte[] data = udp.Receive(ref from);
                    var b = JsonConvert.DeserializeObject<DesktopBeacon>(Encoding.UTF8.GetString(data));
                    if (b != null && b.Version == 1 && b.GatewayPort > 0 && !string.IsNullOrEmpty(b.Session))
                    {
                        b.SourceIp = from.Address.ToString();
                        inbox.Enqueue(b);
                    }
                }
                catch (SocketException) { if (!running) return; }
                catch (ObjectDisposedException) { return; }
                catch (Exception) { /* not ours */ }
            }
        }

        /// <summary>Desktops heard in the last few seconds, keyed by host. Call from the main thread.</summary>
        public List<DesktopBeacon> Current(float maxAgeS = 4f)
        {
            while (inbox.TryDequeue(out var b))
            {
                b.LastSeen = Time.realtimeSinceStartup;
                if (known.TryGetValue(b.Host, out var prev) && prev.SourceIp != "127.0.0.1" && b.SourceIp == "127.0.0.1")
                    b.SourceIp = prev.SourceIp; // keep the LAN route once we have it
                known[b.Host] = b;
            }
            var list = new List<DesktopBeacon>();
            foreach (var b in known.Values)
                if (Time.realtimeSinceStartup - b.LastSeen <= maxAgeS) list.Add(b);
            return list;
        }

        public void Dispose()
        {
            running = false;
            try { udp?.Close(); } catch { }
        }
    }

    /// <summary>The headset side of the pairing handshake (aerofleet/api/routes/vr.py).</summary>
    public static class PairingClient
    {
        public class PairRequest { [JsonProperty("request_id")] public string RequestId; [JsonProperty("confirm_code")] public string ConfirmCode; }
        public class PairPoll { [JsonProperty("status")] public string Status; [JsonProperty("token")] public string Token; }

        /// <summary>Ask to pair; reports the confirm code as soon as it's known, then waits for the desktop.</summary>
        public static IEnumerator Pair(string gatewayUrl, string deviceName, Action<string> onCode,
                                       Action<string> onApproved, Action<string> onFailed)
        {
            PairRequest req = null;
            string body = JsonConvert.SerializeObject(new { device_name = deviceName });
            yield return Send("POST", gatewayUrl + "/api/v1/vr/pair-requests", body, null,
                t => req = JsonConvert.DeserializeObject<PairRequest>(t), onFailed);
            if (req == null) yield break;
            onCode(req.ConfirmCode);

            float until = Time.realtimeSinceStartup + 125f;
            while (Time.realtimeSinceStartup < until)
            {
                PairPoll poll = null;
                yield return Send("GET", gatewayUrl + "/api/v1/vr/pair-requests/" + req.RequestId, null, null,
                    t => poll = JsonConvert.DeserializeObject<PairPoll>(t), onFailed);
                if (poll == null) yield break;
                if (poll.Status == "APPROVED" && !string.IsNullOrEmpty(poll.Token)) { onApproved(poll.Token); yield break; }
                if (poll.Status == "DENIED") { onFailed("The desktop denied this headset."); yield break; }
                if (poll.Status == "EXPIRED") { onFailed("The request expired — try again."); yield break; }
                yield return new WaitForSeconds(1f);
            }
            onFailed("No answer from the desktop.");
        }

        public static IEnumerator Send(string method, string url, string json, string token, Action<string> ok, Action<string> fail,
                                       Action<long> status = null)
        {
            using (var req = new UnityWebRequest(url, method))
            {
                req.downloadHandler = new DownloadHandlerBuffer();
                if (json != null)
                {
                    req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json));
                    req.SetRequestHeader("Content-Type", "application/json");
                }
                if (!string.IsNullOrEmpty(token)) req.SetRequestHeader("Authorization", "Bearer " + token);
                req.timeout = 10;
                yield return req.SendWebRequest();
                status?.Invoke(req.responseCode);
                if (req.result == UnityWebRequest.Result.Success) ok?.Invoke(req.downloadHandler.text);
                else fail?.Invoke(req.responseCode == 0 ? $"Can't reach {url.Split('/')[2]} ({req.error})" : $"{req.responseCode}: {req.downloadHandler.text}");
            }
        }
    }
}
