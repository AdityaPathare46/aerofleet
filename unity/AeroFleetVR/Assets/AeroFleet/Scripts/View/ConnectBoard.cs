using System.Collections.Generic;
using TMPro;
using UnityEngine;

namespace AeroFleet.VR.View
{
    /// <summary>
    /// The "connect to your desktop" board. Home (fresh headset): lists AeroFleet desktops heard on
    /// the Wi-Fi and pairs with one. Prompt (already running standalone): a desktop started sharing —
    /// connect or not now. Code: the 4-digit confirm code the operator must see on the desktop too.
    /// </summary>
    public class ConnectBoard : MonoBehaviour
    {
        public const float Width = 0.9f, Height = 0.56f;
        const float M = 0.04f;

        Panel panel;
        Transform content;
        AeroFleetApp app;
        string shownKey;

        public bool Visible => gameObject.activeSelf;

        public static ConnectBoard Create(Transform parent, AeroFleetApp app)
        {
            var p = Panel.Create(parent, "ConnectBoard", Width, Height);
            var b = p.gameObject.AddComponent<ConnectBoard>();
            b.panel = p;
            b.app = app;
            p.gameObject.SetActive(false);
            return b;
        }

        public void Hide()
        {
            shownKey = null;
            gameObject.SetActive(false);
        }

        void Begin(string key)
        {
            gameObject.SetActive(true);
            shownKey = key;
            if (content != null) Destroy(content.gameObject);
            content = new GameObject("Content").transform;
            content.SetParent(transform, false);
        }

        TextMeshPro T(string text, float x, float y, float h, Color c, TextAlignmentOptions a = TextAlignmentOptions.Left,
                      float wrap = 0f, FontStyles s = FontStyles.Normal)
        {
            var t = panel.Text(text, x, y, h, c, a, wrap, s);
            t.transform.SetParent(content, true);
            return t;
        }

        Button3D B(string label, float x, float y, float w, System.Action click)
        {
            var b = panel.Button(label, x, y, w, 0.062f, click);
            b.transform.SetParent(content, true);
            return b;
        }

        void Title(string sub)
        {
            var t = T("AEROFLEET VR", M, 0.05f, 0.03f, Palette.Accent, s: FontStyles.Bold);
            t.characterSpacing = 6;
            T(sub, M, 0.1f, 0.019f, Palette.TextDim, wrap: Width - 2 * M);
        }

        /// <summary>Fresh headset: which desktops are announcing themselves on this Wi-Fi.</summary>
        public void ShowHome(List<DesktopBeacon> desktops, string message, bool canRunStandalone, string listenError)
        {
            var hosts = new List<string>();
            foreach (var d in desktops) hosts.Add(d.Host);
            string key = "home|" + string.Join(",", hosts) + "|" + message;
            if (key == shownKey) return;
            Begin(key);
            Title(message ?? "Connect to the AeroFleet app on your computer.");
            if (desktops.Count == 0)
            {
                T("Looking for AeroFleet on this Wi-Fi…", M, 0.2f, 0.022f, Palette.Text, s: FontStyles.Bold);
                T("On the computer: open AeroFleet ▸ VR Safety View ▸ Connect a headset. The headset and the computer must be on the same Wi-Fi.",
                  M, 0.24f, 0.016f, Palette.TextDim, wrap: Width - 2 * M);
                if (listenError != null)
                    T($"Can't listen on the network ({listenError}).", M, 0.34f, 0.015f, Palette.Bad, wrap: Width - 2 * M);
            }
            else
            {
                T("Found:", M, 0.2f, 0.018f, Palette.TextDim);
                float y = 0.225f;
                foreach (var d in desktops)
                {
                    var desk = d;
                    T(desk.Host, M, y + 0.031f, 0.02f, Palette.Text, s: FontStyles.Bold);
                    B("CONNECT", Width - M - 0.2f, y, 0.2f, () => app.PairWith(desk));
                    y += 0.08f;
                    if (y > 0.42f) break;
                }
            }
            if (canRunStandalone) B("USE WITHOUT DESKTOP", M, Height - M - 0.062f, 0.34f, app.RunStandalone);
        }

        /// <summary>Running standalone and a desktop starts sharing.</summary>
        public void ShowPrompt(DesktopBeacon desk)
        {
            string key = "prompt|" + desk.Host + "|" + desk.Session;
            if (key == shownKey) return;
            Begin(key);
            Title($"{desk.Host} is sharing a view.");
            T("Connect to follow what the operator is looking at on the desktop — city, live swarm or incident, selected drone.",
              M, 0.17f, 0.017f, Palette.TextDim, wrap: Width - 2 * M);
            B("CONNECT", M, 0.3f, 0.22f, () => app.PairWith(desk));
            B("NOT NOW", M + 0.24f, 0.3f, 0.22f, () => app.DismissPrompt(desk.Session));
        }

        public void ShowCode(string host, string code)
        {
            Begin("code|" + host + "|" + code);
            Title($"Asking {host} to connect…");
            T("Confirm this code on the computer:", M, 0.19f, 0.02f, Palette.Text);
            var c = T(code, Width / 2, 0.32f, 0.11f, Palette.Accent, TextAlignmentOptions.Center, s: FontStyles.Bold);
            c.characterSpacing = 30;
            T("Click Allow in AeroFleet if the codes match.", M, 0.44f, 0.016f, Palette.TextDim);
        }

        public void ShowError(string message, System.Action retry)
        {
            Begin("error|" + message);
            Title("Couldn't connect.");
            T(message, M, 0.19f, 0.018f, Palette.Bad, wrap: Width - 2 * M);
            B("TRY AGAIN", M, 0.36f, 0.22f, retry);
        }
    }
}
