//! flave desktop host.
//!
//! The filesystem is exposed as three explicit commands rather than through
//! `tauri-plugin-fs`. That is deliberate: the plugin's capability scoping is a
//! second permission model to keep in sync, and what the app actually needs is
//! the narrow `WorkspaceFs` contract — tree, read, write — rooted at one folder.
//! Three commands express exactly that and nothing more.
//!
//! Every path is resolved against the workspace root and rejected if it escapes
//! it, so a traversal in a document can never reach outside the folder the user
//! opened.

use serde::Serialize;
use std::fs;
use std::path::{Component, Path, PathBuf};

#[derive(Serialize)]
pub struct FsNode {
    name: String,
    path: String,
    is_dir: bool,
    children: Vec<FsNode>,
}

/// Reject `..`, absolute paths, and anything that resolves outside the root.
fn resolve(root: &str, rel: &str) -> Result<PathBuf, String> {
    let rel_path = Path::new(rel);
    if rel_path.is_absolute() {
        return Err(format!("absolute paths are not allowed: {rel}"));
    }
    for c in rel_path.components() {
        if matches!(c, Component::ParentDir) {
            return Err(format!("path escapes the workspace: {rel}"));
        }
    }
    let full = Path::new(root).join(rel_path);
    Ok(full)
}

fn walk(dir: &Path, root: &Path) -> Vec<FsNode> {
    let mut out: Vec<FsNode> = Vec::new();
    let Ok(entries) = fs::read_dir(dir) else {
        return out;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();
        // Dotfiles are the app's business, not the author's.
        if name.starts_with('.') {
            continue;
        }
        let is_dir = path.is_dir();
        let rel = path
            .strip_prefix(root)
            .unwrap_or(&path)
            .to_string_lossy()
            .to_string();
        let children = if is_dir { walk(&path, root) } else { Vec::new() };
        out.push(FsNode { name, path: rel, is_dir, children });
    }
    // Folders first, then alphabetical — the order a person expects.
    out.sort_by(|a, b| b.is_dir.cmp(&a.is_dir).then(a.name.cmp(&b.name)));
    out
}

#[tauri::command]
fn fs_tree(root: String) -> Result<Vec<FsNode>, String> {
    let root_path = Path::new(&root);
    if !root_path.is_dir() {
        return Err(format!("not a directory: {root}"));
    }
    Ok(walk(root_path, root_path))
}

#[tauri::command]
fn fs_read(root: String, path: String) -> Result<String, String> {
    let full = resolve(&root, &path)?;
    fs::read_to_string(&full).map_err(|e| format!("{}: {e}", full.display()))
}

#[tauri::command]
fn fs_write(root: String, path: String, contents: String) -> Result<(), String> {
    let full = resolve(&root, &path)?;
    if let Some(parent) = full.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("{}: {e}", parent.display()))?;
    }
    fs::write(&full, contents).map_err(|e| format!("{}: {e}", full.display()))
}

/// Where the workspace lives. Resolved by the host so the frontend never has to
/// guess an absolute path, and so a folder picker can replace this later
/// without the frontend changing.
#[tauri::command]
fn workspace_root() -> Result<String, String> {
    let cwd = std::env::current_dir().map_err(|e| e.to_string())?;
    // `tauri dev` runs from src-tauri/; the workspace sits beside it.
    let candidate = if cwd.ends_with("src-tauri") {
        cwd.parent().map(|p| p.join("workspace"))
    } else {
        Some(cwd.join("workspace"))
    };
    candidate
        .filter(|p| p.is_dir())
        .map(|p| p.to_string_lossy().to_string())
        .ok_or_else(|| "workspace/ not found".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            fs_tree,
            fs_read,
            fs_write,
            workspace_root
        ])
        .run(tauri::generate_context!())
        .expect("error while running flave");
}
