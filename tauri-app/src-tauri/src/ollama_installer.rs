//! Ollama detection + Windows/macOS installer automation.
//!
//! These are narrow, purpose-built Tauri commands — the frontend can only
//! ever call `check_ollama_status`, `install_ollama`, `pull_model`, and
//! `get_linux_install_command`. There is no general-purpose shell-execute
//! surface exposed to JS (we deliberately don't use tauri-plugin-shell's
//! JS-invokable Command API for this): every subprocess spawn and network
//! download happens inside these Rust functions, against fixed per-OS
//! install paths and a server-side-validated model-tag allow-list, not
//! whatever the frontend happens to pass in.
//!
//! Linux is intentionally NOT automated — Ollama's official Linux install
//! method is `curl -fsSL https://ollama.com/install.sh | sh`, piping a
//! fetched script straight into a shell. That's a meaningfully bigger
//! trust surface than running a checksum-verified signed installer binary
//! (Windows/macOS), so `get_linux_install_command` just returns the
//! official command as text for the user to copy and run themselves.

use serde::Serialize;
use sha2::{Digest, Sha256};
use std::path::PathBuf;
use tauri::{AppHandle, Emitter};

const GITHUB_LATEST_RELEASE: &str = "https://api.github.com/repos/ollama/ollama/releases/latest";
const OLLAMA_API_TAGS: &str = "http://localhost:11434/api/tags";

/// The Phase Q model roster — the only tags `pull_model` will ever spawn
/// `ollama pull` for. Defense in depth alongside whatever the caller
/// already validated; this command doesn't trust its argument blindly.
const KNOWN_ROSTER_TAGS: &[&str] = &[
    "llama4:scout",
    "mistral-small3.2",
    "mistral-large-3",
    "gemma4:12b",
    "phi4-reasoning:plus",
];

#[derive(Serialize, Clone)]
pub struct OllamaStatus {
    pub installed: bool,
    pub running: bool,
    pub version: Option<String>,
}

#[derive(Serialize, Clone)]
struct InstallProgress {
    stage: String,
    percent: Option<f32>,
}

#[derive(Serialize, Clone)]
struct PullProgress {
    model_tag: String,
    stage: String,
}

// ── Fixed per-OS install locations ───────────────────────────────────────
// Deliberately NOT resolving a bare `ollama` on PATH — that would happily
// execute whatever binary named "ollama" appears first on PATH, which
// isn't necessarily the one we installed. Fixed known paths avoid that.

#[cfg(target_os = "macos")]
fn known_ollama_binary_path() -> PathBuf {
    PathBuf::from("/usr/local/bin/ollama")
}

#[cfg(target_os = "macos")]
fn known_ollama_app_path() -> PathBuf {
    PathBuf::from("/Applications/Ollama.app")
}

#[cfg(target_os = "windows")]
fn known_ollama_binary_path() -> PathBuf {
    let local_appdata = std::env::var("LOCALAPPDATA").unwrap_or_default();
    PathBuf::from(local_appdata).join("Programs\\Ollama\\ollama.exe")
}

#[cfg(target_os = "linux")]
fn known_ollama_binary_path() -> PathBuf {
    PathBuf::from("/usr/local/bin/ollama")
}

// ── Status check ──────────────────────────────────────────────────────

#[tauri::command]
pub async fn check_ollama_status() -> Result<OllamaStatus, String> {
    let bin_path = known_ollama_binary_path();
    let installed = bin_path.exists();

    let mut version: Option<String> = None;
    if installed {
        if let Ok(output) = tokio::process::Command::new(&bin_path)
            .arg("--version")
            .output()
            .await
        {
            if output.status.success() {
                version = Some(String::from_utf8_lossy(&output.stdout).trim().to_string());
            }
        }
    }

    let running = reqwest::Client::new()
        .get(OLLAMA_API_TAGS)
        .timeout(std::time::Duration::from_secs(2))
        .send()
        .await
        .map(|r| r.status().is_success())
        .unwrap_or(false);

    Ok(OllamaStatus { installed, running, version })
}

// ── Linux: manual instructions, never auto-executed ──────────────────

#[tauri::command]
pub fn get_linux_install_command() -> String {
    "curl -fsSL https://ollama.com/install.sh | sh".to_string()
}

// ── Windows/macOS: download, checksum-verify, install ─────────────────

#[derive(serde::Deserialize)]
struct GithubAsset {
    name: String,
    browser_download_url: String,
}

#[derive(serde::Deserialize)]
struct GithubRelease {
    tag_name: String,
    assets: Vec<GithubAsset>,
}

async fn fetch_latest_release() -> Result<GithubRelease, String> {
    let client = reqwest::Client::builder()
        .user_agent("AeroFleet-Desktop-App")
        .build()
        .map_err(|e| e.to_string())?;
    let release: GithubRelease = client
        .get(GITHUB_LATEST_RELEASE)
        .send()
        .await
        .map_err(|e| format!("Failed to reach GitHub Releases API: {e}"))?
        .json()
        .await
        .map_err(|e| format!("Failed to parse GitHub release JSON: {e}"))?;
    Ok(release)
}

fn find_asset<'a>(release: &'a GithubRelease, filename: &str) -> Result<&'a GithubAsset, String> {
    release
        .assets
        .iter()
        .find(|a| a.name == filename)
        .ok_or_else(|| format!("Release {} has no asset named {}", release.tag_name, filename))
}

/// Parses the standard `sha256sum` output format ("<hash>  <filename>" per
/// line) and returns the hash matching `filename`.
fn parse_checksum(sha256sum_txt: &str, filename: &str) -> Result<String, String> {
    for line in sha256sum_txt.lines() {
        let mut parts = line.split_whitespace();
        if let (Some(hash), Some(name)) = (parts.next(), parts.next()) {
            // sha256sum output uses a `*` prefix for binary mode and, in
            // Ollama's actual release file, a `./` relative-path prefix
            // (e.g. "./Ollama-darwin.zip") — strip both before comparing.
            let name = name.trim_start_matches('*').trim_start_matches("./");
            if name == filename {
                return Ok(hash.to_lowercase());
            }
        }
    }
    Err(format!("No checksum entry found for {filename} in sha256sum.txt"))
}

async fn download_and_verify(
    app: &AppHandle,
    url: &str,
    expected_sha256: &str,
    dest: &PathBuf,
) -> Result<(), String> {
    use futures_util::StreamExt;

    let _ = app.emit("install-progress", InstallProgress {
        stage: "downloading".into(),
        percent: Some(0.0),
    });

    let response = reqwest::get(url).await.map_err(|e| format!("Download failed: {e}"))?;
    let total_size = response.content_length().unwrap_or(0);
    let mut downloaded: u64 = 0;
    let mut hasher = Sha256::new();
    let mut file = tokio::fs::File::create(dest)
        .await
        .map_err(|e| format!("Failed to create temp file: {e}"))?;

    let mut stream = response.bytes_stream();
    use tokio::io::AsyncWriteExt;
    while let Some(chunk) = stream.next().await {
        let chunk = chunk.map_err(|e| format!("Download stream error: {e}"))?;
        hasher.update(&chunk);
        file.write_all(&chunk).await.map_err(|e| format!("Write failed: {e}"))?;
        downloaded += chunk.len() as u64;
        if total_size > 0 {
            let percent = (downloaded as f32 / total_size as f32) * 100.0;
            let _ = app.emit("install-progress", InstallProgress {
                stage: "downloading".into(),
                percent: Some(percent),
            });
        }
    }
    file.flush().await.map_err(|e| e.to_string())?;

    let actual_sha256 = format!("{:x}", hasher.finalize());
    if actual_sha256.to_lowercase() != expected_sha256.to_lowercase() {
        let _ = tokio::fs::remove_file(dest).await;
        return Err(format!(
            "Checksum mismatch — expected {expected_sha256}, got {actual_sha256}. \
             Refusing to run an unverified download."
        ));
    }

    let _ = app.emit("install-progress", InstallProgress {
        stage: "verified".into(),
        percent: Some(100.0),
    });
    Ok(())
}

#[cfg(target_os = "macos")]
async fn install_ollama_impl(app: &AppHandle) -> Result<(), String> {
    let release = fetch_latest_release().await?;
    let zip_asset = find_asset(&release, "Ollama-darwin.zip")?;
    let checksums_asset = find_asset(&release, "sha256sum.txt")?;

    let checksums_text = reqwest::get(&checksums_asset.browser_download_url)
        .await
        .map_err(|e| e.to_string())?
        .text()
        .await
        .map_err(|e| e.to_string())?;
    let expected_sha256 = parse_checksum(&checksums_text, "Ollama-darwin.zip")?;

    let tmp_dir = std::env::temp_dir();
    let zip_path = tmp_dir.join("Ollama-darwin.zip");
    download_and_verify(app, &zip_asset.browser_download_url, &expected_sha256, &zip_path).await?;

    let _ = app.emit("install-progress", InstallProgress { stage: "installing".into(), percent: None });

    // Unzip Ollama.app and copy into /Applications.
    let file = std::fs::File::open(&zip_path).map_err(|e| e.to_string())?;
    let mut archive = zip::ZipArchive::new(file).map_err(|e| e.to_string())?;
    let extract_dir = tmp_dir.join("aerofleet-ollama-extract");
    let _ = std::fs::remove_dir_all(&extract_dir);
    std::fs::create_dir_all(&extract_dir).map_err(|e| e.to_string())?;
    archive.extract(&extract_dir).map_err(|e| format!("Failed to extract Ollama.app: {e}"))?;

    let extracted_app = extract_dir.join("Ollama.app");
    let dest_app = known_ollama_app_path();
    if dest_app.exists() {
        let _ = std::fs::remove_dir_all(&dest_app);
    }
    copy_dir_recursive(&extracted_app, &dest_app)?;

    let _ = tokio::fs::remove_file(&zip_path).await;
    let _ = tokio::fs::remove_dir_all(&extract_dir).await;

    // Launch once — Ollama.app runs the background daemon that exposes the
    // CLI at /usr/local/bin/ollama via a symlink it creates on first launch.
    let _ = std::process::Command::new("open").arg(&dest_app).spawn();

    let _ = app.emit("install-progress", InstallProgress { stage: "launched".into(), percent: None });
    Ok(())
}

#[cfg(target_os = "macos")]
fn copy_dir_recursive(src: &PathBuf, dst: &PathBuf) -> Result<(), String> {
    std::fs::create_dir_all(dst).map_err(|e| e.to_string())?;
    for entry in std::fs::read_dir(src).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let ty = entry.file_type().map_err(|e| e.to_string())?;
        let dest_path = dst.join(entry.file_name());
        if ty.is_dir() {
            copy_dir_recursive(&entry.path(), &dest_path)?;
        } else {
            std::fs::copy(entry.path(), &dest_path).map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

#[cfg(target_os = "windows")]
async fn install_ollama_impl(app: &AppHandle) -> Result<(), String> {
    let release = fetch_latest_release().await?;
    let exe_asset = find_asset(&release, "OllamaSetup.exe")?;
    let checksums_asset = find_asset(&release, "sha256sum.txt")?;

    let checksums_text = reqwest::get(&checksums_asset.browser_download_url)
        .await
        .map_err(|e| e.to_string())?
        .text()
        .await
        .map_err(|e| e.to_string())?;
    let expected_sha256 = parse_checksum(&checksums_text, "OllamaSetup.exe")?;

    let tmp_dir = std::env::temp_dir();
    let exe_path = tmp_dir.join("OllamaSetup.exe");
    download_and_verify(app, &exe_asset.browser_download_url, &expected_sha256, &exe_path).await?;

    let _ = app.emit("install-progress", InstallProgress { stage: "installing".into(), percent: None });

    // /VERYSILENT: Inno-Setup-style unattended install — Ollama's installer
    // is Inno-Setup-based as of this writing. Verify against Ollama's own
    // docs at implementation/release time if this stops working; installer
    // frameworks change their silent-install flag between major versions.
    let status = tokio::process::Command::new(&exe_path)
        .arg("/VERYSILENT")
        .arg("/SUPPRESSMSGBOXES")
        .status()
        .await
        .map_err(|e| format!("Failed to launch installer: {e}"))?;

    let _ = tokio::fs::remove_file(&exe_path).await;

    if !status.success() {
        return Err(format!("Installer exited with status: {status}"));
    }

    let _ = app.emit("install-progress", InstallProgress { stage: "installed".into(), percent: None });
    Ok(())
}

#[cfg(target_os = "linux")]
async fn install_ollama_impl(_app: &AppHandle) -> Result<(), String> {
    Err("Automated install isn't available on Linux — use get_linux_install_command() \
         and run it yourself. Piping a fetched script into a shell unattended is a \
         bigger trust surface than a checksum-verified installer binary, so this \
         app doesn't do it for you."
        .to_string())
}

#[tauri::command]
pub async fn install_ollama(app: AppHandle) -> Result<(), String> {
    install_ollama_impl(&app).await
}

// ── Model pulling ──────────────────────────────────────────────────────

#[tauri::command]
pub async fn pull_model(app: AppHandle, model_tag: String) -> Result<(), String> {
    if !KNOWN_ROSTER_TAGS.contains(&model_tag.as_str()) {
        return Err(format!(
            "'{model_tag}' is not one of the AeroFleet roster models — refusing to pull it."
        ));
    }

    let bin_path = known_ollama_binary_path();
    if !bin_path.exists() {
        return Err("Ollama isn't installed yet.".to_string());
    }

    let _ = app.emit("pull-progress", PullProgress {
        model_tag: model_tag.clone(),
        stage: "starting".into(),
    });

    let status = tokio::process::Command::new(&bin_path)
        .arg("pull")
        .arg(&model_tag)
        .status()
        .await
        .map_err(|e| format!("Failed to run ollama pull: {e}"))?;

    if !status.success() {
        return Err(format!("ollama pull {model_tag} exited with status: {status}"));
    }

    let _ = app.emit("pull-progress", PullProgress {
        model_tag,
        stage: "complete".into(),
    });
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_checksum_finds_matching_line() {
        let sample = "\
abc123def456  Ollama-darwin.zip
789fedcba012  OllamaSetup.exe
111222333444  ollama-linux-amd64.tar.zst
";
        assert_eq!(
            parse_checksum(sample, "Ollama-darwin.zip").unwrap(),
            "abc123def456"
        );
        assert_eq!(
            parse_checksum(sample, "OllamaSetup.exe").unwrap(),
            "789fedcba012"
        );
    }

    #[test]
    fn parse_checksum_handles_binary_mode_marker() {
        // Some sha256sum output uses a `*` prefix on the filename to mark
        // binary mode — must still match.
        let sample = "abc123  *Ollama-darwin.zip\n";
        assert_eq!(parse_checksum(sample, "Ollama-darwin.zip").unwrap(), "abc123");
    }

    #[test]
    fn parse_checksum_handles_relative_path_prefix() {
        // Ollama's actual sha256sum.txt release asset prefixes every
        // filename with "./" — caught by the live network test below
        // against real release data; regression-tested here without
        // needing network access.
        let sample = "abc123  ./Ollama-darwin.zip\n";
        assert_eq!(parse_checksum(sample, "Ollama-darwin.zip").unwrap(), "abc123");
    }

    #[test]
    fn parse_checksum_missing_entry_errors() {
        let sample = "abc123  Ollama-darwin.zip\n";
        assert!(parse_checksum(sample, "OllamaSetup.exe").is_err());
    }

    #[test]
    fn linux_install_command_is_the_official_one() {
        assert_eq!(
            get_linux_install_command(),
            "curl -fsSL https://ollama.com/install.sh | sh"
        );
    }

    #[test]
    fn roster_tags_reject_unknown_model() {
        assert!(!KNOWN_ROSTER_TAGS.contains(&"some-random-unvetted-model"));
        assert!(KNOWN_ROSTER_TAGS.contains(&"llama4:scout"));
    }

    /// Live network test — hits the real GitHub Releases API to confirm
    /// the actual current Ollama release still has the exact asset names
    /// (Ollama-darwin.zip, OllamaSetup.exe, sha256sum.txt) this module's
    /// filename constants assume, and that sha256sum.txt parses with a
    /// real checksum for a real asset. Run explicitly, not part of the
    /// default `cargo test` — needs network access and depends on an
    /// external project's release contents staying stable.
    #[tokio::test]
    #[ignore]
    async fn live_github_release_has_expected_assets_and_checksums() {
        let release = fetch_latest_release().await.expect("GitHub API reachable");
        let zip_asset = find_asset(&release, "Ollama-darwin.zip").expect("macOS asset present");
        let exe_asset = find_asset(&release, "OllamaSetup.exe").expect("Windows asset present");
        let checksums_asset = find_asset(&release, "sha256sum.txt").expect("checksum file present");

        let checksums_text = reqwest::get(&checksums_asset.browser_download_url)
            .await
            .expect("checksum file downloads")
            .text()
            .await
            .expect("checksum file is text");

        let zip_hash = parse_checksum(&checksums_text, "Ollama-darwin.zip")
            .expect("macOS asset has a checksum entry");
        let exe_hash = parse_checksum(&checksums_text, "OllamaSetup.exe")
            .expect("Windows asset has a checksum entry");

        assert_eq!(zip_hash.len(), 64, "sha256 hex digest should be 64 chars");
        assert_eq!(exe_hash.len(), 64, "sha256 hex digest should be 64 chars");
        println!(
            "Verified against {}: {} -> {}, {} -> {}",
            release.tag_name, zip_asset.name, zip_hash, exe_asset.name, exe_hash
        );
    }
}
