use std::fs;
use std::io::Write;
use std::path::Path;

use serde_json::{json, Value};

use super::ApiError;

pub async fn create_firm(repo_path: &str, conventional_name: &str) -> Result<Value, ApiError> {
    let trimmed = conventional_name.trim();
    if trimmed.is_empty() {
        return Err(ApiError::validation("Firm name cannot be empty"));
    }

    let slug = slugify(trimmed);
    if slug.is_empty() {
        return Err(ApiError::validation(
            "Firm name must contain at least one letter or number",
        ));
    }

    let repo = Path::new(repo_path);
    let io_dir = repo.join("io");
    let firm_dir = io_dir.join(&slug);

    if firm_dir.exists() {
        return Err(ApiError {
            status: 409,
            code: "firm_already_exists".into(),
            message: format!("Firm '{}' already exists at {}", slug, firm_dir.display()),
        });
    }

    fs::create_dir_all(&io_dir)
        .map_err(|e| ApiError::internal(format!("mkdir io: {}", e)))?;
    fs::create_dir_all(firm_dir.join("configs"))
        .map_err(|e| ApiError::internal(format!("mkdir configs: {}", e)))?;
    fs::create_dir_all(firm_dir.join("deals"))
        .map_err(|e| ApiError::internal(format!("mkdir deals: {}", e)))?;

    let brand_path = firm_dir
        .join("configs")
        .join(format!("brand-{}-config.yaml", slug));

    let brand_yaml = format!(
        r#"# io/{slug}/configs/brand-{slug}-config.yaml
# Firm identity stub. Real branding (colors, fonts, logos, tagline) is filled
# in by the "Brand setup" flow — not part of onboarding.
#
# Three names, three purposes:
#   conventional_name  - short, common-usage name (collected at onboarding)
#   name               - official name (collected later)
#   legal_entity_name  - legal name for memo disclosures (collected later)

company:
  conventional_name: "{name}"
"#,
        slug = slug,
        name = escape_yaml_string(trimmed)
    );

    fs::write(&brand_path, brand_yaml)
        .map_err(|e| ApiError::internal(format!("write brand-config: {}", e)))?;

    ensure_gitignore_entry(repo)
        .map_err(|e| ApiError::internal(format!("update .gitignore: {}", e)))?;

    Ok(json!({
        "slug": slug,
        "conventional_name": trimmed,
        "firm_dir": firm_dir.to_string_lossy(),
        "brand_config_path": brand_path.to_string_lossy(),
    }))
}

/// Normalize a firm name to snake_case for use as a directory name.
/// - Lowercase
/// - Spaces and hyphens → underscores
/// - Strip everything that isn't alphanumeric or underscore
/// - Collapse runs of underscores
/// - Trim leading/trailing underscores
fn slugify(input: &str) -> String {
    let lowered = input.to_lowercase();
    let mut out = String::with_capacity(lowered.len());
    let mut last_was_underscore = false;

    for ch in lowered.chars() {
        if ch.is_ascii_alphanumeric() {
            out.push(ch);
            last_was_underscore = false;
        } else if ch == ' ' || ch == '-' || ch == '_' || ch == '.' {
            if !last_was_underscore && !out.is_empty() {
                out.push('_');
                last_was_underscore = true;
            }
        }
        // Drop all other characters (commas, parentheses, etc.)
    }

    out.trim_matches('_').to_string()
}

fn escape_yaml_string(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

fn ensure_gitignore_entry(repo: &Path) -> std::io::Result<()> {
    const MARKER: &str = "# Added by MemoPop — firm data is private";
    const RULE: &str = "/io/*/";

    let gitignore = repo.join(".gitignore");
    let existing = if gitignore.exists() {
        fs::read_to_string(&gitignore)?
    } else {
        String::new()
    };

    // Idempotent: do nothing if our rule is already present.
    if existing
        .lines()
        .any(|line| line.trim() == RULE || line.trim() == "/io/*" || line.trim() == "io/*/")
    {
        return Ok(());
    }

    let mut file = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&gitignore)?;

    if !existing.is_empty() && !existing.ends_with('\n') {
        file.write_all(b"\n")?;
    }
    if !existing.is_empty() {
        file.write_all(b"\n")?;
    }
    writeln!(file, "{}", MARKER)?;
    writeln!(file, "{}", RULE)?;
    Ok(())
}
