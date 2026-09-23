/**
 * WorkspaceFs — the one interface the app talks to, with swappable backends.
 *
 * D-26 resolved to bring Tauri forward, so the native host is the first
 * implementation. The interface still stands, because a browser build has to
 * follow for anyone without the desktop app — and because writing the seam
 * before the second backend exists is the only time it is cheap.
 *
 * Paths are always workspace-relative. The host resolves them against the root
 * and rejects anything that escapes it; the frontend never handles an absolute
 * path, which is what keeps a traversal in a document from reaching your disk.
 */
export interface FsNode {
  name: string;
  path: string;
  is_dir: boolean;
  children: FsNode[];
}

export interface WorkspaceFs {
  readonly kind: 'tauri' | 'memory';
  root(): Promise<string>;
  tree(): Promise<FsNode[]>;
  read(path: string): Promise<string>;
  write(path: string, contents: string): Promise<void>;
}

/** Tauri exposes its bridge on the window before any app code runs. */
function inTauri(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

class TauriFs implements WorkspaceFs {
  readonly kind = 'tauri' as const;
  #root: string | null = null;

  async #invoke<T>(cmd: string, args: Record<string, unknown>): Promise<T> {
    const { invoke } = await import('@tauri-apps/api/core');
    return invoke<T>(cmd, args);
  }

  async root(): Promise<string> {
    if (this.#root === null) this.#root = await this.#invoke<string>('workspace_root', {});
    return this.#root;
  }
  async tree(): Promise<FsNode[]> {
    return this.#invoke<FsNode[]>('fs_tree', { root: await this.root() });
  }
  async read(path: string): Promise<string> {
    return this.#invoke<string>('fs_read', { root: await this.root(), path });
  }
  async write(path: string, contents: string): Promise<void> {
    return this.#invoke<void>('fs_write', { root: await this.root(), path, contents });
  }
}

/**
 * Browser fallback so `pnpm dev` still shows a working surface outside the
 * desktop app. It is explicitly NOT persistent — edits live for the session and
 * the UI says so, rather than pretending to save and losing the work.
 */
class MemoryFs implements WorkspaceFs {
  readonly kind = 'memory' as const;
  #files = new Map<string, string>([
    ['themes/lossless.css', ':root {\n  /* The desktop app reads this from disk. */\n}\n'],
    ['content/welcome.md', '## Running in a browser\n\nThis workspace is in memory. Launch the desktop app for real files.\n'],
  ]);
  async root() { return '(in-memory)'; }
  async tree(): Promise<FsNode[]> {
    const dirs = new Map<string, FsNode>();
    for (const path of this.#files.keys()) {
      const [dir, name] = path.split('/');
      if (!dirs.has(dir)) dirs.set(dir, { name: dir, path: dir, is_dir: true, children: [] });
      dirs.get(dir)!.children.push({ name, path, is_dir: false, children: [] });
    }
    return [...dirs.values()];
  }
  async read(path: string) {
    const f = this.#files.get(path);
    if (f === undefined) throw new Error(`not found: ${path}`);
    return f;
  }
  async write(path: string, contents: string) { this.#files.set(path, contents); }
}

export const workspaceFs: WorkspaceFs = inTauri() ? new TauriFs() : new MemoryFs();

/** Language mode key for the Source pane, by extension. */
export function languageOf(path: string): 'markdown' | 'css' | 'json' | 'yaml' | 'text' {
  const ext = path.slice(path.lastIndexOf('.') + 1).toLowerCase();
  if (ext === 'md' || ext === 'markdown') return 'markdown';
  if (ext === 'css') return 'css';
  if (ext === 'json') return 'json';
  if (ext === 'yaml' || ext === 'yml') return 'yaml';
  return 'text';
}

/** A theme is any .css living under the workspace-level themes/ folder (§5.6). */
export function isTheme(path: string): boolean {
  return path.startsWith('themes/') && path.endsWith('.css');
}
