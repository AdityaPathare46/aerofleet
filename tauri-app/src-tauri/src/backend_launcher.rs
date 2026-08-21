//! Auto-launches the Python FastAPI backend on app startup.
//!
//! Before this module existed, the desktop app was a pure frontend shell
//! that silently assumed `http://127.0.0.1:8000` was already running —
//! nothing ever started it. Every "start the app" this session meant
//! manually running `uvicorn aerofleet.api.app:app` in a separate
//! terminal first. That's the actual bug behind "localhost:8000 not
//! working": the packaged app has no idea it's supposed to start its own
//! backend.
//!
//! What this does instead: on launch, look for an already-running backend
//! first (don't spawn a duplicate if one exists — useful during
//! development, and harmless if the previous run's process is still
//! shutting down). If none is found, locate the AeroFleet project root
//! (walking up from the app's own location and the current directory,
//! looking for the `requirements.txt` + `aerofleet/api/app.py` markers
//! that only exist in a real checkout of this repo) and the Python
//! interpreter that has this project's dependencies installed (its
//! `.venv`/`venv`, or whatever `python3`/`python` resolves to on PATH),
//! then spawn `python -m uvicorn aerofleet.api.app:app` against it.
//!
//! Honest limitation: this requires a clone of the AeroFleet repo with
//! `pip install -r requirements.txt` already done somewhere findable —
//! it does NOT bundle a standalone, dependency-free Python runtime inside
//! the installer. The backend's real dependency surface (osmnx, shapely,
//! scikit-learn, cvxpy, chromadb — several with compiled native
//! extensions) makes a single-file frozen executable a substantial
//! separate undertaking, not something to bolt on lightly. Until that
//! exists, "install AeroFleet" means: clone the repo, set up the Python
//! env once (see docs/COLLEGE_PC_TEST_RUNBOOK.md), and the app finds it
//! automatically every launch after that — no manually-run server, no
//! separate terminal.

use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};

const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: &str = "8000";

fn looks_like_project_root(dir: &Path) -> bool {
    dir.join("requirements.txt").is_file() && dir.join("aerofleet").join("api").join("app.py").is_file()
}

/// Walks upward (a handful of levels — this repo is never deeply nested
/// relative to the app or the current directory in any real scenario)
/// from each candidate starting point, looking for the project markers.
fn find_project_root() -> Option<PathBuf> {
    let mut starts: Vec<PathBuf> = Vec::new();
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            starts.push(dir.to_path_buf());
        }
    }
    // Dev builds (`cargo run` / `npm run tauri dev`): the crate's own
    // source directory, known at compile time.
    starts.push(PathBuf::from(env!("CARGO_MANIFEST_DIR")));
    if let Ok(cwd) = std::env::current_dir() {
        starts.push(cwd);
    }

    for start in starts {
        let mut dir: &Path = &start;
        for _ in 0..8 {
            if looks_like_project_root(dir) {
                return Some(dir.to_path_buf());
            }
            match dir.parent() {
                Some(p) => dir = p,
                None => break,
            }
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

/// Returns `Ok` with `child: None` if a backend was already reachable
/// (nothing spawned), `Ok` with `child: Some(..)` for a freshly spawned
/// process the caller is responsible for killing on app exit, or `Err`
/// with a message suitable for showing directly to the user — this is
/// the one function whose failure the whole app's usefulness depends on,
/// so the error needs to say exactly what's missing, not just "failed".
pub async fn launch_backend_if_needed() -> Result<BackendLaunchResult, String> {
    if backend_already_running().await {
        return Ok(BackendLaunchResult { child: None, already_running: true });
    }

    let root = find_project_root().ok_or_else(|| {
        "Couldn't find the AeroFleet project (looking for requirements.txt and aerofleet/api/app.py) \
         near the app or in the current directory. Clone https://github.com/AdityaPathare46/aerofleet \
         and run AeroFleet from inside (or next to) that checkout."
            .to_string()
    })?;

    let python = find_python(&root).ok_or_else(|| {
        format!(
            "Found the AeroFleet project at {} but no Python interpreter with its dependencies — \
             expected a virtual environment at .venv/ or venv/, or python3/python on PATH. \
             Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt (see \
             docs/COLLEGE_PC_TEST_RUNBOOK.md), then relaunch AeroFleet.",
            root.display()
        )
    })?;

    let child = Command::new(&python)
        .args(["-m", "uvicorn", "aerofleet.api.app:app", "--host", BACKEND_HOST, "--port", BACKEND_PORT])
        .current_dir(&root)
        .env("DATABASE_URL", "sqlite:///./data/aerofleet.db")
        .env("ENVIRONMENT", "development")
        .env("PYTHONPATH", &root)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Found Python at {} but failed to launch it: {e}", python.display()))?;

    Ok(BackendLaunchResult { child: Some(child), already_running: false })
}
