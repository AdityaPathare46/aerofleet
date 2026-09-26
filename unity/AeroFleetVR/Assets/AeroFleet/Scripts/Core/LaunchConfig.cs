using System;
using System.IO;
using UnityEngine;

namespace AeroFleet.VR
{
    public enum ViewMode { Live, Replay }

    /// <summary>
    /// Where the headset app gets its connection settings, lowest to highest priority:
    ///   1. defaults (a backend on this machine)
    ///   2. aerofleet_config.json in persistentDataPath — for a standalone Quest build, where nothing
    ///      launches the app with arguments
    ///   3. command-line arguments — how the AeroFleet Windows app launches this as a PC-VR viewer
    ///   4. AEROFLEET_TOKEN environment variable for the login token. Deliberately never a
    ///      command-line argument: process arguments are visible to every other process on the PC.
    /// </summary>
    [Serializable]
    public class LaunchConfig
    {
        public string apiUrl = "http://localhost:8000";
        public string token = "";
        public string city = "pune";
        public ViewMode mode = ViewMode.Live;
        public string incidentId = "";
        // Development only, config file only: lets the editor / a lab Quest sign in to a *local*
        // backend with a test account. Never read from the command line or shipped in a build.
        public string username = "";
        public string password = "";
        public string source = "defaults";

        public const string ConfigFileName = "aerofleet_config.json";

        public static LaunchConfig Resolve()
        {
            var cfg = new LaunchConfig();

            string file = Path.Combine(Application.persistentDataPath, ConfigFileName);
            if (File.Exists(file))
            {
                try
                {
                    JsonUtility.FromJsonOverwrite(File.ReadAllText(file), cfg);
                    cfg.source = "config file";
                }
                catch (Exception e)
                {
                    Debug.LogWarning($"[AeroFleet] Ignoring unreadable {file}: {e.Message}");
                }
            }

            string[] args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length; i++)
            {
                string a = args[i];
                string Next() => i + 1 < args.Length ? args[++i] : "";
                switch (a)
                {
                    case "--aerofleet-api": cfg.apiUrl = Next(); cfg.source = "launched by AeroFleet"; break;
                    case "--aerofleet-city": cfg.city = Next(); break;
                    case "--aerofleet-mode": cfg.mode = Next() == "replay" ? ViewMode.Replay : ViewMode.Live; break;
                    case "--aerofleet-incident": cfg.incidentId = Next(); break;
                }
            }

            string envToken = Environment.GetEnvironmentVariable("AEROFLEET_TOKEN");
            if (!string.IsNullOrEmpty(envToken)) cfg.token = envToken;

            cfg.apiUrl = cfg.apiUrl.TrimEnd('/');
            return cfg;
        }
    }
}
