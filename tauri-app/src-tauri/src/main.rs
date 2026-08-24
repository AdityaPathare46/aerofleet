// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod backend_launcher;
mod ollama_installer;

use std::process::Child;
use std::sync::Mutex;
use tauri::{Emitter, Manager, State};

/// Holds the backend process this app spawned, if any — `None` both
/// before launch and when a backend was already running externally (in
/// which case this app doesn't own its lifecycle and won't kill it on
/// exit).
struct BackendChild(Mutex<Option<Child>>);

/// Invoked from App.tsx's "Locate my AeroFleet folder" fallback, after
/// the native folder picker returns a path — see backend_launcher.rs's
/// module docs for why this exists (an installed app's location has no
/// relation to wherever the user cloned the repo, so automatic discovery
/// can legitimately fail and needs a one-time manual answer). Replaces
/// any previously-tracked child so a stale one from a first failed guess
/// isn't silently leaked.
#[tauri::command]
async fn set_project_root_and_launch(path: String, state: State<'_, BackendChild>) -> Result<(), String> {
    let child = backend_launcher::set_project_root_and_launch(path)?;
    let mut guard = state.0.lock().unwrap();
    if let Some(mut old) = guard.take() {
        let _ = old.kill();
    }
    *guard = Some(child);
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(BackendChild(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![
            ollama_installer::check_ollama_status,
            ollama_installer::install_ollama,
            ollama_installer::pull_model,
            ollama_installer::get_linux_install_command,
            set_project_root_and_launch,
        ])
        .setup(|app| {
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                match backend_launcher::launch_backend_if_needed().await {
                    Ok(result) => {
                        if let Some(child) = result.child {
                            if let Some(state) = handle.try_state::<BackendChild>() {
                                *state.0.lock().unwrap() = Some(child);
                            }
                        }
                        let _ = handle.emit(
                            "backend-status",
                            serde_json::json!({ "ok": true, "already_running": result.already_running }),
                        );
                    }
                    Err(message) => {
                        eprintln!("[backend_launcher] {message}");
                        let _ = handle.emit("backend-status", serde_json::json!({ "ok": false, "error": message }));
                    }
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building AeroFleet")
        .run(|app_handle, event| {
            // Best-effort cleanup: a force-quit or crash won't run this,
            // same limitation any process-supervising launcher has without
            // OS-specific parent-death-signal wiring — next launch's
            // "is a backend already reachable?" check (backend_launcher::
            // backend_already_running) tolerates a stray leftover process
            // by just not spawning a second one on top of it.
            if let tauri::RunEvent::ExitRequested { .. } = event {
                if let Some(state) = app_handle.try_state::<BackendChild>() {
                    if let Some(mut child) = state.0.lock().unwrap().take() {
                        let _ = child.kill();
                    }
                }
            }
        });
}
