import { Store } from '@tauri-apps/plugin-store';
import { getTransport } from '$lib/transport';

const STORE_FILE = 'settings.json';

class SettingsState {
  repoPath = $state<string | null>(null);
  activeFirm = $state<string | null>(null);
  // Optional .app bundle path used to open markdown files (single .md) and
  // markdown-aware folder/vault containers (a deal output_dir, an Obsidian
  // vault). Both are absolute paths to a .app bundle on macOS; on other
  // platforms they'd be the executable path. Empty/null → fall back to the
  // OS default handler for the file or directory.
  markdownEditor = $state<string | null>(null);
  markdownNotebook = $state<string | null>(null);
  loaded = $state(false);

  #store: Store | null = null;

  async load() {
    if (this.loaded) return;
    this.#store = await Store.load(STORE_FILE);
    this.repoPath = (await this.#store.get<string>('repoPath')) ?? null;
    this.activeFirm = (await this.#store.get<string>('activeFirm')) ?? null;
    this.markdownEditor = (await this.#store.get<string>('markdownEditor')) ?? null;
    this.markdownNotebook = (await this.#store.get<string>('markdownNotebook')) ?? null;

    // Auto-seed the sibling orchestrator path when nothing is saved. Only
    // resolves on dev installs (Rust uses CARGO_MANIFEST_DIR at compile time);
    // release builds shipped elsewhere fall through to the manual Browse flow.
    if (this.repoPath === null) {
      try {
        const res = await getTransport().request<{ path: string | null }>(
          'GET',
          '/defaults/orchestrator-path',
        );
        if (res.path) {
          this.repoPath = res.path;
          await this.#store.set('repoPath', res.path);
          await this.#store.save();
        }
      } catch {
        // Non-fatal — user can still set it via Settings.
      }
    }

    this.loaded = true;
  }

  async setRepoPath(path: string | null) {
    const changed = path !== this.repoPath;
    this.repoPath = path;
    if (changed) {
      this.activeFirm = null;
      await this.#store?.delete('activeFirm');
    }
    if (path === null) {
      await this.#store?.delete('repoPath');
    } else {
      await this.#store?.set('repoPath', path);
    }
    await this.#store?.save();
  }

  async setActiveFirm(firm: string | null) {
    this.activeFirm = firm;
    if (firm === null) {
      await this.#store?.delete('activeFirm');
    } else {
      await this.#store?.set('activeFirm', firm);
    }
    await this.#store?.save();
  }

  async setMarkdownEditor(path: string | null) {
    this.markdownEditor = path;
    if (path === null) {
      await this.#store?.delete('markdownEditor');
    } else {
      await this.#store?.set('markdownEditor', path);
    }
    await this.#store?.save();
  }

  async setMarkdownNotebook(path: string | null) {
    this.markdownNotebook = path;
    if (path === null) {
      await this.#store?.delete('markdownNotebook');
    } else {
      await this.#store?.set('markdownNotebook', path);
    }
    await this.#store?.save();
  }
}

export const settings = new SettingsState();
