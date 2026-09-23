//! Manages the FastAPI sidecar process and forwards HTTP calls to it.
//!
//! The sidecar lives at `{repo_path}/.venv/bin/python -m src.server` (Mac/Linux)
//! or `{repo_path}/.venv/Scripts/python.exe -m src.server` (Windows). It is
//! lazy-spawned on the first `/memos*` request and torn down on app shutdown.

use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use reqwest::Client;
use serde_json::Value;
use tauri::Manager;
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

use super::ApiError;

const SIDECAR_HOST: &str = "127.0.0.1";
const SIDECAR_PORT: u16 = 8765;
const HEALTHZ_TIMEOUT_SECS: u64 = 15;
const HEALTHZ_POLL_MS: u64 = 250;

pub struct SidecarManager {
    state: Mutex<SidecarState>,
    http: Client,
}

struct SidecarState {
    child: Option<CommandChild>,
    repo_path: Option<String>,
}

impl SidecarManager {
    pub fn new() -> Self {
        Self {
            state: Mutex::new(SidecarState {
                child: None,
                repo_path: None,
            }),
            http: Client::builder()
                .timeout(Duration::from_secs(60))
                .build()
                .expect("reqwest client"),
        }
    }

    /// Start the sidecar if it isn't already running, and wait for /healthz.
    pub async fn ensure_running<R: tauri::Runtime>(
        &self,
        app: &tauri::AppHandle<R>,
        repo_path: &str,
    ) -> Result<(), ApiError> {
        // Self-healing entry: ALWAYS probe /healthz first, regardless of what
        // our state thinks. If a sidecar is alive, we use it. If it's dead
        // (externally killed, crashed, hung), we drop the stale handle and
        // spawn fresh below. Without this, a dead-but-still-tracked child
        // would route requests into the void until the user restarts the app
        // — exactly the failure mode that wasted hours tonight.
        if self.healthz_ok().await {
            // Healthy sidecar (ours, or one the user started manually). Done.
            return Ok(());
        }

        // Sidecar isn't responding. Clear any stale handle we might still hold,
        // killing the process best-effort (it may already be dead — that's fine).
        if let Ok(mut state) = self.state.lock() {
            if let Some(child) = state.child.take() {
                let _ = child.kill();
            }
            state.repo_path = None;
        }

        let venv_python = find_venv_python(Path::new(repo_path)).ok_or_else(|| {
            ApiError::validation(format!(
                "No Python venv found at {}/.venv. Run `uv venv && uv pip install -e .` from the orchestrator repo first.",
                repo_path
            ))
        })?;

        let shell = app.shell();
        let (mut rx, child) = shell
            .command(venv_python.to_string_lossy().as_ref())
            .args([
                "-m",
                "src.server",
                "--port",
                &SIDECAR_PORT.to_string(),
            ])
            .current_dir(Path::new(repo_path))
            .spawn()
            .map_err(|e| ApiError::internal(format!("Failed to spawn sidecar: {}", e)))?;

        // Drain stdout/stderr so the child's pipes don't fill and block.
        // The SSE stream is the canonical log path for the UI; this is just keep-alive.
        tauri::async_runtime::spawn(async move {
            while let Some(_event) = rx.recv().await {}
        });

        // Poll /healthz until it answers or we hit the deadline.
        let deadline = Instant::now() + Duration::from_secs(HEALTHZ_TIMEOUT_SECS);
        while Instant::now() < deadline {
            tokio::time::sleep(Duration::from_millis(HEALTHZ_POLL_MS)).await;
            if self.healthz_ok().await {
                let mut state = self.state.lock().unwrap();
                state.child = Some(child);
                state.repo_path = Some(repo_path.to_string());
                return Ok(());
            }
        }

        // Timed out — kill what we just started so we don't leak a process.
        let _ = child.kill();
        Err(ApiError::internal(format!(
            "Sidecar did not become healthy on {}:{} within {}s",
            SIDECAR_HOST, SIDECAR_PORT, HEALTHZ_TIMEOUT_SECS
        )))
    }

    /// Forward an HTTP request to the running sidecar and return the parsed body.
    pub async fn forward(
        &self,
        method: &str,
        path: &str,
        body: Option<Value>,
    ) -> Result<Value, ApiError> {
        let url = format!("http://{}:{}{}", SIDECAR_HOST, SIDECAR_PORT, path);
        let req = match method {
            "GET" => self.http.get(&url),
            "POST" => self.http.post(&url),
            _ => {
                return Err(ApiError::validation(format!(
                    "Unsupported method for sidecar forwarding: {}",
                    method
                )))
            }
        };

        let req = if let Some(b) = body {
            req.json(&b)
        } else {
            req
        };

        let resp = req
            .send()
            .await
            .map_err(|e| ApiError::internal(format!("Sidecar request failed: {}", e)))?;

        let status = resp.status();
        let text = resp
            .text()
            .await
            .map_err(|e| ApiError::internal(format!("Reading sidecar response: {}", e)))?;

        let value: Value =
            serde_json::from_str(&text).unwrap_or_else(|_| Value::String(text));

        if !status.is_success() {
            return Err(ApiError {
                status: status.as_u16(),
                code: "sidecar_error".into(),
                message: value.to_string(),
            });
        }

        Ok(value)
    }

    /// Best-effort termination of the child process. Safe to call multiple times.
    pub fn shutdown(&self) {
        if let Ok(mut state) = self.state.lock() {
            if let Some(child) = state.child.take() {
                let _ = child.kill();
            }
        }
    }

    async fn healthz_ok(&self) -> bool {
        let url = format!("http://{}:{}/healthz", SIDECAR_HOST, SIDECAR_PORT);
        match self
            .http
            .get(&url)
            .timeout(Duration::from_millis(500))
            .send()
            .await
        {
            Ok(r) => r.status().is_success(),
            Err(_) => false,
        }
    }
}

impl Default for SidecarManager {
    fn default() -> Self {
        Self::new()
    }
}

fn find_venv_python(repo: &Path) -> Option<PathBuf> {
    let unix = repo.join(".venv").join("bin").join("python");
    if unix.exists() {
        return Some(unix);
    }
    let win = repo.join(".venv").join("Scripts").join("python.exe");
    if win.exists() {
        return Some(win);
    }
    None
}

/// Convenience: pull the manager off the app handle.
pub fn manager<R: tauri::Runtime>(app: &tauri::AppHandle<R>) -> tauri::State<'_, SidecarManager> {
    app.state::<SidecarManager>()
}
