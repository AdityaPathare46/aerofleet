using System;
using System.IO;
using System.Linq;
using AeroFleet.VR;
using AeroFleet.VR.View;
using TMPro;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEditor.XR.Management;
using UnityEditor.XR.Management.Metadata;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.XR.Interaction.Toolkit;
using UnityEngine.XR.OpenXR;

namespace AeroFleet.VR.EditorTools
{
    /// <summary>
    /// One-click project setup and builds for the AeroFleet headset viewer.
    ///   AeroFleet ▸ Setup ▸ Run All       — theme/materials, the VR scene, PC-VR OpenXR config
    ///   AeroFleet ▸ Build ▸ Windows PC-VR  — the .exe the AeroFleet desktop app launches (Quest 3 via Link / Air Link)
    ///   AeroFleet ▸ Build ▸ Quest APK       — standalone on the headset, talks to the backend over Wi-Fi / adb reverse
    /// Every step is idempotent; re-running it repairs rather than duplicates.
    /// </summary>
    public static class AeroFleetSetup
    {
        const string Root = "Assets/AeroFleet";
        const string ResourcesDir = Root + "/Resources";
        const string ScenePath = Root + "/Scenes/AeroFleetVR.unity";
        const string XrOriginPrefab = "Assets/Samples/XR Interaction Toolkit/3.6.1/Starter Assets/Prefabs/XR Origin (XR Rig).prefab";
        const string DefaultFont = "Assets/TextMesh Pro/Resources/Fonts & Materials/LiberationSans SDF.asset";
        public const string WindowsExe = "Builds/Windows/AeroFleetVR.exe";
        public const string QuestApk = "Builds/Quest/AeroFleetVR.apk";

        [MenuItem("AeroFleet/Setup/Run All", priority = 0)]
        public static void RunAll()
        {
            CreateTheme();
            BuildScene();
            ConfigurePcVr();
            ConfigureQuestNetworking();
            Debug.Log("[AeroFleet] Setup complete. Press Play to run the viewer against the local backend.");
        }

        // ── 1. theme ───────────────────────────────────────────────────────

        [MenuItem("AeroFleet/Setup/1. Create Theme && Materials", priority = 11)]
        public static void CreateTheme()
        {
            Directory.CreateDirectory(ResourcesDir);
            var lit = MaterialAsset("AF_Lit", "Universal Render Pipeline/Lit", m => { m.SetFloat("_Smoothness", 0.35f); });
            var unlit = MaterialAsset("AF_Unlit", "Sprites/Default", null);
            var solid = MaterialAsset("AF_Solid", "Universal Render Pipeline/Unlit", null);

            string themePath = ResourcesDir + "/AeroFleetTheme.asset";
            var theme = AssetDatabase.LoadAssetAtPath<AeroFleetTheme>(themePath);
            if (theme == null)
            {
                theme = ScriptableObject.CreateInstance<AeroFleetTheme>();
                AssetDatabase.CreateAsset(theme, themePath);
            }
            theme.lit = lit;
            theme.unlit = unlit;
            theme.solid = solid;
            theme.font = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(DefaultFont) ?? TMP_Settings.defaultFontAsset;
            EditorUtility.SetDirty(theme);
            AssetDatabase.SaveAssets();
            Debug.Log($"[AeroFleet] Theme ready: {themePath} (font {(theme.font ? theme.font.name : "MISSING")})");
        }

        static Material MaterialAsset(string name, string shaderName, Action<Material> configure)
        {
            string path = $"{ResourcesDir}/{name}.mat";
            var shader = Shader.Find(shaderName) ?? throw new Exception($"Shader not found: {shaderName}");
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (m == null)
            {
                m = new Material(shader);
                AssetDatabase.CreateAsset(m, path);
            }
            m.shader = shader;
            configure?.Invoke(m);
            EditorUtility.SetDirty(m);
            return m;
        }

        // ── 2. scene ───────────────────────────────────────────────────────

        [MenuItem("AeroFleet/Setup/2. Build VR Scene", priority = 12)]
        public static void BuildScene()
        {
            Directory.CreateDirectory(Path.GetDirectoryName(ScenePath));
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            var sun = new GameObject("Key Light").AddComponent<Light>();
            sun.type = LightType.Directional;
            sun.intensity = 1.05f;
            sun.color = new Color(0.86f, 0.92f, 1f);
            sun.shadows = LightShadows.Soft;
            sun.transform.rotation = Quaternion.Euler(55, -35, 0);

            RenderSettings.skybox = null;
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = Palette.Hex("3A4C66");

            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(XrOriginPrefab)
                         ?? throw new Exception("XR Interaction Toolkit Starter Assets are missing: " + XrOriginPrefab);
            var rig = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            rig.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            foreach (var cam in rig.GetComponentsInChildren<Camera>(true))
            {
                cam.clearFlags = CameraClearFlags.SolidColor;
                cam.backgroundColor = Palette.Void;
                cam.nearClipPlane = 0.01f;
                cam.farClipPlane = 60f;
            }

            new GameObject("XR Interaction Manager").AddComponent<XRInteractionManager>();

            // The rig's gravity provider needs something to stand on.
            var ground = new GameObject("Ground");
            ground.transform.position = new Vector3(0, -0.05f, 0);
            ground.AddComponent<BoxCollider>().size = new Vector3(40, 0.1f, 40);

            new GameObject("AeroFleet").AddComponent<AeroFleetApp>();

            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            Debug.Log($"[AeroFleet] Scene saved: {ScenePath} (only scene in the build)");
        }

        // ── 3. PC VR (OpenXR on Windows) ───────────────────────────────────

        [MenuItem("AeroFleet/Setup/3. Configure PC VR (OpenXR)", priority = 13)]
        public static void ConfigurePcVr()
        {
            var group = BuildTargetGroup.Standalone;
            var general = XRGeneralSettingsPerBuildTarget.XRGeneralSettingsForBuildTarget(group);
            if (general == null)
            {
                EditorBuildSettings.TryGetConfigObject(UnityEngine.XR.Management.XRGeneralSettings.k_SettingsKey,
                    out XRGeneralSettingsPerBuildTarget perTarget);
                if (perTarget == null) throw new Exception("XR Plug-in Management is not initialised (Project Settings ▸ XR Plug-in Management).");
                perTarget.CreateDefaultSettingsForBuildTarget(group);
                general = XRGeneralSettingsPerBuildTarget.XRGeneralSettingsForBuildTarget(group);
            }
            general.InitManagerOnStart = true;
            bool assigned = XRPackageMetadataStore.AssignLoader(general.AssignedSettings, "UnityEngine.XR.OpenXR.OpenXRLoader", group);

            // Quest 3 over Link presents Meta's controllers; enable their interaction profiles.
            var oxr = OpenXRSettings.GetSettingsForBuildTargetGroup(group);
            var wanted = new[] { "OculusTouchControllerProfile", "MetaQuestTouchPlusControllerProfile", "MetaQuestTouchProControllerProfile" };
            var enabled = oxr.GetFeatures().Where(f => wanted.Contains(f.GetType().Name)).ToList();
            foreach (var f in enabled) f.enabled = true;
            EditorUtility.SetDirty(oxr);

            // The backend is plain http on the LAN / localhost.
            PlayerSettings.insecureHttpOption = InsecureHttpOption.AlwaysAllowed;
            PlayerSettings.productName = "AeroFleet VR";
            PlayerSettings.companyName = "AeroFleet";
            PlayerSettings.runInBackground = true;
            SavePlayerSettings();
            Debug.Log($"[AeroFleet] Standalone OpenXR loader {(assigned ? "assigned" : "already assigned")}; " +
                      $"profiles enabled: {string.Join(", ", enabled.Select(f => f.GetType().Name))}");
        }

        // ── 4. Quest standalone networking ────────────────────────────────

        [MenuItem("AeroFleet/Setup/4. Configure Quest Networking", priority = 14)]
        public static void ConfigureQuestNetworking()
        {
            // The standalone headset pairs with the desktop over Wi-Fi: HTTP to the desktop's VR
            // gateway and a UDP listener for its beacon (Core/Pairing.cs). Unity only adds the
            // INTERNET permission automatically when it sees UnityWebRequest in use at build time;
            // force it so the beacon listener works even before the first request.
            PlayerSettings.Android.forceInternetPermission = true;
            PlayerSettings.insecureHttpOption = InsecureHttpOption.AlwaysAllowed;
            SavePlayerSettings();
            Debug.Log("[AeroFleet] Quest networking: INTERNET permission forced, plain HTTP to the desktop gateway allowed.");
        }

        /// <summary>
        /// Persist PlayerSettings. With a Unity 6 build profile active (this project's "Meta Quest"),
        /// the PlayerSettings API writes into that profile only — the global settings, which a Windows
        /// build made with BuildPipeline uses, stay untouched. So the settings the viewer needs on every
        /// platform are also written to the global ProjectSettings asset directly.
        /// </summary>
        static void SavePlayerSettings()
        {
            var settings = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/ProjectSettings.asset");
            if (settings.Length > 0)
            {
                var so = new SerializedObject(settings[0]);
                so.FindProperty("insecureHttpOption").intValue = (int)InsecureHttpOption.AlwaysAllowed;
                so.FindProperty("runInBackground").boolValue = true;
                so.FindProperty("productName").stringValue = "AeroFleet VR";
                so.FindProperty("companyName").stringValue = "AeroFleet";
                so.ApplyModifiedPropertiesWithoutUndo();
                EditorUtility.SetDirty(settings[0]);
            }
            AssetDatabase.SaveAssets();
        }

        // ── dev helper ─────────────────────────────────────────────────────

        [MenuItem("AeroFleet/Dev/Write Local Test Config", priority = 30)]
        public static void WriteLocalTestConfig()
        {
            // Local development only: the demo account tools/seed_demo_swarm.py creates on a local backend.
            var cfg = new LaunchConfig
            {
                apiUrl = "http://localhost:8000",
                username = "demo_operator",
                password = Environment.GetEnvironmentVariable("AEROFLEET_DEMO_PASSWORD") ?? "aerofleet-demo-2026",
            };
            string path = Path.Combine(Application.persistentDataPath, LaunchConfig.ConfigFileName);
            File.WriteAllText(path, JsonUtility.ToJson(cfg, true));
            Debug.Log("[AeroFleet] Wrote local test config: " + path);
        }

        // ── builds ─────────────────────────────────────────────────────────

        [MenuItem("AeroFleet/Build/Windows PC-VR (.exe)", priority = 50)]
        public static void BuildWindows() => Build(BuildTargetGroup.Standalone, BuildTarget.StandaloneWindows64, WindowsExe,
            "Install \"Windows Build Support (Mono)\" for this editor in Unity Hub, or build on the Windows PC.");

        [MenuItem("AeroFleet/Build/Quest APK (standalone)", priority = 51)]
        public static void BuildQuest() => Build(BuildTargetGroup.Android, BuildTarget.Android, QuestApk,
            "Install \"Android Build Support\" for this editor in Unity Hub.");

        static void Build(BuildTargetGroup group, BuildTarget target, string output, string missingModuleHint)
        {
            if (!BuildPipeline.IsBuildTargetSupported(group, target))
            {
                Debug.LogError($"[AeroFleet] Can't build {target}: module not installed. {missingModuleHint}");
                return;
            }
            if (!File.Exists(ScenePath)) BuildScene();
            Directory.CreateDirectory(Path.GetDirectoryName(output));
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = new[] { ScenePath },
                locationPathName = output,
                targetGroup = group,
                target = target,
                options = BuildOptions.None,
            });
            var s = report.summary;
            if (s.result == BuildResult.Succeeded)
                Debug.Log($"[AeroFleet] Built {output} ({s.totalSize / (1024 * 1024)} MB) in {s.totalTime.TotalSeconds:0} s");
            else
                Debug.LogError($"[AeroFleet] {target} build {s.result}: {s.totalErrors} error(s) — see the console above.");
        }
    }
}
