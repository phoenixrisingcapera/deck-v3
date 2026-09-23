<script lang="ts">
  import { open } from '@tauri-apps/plugin-dialog';
  import { openUrl } from '@tauri-apps/plugin-opener';
  import { goto } from '$app/navigation';
  import { settings } from '$lib/stores/settings.svelte';
  import { flow } from '$lib/stores/flow.svelte';
  import { getTransport, type ApiError } from '$lib/transport';

  type FirmsResponse = { firms: string[] };

  const ORCHESTRATOR_REPO_URL = 'https://github.com/lossless-group/investment-memo-orchestrator';

  let firms = $state<string[]>([]);
  let loadingFirms = $state(false);
  let firmsError = $state<string | null>(null);

  async function openOrchestratorRepo() {
    await openUrl(ORCHESTRATOR_REPO_URL);
  }

  $effect(() => {
    if (!settings.loaded) {
      settings.load();
    }
  });

  $effect(() => {
    const path = settings.repoPath;
    if (path) {
      void loadFirms(path);
    } else {
      firms = [];
      firmsError = null;
    }
  });

  async function loadFirms(repoPath: string) {
    loadingFirms = true;
    firmsError = null;
    try {
      const res = await getTransport().request<FirmsResponse>(
        'GET',
        '/firms',
        { repoPath }
      );
      firms = res.firms;
      if (firms.length === 0) {
        firmsError = `No \`io/\` directory found at this path. Did you pick the orchestrator repo root?`;
      }
    } catch (e) {
      const err = e as ApiError;
      firmsError = err.message ?? 'Failed to load firms';
      firms = [];
    } finally {
      loadingFirms = false;
    }
  }

  async function browse() {
    const selected = await open({
      directory: true,
      multiple: false,
      title: 'Select the memopop-orchestrator repo root',
    });
    if (typeof selected === 'string') {
      await settings.setRepoPath(selected);
    }
  }

  // macOS .app bundles are technically directories that the OS presents as
  // single files. The native dialog handles them transparently when you
  // navigate into /Applications — no special flag needed beyond the
  // extension filter.
  async function pickApp(kind: 'editor' | 'notebook') {
    const title =
      kind === 'editor'
        ? 'Choose a markdown editor (.app)'
        : 'Choose a markdown notebook / workspace app (.app)';
    const selected = await open({
      directory: false,
      multiple: false,
      defaultPath: '/Applications',
      filters: [{ name: 'Applications', extensions: ['app'] }],
      title,
    });
    if (typeof selected !== 'string') return;
    if (kind === 'editor') await settings.setMarkdownEditor(selected);
    else await settings.setMarkdownNotebook(selected);
  }

  async function clearApp(kind: 'editor' | 'notebook') {
    if (kind === 'editor') await settings.setMarkdownEditor(null);
    else await settings.setMarkdownNotebook(null);
  }

  // Strip everything but the .app bundle name for display — paths get long
  // (/Applications/Visual Studio Code.app) and the bundle name is the
  // signal the user cares about.
  function appLabel(path: string | null): string {
    if (!path) return '';
    const segs = path.split('/');
    return segs[segs.length - 1] || path;
  }

  async function clearRepoPath() {
    await settings.setRepoPath(null);
  }

  async function selectFirm(firm: string | null) {
    await settings.setActiveFirm(firm);
  }
</script>

<section class="settings">
  <h1>Settings</h1>
  <p class="lede">
    The app's wiring. New users land here only by intent — onboarding lives on
    the home view.
  </p>

  <div class="field">
    <label for="repo-path" title="The local directory where you cloned the memopop-orchestrator (sibling of memopop-native in the monorepo)">Orchestrator repo path</label>
    <div class="row">
      <input
        id="repo-path"
        type="text"
        readonly
        value={settings.repoPath ?? ''}
        placeholder="Not set"
      />
      <button type="button" onclick={browse}>Browse…</button>
      {#if settings.repoPath}
        <button type="button" class="ghost" onclick={clearRepoPath}>Clear</button>
      {/if}
    </div>
    <p class="help">
      The directory where you cloned the orchestrator repo. The app finds the
      <code>io/</code> folder inside automatically.
      <button type="button" class="inline-link" onclick={openOrchestratorRepo}>
        Get the orchestrator&nbsp;↗
      </button>
    </p>
  </div>

  <div class="field">
    <label for="active-firm" title="Subdirectories under io/ are treated as firms">Active firm</label>
    <select
      id="active-firm"
      disabled={!settings.repoPath || loadingFirms || firms.length === 0}
      value={settings.activeFirm ?? ''}
      onchange={(e) => selectFirm((e.currentTarget as HTMLSelectElement).value || null)}
    >
      <option value="" disabled>
        {#if !settings.repoPath}
          Set the repo path first
        {:else if loadingFirms}
          Loading…
        {:else if firms.length === 0}
          No firms found
        {:else}
          Choose a firm
        {/if}
      </option>
      {#each firms as firm}
        <option value={firm}>{firm}</option>
      {/each}
    </select>
    {#if firmsError}
      <p class="error">{firmsError}</p>
    {/if}
  </div>

  {#if settings.activeFirm}
    <div class="active">
      Active: <strong>{settings.activeFirm}</strong>
    </div>
    <div class="brand-setup-row">
      <button
        type="button"
        class="brand-setup-btn"
        onclick={() => {
          flow.startBrandSetup(settings.activeFirm!);
          goto('/');
        }}
      >
        Brand setup →
      </button>
      <span class="brand-setup-hint">
        Auto-populate colors, fonts, and logo from your firm's website.
      </span>
    </div>
    <div class="brand-setup-row">
      <button
        type="button"
        class="brand-view-btn"
        onclick={() => goto('/brand')}
      >
        View brand config →
      </button>
      <span class="brand-setup-hint">
        Live design-system view of <code>brand-{settings.activeFirm}-config.yaml</code> — colors, logo, fonts. Edits save to YAML on blur.
      </span>
    </div>
  {/if}

  <hr class="divider" />

  <div class="field">
    <label for="md-editor" title="App used to open single .md files">Markdown editor</label>
    <div class="row">
      <input
        id="md-editor"
        type="text"
        readonly
        value={appLabel(settings.markdownEditor)}
        placeholder="Default — OS picks"
      />
      <button type="button" onclick={() => pickApp('editor')}>Choose…</button>
      {#if settings.markdownEditor}
        <button type="button" class="ghost" onclick={() => clearApp('editor')}>Clear</button>
      {/if}
    </div>
    <p class="help">
      Used when you click a <code>.md</code> file in a deal workspace. Pick
      <code>Obsidian.app</code>, <code>Typora.app</code>, <code>Cursor.app</code>,
      whatever your reading-and-editing app of choice is.
    </p>
  </div>

  <div class="field">
    <label for="md-notebook" title="App used to open a directory of markdown files">Markdown notebook / workspace</label>
    <div class="row">
      <input
        id="md-notebook"
        type="text"
        readonly
        value={appLabel(settings.markdownNotebook)}
        placeholder="Default — OS picks"
      />
      <button type="button" onclick={() => pickApp('notebook')}>Choose…</button>
      {#if settings.markdownNotebook}
        <button type="button" class="ghost" onclick={() => clearApp('notebook')}>Clear</button>
      {/if}
    </div>
    <p class="help">
      Default vault root: the entire firm folder
      (<code>io/{settings.activeFirm ?? '{firm}'}/</code>) — so you get
      cross-deal context, shared notes, brand configs, the whole knowledge
      graph in one place. The deal workspace exposes a smaller "just this
      version" escape hatch when you want to focus on a single run.
      For Obsidian: pick <code>Obsidian.app</code>. For VS Code / Cursor:
      same idea (opens the directory as a workspace).
    </p>
  </div>
</section>

<style>
  .settings {
    max-width: 640px;
    margin: 4rem auto;
    padding: 2rem;
    text-align: left;
  }

  h1 {
    font-size: 1.5rem;
    margin-bottom: 0.4rem;
  }

  .brand-setup-row {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid #f3f4f6;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .brand-setup-btn {
    background: #5b21b6;
    color: white;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font: inherit;
    font-weight: 500;
    cursor: pointer;
  }

  .brand-setup-btn:hover {
    background: #4c1d95;
  }

  .brand-view-btn {
    background: transparent;
    color: #5b21b6;
    border: 1px solid #5b21b6;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font: inherit;
    font-weight: 500;
    cursor: pointer;
  }

  .brand-view-btn:hover {
    background: #f5f3ff;
  }

  .brand-setup-hint code {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 0.85em;
    background: #f3f4f6;
    padding: 0.05rem 0.3rem;
    border-radius: 3px;
  }

  .brand-setup-hint {
    color: #6b7280;
    font-size: 0.82rem;
    flex: 1;
    min-width: 200px;
  }

  .lede {
    color: #6b7280;
    margin: 0 0 2rem;
    font-size: 0.95rem;
  }

  .field {
    margin-bottom: 1.5rem;
  }

  label {
    display: block;
    font-weight: 500;
    margin-bottom: 0.4rem;
    font-size: 0.95rem;
  }

  .row {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  input[type='text'],
  select {
    flex: 1;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    border: 1px solid #d0d0d0;
    font: inherit;
    background: white;
    color: #0f0f0f;
  }

  input[readonly] {
    background: #f6f6f6;
    cursor: default;
  }

  button {
    padding: 0.5rem 1rem;
    border-radius: 6px;
    border: 1px solid transparent;
    background: #396cd8;
    color: white;
    font: inherit;
    cursor: pointer;
  }

  button:hover {
    background: #2a52a8;
  }

  button.ghost {
    background: transparent;
    color: #555;
    border-color: #d0d0d0;
  }

  button.ghost:hover {
    background: #f0f0f0;
    color: #0f0f0f;
  }

  .help {
    font-size: 0.85rem;
    color: #666;
    margin-top: 0.4rem;
  }

  .divider {
    border: none;
    border-top: 1px solid #e5e7eb;
    margin: 2rem 0 1.5rem;
  }

  code {
    background: #f0f0f0;
    padding: 0 0.25rem;
    border-radius: 3px;
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 0.85em;
  }

  .error {
    color: #c0392b;
    font-size: 0.85rem;
    margin-top: 0.4rem;
  }

  .active {
    margin-top: 2rem;
    padding: 0.75rem 1rem;
    background: #e8f5e9;
    border-radius: 6px;
    font-size: 0.9rem;
  }







  button.inline-link {
    background: transparent;
    border: none;
    padding: 0;
    color: #5b21b6;
    font: inherit;
    cursor: pointer;
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  button.inline-link:hover {
    background: transparent;
    color: #4c1d95;
    border: none;
  }

  button.inline-link {
    margin-left: 0.4rem;
    font-size: 0.85rem;
  }

  @media (prefers-color-scheme: dark) {
    input[type='text'],
    select {
      background: #1f1f1f;
      color: #f6f6f6;
      border-color: #444;
    }

    input[readonly] {
      background: #161616;
    }

    button.ghost {
      color: #ccc;
      border-color: #444;
    }

    button.ghost:hover {
      background: #2a2a2a;
      color: #f6f6f6;
    }

    code {
      background: #2a2a2a;
    }

    .help {
      color: #aaa;
    }

    .divider {
      border-top-color: #2a2a2c;
    }

    .active {
      background: #1e3a23;
      color: #c8e6c9;
    }




    button.inline-link {
      color: #c4b5fd;
    }

    button.inline-link:hover {
      color: #ddd6fe;
    }
  }
</style>
