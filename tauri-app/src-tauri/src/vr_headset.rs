//! PC-VR headset support for the VR Safety View.
//!
//! The in-app view renders with WebXR, which a desktop WebView2 can't be relied on to
//! expose to a Quest over Link. So on Windows the app hands off to the native viewer
//! (`unity/AeroFleetVR`, built as `AeroFleetVR.exe`): it detects whether a PC-VR runtime
//! is ready, then launches the viewer pointed at the same backend, city, mode and
//! incident the operator is looking at.
//!
//! **Detection** — the Khronos OpenXR loader reads the active runtime from
//! `HKLM\SOFTWARE\Khronos\OpenXR\1\ActiveRuntime`; that is exactly what the viewer's
//! OpenXR loader will use, so it's the honest "will the headset work" signal. Quest
//! Link's service (`OVRServer_x64.exe`) and SteamVR's (`vrserver.exe`) are reported
//! separately because a runtime can be installed but not running.
//!
//! **Viewer discovery**, in order: `AEROFLEET_VR_VIEWER` env var; the path the operator
//! picked once with "Locate viewer…" (persisted to `<config>/AeroFleet/vr-viewer.json`);
//! `AeroFleetVR/AeroFleetVR.exe` next to this app's exe (how an installer would ship it);
//! the project checkout's `unity/AeroFleetVR/Builds/Windows/AeroFleetVR.exe`.
//!
//! **Token** — passed as the `AEROFLEET_TOKEN` environment variable of the child only,
//! never as an argument: process arguments are readable by every process on the PC.

use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::State;

pub struct VrViewerChild(pub Mutex<Option<Child>>);

#[derive(Serialize)]
pub struct HeadsetStatus {
    pub platform: String,
    pub openxr_runtime_path: Option<String>,
    pub runtime_name: Option<String>,
    pub quest_link_running: bool,
    pub steamvr_running: bool,
    pub viewer_path: Option<String>,
    pub viewer_running: bool,
    pub ready: bool,
    pub hint: String,
}

#[derive(Serialize, Deserialize)]
struct ViewerConfig {
    viewer_path: String,
}

fn config_path() -> Option<PathBuf> {
    dirs::config_dir().map(|d| d.join("AeroFleet").join("vr-viewer.json"))
}

fn persisted_viewer() -> Option<PathBuf> {
    let text = std::fs::read_to_string(config_path()?).ok()?;
    let cfg: ViewerConfig = serde_json::from_str(&text).ok()?;
    Some(PathBuf::from(cfg.viewer_path))
}

fn find_viewer() -> Option<PathBuf> {
    let mut candidates: Vec<PathBuf> = Vec::new();
    if let Ok(p) = std::env::var("AEROFLEET_VR_VIEWER") {
        candidates.push(PathBuf::from(p));
    }
    if let Some(p) = persisted_viewer() {
        candidates.push(p);
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            candidates.push(dir.join("AeroFleetVR").join("AeroFleetVR.exe"));
        }
    }
    if let Some(root) = crate::backend_launcher::find_project_root() {
        candidates.push(root.join("unity").join("AeroFleetVR").join("Builds").join("Windows").join("AeroFleetVR.exe"));
    }
    candidates.into_iter().find(|p| p.is_file())
}

/// Friendly name for the runtime manifest the OpenXR loader will use.
fn runtime_name(manifest_path: &str) -> String {
    let p = manifest_path.to_ascii_lowercase();
    if p.contains("oculus") || p.contains("meta") {
        "Meta Quest Link".into()
    } else if p.contains("steamvr") {
        "SteamVR".into()
    } else if p.contains("virtualdesktop") {
        "Virtual Desktop".into()
    } else if p.contains("mixedreality") {
        "Windows Mixed Reality".into()
    } else {
        Path::new(manifest_path).file_stem().map(|s| s.to_string_lossy().to_string()).unwrap_or_else(|| manifest_path.into())
    }
}

#[cfg(windows)]
fn quiet(cmd: &mut Command) -> &mut Command {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    cmd.creation_flags(CREATE_NO_WINDOW)
}

#[cfg(windows)]
fn active_openxr_runtime() -> Option<String> {
    let out = quiet(Command::new("reg").args(["query", r"HKLM\SOFTWARE\Khronos\OpenXR\1", "/v", "ActiveRuntime"]))
        .output()
        .ok()?;
    let text = String::from_utf8_lossy(&out.stdout);
    // "    ActiveRuntime    REG_SZ    C:\Program Files\Oculus\Support\oculus-runtime\oculus_openxr_64.json"
    text.lines()
        .find(|l| l.contains("ActiveRuntime"))
        .and_then(|l| l.split("REG_SZ").nth(1))
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
}

#[cfg(windows)]
fn process_running(image: &str) -> bool {
    quiet(Command::new("tasklist").args(["/FI", &format!("IMAGENAME eq {image}"), "/NH"]))
        .output()
        .map(|o| String::from_utf8_lossy(&o.stdout).to_ascii_lowercase().contains(&image.to_ascii_lowercase()))
        .unwrap_or(false)
}

#[cfg(not(windows))]
fn active_openxr_runtime() -> Option<String> {
    // Linux (Monado/SteamVR) keeps the same information in a JSON symlink; macOS has no OpenXR runtime.
    let mut paths = vec![PathBuf::from("/etc/xdg/openxr/1/active_runtime.json")];
    if let Some(cfg) = dirs::config_dir() {
        paths.insert(0, cfg.join("openxr").join("1").join("active_runtime.json"));
    }
    paths.into_iter().find(|p| p.exists()).map(|p| std::fs::canonicalize(&p).unwrap_or(p).to_string_lossy().to_string())
}

#[cfg(not(windows))]
fn process_running(_image: &str) -> bool {
    false
}

fn viewer_running(state: &State<'_, VrViewerChild>) -> bool {
    let mut guard = state.0.lock().unwrap();
    match guard.as_mut() {
        Some(child) => match child.try_wait() {
            Ok(None) => true,
            _ => {
                *guard = None;
                false
            }
        },
        None => false,
    }
}

#[tauri::command]
pub fn vr_headset_status(state: State<'_, VrViewerChild>) -> HeadsetStatus {
    let platform = std::env::consts::OS.to_string();
    let runtime = active_openxr_runtime();
    let quest_link_running = process_running("OVRServer_x64.exe");
    let steamvr_running = process_running("vrserver.exe");
    let viewer = find_viewer();
    let running = viewer_running(&state);

    let hint = if platform != "windows" {
        "PC-VR runs on Windows: connect the Quest 3 with Quest Link / Air Link on the Windows PC. \
         On this machine, use Enter VR from the Quest Browser instead (docs/VR_QUEST3_GUIDE.md)."
            .to_string()
    } else if runtime.is_none() {
        "No OpenXR runtime is set. Install the Meta Quest Link app, open it, and set it as the active OpenXR runtime \
         (Settings ▸ General ▸ OpenXR Runtime)."
            .to_string()
    } else if !quest_link_running && !steamvr_running {
        "An OpenXR runtime is set but no headset service is running. Open the Meta Quest Link app and put on the \
         headset, then enable Link (or Air Link) from the Quest's quick settings."
            .to_string()
    } else if viewer.is_none() {
        "Headset runtime ready, but the AeroFleet VR viewer isn't installed. Build it (Unity ▸ AeroFleet ▸ Build ▸ \
         Windows PC-VR) or use Locate viewer…"
            .to_string()
    } else if running {
        "Running in the headset.".to_string()
    } else {
        "Ready — put on the headset and launch.".to_string()
    };

    HeadsetStatus {
        platform,
        runtime_name: runtime.as_deref().map(runtime_name),
        openxr_runtime_path: runtime.clone(),
        quest_link_running,
        steamvr_running,
        viewer_path: viewer.as_ref().map(|p| p.to_string_lossy().to_string()),
        viewer_running: running,
        ready: runtime.is_some() && (quest_link_running || steamvr_running) && viewer.is_some(),
        hint,
    }
}

#[tauri::command]
pub fn set_vr_viewer_path(path: String) -> Result<(), String> {
    let p = PathBuf::from(&path);
    if !p.is_file() {
        return Err(format!("Not a file: {path}"));
    }
    let cfg_path = config_path().ok_or("Could not determine this OS's config directory")?;
    if let Some(parent) = cfg_path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let text = serde_json::to_string_pretty(&ViewerConfig { viewer_path: path }).map_err(|e| e.to_string())?;
    std::fs::write(cfg_path, text).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn launch_vr_viewer(
    api_url: String,
    city: String,
    mode: String,
    incident_id: Option<String>,
    token: Option<String>,
    state: State<'_, VrViewerChild>,
) -> Result<(), String> {
    if viewer_running(&state) {
        return Err("The AeroFleet VR viewer is already running in the headset.".into());
    }
    let exe = find_viewer().ok_or("AeroFleet VR viewer not found — build it or use Locate viewer….")?;
    let mut cmd = Command::new(&exe);
    cmd.args(["--aerofleet-api", &api_url, "--aerofleet-city", &city, "--aerofleet-mode", &mode]);
    if let Some(id) = incident_id.filter(|s| !s.is_empty()) {
        cmd.args(["--aerofleet-incident", &id]);
    }
    if let Some(t) = token.filter(|s| !s.is_empty()) {
        cmd.env("AEROFLEET_TOKEN", t);
    }
    if let Some(dir) = exe.parent() {
        cmd.current_dir(dir);
    }
    let child = cmd.stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null()).spawn()
        .map_err(|e| format!("Could not start {}: {e}", exe.display()))?;
    *state.0.lock().unwrap() = Some(child);
    Ok(())
}

#[tauri::command]
pub fn stop_vr_viewer(state: State<'_, VrViewerChild>) {
    if let Some(mut child) = state.0.lock().unwrap().take() {
        let _ = child.kill();
    }
}
