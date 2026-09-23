<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { openPath } from '@tauri-apps/plugin-opener';
  import { settings } from '$lib/stores/settings.svelte';
  import { outlines } from '$lib/stores/outlines.svelte';
  import { flow } from '$lib/stores/flow.svelte';
  import { getTransport } from '$lib/transport';
  import { openWithPreferred, revealInVaultOrFinder } from '$lib/openers';
  import SourceApproval from '$lib/components/SourceApproval.svelte';
  import type { Outline } from '$lib/types';

  interface Props {
    firm: string;
    deal: string;
  }

  let { firm, deal }: Props = $props();

  interface Version {
    name: string;
    output_dir: string;
    last_modified_ms: number;
  }

  interface FileInfo {
    path: string;
    size: number;
  }

  let versions = $state<Version[]>([]);
  let selectedVersion = $state<string | null>(null);
  let files = $state<FileInfo[]>([]);
  let outputDir = $state<string | null>(null);

  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let collapsed = $state<Set<string>>(new Set());

  interface CurationResult {
    output_dir: string;
    versions_scanned: string[];
    total_unique_sources: number;
    total_section_entries: number;
    sections: { number: string; slug: string; source_count: number }[];
  }

  let curating = $state(false);
  let curationResult = $state<CurationResult | null>(null);
  let curationError = $state<string | null>(null);

  // Source approval for an already-saved deal. Distinct from the create-deal
  // flow's `approving_sources` stage — same surface, reached from a deal that
  // already exists on disk, so it commits and closes rather than advancing a
  // journey.
  let approvingSources = $state(false);

  // Deal config (the on-disk deal.json or {deal}.json). Loaded once on mount;
  // used by the "Run MemoPop" action to replay all fields to /memos with full
  // fidelity instead of running with bare defaults.
  interface DealConfig {
    type?: 'direct' | 'fund';
    mode?: 'consider' | 'justify';
    outline?: string;
    scorecard?: string;
    url?: string;
    description?: string;
    stage?: string;
    notes?: string;
    deck?: string;
    dataroom?: string;
    trademark_light?: string;
    trademark_dark?: string;
  }
  let dealConfig = $state<DealConfig | null>(null);
  let dealConfigError = $state<string | null>(null);
  let running = $state(false);
  let runError = $state<string | null>(null);
  // Resume is for the "ran-and-died-mid-flight" case: app crashed, laptop slept,
  // sidecar killed. The orchestrator's resume CLI walks the latest output_dir
  // for checkpoints and picks up from the last completed phase. We always offer
  // the button when versions exist; the backend gracefully refuses if there's
  // nothing to resume ("No resumable checkpoints found — start a fresh run").
  let resuming = $state(false);
  let resumeError = $state<string | null>(null);

  // Export: branded HTML + PDF via cli/export_branded.py. Targets the currently
  // selected version (not necessarily the latest). Default mode is dark, which
  // matches the script default and is what most VC memos ship as.
  interface ExportResult {
    exports_dir: string;
    html_path: string | null;
    pdf_path: string | null;
    mode: 'light' | 'dark';
    version: string | null;
  }
  let exporting = $state(false);
  let exportError = $state<string | null>(null);
  let exportResult = $state<ExportResult | null>(null);
  let exportMode = $state<'light' | 'dark'>('dark');

  // Editable overrides for this run. Initialized from the on-disk deal config
  // the moment it loads, then the user can change them before clicking Run.
  // We deliberately don't write back to disk — this is per-run intent, not a
  // config edit. (For permanent changes, edit the deal's JSON directly.)
  let selectedOutlineId = $state<string | null>(null);
  let selectedMode = $state<'consider' | 'justify'>('consider');

  // Restrict the outline dropdown to outlines compatible with this deal's
  // investment type — picking a fund-commitment outline for a direct deal
  // would silently produce a broken memo. The outline_type field is the
  // discriminator emitted by the sidecar's /outlines endpoint.
  let compatibleOutlines = $derived.by(() => {
    const wantFund = dealConfig?.type === 'fund';
    return outlines.outlines.filter((o) =>
      wantFund ? o.outline_type === 'fund_commitment' : o.outline_type !== 'fund_commitment'
    );
  });

  // Initial load: pull versions, then fetch the most recent (or ?v= override).
  // Also kick off (in parallel) the deal-config + outlines fetches the "Run
  // MemoPop" button needs — we want the button enabled by the time the page
  // settles, not after the user clicks it.
  onMount(async () => {
    if (!settings.repoPath) return;
    void loadDealConfig();
    void outlines.load(settings.repoPath);
    await loadVersions();
    const requested = page.url.searchParams.get('v');
    if (requested && versions.some((v) => v.name === requested)) {
      selectedVersion = requested;
    } else if (versions.length > 0) {
      selectedVersion = versions[0].name;
    }
    if (selectedVersion) {
      await loadFiles(selectedVersion);
    }
    loading = false;
  });

  async function loadDealConfig() {
    try {
      const result = await getTransport().request<{ config: DealConfig }>(
        'GET',
        `/firms/${encodeURIComponent(firm)}/deals/${encodeURIComponent(deal)}/config`,
        { repoPath: settings.repoPath }
      );
      dealConfig = result.config;
      // Seed the editable overrides from disk. The user can still change
      // either before they click Run; we only persist on disk if they edit
      // the JSON directly.
      selectedOutlineId = result.config.outline ?? null;
      selectedMode = result.config.mode === 'justify' ? 'justify' : 'consider';
    } catch (e) {
      // Don't surface as a fatal page error — the workspace still works for
      // browsing artifacts even if the deal config is missing. Only the Run
      // button cares, and it'll show its own message when clicked.
      dealConfigError =
        (e as { message?: string })?.message ?? 'Failed to load deal config';
    }
  }

  // The /memos POST needs an outline_name; flow.markRunning needs the full
  // Outline object for JobView's header. Resolve it from the outlines store
  // (loaded on mount) by id-match. Falls back to a synthesized stub if not
  // found so the run still proceeds — JobView degrades gracefully.
  function findOutline(id: string | undefined) {
    if (!id) return null;
    return outlines.outlines.find((o) => o.id === id) ?? null;
  }

  async function runMemoPop() {
    if (running) return;
    runError = null;
    if (!settings.repoPath) {
      runError = 'Orchestrator path not set. Open Settings to anchor the repo.';
      return;
    }
    if (!dealConfig) {
      runError =
        dealConfigError ??
        'Deal config not loaded yet — give it a moment, then try again.';
      return;
    }
    const outlineId = selectedOutlineId ?? dealConfig.outline;
    const outline = findOutline(outlineId);
    if (!outline) {
      runError = outlineId
        ? `Outline "${outlineId}" not found in this firm's outlines.`
        : 'Pick an outline before running.';
      return;
    }
    const investmentType =
      dealConfig.type === 'fund' ? 'fund' : 'direct';
    const mode: 'consider' | 'justify' = selectedMode;

    running = true;
    try {
      const result = await getTransport().request<{ job_id: string; status: string }>(
        'POST',
        '/memos',
        {
          repoPath: settings.repoPath,
          company_name: deal,
          firm,
          company_url: dealConfig.url || undefined,
          company_description: dealConfig.description || undefined,
          company_stage: dealConfig.stage || undefined,
          research_notes: dealConfig.notes || undefined,
          investment_type: investmentType,
          memo_mode: mode,
          deck_path: dealConfig.deck || undefined,
          dataroom_path: dealConfig.dataroom || undefined,
          company_trademark_light: dealConfig.trademark_light || undefined,
          company_trademark_dark: dealConfig.trademark_dark || undefined,
          outline_name: outline.id,
          scorecard_name: dealConfig.scorecard || undefined,
        }
      );
      // Hand off to the same JobView path the onboarding flow uses — root
      // +page.svelte renders JobView whenever flow.stage.kind === 'running_job'.
      flow.markRunning(
        outline,
        {
          companyUrl: dealConfig.url ?? '',
          companyName: deal,
          deckPath: dealConfig.deck ?? null,
          mode,
        },
        result.job_id
      );
      await goto('/');
    } catch (e) {
      runError =
        (e as { message?: string })?.message ?? 'Failed to start memo generation';
    } finally {
      running = false;
    }
  }

  async function exportMemo() {
    if (exporting) return;
    exportError = null;
    exportResult = null;
    if (!settings.repoPath) {
      exportError = 'Orchestrator path not set. Open Settings to anchor the repo.';
      return;
    }
    if (!selectedVersion) {
      exportError = 'Pick a version first.';
      return;
    }
    exporting = true;
    try {
      exportResult = await getTransport().request<ExportResult>(
        'POST',
        '/actions/export-memo',
        {
          repoPath: settings.repoPath,
          firm,
          deal,
          version: selectedVersion,
          mode: exportMode,
          pdf: true,
        }
      );
    } catch (e) {
      exportError = (e as { message?: string })?.message ?? 'Export failed';
    } finally {
      exporting = false;
    }
  }

  async function revealExportFile(path: string | null) {
    if (!path) return;
    try {
      await openPath(path);
    } catch (e) {
      exportError = `Couldn't open ${path}: ${e}`;
    }
  }

  async function resumeLatest() {
    if (resuming) return;
    resumeError = null;
    if (!settings.repoPath) {
      resumeError = 'Orchestrator path not set. Open Settings to anchor the repo.';
      return;
    }
    // Outline is needed for JobView's header; resume itself doesn't need it
    // server-side (the checkpoint reconstruction reads the deal config from
    // disk). Fall back to a synthesized stub so resume still works even if
    // outlines store hasn't loaded yet.
    const outlineId = selectedOutlineId ?? dealConfig?.outline;
    const outline =
      findOutline(outlineId) ??
      ({
        id: outlineId ?? 'unknown',
        title: outlineId ?? 'Resumed run',
        outline_type: dealConfig?.type === 'fund' ? 'fund_commitment' : 'direct_investment',
        type_label: '',
        description: '',
        section_count: 0,
        compatible_modes: [],
        firm: null,
        version: null,
      } as Outline);

    resuming = true;
    try {
      const result = await getTransport().request<{ job_id: string; status: string }>(
        'POST',
        '/memos/resume',
        {
          repoPath: settings.repoPath,
          firm,
          company_name: deal,
        }
      );
      flow.markRunning(
        outline,
        {
          companyUrl: dealConfig?.url ?? '',
          companyName: deal,
          deckPath: dealConfig?.deck ?? null,
          mode: selectedMode,
        },
        result.job_id
      );
      await goto('/');
    } catch (e) {
      resumeError =
        (e as { message?: string })?.message ?? 'Failed to start resume';
    } finally {
      resuming = false;
    }
  }

  async function loadVersions() {
    try {
      const result = await getTransport().request<{ versions: Version[] }>(
        'GET',
        `/firms/${encodeURIComponent(firm)}/deals/${encodeURIComponent(deal)}/versions`,
        { repoPath: settings.repoPath }
      );
      versions = result.versions;
    } catch (e) {
      loadError = (e as { message?: string })?.message ?? 'Failed to load versions';
    }
  }

  async function loadFiles(version: string) {
    try {
      const result = await getTransport().request<{
        version_dir: string;
        files: FileInfo[];
      }>(
        'GET',
        `/firms/${encodeURIComponent(firm)}/deals/${encodeURIComponent(deal)}/versions/${encodeURIComponent(version)}/files`,
        { repoPath: settings.repoPath }
      );
      outputDir = result.version_dir;
      files = result.files;
    } catch (e) {
      loadError = (e as { message?: string })?.message ?? 'Failed to load files';
      files = [];
    }
  }

  async function selectVersion(name: string) {
    selectedVersion = name;
    files = [];
    // Reflect in URL so reloads / shares preserve the choice.
    const url = new URL(page.url);
    url.searchParams.set('v', name);
    history.replaceState(null, '', url.toString());
    await loadFiles(name);
  }

  // The firm directory is the natural Obsidian vault — its configs/, all
  // deals/, assets/, brand setup, etc. live under one root. Opening the
  // firm gives the user the full knowledge-graph context (cross-deal links,
  // shared notes), which is the whole point of a markdown notebook.
  // The deal's version dir is still openable as a secondary action below.
  let firmDir = $derived(
    settings.repoPath ? `${settings.repoPath}/io/${firm}` : null
  );

  // Always Finder — the "Open in Finder" button promises Finder, not the
  // user's preferred app. Keeps that contract regardless of notebook prefs.
  async function revealOutputDir() {
    if (!outputDir) return;
    try {
      await openPath(outputDir);
    } catch (e) {
      loadError = `Couldn't open: ${e}`;
    }
  }

  // Default notebook open: the FIRM, not the version. Cross-deal context is
  // the value of using a notebook; opening one version dir misses that.
  async function openFirmInNotebook() {
    if (!firmDir) return;
    try {
      await revealInVaultOrFinder(firmDir);
    } catch (e) {
      loadError = `Couldn't open firm in notebook: ${e}`;
    }
  }

  // Cross-version curation: walks every outputs/{deal}-v*/3-source-catalog,
  // dedupes by URL per section, keeps the highest-ranked status, drops
  // hallucinated/invalid. Writes a single best-of-sources/ under exports/.
  // The result banner sticks around with a button to reveal the dir — we
  // don't auto-load it into the version tree because it's deal-level, not
  // version-scoped.
  async function curateBestSources() {
    if (!settings.repoPath || curating) return;
    curating = true;
    curationError = null;
    curationResult = null;
    try {
      curationResult = await getTransport().request<CurationResult>(
        'POST',
        '/actions/curate-sources',
        { repoPath: settings.repoPath, firm, deal }
      );
    } catch (e) {
      curationError =
        (e as { message?: string })?.message ?? 'Failed to curate sources';
    } finally {
      curating = false;
    }
  }

  async function revealCurationDir() {
    if (!curationResult?.output_dir) return;
    try {
      await revealInVaultOrFinder(curationResult.output_dir, {
        preferFileInDir: 'Master-Sources.md',
      });
    } catch (e) {
      console.error('revealCurationDir failed', e);
      curationError = `Couldn't open ${curationResult.output_dir}: ${e}`;
    }
  }

  // Escape hatch: open just the current version dir in the notebook. Useful
  // when collaborating on one deal without distracting cross-deal context.
  async function openVersionInNotebook() {
    if (!outputDir) return;
    try {
      await revealInVaultOrFinder(outputDir);
    } catch (e) {
      loadError = `Couldn't open version in notebook: ${e}`;
    }
  }

  // File clicks honor the markdown-editor preference for .md files. Other
  // extensions go through the OS default (image previews, etc.).
  async function openFile(rel: string) {
    if (!outputDir) return;
    const abs = `${outputDir}/${rel}`;
    try {
      await openWithPreferred(abs);
    } catch (e) {
      loadError = `Couldn't open ${rel}: ${e}`;
    }
  }

  function toggleFolder(folderPath: string) {
    const next = new Set(collapsed);
    if (next.has(folderPath)) next.delete(folderPath);
    else next.add(folderPath);
    collapsed = next;
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  function formatRelTime(ms: number): string {
    const diff = Date.now() - ms;
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    return new Date(ms).toLocaleDateString();
  }

  // ----- Tree construction (mirrors ArtifactBrowser's logic) -----

  type FileNode = { kind: 'file'; name: string; fullPath: string; size: number };
  type FolderNode = {
    kind: 'folder';
    name: string;
    fullPath: string;
    children: TreeNode[];
  };
  type TreeNode = FileNode | FolderNode;

  function buildTree(items: FileInfo[]): TreeNode[] {
    const root: FolderNode = { kind: 'folder', name: '', fullPath: '', children: [] };
    for (const f of items) {
      const parts = f.path.split('/').filter(Boolean);
      let cursor: FolderNode = root;
      for (let i = 0; i < parts.length; i++) {
        const name = parts[i];
        const isFile = i === parts.length - 1;
        const fullPath = parts.slice(0, i + 1).join('/');
        let child: TreeNode | undefined = cursor.children.find((c) => c.name === name);
        if (!child) {
          child = isFile
            ? { kind: 'file', name, fullPath, size: f.size }
            : { kind: 'folder', name, fullPath, children: [] };
          cursor.children.push(child);
        }
        if (child.kind === 'folder') cursor = child;
      }
    }
    sortFolder(root);
    return root.children;
  }

  function sortFolder(folder: FolderNode) {
    folder.children.sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === 'folder' ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    for (const c of folder.children) {
      if (c.kind === 'folder') sortFolder(c);
    }
  }

  type FlatRow = { node: TreeNode; depth: number };

  function flatten(nodes: TreeNode[], depth: number, out: FlatRow[]) {
    for (const n of nodes) {
      out.push({ node: n, depth });
      if (n.kind === 'folder' && !collapsed.has(n.fullPath)) {
        flatten(n.children, depth + 1, out);
      }
    }
  }

  function folderFileCount(node: TreeNode): number {
    if (node.kind !== 'folder') return 0;
    let count = 0;
    for (const c of node.children) {
      if (c.kind === 'file') count++;
      else count += folderFileCount(c);
    }
    return count;
  }

  let tree = $derived(buildTree(files));
  let rows = $derived.by(() => {
    const out: FlatRow[] = [];
    flatten(tree, 0, out);
    return out;
  });
</script>

{#if approvingSources}
  <!-- Takes over the workspace rather than opening a modal: the same list
       work as in the create-deal flow, so it gets the same room. -->
  <SourceApproval
    {firm}
    {deal}
    showSkip={false}
    onBack={() => (approvingSources = false)}
    onDone={() => (approvingSources = false)}
  />
{:else}
<section class="page">
  <header class="head">
    <div class="head-lead">
      <button
        type="button"
        class="back-icon"
        onclick={() => goto('/')}
        aria-label="Back to deals"
        title="Back to deals"
      >←</button>
      <div class="title-block">
        <h1>{deal}</h1>
        <p class="subtitle">
          <code>{firm}</code>
          {#if versions.length > 0}
            <span class="sep" aria-hidden="true">·</span>
            <span>{versions.length} {versions.length === 1 ? 'version' : 'versions'}</span>
          {/if}
        </p>
      </div>
    </div>

    <div class="head-actions">
      {#if versions.length > 0}
        <select
          class="version-select"
          value={selectedVersion ?? ''}
          onchange={(e) => selectVersion((e.currentTarget as HTMLSelectElement).value)}
          disabled={loading}
          aria-label="Select version"
        >
          {#each versions as v (v.name)}
            <option value={v.name}>
              {v.name} · {formatRelTime(v.last_modified_ms)}
            </option>
          {/each}
        </select>
      {/if}
      <button
        type="button"
        class="run-btn"
        onclick={runMemoPop}
        disabled={running || resuming || !dealConfig}
        title={dealConfig
          ? `Run MemoPop on ${deal} using the on-disk deal config (outline: ${dealConfig.outline ?? 'unset'})`
          : 'Loading deal config…'}
      >
        {#if running}
          <span class="curate-spinner" aria-hidden="true">⏳</span> Starting…
        {:else}
          <span aria-hidden="true">▶</span> Run MemoPop
        {/if}
      </button>
      {#if versions.length > 0}
        <button
          type="button"
          class="resume-btn"
          onclick={resumeLatest}
          disabled={resuming || running}
          title="Resume the latest run from its last on-disk checkpoint. Useful when the laptop slept or the sidecar died mid-run."
        >
          {#if resuming}
            <span class="curate-spinner" aria-hidden="true">⏳</span> Resuming…
          {:else}
            <span aria-hidden="true">↻</span> Resume latest
          {/if}
        </button>
      {/if}
      {#if versions.length > 0}
        <div class="export-group" role="group" aria-label="Export memo">
          <select
            class="export-mode"
            bind:value={exportMode}
            disabled={exporting}
            aria-label="Export mode"
            title="Light or dark theme for the exported memo"
          >
            <option value="dark">dark</option>
            <option value="light">light</option>
          </select>
          <button
            type="button"
            class="export-btn"
            onclick={exportMemo}
            disabled={exporting || !selectedVersion}
            title="Render the selected version to branded HTML + PDF under exports/{exportMode}/"
          >
            {#if exporting}
              <span class="curate-spinner" aria-hidden="true">⏳</span> Exporting…
            {:else}
              <span aria-hidden="true">📤</span> Export HTML + PDF
            {/if}
          </button>
        </div>
      {/if}
      <!-- Approve sources BEFORE a run: the analyst's set is what the
           membership gate enforces. Distinct from "Curate Best Sources",
           which merges 3-source-catalog/ across *completed* runs and is
           therefore unavailable until at least one run has produced one. -->
      <button
        type="button"
        class="approve-btn"
        onclick={() => (approvingSources = true)}
        title="Review and approve the sources this deal's memo may cite"
      >
        <span aria-hidden="true">📋</span> Approve Sources
      </button>
      <button
        type="button"
        class="curate-btn"
        onclick={curateBestSources}
        disabled={curating || versions.length === 0}
        title="Merge every completed run's 3-source-catalog/ into one best-of set. Requires at least one run that got far enough to produce a catalog — to approve sources before a run, use Approve Sources."
      >
        {#if curating}
          <span class="curate-spinner" aria-hidden="true">⏳</span> Curating…
        {:else}
          <span aria-hidden="true">✨</span> Curate Best Sources
        {/if}
      </button>
      <div class="icon-group" role="group" aria-label="Open this deal">
        <button
          type="button"
          class="icon-btn"
          onclick={revealOutputDir}
          disabled={!outputDir}
          aria-label="Reveal in Finder"
          title="Reveal this version's folder in Finder"
        >
          <span aria-hidden="true">📁</span>
        </button>
        {#if settings.markdownNotebook}
          {@const notebookName = (settings.markdownNotebook.split('/').pop() ?? '').replace(/\.app$/, '')}
          <button
            type="button"
            class="icon-btn icon-btn--accent"
            onclick={openFirmInNotebook}
            disabled={!firmDir}
            aria-label="Open in {notebookName}"
            title="Open the entire {firm} firm folder as a {notebookName} vault — cross-deal links, shared notes, brand configs, one knowledge graph."
          >
            <span aria-hidden="true">📓</span>
          </button>
        {/if}
      </div>
    </div>
  </header>

  {#if loading}
    <div class="empty">Loading workspace…</div>
  {:else if loadError}
    <div class="empty error">{loadError}</div>
  {:else if versions.length === 0}
    <div class="empty">
      <strong>No runs yet for {deal}.</strong>
      <p class="hint">Generate a memo from this deal's outline to see artifacts here.</p>
      <div class="empty-cta">
        <button
          type="button"
          class="run-btn run-btn--large"
          onclick={runMemoPop}
          disabled={running || !dealConfig}
          title={dealConfig
            ? `Run MemoPop on ${deal} using the on-disk deal config`
            : 'Loading deal config…'}
        >
          {#if running}
            <span class="curate-spinner" aria-hidden="true">⏳</span> Starting…
          {:else}
            <span aria-hidden="true">▶</span> Run MemoPop on {deal}
          {/if}
        </button>
        {#if dealConfig}
          <div class="empty-controls">
            <label class="empty-control">
              <span>Outline</span>
              <select
                bind:value={selectedOutlineId}
                disabled={running || outlines.loading || compatibleOutlines.length === 0}
                aria-label="Outline"
              >
                {#if selectedOutlineId && !compatibleOutlines.some((o) => o.id === selectedOutlineId)}
                  <option value={selectedOutlineId}>{selectedOutlineId} (not in this firm)</option>
                {/if}
                {#each compatibleOutlines as o (o.id)}
                  <option value={o.id}>{o.id}</option>
                {/each}
              </select>
            </label>
            <label class="empty-control">
              <span>Mode</span>
              <select
                bind:value={selectedMode}
                disabled={running}
                aria-label="Mode"
              >
                <option value="consider">consider</option>
                <option value="justify">justify</option>
              </select>
            </label>
            {#if dealConfig.deck}
              <div class="empty-control deck-readonly">
                <span>Deck</span>
                <code>{(dealConfig.deck.split('/').pop()) ?? dealConfig.deck}</code>
              </div>
            {/if}
          </div>
        {/if}
        {#if runError}
          <p class="empty-error">{runError}</p>
        {/if}
        {#if dealConfigError}
          <p class="empty-error">Deal config: {dealConfigError}</p>
        {/if}
      </div>
    </div>
  {:else if !selectedVersion}
    <div class="empty">Pick a version above.</div>
  {:else}
    {#if curationResult}
      <div class="curation-banner success">
        <div class="curation-summary">
          <strong>✨ {curationResult.total_unique_sources} unique sources</strong>
          (collapsed from {curationResult.total_section_entries} per-section entries)
          across {curationResult.sections.length} sections, from
          {curationResult.versions_scanned.length} versions. See
          <code>Master-Sources.md</code> for the headline list. Validity not yet
          checked — soft-404s and paywall stubs may still be present.
        </div>
        <div class="curation-actions">
          <button type="button" class="banner-action" onclick={revealCurationDir}>
            <span aria-hidden="true">📁</span> Open best-of-sources/
          </button>
          <button
            type="button"
            class="banner-dismiss"
            onclick={() => (curationResult = null)}
            aria-label="Dismiss"
          >×</button>
        </div>
      </div>
    {/if}
    {#if curationError}
      <div class="curation-banner error">
        <span>{curationError}</span>
        <button
          type="button"
          class="banner-dismiss"
          onclick={() => (curationError = null)}
          aria-label="Dismiss"
        >×</button>
      </div>
    {/if}
    {#if runError}
      <div class="curation-banner error">
        <span>Run MemoPop: {runError}</span>
        <button
          type="button"
          class="banner-dismiss"
          onclick={() => (runError = null)}
          aria-label="Dismiss"
        >×</button>
      </div>
    {/if}
    {#if resumeError}
      <div class="curation-banner error">
        <span>Resume: {resumeError}</span>
        <button
          type="button"
          class="banner-dismiss"
          onclick={() => (resumeError = null)}
          aria-label="Dismiss"
        >×</button>
      </div>
    {/if}
    {#if exportResult}
      <div class="curation-banner success">
        <div class="curation-summary">
          <strong>📤 Exported {exportResult.version ?? ''} ({exportResult.mode})</strong> —
          {#if exportResult.pdf_path && exportResult.html_path}
            HTML + PDF written to <code>exports/{exportResult.mode}/</code>.
          {:else if exportResult.html_path}
            HTML written to <code>exports/{exportResult.mode}/</code> (PDF failed — check brand config / WeasyPrint deps).
          {:else}
            See <code>exports/{exportResult.mode}/</code> for output.
          {/if}
        </div>
        <div class="curation-actions">
          {#if exportResult.pdf_path}
            <button
              type="button"
              class="banner-action"
              onclick={() => revealExportFile(exportResult?.pdf_path ?? null)}
            >
              <span aria-hidden="true">📄</span> Open PDF
            </button>
          {/if}
          {#if exportResult.html_path}
            <button
              type="button"
              class="banner-action"
              onclick={() => revealExportFile(exportResult?.html_path ?? null)}
            >
              <span aria-hidden="true">🌐</span> Open HTML
            </button>
          {/if}
          <button
            type="button"
            class="banner-action"
            onclick={() => revealExportFile(exportResult?.exports_dir ?? null)}
          >
            <span aria-hidden="true">📁</span> Folder
          </button>
          <button
            type="button"
            class="banner-dismiss"
            onclick={() => (exportResult = null)}
            aria-label="Dismiss"
          >×</button>
        </div>
      </div>
    {/if}
    {#if exportError}
      <div class="curation-banner error">
        <span>Export: {exportError}</span>
        <button
          type="button"
          class="banner-dismiss"
          onclick={() => (exportError = null)}
          aria-label="Dismiss"
        >×</button>
      </div>
    {/if}
    <div class="content">
      <header class="content-head">
        <span class="version-badge">{selectedVersion}</span>
        <span class="file-count">
          {files.length} {files.length === 1 ? 'file' : 'files'}
        </span>
        {#if settings.markdownNotebook && outputDir}
          {@const notebookName = (settings.markdownNotebook.split('/').pop() ?? '').replace(/\.app$/, '')}
          <button
            type="button"
            class="notebook-version-link"
            onclick={openVersionInNotebook}
            title="Open just this version's folder (without the rest of the firm)"
          >
            📓 just this version →
          </button>
        {/if}
        {#if outputDir}
          <code class="path">{outputDir}</code>
        {/if}
      </header>

      <div class="tree">
        {#if rows.length === 0}
          <div class="empty">
            <p>No files in this version.</p>
          </div>
        {:else}
          {#each rows as { node, depth } (node.fullPath)}
            {#if node.kind === 'folder'}
              <button
                type="button"
                class="row folder"
                style:padding-left="{depth * 14 + 6}px"
                onclick={() => toggleFolder(node.fullPath)}
              >
                <span class="caret">{collapsed.has(node.fullPath) ? '▶' : '▼'}</span>
                <span class="folder-name">{node.name}/</span>
                <span class="folder-count">{folderFileCount(node)}</span>
              </button>
            {:else}
              <button
                type="button"
                class="row file"
                style:padding-left="{depth * 14 + 22}px"
                onclick={() => openFile(node.fullPath)}
                title="Open {node.fullPath}"
              >
                <span class="file-name">{node.name}</span>
                <span class="size">{formatSize(node.size)}</span>
              </button>
            {/if}
          {/each}
        {/if}
      </div>
    </div>
  {/if}
</section>
{/if}

<style>
  .page {
    max-width: 1100px;
    margin: 2rem auto;
    padding: 0 1.5rem 4rem;
    display: flex;
    flex-direction: column;
    height: calc(100vh - 5rem);
    min-height: 0;
  }

  .head {
    --ctl-height: 32px;
    --ctl-radius: 8px;
    --ctl-border: rgba(148, 163, 184, 0.25);
    --ctl-border-hover: rgba(148, 163, 184, 0.5);
    --ctl-bg: rgba(148, 163, 184, 0.08);
    --ctl-bg-hover: rgba(148, 163, 184, 0.16);
    --ctl-fg: inherit;
    --ctl-fg-muted: #6b7280;
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 1.25rem;
    padding: 0 0.25rem 0.85rem;
    border-bottom: 1px solid var(--ctl-border);
    margin-bottom: 1rem;
    flex-shrink: 0;
  }

  .head-lead {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    min-width: 0;
  }

  .back-icon {
    width: var(--ctl-height);
    height: var(--ctl-height);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: 1px solid var(--ctl-border);
    border-radius: var(--ctl-radius);
    color: var(--ctl-fg-muted);
    font: inherit;
    font-size: 1rem;
    line-height: 1;
    cursor: pointer;
    flex-shrink: 0;
    transition: background 120ms ease, color 120ms ease, border-color 120ms ease;
  }

  .back-icon:hover {
    background: var(--ctl-bg-hover);
    color: var(--ctl-fg);
    border-color: var(--ctl-border-hover);
  }

  .title-block {
    min-width: 0;
  }

  .title-block h1 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 700;
    line-height: 1.2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .subtitle {
    margin: 0.15rem 0 0;
    color: var(--ctl-fg-muted);
    font-size: 0.78rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
    white-space: nowrap;
  }

  .subtitle code {
    font-family: ui-monospace, SFMono-Regular, monospace;
    color: #c4b5fd;
    background: rgba(124, 58, 237, 0.15);
    padding: 0.05rem 0.4rem;
    border-radius: 4px;
    font-size: 0.78rem;
  }

  .subtitle .sep {
    opacity: 0.5;
  }

  .head-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .version-select {
    height: var(--ctl-height);
    padding: 0 1.6rem 0 0.65rem;
    border: 1px solid var(--ctl-border);
    border-radius: var(--ctl-radius);
    background: var(--ctl-bg);
    color: var(--ctl-fg);
    font: inherit;
    font-size: 0.82rem;
    cursor: pointer;
    appearance: none;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><path fill='none' stroke='%239ca3af' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round' d='M1 1l4 4 4-4'/></svg>");
    background-repeat: no-repeat;
    background-position: right 0.6rem center;
    transition: border-color 120ms ease, background-color 120ms ease;
  }

  .version-select:hover:not(:disabled) {
    border-color: var(--ctl-border-hover);
  }

  /* Deliberately quieter than .curate-btn: approving sources is the routine
     pre-run step, not the showy cross-version merge. */
  .approve-btn {
    height: var(--ctl-height);
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: transparent;
    color: inherit;
    border: 1px solid #d1d5db;
    padding: 0 0.85rem;
    border-radius: var(--ctl-radius);
    font: inherit;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
  }

  .approve-btn:hover {
    background: rgba(124, 58, 237, 0.08);
    border-color: #7c3aed;
  }

  @media (prefers-color-scheme: dark) {
    .approve-btn {
      border-color: #3a3a3c;
    }
  }

  .curate-btn {
    height: var(--ctl-height);
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%);
    color: white;
    border: 1px solid transparent;
    padding: 0 0.85rem;
    border-radius: var(--ctl-radius);
    font: inherit;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    box-shadow: 0 1px 0 rgba(0, 0, 0, 0.1), 0 6px 16px -8px rgba(124, 58, 237, 0.55);
    transition: filter 120ms ease, transform 120ms ease;
  }

  .run-btn {
    height: var(--ctl-height);
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: linear-gradient(135deg, #16a34a 0%, #0891b2 100%);
    color: white;
    border: 1px solid transparent;
    padding: 0 0.85rem;
    border-radius: var(--ctl-radius);
    font: inherit;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    box-shadow: 0 1px 0 rgba(0, 0, 0, 0.1), 0 6px 16px -8px rgba(22, 163, 74, 0.5);
    transition: filter 120ms ease, transform 120ms ease;
  }

  .run-btn:hover:not(:disabled) {
    filter: brightness(1.08);
  }

  .run-btn:active:not(:disabled) {
    transform: translateY(1px);
  }

  .run-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    box-shadow: none;
  }

  .run-btn--large {
    height: 44px;
    padding: 0 1.4rem;
    font-size: 0.95rem;
  }

  .export-group {
    display: inline-flex;
    align-items: stretch;
    border: 1px solid var(--ctl-border);
    border-radius: var(--ctl-radius);
    background: var(--ctl-bg);
    overflow: hidden;
    height: var(--ctl-height);
  }

  .export-mode {
    height: 100%;
    border: none;
    border-right: 1px solid var(--ctl-border);
    background: transparent;
    color: inherit;
    font: inherit;
    font-size: 0.78rem;
    font-family: ui-monospace, SFMono-Regular, monospace;
    padding: 0 1.4rem 0 0.55rem;
    cursor: pointer;
    appearance: none;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><path fill='none' stroke='%239ca3af' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round' d='M1 1l4 4 4-4'/></svg>");
    background-repeat: no-repeat;
    background-position: right 0.45rem center;
  }

  .export-mode:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .export-btn {
    height: 100%;
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    border: none;
    background: transparent;
    color: inherit;
    font: inherit;
    font-size: 0.82rem;
    font-weight: 500;
    padding: 0 0.75rem;
    cursor: pointer;
    white-space: nowrap;
    transition: background 120ms ease;
  }

  .export-btn:hover:not(:disabled) {
    background: var(--ctl-bg-hover);
  }

  .export-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .resume-btn {
    height: var(--ctl-height);
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: rgba(148, 163, 184, 0.12);
    color: inherit;
    border: 1px solid var(--ctl-border);
    padding: 0 0.75rem;
    border-radius: var(--ctl-radius);
    font: inherit;
    font-size: 0.82rem;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
    transition: background 120ms ease, border-color 120ms ease;
  }

  .resume-btn:hover:not(:disabled) {
    background: rgba(148, 163, 184, 0.22);
    border-color: var(--ctl-border-hover);
  }

  .resume-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .empty-cta {
    margin-top: 1.5rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.65rem;
  }



  .empty-controls {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    flex-wrap: wrap;
    justify-content: center;
  }

  .empty-control {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.78rem;
    color: #9ca3af;
  }

  .empty-control select {
    height: 30px;
    padding: 0 1.6rem 0 0.55rem;
    border: 1px solid rgba(148, 163, 184, 0.3);
    border-radius: 6px;
    background-color: rgba(148, 163, 184, 0.08);
    color: inherit;
    font: inherit;
    font-size: 0.78rem;
    font-family: ui-monospace, SFMono-Regular, monospace;
    cursor: pointer;
    appearance: none;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><path fill='none' stroke='%239ca3af' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round' d='M1 1l4 4 4-4'/></svg>");
    background-repeat: no-repeat;
    background-position: right 0.5rem center;
    transition: border-color 120ms ease, background-color 120ms ease;
  }

  .empty-control select:hover:not(:disabled) {
    border-color: rgba(148, 163, 184, 0.5);
    background-color: rgba(148, 163, 184, 0.16);
  }

  .empty-control select:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .empty-control.deck-readonly code {
    font-family: ui-monospace, SFMono-Regular, monospace;
    background: rgba(148, 163, 184, 0.12);
    padding: 0.1rem 0.45rem;
    border-radius: 4px;
    font-size: 0.78rem;
  }

  .empty-error {
    color: #b91c1c;
    font-size: 0.85rem;
    background: #fef2f2;
    border: 1px solid #fecaca;
    padding: 0.4rem 0.7rem;
    border-radius: 6px;
    margin: 0;
    max-width: 480px;
  }

  .curate-btn:hover:not(:disabled) {
    filter: brightness(1.08);
  }

  .curate-btn:active:not(:disabled) {
    transform: translateY(1px);
  }

  .curate-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    box-shadow: none;
  }

  .curate-spinner {
    display: inline-block;
    animation: spin 1.2s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .icon-group {
    display: inline-flex;
    align-items: center;
    border: 1px solid var(--ctl-border);
    border-radius: var(--ctl-radius);
    background: var(--ctl-bg);
    overflow: hidden;
  }

  .icon-btn {
    width: var(--ctl-height);
    height: var(--ctl-height);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    color: var(--ctl-fg);
    font: inherit;
    font-size: 0.95rem;
    line-height: 1;
    cursor: pointer;
    transition: background 120ms ease;
  }

  .icon-btn + .icon-btn {
    border-left: 1px solid var(--ctl-border);
  }

  .icon-btn:hover:not(:disabled) {
    background: var(--ctl-bg-hover);
  }

  .icon-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .icon-btn--accent:hover:not(:disabled) {
    background: rgba(124, 58, 237, 0.2);
  }

  .curation-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.8rem;
    padding: 0.7rem 1rem;
    border-radius: 8px;
    margin-bottom: 0.85rem;
    font-size: 0.88rem;
    flex-shrink: 0;
  }

  .curation-banner.success {
    background: #f5f3ff;
    border: 1px solid #ddd6fe;
    color: #4c1d95;
  }

  .curation-banner.error {
    background: #fef2f2;
    border: 1px solid #fecaca;
    color: #991b1b;
  }

  .curation-summary {
    flex: 1;
    line-height: 1.4;
  }

  .curation-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .banner-dismiss {
    background: transparent;
    border: none;
    color: inherit;
    font-size: 1.2rem;
    line-height: 1;
    padding: 0 0.3rem;
    cursor: pointer;
    opacity: 0.6;
  }

  .banner-dismiss:hover {
    opacity: 1;
  }

  .banner-action {
    height: 30px;
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    background: rgba(255, 255, 255, 0.08);
    color: inherit;
    border: 1px solid currentColor;
    border-color: rgba(255, 255, 255, 0.15);
    padding: 0 0.7rem;
    border-radius: 6px;
    font: inherit;
    font-size: 0.82rem;
    cursor: pointer;
    white-space: nowrap;
    transition: background 120ms ease;
  }

  .banner-action:hover {
    background: rgba(255, 255, 255, 0.16);
  }

  .empty {
    text-align: center;
    padding: 3rem 1rem;
    color: #6b7280;
  }

  .empty.error {
    color: #c0392b;
  }

  .hint {
    color: #9ca3af;
    font-size: 0.9rem;
    margin-top: 0.5rem;
  }

  .content {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    overflow: hidden;
  }

  .content-head {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    padding: 0.75rem 1rem;
    background: #fafaf9;
    border-bottom: 1px solid #e5e7eb;
    flex-shrink: 0;
    flex-wrap: wrap;
  }

  .version-badge {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 0.8rem;
    background: #5b21b6;
    color: white;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
    font-weight: 600;
  }

  .file-count {
    font-size: 0.78rem;
    color: #6b7280;
    font-variant-numeric: tabular-nums;
  }

  .notebook-version-link {
    background: transparent;
    border: 1px solid transparent;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
    font: inherit;
    font-size: 0.72rem;
    color: #5b21b6;
    cursor: pointer;
    line-height: 1.2;
  }

  .notebook-version-link:hover {
    background: #f5f3ff;
    border-color: #ddd6fe;
  }

  .path {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 0.75rem;
    color: #9ca3af;
    margin-left: auto;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 100%;
  }

  .tree {
    flex: 1;
    overflow-y: auto;
    padding: 0.4rem 0;
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 0.82rem;
  }

  .row {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    padding-top: 0.22rem;
    padding-bottom: 0.22rem;
    padding-right: 1rem;
    line-height: 1.3;
    width: 100%;
    text-align: left;
    background: transparent;
    border: none;
    cursor: pointer;
    color: inherit;
    font: inherit;
  }

  .row:hover {
    background: #f5f3ff;
  }

  .caret {
    color: #9ca3af;
    font-size: 0.65rem;
    width: 10px;
    flex-shrink: 0;
  }

  .folder-name {
    color: #4b5563;
    font-weight: 600;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .folder-count {
    background: #e5e7eb;
    color: #6b7280;
    font-size: 0.65rem;
    padding: 0.05rem 0.4rem;
    border-radius: 999px;
    font-family: system-ui, -apple-system, sans-serif;
    flex-shrink: 0;
  }

  .file-name {
    color: #0f0f0f;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .size {
    font-size: 0.7rem;
    color: #9ca3af;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }

  @media (prefers-color-scheme: dark) {
    .title-block h1 {
      color: #f6f6f6;
    }
    .empty {
      color: #9ca3af;
    }
    .empty.error {
      color: #fca5a5;
    }
    .hint {
      color: #6b7280;
    }
    .content {
      background: #1c1c1e;
      border-color: #2a2a2c;
    }
    .content-head {
      background: #2a2a2c;
      border-bottom-color: #3a3a3c;
    }
    .file-count,
    .path {
      color: #9ca3af;
    }
    .notebook-version-link {
      color: #c4b5fd;
    }
    .notebook-version-link:hover {
      background: #2a1f3d;
      border-color: #5b21b6;
    }
    .row:hover {
      background: #2a1f3d;
    }
    .caret,
    .size {
      color: #6b7280;
    }
    .folder-name {
      color: #d1d5db;
    }
    .folder-count {
      background: #2a2a2c;
      color: #9ca3af;
    }
    .file-name {
      color: #f6f6f6;
    }
    .curation-banner.success {
      background: #2a1f3d;
      border-color: #5b21b6;
      color: #ddd6fe;
    }
    .curation-banner.error {
      background: #3f1d1d;
      border-color: #7f1d1d;
      color: #fecaca;
    }
    .empty-error {
      background: #3f1d1d;
      border-color: #7f1d1d;
      color: #fecaca;
    }
  }
</style>
