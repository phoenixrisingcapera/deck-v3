use serde_json::Value;

use super::{actions, queries, sidecar, ApiError};

#[tauri::command]
pub async fn api_dispatch(
    app: tauri::AppHandle,
    method: String,
    path: String,
    body: Option<Value>,
) -> Result<Value, ApiError> {
    match (method.as_str(), path.as_str()) {
        // --- Queries ---
        ("GET", "/firms") => {
            let repo_path = require_string(&body, "repoPath")?;
            queries::list_firms(repo_path).await
        }

        // GET /firms/{firm}/deals — list deals under io/{firm}/deals/.
        // Returns name + abs path to the deal dir + latest version + version count.
        ("GET", p) if p.starts_with("/firms/") && p.ends_with("/deals") => {
            let repo_path = require_string(&body, "repoPath")?;
            let firm = p
                .trim_start_matches("/firms/")
                .trim_end_matches("/deals");
            queries::list_deals(repo_path, firm).await
        }

        // GET /firms/{firm}/brand-config — forwarded to the sidecar, which reads
        // io/{firm}/configs/brand-{firm}-config.yaml and returns it as JSON.
        ("GET", p) if p.starts_with("/firms/") && p.ends_with("/brand-config") => {
            forward_to_sidecar(&app, &body, &method, p).await
        }

        // GET /firms/{firm}/deals/{deal}/versions — list output_dir versions
        // for a single deal, sorted by mtime (most recent first).
        ("GET", p)
            if p.starts_with("/firms/")
                && p.contains("/deals/")
                && p.ends_with("/versions") =>
        {
            let repo_path = require_string(&body, "repoPath")?;
            let stripped = p
                .trim_start_matches("/firms/")
                .trim_end_matches("/versions");
            let (firm, deal) = match stripped.split_once("/deals/") {
                Some(t) => t,
                None => return Err(ApiError::validation("expected /firms/{firm}/deals/{deal}/versions")),
            };
            queries::list_versions(repo_path, firm, deal).await
        }

        // GET /firms/{firm}/deals/{deal}/config — forwarded to the sidecar.
        // Returns the parsed deal config (inputs/deal.json OR {deal}/{deal}.json),
        // used by DealWorkspace's "Run MemoPop" button to replay all on-disk
        // fields back into POST /memos with full fidelity.
        ("GET", p)
            if p.starts_with("/firms/")
                && p.contains("/deals/")
                && p.ends_with("/config") =>
        {
            forward_to_sidecar(&app, &body, &method, p).await
        }

        // GET /firms/{firm}/deals/{deal}/versions/{version}/files — flat list
        // of files (relative paths + sizes) under one version's output_dir.
        ("GET", p)
            if p.starts_with("/firms/")
                && p.contains("/deals/")
                && p.contains("/versions/")
                && p.ends_with("/files") =>
        {
            let repo_path = require_string(&body, "repoPath")?;
            let stripped = p
                .trim_start_matches("/firms/")
                .trim_end_matches("/files");
            // stripped is now: {firm}/deals/{deal}/versions/{version}
            let (firm_part, rest) = match stripped.split_once("/deals/") {
                Some(t) => t,
                None => return Err(ApiError::validation("malformed path")),
            };
            let (deal_part, version_part) = match rest.split_once("/versions/") {
                Some(t) => t,
                None => return Err(ApiError::validation("malformed path")),
            };
            queries::list_version_files(repo_path, firm_part, deal_part, version_part).await
        }

        ("GET", "/outlines") => {
            let repo_path = require_string(&body, "repoPath")?;
            queries::list_outlines(repo_path).await
        }

        // Returns the monorepo-sibling orchestrator path if this build can
        // resolve it (dev installs only). Used by the settings store to
        // auto-seed `repoPath` when nothing is saved, so a fresh dev install
        // doesn't require a manual Browse.
        ("GET", "/defaults/orchestrator-path") => {
            Ok(serde_json::json!({ "path": queries::default_orchestrator_path() }))
        }

        // Walk up from a path to find the enclosing Obsidian vault, so the
        // frontend can build an `obsidian://open?vault=…&file=…` URI rather
        // than `open -a Obsidian <folder>` (which silently no-ops for
        // non-vault folders).
        ("GET", "/local/obsidian-vault") => {
            let path = require_string(&body, "path")?;
            Ok(queries::find_obsidian_vault(path))
        }

        ("GET", p) if p.starts_with("/outlines/") => {
            let repo_path = require_string(&body, "repoPath")?;
            let id = p.trim_start_matches("/outlines/");
            if id.is_empty() {
                return Err(ApiError::validation("outline id required"));
            }
            queries::get_outline_detail(repo_path, id).await
        }

        // --- Actions ---
        ("POST", "/actions/create-firm") => {
            let repo_path = require_string(&body, "repoPath")?;
            let conventional_name = require_string(&body, "conventionalName")?;
            actions::create_firm(repo_path, conventional_name).await
        }

        // Stop the Python sidecar process. Goes directly to the SidecarManager
        // — it does NOT round-trip through the FastAPI server, because the whole
        // point of "stop" is to handle the case where Python is unresponsive
        // (rate-limited, deadlocked, in a runaway retry loop). SIGKILL is the
        // promise here, not a polite request.
        ("POST", "/actions/stop-sidecar") => {
            let manager = sidecar::manager(&app);
            manager.shutdown();
            Ok(serde_json::json!({"stopped": true}))
        }

        // Brand fetch + save — forwarded to the Python sidecar. fetch-brand drives
        // a Claude tool-use loop (~10–20s) reading the firm's website; save-brand
        // writes the user-confirmed config to disk.
        ("POST", "/actions/fetch-brand") | ("POST", "/actions/save-brand") => {
            forward_to_sidecar(&app, &body, &method, &path).await
        }

        // Cross-version source-catalog merge. Parses every version's
        // 3-source-catalog/, dedupes per section, writes exports/best-of-sources/.
        ("POST", "/actions/curate-sources") => {
            forward_to_sidecar(&app, &body, &method, &path).await
        }

        // Render a memo version to branded HTML (and optionally PDF). Shells
        // out to cli/export_branded.py inside the sidecar. Writes to
        // io/{firm}/deals/{deal}/exports/{mode}/. Synchronous — the script
        // completes in seconds for a typical memo.
        ("POST", "/actions/export-memo") => {
            forward_to_sidecar(&app, &body, &method, &path).await
        }

        // --- Source approval surface ---
        // Frontloaded curation: the analyst approves the corpus before the
        // run starts, and the sidecar's membership gate enforces it after.
        // Candidate discovery (`search-sources`) hits SearXNG, never an LLM —
        // a URL from a search index cannot be fabricated.
        ("GET", p) | ("POST", p)
            if p.starts_with("/firms/")
                && p.contains("/deals/")
                && p.ends_with("/sources") =>
        {
            forward_to_sidecar(&app, &body, &method, p).await
        }

        ("POST", "/actions/search-sources")
        | ("POST", "/actions/fetch-source")
        | ("POST", "/actions/recover-source")
        | ("POST", "/actions/approve-sources") => {
            forward_to_sidecar(&app, &body, &method, &path).await
        }

        // --- Sidecar-forwarded routes (FastAPI orchestrator API) ---
        // The sidecar is lazy-spawned on the first /memos call. SSE streaming
        // (`/memos/{id}/events`) intentionally goes direct from the webview to
        // localhost:8765 — only JSON routes pass through here.
        ("POST", "/memos") | ("GET", "/memos") => {
            forward_to_sidecar(&app, &body, &method, &path).await
        }

        // POST /memos/resume — pick up an interrupted run from the last
        // on-disk checkpoint. Same job machinery as a fresh run; different
        // worker entry point on the Python side.
        ("POST", "/memos/resume") => {
            forward_to_sidecar(&app, &body, &method, &path).await
        }

        ("GET", p)
            if p.starts_with("/memos/")
                && !p.ends_with("/events") =>
        {
            forward_to_sidecar(&app, &body, &method, p).await
        }

        _ => Err(ApiError::not_found(&format!("{} {}", method, path))),
    }
}

async fn forward_to_sidecar(
    app: &tauri::AppHandle,
    body: &Option<Value>,
    method: &str,
    path: &str,
) -> Result<Value, ApiError> {
    let repo_path = require_string(body, "repoPath")?.to_string();
    let manager = sidecar::manager(app);
    manager.ensure_running(app, &repo_path).await?;

    // Strip the dispatcher-only `repoPath` field before forwarding — the FastAPI
    // sidecar doesn't expect it and Pydantic won't gracefully ignore unknown keys
    // unless the model declares `extra=allow` (which we deliberately don't).
    let forward_body = body.as_ref().map(|b| {
        if let Value::Object(map) = b {
            let mut filtered = map.clone();
            filtered.remove("repoPath");
            Value::Object(filtered)
        } else {
            b.clone()
        }
    });

    manager.forward(method, path, forward_body).await
}

fn require_string<'a>(body: &'a Option<Value>, key: &str) -> Result<&'a str, ApiError> {
    body.as_ref()
        .and_then(|b| b.get(key))
        .and_then(|v| v.as_str())
        .ok_or_else(|| ApiError::validation(format!("{} required", key)))
}
