// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod ollama_installer;

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            ollama_installer::check_ollama_status,
            ollama_installer::install_ollama,
            ollama_installer::pull_model,
            ollama_installer::get_linux_install_command,
        ])
        .run(tauri::generate_context!())
        .expect("error while running AeroFleet");
}
