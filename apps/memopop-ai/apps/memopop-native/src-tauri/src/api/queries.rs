use std::path::Path;

use serde::Serialize;
use serde_json::{json, Value};

use super::ApiError;

/// Resolves the sibling `memopop-orchestrator/` directory inside this
/// monorepo, anchored at the Tauri crate's compile-time location. Returns
/// `None` outside of a dev install (release builds shipped elsewhere will not
/// find the path) — callers fall back to the manual Browse flow.
///
/// Why this exists: the orchestrator was previously at
/// `ai-labs/investment-memo-orchestrator/` and is now at
/// `ai-labs/memopop-ai/apps/memopop-orchestrator/`. Stale `repoPath` values
/// in the Tauri store kept pointing at the old location after the move.
pub fn default_orchestrator_path() -> Option<String> {
    let manifest = Path::new(env!("CARGO_MANIFEST_DIR"));
    let candidate = manifest.parent()?.parent()?.join("memopop-orchestrator");
    if candidate.join("pyproject.toml").is_file() {
        candidate
            .canonicalize()
            .ok()
            .and_then(|p| p.to_str().map(String::from))
    } else {
        None
    }
}

/// Walk up from `path` looking for a `.obsidian/` directory, the marker
/// of an Obsidian vault root. Returns `{vault_root, vault_name, rel_path}`
/// where `rel_path` is `path` relative to `vault_root` (POSIX-style, may be
/// empty if `path` is the vault root itself), or `null` if no vault was found.
///
/// `open -a Obsidian <arbitrary-folder>` silently no-ops when the folder
/// isn't a vault — the callers need to know whether to invoke the
/// `obsidian://open?vault=…&file=…` URI or fall back to Finder.
pub fn find_obsidian_vault(path: &str) -> Value {
    let target = Path::new(path);
    let mut cursor = if target.is_file() {
        target.parent().map(|p| p.to_path_buf())
    } else {
        Some(target.to_path_buf())
    };
    while let Some(dir) = cursor {
        if dir.join(".obsidian").is_dir() {
            let vault_name = dir
                .file_name()
                .map(|n| n.to_string_lossy().into_owned())
                .unwrap_or_default();
            let rel_path = target
                .strip_prefix(&dir)
                .ok()
                .map(|p| p.to_string_lossy().replace('\\', "/"))
                .unwrap_or_default();
            return json!({
                "vault_root": dir.to_string_lossy(),
                "vault_name": vault_name,
                "rel_path": rel_path,
            });
        }
        cursor = dir.parent().map(|p| p.to_path_buf());
    }
    Value::Null
}

pub async fn list_firms(repo_path: &str) -> Result<Value, ApiError> {
    let io_dir = Path::new(repo_path).join("io");
    if !io_dir.is_dir() {
        return Ok(json!({ "firms": [] }));
    }

    let mut firms: Vec<String> = Vec::new();

    let entries = std::fs::read_dir(&io_dir)
        .map_err(|e| ApiError::internal(format!("read_dir({}): {}", io_dir.display(), e)))?;

    for entry in entries {
        let entry = entry
            .map_err(|e| ApiError::internal(format!("entry: {}", e)))?;

        if !entry.file_type().map(|t| t.is_dir()).unwrap_or(false) {
            continue;
        }

        let name = match entry.file_name().into_string() {
            Ok(s) => s,
            Err(_) => continue,
        };

        if name.starts_with('.') {
            continue;
        }

        firms.push(name);
    }

    firms.sort();
    Ok(json!({ "firms": firms }))
}

#[derive(Debug, Serialize)]
struct DealSummary {
    name: String,
    deal_dir: String,
    latest_version: Option<String>,
    version_count: usize,
}

pub async fn list_deals(repo_path: &str, firm: &str) -> Result<Value, ApiError> {
    if firm.is_empty() {
        return Err(ApiError::validation("firm required"));
    }

    let deals_dir = Path::new(repo_path).join("io").join(firm).join("deals");
    if !deals_dir.is_dir() {
        return Ok(json!({ "deals": [] }));
    }

    let mut deals: Vec<DealSummary> = Vec::new();

    let entries = std::fs::read_dir(&deals_dir)
        .map_err(|e| ApiError::internal(format!("read_dir({}): {}", deals_dir.display(), e)))?;

    for entry in entries {
        let entry = match entry {
            Ok(e) => e,
            Err(_) => continue,
        };
        if !entry.file_type().map(|t| t.is_dir()).unwrap_or(false) {
            continue;
        }
        let name = match entry.file_name().into_string() {
            Ok(s) => s,
            Err(_) => continue,
        };
        if name.starts_with('.') {
            continue;
        }

        let deal_dir = entry.path();

        // Walk outputs/ to find the latest version (by mtime) + count.
        let outputs_dir = deal_dir.join("outputs");
        let mut versions: Vec<(String, std::time::SystemTime)> = Vec::new();
        if outputs_dir.is_dir() {
            if let Ok(version_entries) = std::fs::read_dir(&outputs_dir) {
                for v in version_entries.flatten() {
                    if !v.file_type().map(|t| t.is_dir()).unwrap_or(false) {
                        continue;
                    }
                    let v_name = match v.file_name().into_string() {
                        Ok(s) => s,
                        Err(_) => continue,
                    };
                    if v_name.starts_with('.') {
                        continue;
                    }
                    let mtime = v
                        .metadata()
                        .and_then(|m| m.modified())
                        .unwrap_or(std::time::UNIX_EPOCH);
                    versions.push((v_name, mtime));
                }
            }
        }
        versions.sort_by(|a, b| b.1.cmp(&a.1));
        let latest_version = versions.first().map(|(n, _)| n.clone());
        let version_count = versions.len();

        deals.push(DealSummary {
            name,
            deal_dir: deal_dir.to_string_lossy().into_owned(),
            latest_version,
            version_count,
        });
    }

    deals.sort_by(|a, b| a.name.cmp(&b.name));
    Ok(json!({ "deals": deals }))
}

#[derive(Debug, Serialize)]
struct VersionSummary {
    name: String,
    output_dir: String,
    last_modified_ms: u64,
}

pub async fn list_versions(
    repo_path: &str,
    firm: &str,
    deal: &str,
) -> Result<Value, ApiError> {
    if firm.is_empty() || deal.is_empty() {
        return Err(ApiError::validation("firm and deal required"));
    }

    let outputs_dir = Path::new(repo_path)
        .join("io")
        .join(firm)
        .join("deals")
        .join(deal)
        .join("outputs");

    if !outputs_dir.is_dir() {
        return Ok(json!({ "versions": [] }));
    }

    let mut versions: Vec<VersionSummary> = Vec::new();

    let entries = std::fs::read_dir(&outputs_dir)
        .map_err(|e| ApiError::internal(format!("read_dir({}): {}", outputs_dir.display(), e)))?;

    for entry in entries.flatten() {
        if !entry.file_type().map(|t| t.is_dir()).unwrap_or(false) {
            continue;
        }
        let name = match entry.file_name().into_string() {
            Ok(s) => s,
            Err(_) => continue,
        };
        if name.starts_with('.') {
            continue;
        }
        let dir = entry.path();
        let last_modified_ms = entry
            .metadata()
            .and_then(|m| m.modified())
            .ok()
            .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0);
        versions.push(VersionSummary {
            name,
            output_dir: dir.to_string_lossy().into_owned(),
            last_modified_ms,
        });
    }

    versions.sort_by(|a, b| b.last_modified_ms.cmp(&a.last_modified_ms));
    Ok(json!({ "versions": versions }))
}

#[derive(Debug, Serialize)]
struct ArtifactInfo {
    path: String,
    size: u64,
}

pub async fn list_version_files(
    repo_path: &str,
    firm: &str,
    deal: &str,
    version: &str,
) -> Result<Value, ApiError> {
    if firm.is_empty() || deal.is_empty() || version.is_empty() {
        return Err(ApiError::validation("firm, deal, and version required"));
    }
    if version.contains("..") || version.contains('/') {
        return Err(ApiError::validation("invalid version name"));
    }

    let version_dir = Path::new(repo_path)
        .join("io")
        .join(firm)
        .join("deals")
        .join(deal)
        .join("outputs")
        .join(version);

    if !version_dir.is_dir() {
        return Err(ApiError {
            status: 404,
            code: "version_not_found".into(),
            message: format!("version directory not found: {}", version_dir.display()),
        });
    }

    let mut files: Vec<ArtifactInfo> = Vec::new();
    walk_files(&version_dir, &version_dir, &mut files)
        .map_err(|e| ApiError::internal(format!("walk: {}", e)))?;

    files.sort_by(|a, b| a.path.cmp(&b.path));
    Ok(json!({
        "version_dir": version_dir.to_string_lossy().into_owned(),
        "files": files,
    }))
}

fn walk_files(
    root: &Path,
    cur: &Path,
    out: &mut Vec<ArtifactInfo>,
) -> Result<(), std::io::Error> {
    for entry in std::fs::read_dir(cur)?.flatten() {
        let p = entry.path();
        let ft = match entry.file_type() {
            Ok(ft) => ft,
            Err(_) => continue,
        };
        if ft.is_dir() {
            // Skip dot-dirs (e.g., .DS_Store leftovers, .git in submodule deals).
            if p.file_name().and_then(|s| s.to_str()).map(|s| s.starts_with('.')).unwrap_or(false) {
                continue;
            }
            walk_files(root, &p, out)?;
        } else if ft.is_file() {
            let rel = match p.strip_prefix(root) {
                Ok(r) => r,
                Err(_) => continue,
            };
            let path_str = rel.to_string_lossy().replace('\\', "/");
            let size = entry.metadata().map(|m| m.len()).unwrap_or(0);
            out.push(ArtifactInfo {
                path: path_str,
                size,
            });
        }
    }
    Ok(())
}

#[derive(Debug, Serialize)]
struct OutlineSummary {
    id: String,
    title: String,
    outline_type: String,
    type_label: String,
    description: String,
    section_count: usize,
    compatible_modes: Vec<String>,
    firm: Option<String>,
    version: Option<String>,
}

pub async fn list_outlines(repo_path: &str) -> Result<Value, ApiError> {
    let outlines_dir = Path::new(repo_path).join("templates").join("outlines");
    if !outlines_dir.is_dir() {
        return Err(ApiError {
            status: 404,
            code: "outlines_dir_missing".into(),
            message: format!(
                "No templates/outlines directory at {}. Did you pick the orchestrator repo root?",
                repo_path
            ),
        });
    }

    let mut outlines: Vec<OutlineSummary> = Vec::new();

    let entries = std::fs::read_dir(&outlines_dir)
        .map_err(|e| ApiError::internal(format!("read_dir({}): {}", outlines_dir.display(), e)))?;

    for entry in entries {
        let entry = match entry {
            Ok(e) => e,
            Err(_) => continue,
        };

        let path = entry.path();
        let extension = path.extension().and_then(|s| s.to_str()).unwrap_or("");
        if extension != "yaml" && extension != "yml" {
            continue;
        }

        let stem = match path.file_stem().and_then(|s| s.to_str()) {
            Some(s) => s.to_string(),
            None => continue,
        };

        match parse_outline(&path, &stem) {
            Ok(summary) => outlines.push(summary),
            Err(_) => continue, // skip unparseable outlines silently
        }
    }

    outlines.sort_by(|a, b| a.title.cmp(&b.title));
    Ok(json!({ "outlines": outlines }))
}

pub async fn get_outline_detail(repo_path: &str, id: &str) -> Result<Value, ApiError> {
    let outlines_dir = Path::new(repo_path).join("templates").join("outlines");
    let path = outlines_dir.join(format!("{}.yaml", id));

    let path = if path.exists() {
        path
    } else {
        let yml_path = outlines_dir.join(format!("{}.yml", id));
        if yml_path.exists() {
            yml_path
        } else {
            return Err(ApiError {
                status: 404,
                code: "outline_not_found".into(),
                message: format!("Outline '{}' not found in {}", id, outlines_dir.display()),
            });
        }
    };

    let content = std::fs::read_to_string(&path)
        .map_err(|e| ApiError::internal(format!("read({}): {}", path.display(), e)))?;

    let value: serde_yaml::Value = serde_yaml::from_str(&content)
        .map_err(|e| ApiError::internal(format!("yaml parse {}: {}", path.display(), e)))?;

    let json_value = serde_yaml_to_json(value);
    let summary = parse_outline(&path, path.file_stem().unwrap().to_str().unwrap())
        .map_err(|e| ApiError::internal(e))?;

    Ok(json!({
        "summary": summary,
        "raw": json_value,
    }))
}

fn parse_outline(path: &Path, stem: &str) -> Result<OutlineSummary, String> {
    let content = std::fs::read_to_string(path)
        .map_err(|e| format!("read: {}", e))?;

    let value: serde_yaml::Value = serde_yaml::from_str(&content)
        .map_err(|e| format!("yaml: {}", e))?;

    let metadata = value.get("metadata");

    let outline_type = metadata
        .and_then(|m| m.get("outline_type"))
        .and_then(|v| v.as_str())
        .unwrap_or("unknown")
        .to_string();

    let type_label = match outline_type.as_str() {
        "direct_investment" => "Direct Investment".to_string(),
        "fund_commitment" => "Fund Commitment".to_string(),
        other => humanize(other),
    };

    let description = metadata
        .and_then(|m| m.get("description"))
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();

    let firm = metadata
        .and_then(|m| m.get("firm"))
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());

    let version = metadata
        .and_then(|m| m.get("version"))
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());

    let compatible_modes = metadata
        .and_then(|m| m.get("compatible_modes"))
        .and_then(|v| v.as_sequence())
        .map(|seq| {
            seq.iter()
                .filter_map(|x| x.as_str().map(|s| s.to_string()))
                .collect()
        })
        .unwrap_or_else(Vec::new);

    let section_count = value
        .get("sections")
        .and_then(|s| s.as_sequence())
        .map(|seq| seq.len())
        .unwrap_or(0);

    let title = humanize(stem);

    Ok(OutlineSummary {
        id: stem.to_string(),
        title,
        outline_type,
        type_label,
        description,
        section_count,
        compatible_modes,
        firm,
        version,
    })
}

fn humanize(slug: &str) -> String {
    slug.replace('-', " ")
        .replace('_', " ")
        .split_whitespace()
        .map(|word| {
            let mut chars = word.chars();
            match chars.next() {
                Some(c) => c.to_uppercase().collect::<String>() + chars.as_str(),
                None => String::new(),
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

fn serde_yaml_to_json(value: serde_yaml::Value) -> Value {
    match value {
        serde_yaml::Value::Null => Value::Null,
        serde_yaml::Value::Bool(b) => Value::Bool(b),
        serde_yaml::Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                json!(i)
            } else if let Some(f) = n.as_f64() {
                json!(f)
            } else {
                Value::Null
            }
        }
        serde_yaml::Value::String(s) => Value::String(s),
        serde_yaml::Value::Sequence(seq) => Value::Array(seq.into_iter().map(serde_yaml_to_json).collect()),
        serde_yaml::Value::Mapping(map) => {
            let mut obj = serde_json::Map::new();
            for (k, v) in map {
                let key = match k {
                    serde_yaml::Value::String(s) => s,
                    other => serde_yaml::to_string(&other).unwrap_or_default(),
                };
                obj.insert(key, serde_yaml_to_json(v));
            }
            Value::Object(obj)
        }
        serde_yaml::Value::Tagged(tagged) => serde_yaml_to_json(tagged.value),
    }
}
