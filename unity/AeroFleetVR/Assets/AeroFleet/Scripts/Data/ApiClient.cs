using System;
using System.Collections;
using Newtonsoft.Json;
using UnityEngine;
using UnityEngine.Networking;

namespace AeroFleet.VR.Data
{
    /// <summary>Thin UnityWebRequest wrapper for the AeroFleet backend (bearer-token auth, JSON).</summary>
    public class ApiClient
    {
        public string BaseUrl { get; }
        public string Token { get; private set; }
        public bool HasToken => !string.IsNullOrEmpty(Token);

        public ApiClient(string baseUrl, string token)
        {
            BaseUrl = baseUrl.TrimEnd('/');
            Token = token;
        }

        /// <param name="fail">(HTTP status or -1, message). 401 means the token is missing/expired.</param>
        public IEnumerator Get<T>(string path, bool auth, Action<T> ok, Action<long, string> fail = null)
        {
            using (var req = UnityWebRequest.Get(BaseUrl + path))
            {
                // Always send the token when we have one: through the VR gateway even the "public" reads
                // (cities, roads, buildings) need the headset's session token. `auth` only documents that
                // the endpoint requires it.
                if (HasToken) req.SetRequestHeader("Authorization", "Bearer " + Token);
                req.timeout = 15;
                yield return req.SendWebRequest();
                if (req.result != UnityWebRequest.Result.Success)
                {
                    fail?.Invoke(req.responseCode, $"{path}: {req.error}");
                    yield break;
                }
                T parsed;
                try { parsed = JsonConvert.DeserializeObject<T>(req.downloadHandler.text); }
                catch (Exception e) { fail?.Invoke(-1, $"{path}: bad JSON ({e.Message})"); yield break; }
                ok(parsed);
            }
        }

        /// <param name="fail">(HTTP status or -1, the API's "detail" message when it gave one).</param>
        public IEnumerator Post<T>(string path, object body, Action<T> ok, Action<long, string> fail = null)
        {
            using (var req = new UnityWebRequest(BaseUrl + path, "POST"))
            {
                req.downloadHandler = new DownloadHandlerBuffer();
                if (body != null)
                {
                    req.uploadHandler = new UploadHandlerRaw(System.Text.Encoding.UTF8.GetBytes(JsonConvert.SerializeObject(body)));
                    req.SetRequestHeader("Content-Type", "application/json");
                }
                if (HasToken) req.SetRequestHeader("Authorization", "Bearer " + Token);
                req.timeout = 20;
                yield return req.SendWebRequest();
                if (req.result != UnityWebRequest.Result.Success)
                {
                    string detail = req.error;
                    try { detail = JsonConvert.DeserializeObject<DetailDto>(req.downloadHandler.text)?.Detail ?? detail; } catch { }
                    fail?.Invoke(req.responseCode, detail);
                    yield break;
                }
                T parsed;
                try { parsed = JsonConvert.DeserializeObject<T>(req.downloadHandler.text); }
                catch (Exception e) { fail?.Invoke(-1, $"{path}: bad JSON ({e.Message})"); yield break; }
                ok(parsed);
            }
        }

        class DetailDto { [JsonProperty("detail")] public string Detail; }

        public IEnumerator Login(string username, string password, Action ok, Action<string> fail)
        {
            var form = new WWWForm();
            form.AddField("username", username);
            form.AddField("password", password);
            using (var req = UnityWebRequest.Post(BaseUrl + "/api/v1/auth/login", form))
            {
                req.timeout = 15;
                yield return req.SendWebRequest();
                if (req.result != UnityWebRequest.Result.Success)
                {
                    fail?.Invoke(req.responseCode == 401 ? "Incorrect username or password" : req.error);
                    yield break;
                }
                Token = JsonConvert.DeserializeObject<TokenDto>(req.downloadHandler.text)?.AccessToken;
                if (HasToken) ok?.Invoke(); else fail?.Invoke("Login returned no token");
            }
        }
    }
}
