/**
 * Slugify a firm name into snake_case for use as a directory name.
 *
 * Mirrors the Rust `slugify` in src-tauri/src/api/actions.rs so the UI can
 * preview the resulting path before the user confirms.
 *
 * Rules:
 *   - Lowercase
 *   - Spaces, hyphens, dots → underscores
 *   - Strip everything that isn't alphanumeric or underscore
 *   - Collapse runs of underscores
 *   - Trim leading/trailing underscores
 */
export function slugify(input: string): string {
  const lowered = input.toLowerCase();
  let out = '';
  let lastWasUnderscore = false;

  for (const ch of lowered) {
    if (/[a-z0-9]/.test(ch)) {
      out += ch;
      lastWasUnderscore = false;
    } else if (ch === ' ' || ch === '-' || ch === '_' || ch === '.') {
      if (!lastWasUnderscore && out.length > 0) {
        out += '_';
        lastWasUnderscore = true;
      }
    }
  }

  return out.replace(/^_+|_+$/g, '');
}

/**
 * Slugify a deal / company name into a path-safe form. Unlike `slugify`
 * (firm slugs, snake_case + lowercased), this preserves case so ChromaDB
 * stays ChromaDB and Mercury Bank becomes Mercury-Bank.
 *
 * Rules:
 *   - Whitespace runs → single hyphen
 *   - Strip filesystem-hostile chars: / \ : * ? " < > | and control chars
 *   - Collapse multiple hyphens to one
 *   - Trim leading / trailing hyphens
 *
 * Why dashes (not underscores like firm slugs): the orchestrator already
 * joins deal name + version with a hyphen ("Mercury-Bank-v0.0.1"). Keeping
 * the deal portion hyphen-friendly means the on-disk version path reads
 * as a single hyphen-segmented identifier instead of a mixed bag.
 */
export function dealSlug(input: string): string {
  // eslint-disable-next-line no-control-regex
  const stripped = input.replace(/[\/\\:*?"<>|\x00-\x1f]/g, '');
  const hyphenated = stripped.replace(/\s+/g, '-');
  const collapsed = hyphenated.replace(/-+/g, '-');
  return collapsed.replace(/^-+|-+$/g, '');
}
