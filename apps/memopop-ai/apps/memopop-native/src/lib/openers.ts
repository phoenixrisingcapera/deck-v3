/**
 * Smart `openPath` wrapper that honors the user's preferred markdown editor
 * (single .md files) and markdown notebook / workspace app (directories).
 *
 * `openPath(path, withApp?)` from @tauri-apps/plugin-opener takes an optional
 * second argument that on macOS maps to `open -a {with} {path}`. We pick the
 * right `with` based on the target shape and the user's settings; if neither
 * preference is set or the target shape doesn't match, we fall through to
 * the OS default handler (the same behavior as plain openPath).
 */

import { openPath, openUrl, revealItemInDir } from '@tauri-apps/plugin-opener';
import { settings } from '$lib/stores/settings.svelte';
import { getTransport } from '$lib/transport';

const MARKDOWN_EXTENSIONS = ['md', 'mdx', 'markdown'];

export interface OpenOptions {
  /** Treat the path as a directory regardless of its on-disk shape. */
  isDir?: boolean;
}

function isMarkdownPath(path: string): boolean {
  const dot = path.lastIndexOf('.');
  if (dot < 0) return false;
  const ext = path.slice(dot + 1).toLowerCase();
  return MARKDOWN_EXTENSIONS.includes(ext);
}

/**
 * Open a path with the user's preferred app when applicable, or the OS
 * default otherwise. Throws on launch failure (caller should surface).
 */
export async function openWithPreferred(
  path: string,
  opts: OpenOptions = {}
): Promise<void> {
  const isDir = opts.isDir === true;
  const isMd = !isDir && isMarkdownPath(path);

  let withApp: string | undefined;
  if (isDir && settings.markdownNotebook) {
    withApp = settings.markdownNotebook;
  } else if (isMd && settings.markdownEditor) {
    withApp = settings.markdownEditor;
  }

  // openPath's second param is optional; passing undefined uses the OS default.
  await openPath(path, withApp);
}

interface ObsidianVaultInfo {
  vault_root: string;
  vault_name: string;
  /** POSIX-style path relative to vault root. May be empty if `path` is the vault root. */
  rel_path: string;
}

/**
 * Reveal an absolute path in its enclosing Obsidian vault when one exists,
 * otherwise fall back to revealing the item in Finder.
 *
 * `open -a Obsidian <arbitrary-folder>` silently no-ops for non-vault
 * folders, which is why we have to detect the vault and use the
 * `obsidian://open?vault=…&file=…` URI scheme instead. `?file=` accepts a
 * note path; for folders, opening the vault alone is the best we can do
 * since the URI scheme has no "reveal folder" verb. Callers with a known
 * headline file inside a target folder can pass `preferFileInDir` to land
 * the user on something useful.
 */
export async function revealInVaultOrFinder(
  absPath: string,
  opts: { preferFileInDir?: string } = {}
): Promise<void> {
  const vault = await getTransport().request<ObsidianVaultInfo | null>(
    'GET',
    '/local/obsidian-vault',
    { path: absPath }
  );

  if (vault && vault.vault_name) {
    const fileRel = opts.preferFileInDir
      ? (vault.rel_path ? `${vault.rel_path}/${opts.preferFileInDir}` : opts.preferFileInDir)
      : vault.rel_path;
    const params = new URLSearchParams({ vault: vault.vault_name });
    if (fileRel) params.set('file', fileRel);
    await openUrl(`obsidian://open?${params.toString()}`);
    return;
  }

  await revealItemInDir(absPath);
}
