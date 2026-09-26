//! Auto-launches the Python FastAPI backend on app startup.
//!
//! Before this module existed, the desktop app was a pure frontend shell
//! that silently assumed `http://127.0.0.1:8000` was already running —
//! nothing ever started it. That's the actual bug behind "localhost:8000
//! not working": the packaged app had no idea it was supposed to start
//! its own backend.
//!
//! What this does instead: on launch, look for an already-running backend
//! first (don't spawn a duplicate). If none is found, locate the
//! AeroFleet project root and a Python interpreter with its dependencies
//! installed, then spawn `python -m uvicorn aerofleet.api.app:app`
//! against it.
//!
//! **Root-discovery, in order — this is the part that had a real gap:**
//! the original version only tried walking up from the running exe's own
//! path and the current working directory. That works great in dev mode
//! (`npm run tauri dev` from inside the cloned repo — the CWD *is* the
//! project) but is fundamentally the wrong strategy for a real installed
//! app: an NSIS/MSI-installed AeroFleet.exe lives in `Program Files` or
//! `%LOCALAPPDATA%\Programs`, launched from the Start Menu with a CWD
//! that has nothing to do with wherever the user happened to `git clone`
//! the repo — those two locations are just unrelated. Confirmed exactly
//! this failure mode on a real Windows install this session.
//!
//! 1. `AEROFLEET_PROJECT_ROOT` env var (power-user/CI override).
//! 2. The persisted config written by step 5 below, from a previous
//!    successful launch on this machine.
//! 3. The original walk-up heuristic (exe dir, this crate's own compiled-
//!    in source dir, current dir) — still correct and free for dev mode.
//! 4. A short list of common places people actually `git clone` things
//!    into (home dir, Desktop, Documents, Downloads, ~/projects,
//!    ~/source, ~/repos), each checked for an `aerofleet` subdirectory.
//! 5. If all of that fails: the frontend shows a "Locate my AeroFleet
//!    folder" button (see App.tsx's backend-status banner) that opens a
//!    native folder picker; `set_project_root_and_relaunch` below
//!    validates whatever's chosen, persists it to this machine's config
//!    (`<app config dir>/backend-root.json`) so every future launch skips
//!    straight to step 2, and retries the launch immediately.
//!
//! Honest limitation, unchanged from before: this finds an *already
//! set up* Python environment (`.venv`/`venv` with
//! `pip install -r requirements.txt` done) — it does not bundle a
//! standalone, dependency-free Python runtime inside the installer. The
//! backend's real dependency surface (osmnx, shapely, scikit-learn,
//! cvxpy, chromadb — several with compiled native extensions) makes a
//! single-file frozen executable a substantial separate undertaking.

use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};

const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: &str = "8000";

fn looks_like_project_root(dir: &Path) -> bool {
    dir.join("requirements.txt").is_file() && dir.join("aerofleet").join("api").join("app.py").is_file()
}

// ── Persisted config (survives across launches) ────────────────────────

#[derive(Serialize, Deserialize)]
struct BackendConfig {
    project_root: String,
}

fn config_path() -> Option<PathBuf> {
    dirs::config_dir().map(|d| d.join("AeroFleet").join("backend-root.json"))
}

fn load_persisted_root() -> Option<PathBuf> {
    let path = config_path()?;
    let text = std::fs::read_to_string(path).ok()?;
    let cfg: BackendConfig = serde_json::from_str(&text).ok()?;
    let root = PathBuf::from(cfg.project_root);
    if looks_like_project_root(&root) { Some(root) } else { None }
}

fn save_persisted_root(root: &Path) -> Result<(), String> {
    let path = config_path().ok_or("Could not determine this OS's config directory")?;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let cfg = BackendConfig { project_root: root.to_string_lossy().to_string() };
    let text = serde_json::to_string_pretty(&cfg).map_err(|e| e.to_string())?;
    std::fs::write(path, text).map_err(|e| e.to_string())
}

// ── Root discovery ───────────────────────────────────────────────────

fn walk_up_from(start: &Path) -> Option<PathBuf> {
    let mut dir: &Path = start;
    for _ in 0..8 {
        if looks_like_project_root(dir) {
            return Some(dir.to_path_buf());
        }
        match dir.parent() {
            Some(p) => dir = p,
            None => break,
        }
    }
    None
}

fn common_clone_locations() -> Vec<PathBuf> {
    let mut candidates = Vec::new();
    if let Some(home) = dirs::home_dir() {
        for sub in ["", "projects", "source", "repos", "dev", "Documents", "Desktop", "Downloads"] {
            let base = if sub.is_empty() { home.clone() } else { home.join(sub) };
            candidates.push(base.join("aerofleet"));
            candidates.push(base.join("AeroFleet"));
        }
    }
    candidates
}

pub(crate) fn find_project_root() -> Option<PathBuf> {
    if let Ok(env_override) = std::env::var("AEROFLEET_PROJECT_ROOT") {
        let root = PathBuf::from(env_override);
        if looks_like_project_root(&root) {
            return Some(root);
        }
    }

    if let Some(persisted) = load_persisted_root() {
        return Some(persisted);
    }

    let mut heuristic_starts: Vec<PathBuf> = Vec::new();
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            heuristic_starts.push(dir.to_path_buf());
        }
    }
    heuristic_starts.push(PathBuf::from(env!("CARGO_MANIFEST_DIR")));
    if let Ok(cwd) = std::env::current_dir() {
        heuristic_starts.push(cwd);
    }
    for start in &heuristic_starts {
        if let Some(root) = walk_up_from(start) {
            return Some(root);
        }
    }

    for candidate in common_clone_locations() {
        if looks_like_project_root(&candidate) {
            return Some(candidate);
        }
    }

    None
}

fn find_python(root: &Path) -> Option<PathBuf> {
    let venv_candidates = [
        root.join(".venv").join("bin").join("python"),
        root.join(".venv").join("Scripts").join("python.exe"),
        root.join("venv").join("bin").join("python"),
        root.join("venv").join("Scripts").join("python.exe"),
    ];
    for c in &venv_candidates {
        if c.is_file() {
            return Some(c.clone());
        }
    }

    // Fall back to PATH — `which`/`where` rather than trusting a bare
    // `Command::new("python3")` to resolve predictably across shells.
    let finder = if cfg!(target_os = "windows") { "where" } else { "which" };
    for name in ["python3", "python"] {
        if let Ok(output) = Command::new(finder).arg(name).output() {
            if output.status.success() {
                if let Some(first_line) = String::from_utf8_lossy(&output.stdout).lines().next() {
                    let trimmed = first_line.trim();
                    if !trimmed.is_empty() {
                        return Some(PathBuf::from(trimmed));
                    }
                }
            }
        }
    }
    None
}

async fn backend_already_running() -> bool {
    reqwest::Client::new()
        .get(format!("http://{BACKEND_HOST}:{BACKEND_PORT}/"))
        .timeout(std::time::Duration::from_millis(800))
        .send()
        .await
        .map(|r| r.status().is_success())
        .unwrap_or(false)
}

pub struct BackendLaunchResult {
    pub child: Option<Child>,
    pub already_running: bool,
}

fn spawn_backend(root: &Path, python: &Path) -> Result<Child, String> {
    Command::new(python)
        .args(["-m", "uvicorn", "aerofleet.api.app:app", "--host", BACKEND_HOST, "--port", BACKEND_PORT])
        .current_dir(root)
        .env("DATABASE_URL", "sqlite:///./data/aerofleet.db")
        .env("ENVIRONMENT", "development")
        .env("PYTHONPATH", root)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Found Python at {} but failed to launch it: {e}", python.display()))
}

/// Returns `Ok` with `child: None` if a backend was already reachable
/// (nothing spawned), `Ok` with `child: Some(..)` for a freshly spawned
/// process the caller is responsible for killing on app exit, or `Err`
/// with a message suitable for showing directly to the user — this is
/// the one function whose failure the whole app's usefulness depends on,
/// so the error needs to say exactly what's missing, not just "failed".
/// The `NEEDS_PROJECT_ROOT` marker at the start of the "couldn't find
/// the project" message is what App.tsx keys off to show the folder
/// picker instead of a plain dismissible error.
pub async fn launch_backend_if_needed() -> Result<BackendLaunchResult, String> {
    if backend_already_running().await {
        return Ok(BackendLaunchResult { child: None, already_running: true });
    }

    let root = find_project_root().ok_or_else(|| {
        "NEEDS_PROJECT_ROOT: Couldn't find your AeroFleet checkout automatically. \
         Locate the folder you cloned https://github.com/AdityaPathare46/aerofleet into."
            .to_string()
    })?;

    let python = find_python(&root).ok_or_else(|| {
        format!(
            "Found the AeroFleet project at {} but no Python interpreter with its dependencies — \
             expected a virtual environment at .venv/ or venv/, or python3/python on PATH. \
             Run: python -m venv .venv && .venv\\Scripts\\pip install -r requirements.txt (see \
             docs/COLLEGE_PC_TEST_RUNBOOK.md), then relaunch AeroFleet.",
            root.display()
        )
    })?;

    let child = spawn_backend(&root, &python)?;
    Ok(BackendLaunchResult { child: Some(child), already_running: false })
}

/// Called (from main.rs's `set_project_root_and_launch` command, so the
/// spawned child can be stored in the same managed state the initial
/// launch uses and killed the same way on exit) after the user picks a
/// folder in the "Locate my AeroFleet folder" fallback flow. Validates
/// it's a real checkout, persists it for every future launch, and starts
/// the backend immediately against it — no app restart required.
pub fn set_project_root_and_launch(path: String) -> Result<Child, String> {
    let root = PathBuf::from(&path);
    if !looks_like_project_root(&root) {
        return Err(format!(
            "{} doesn't look like an AeroFleet checkout — expected requirements.txt and \
             aerofleet/api/app.py inside it. Pick the top-level folder from \
             `git clone https://github.com/AdityaPathare46/aerofleet.git`, not a subfolder.",
            root.display()
        ));
    }

    let python = find_python(&root).ok_or_else(|| {
        format!(
            "Found {} but no Python environment with dependencies installed there yet. \
             Run: python -m venv .venv && .venv\\Scripts\\pip install -r requirements.txt \
             inside that folder, then try again.",
            root.display()
        )
    })?;

    save_persisted_root(&root)?;
    spawn_backend(&root, &python)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_a_folder_with_no_project_markers() {
        let dir = std::env::temp_dir().join("aerofleet-test-empty-dir");
        let _ = std::fs::create_dir_all(&dir);
        assert!(!looks_like_project_root(&dir));
        let err = set_project_root_and_launch(dir.to_string_lossy().to_string())
            .expect_err("an empty folder must not be accepted as a checkout");
        assert!(err.contains("doesn't look like an AeroFleet checkout"), "got: {err}");
    }

    #[test]
    fn rejects_a_path_that_does_not_exist_at_all() {
        let err = set_project_root_and_launch("/definitely/not/a/real/path/anywhere".to_string())
            .expect_err("a nonexistent path must not be accepted");
        assert!(err.contains("doesn't look like an AeroFleet checkout"), "got: {err}");
    }

    #[test]
    fn config_round_trips_through_save_and_load() {
        // Points the config at this actual checkout (the only real project
        // root guaranteed to exist wherever this test runs) to prove
        // save -> load recovers exactly what was saved, then leaves the
        // config exactly as it found it rather than polluting a real
        // machine's state.
        let real_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent().unwrap() // tauri-app/
            .parent().unwrap() // repo root
            .to_path_buf();
        assert!(looks_like_project_root(&real_root), "test assumption: repo root has the markers");

        let previous = load_persisted_root();
        save_persisted_root(&real_root).expect("saving a valid root must succeed");
        let loaded = load_persisted_root().expect("a just-saved valid root must load back");
        assert_eq!(loaded, real_root);

        // Restore whatever was there before this test ran.
        match previous {
            Some(p) => save_persisted_root(&p).unwrap(),
            None => { let _ = std::fs::remove_file(config_path().unwrap()); }
        }
    }

    /// The real integration test — not run by default (see
    /// ollama_installer.rs's live-network test for the same pattern):
    /// actually spawns the backend against this checkout's real Python
    /// environment and confirms it becomes reachable, proving the exact
    /// recovery path a user hits when "Locate my AeroFleet folder"
    /// succeeds. Requires `.venv`/`venv` with `pip install -r
    /// requirements.txt` already done in this checkout, and leaves no
    /// process running afterward (kills it and clears the persisted
    /// config it wrote, so a normal `cargo test` run right after this one
    /// isn't affected).
    #[test]
    #[ignore]
    fn set_project_root_and_launch_actually_starts_a_reachable_backend() {
        let real_root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().unwrap().parent().unwrap().to_path_buf();
        let mut child = set_project_root_and_launch(real_root.to_string_lossy().to_string())
            .expect("launch against a real, already-set-up checkout must succeed");

        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(20);
        let reachable = loop {
            if std::time::Instant::now() > deadline {
                break false;
            }
            let ok = std::process::Command::new("curl")
                .args(["-s", "-o", "/dev/null", "-w", "%{http_code}", "http://127.0.0.1:8000/"])
                .output()
                .map(|o| String::from_utf8_lossy(&o.stdout) == "200")
                .unwrap_or(false);
            if ok { break true; }
            std::thread::sleep(std::time::Duration::from_millis(500));
        };

        let _ = child.kill();
        let _ = std::fs::remove_file(config_path().unwrap());
        assert!(reachable, "backend spawned by set_project_root_and_launch never became reachable within 20s");
    }
}
