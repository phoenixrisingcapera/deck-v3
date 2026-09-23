<script lang="ts">
  import { onMount } from 'svelte';
  import { settings } from '$lib/stores/settings.svelte';
  import { flow, type FileEntry } from '$lib/stores/flow.svelte';
  import { getTransport } from '$lib/transport';

  interface Props {
    jobId: string;
    isRunning: boolean;
  }

  let { jobId, isRunning }: Props = $props();

  // The sidecar's file watcher pushes file_added / file_modified / file_removed
  // events through the SSE stream and the flow store maintains a Map<path,
  // FileEntry> from them. We render that map directly — no polling. The
  // one-shot fetch on mount below is a safety net for two cases:
  //   (1) the user re-opens JobView mid-run (the bus backlog may have rotated
  //       past the watcher's initial snapshot);
  //   (2) the run has already finished and the bus is closed (the snapshot
  //       endpoint is the only authoritative source).
  let outputDir = $state<string | null>(null);
  let initialFetchError = $state<string | null>(null);

  // Per-folder collapse state. Default: every folder expanded. The user can
  // collapse to focus on a specific subtree.
  let collapsed = $state<Set<string>>(new Set());

  function toggle(folderPath: string) {
    const next = new Set(collapsed);
    if (next.has(folderPath)) next.delete(folderPath);
    else next.add(folderPath);
    collapsed = next;
  }

  // ------------- initial REST fetch -------------

  onMount(async () => {
    if (!settings.repoPath) return;
    try {
      const result = await getTransport().request<{
        output_dir: string | null;
        files: Array<{ path: string; size: number }>;
      }>('GET', `/memos/${jobId}/artifacts`, { repoPath: settings.repoPath });
      outputDir = result.output_dir;
      // Seed any files we don't already know about. The SSE-driven flow.files
      // takes precedence — if a path was already received with a 'fresh' or
      // 'modified' flag, don't overwrite it with an idle baseline.
      for (const f of result.files) {
        if (!flow.files.has(f.path)) {
          // Direct mutation is OK here — we go through the public API by
          // synthesizing a file_added event so the upsert + highlight logic
          // is consistent with live events.
          flow.appendEvent({
            type: 'file_added',
            ts: new Date().toISOString(),
            path: f.path,
            size: f.size,
          } as never);
        }
      }
    } catch (e) {
      const status = (e as { status?: number })?.status;
      // 404 just means the orchestrator hasn't created its output dir yet.
      // The watcher will populate flow.files as soon as it does.
      if (status !== 404) {
        initialFetchError = (e as { message?: string })?.message ?? 'Failed to load files';
      }
    }
  });

  // When the run terminates, do one final fetch to catch any writes the watcher
  // didn't see (e.g. files written in the worker thread's last 100ms before
  // the watcher's stop_event fired).
  let finalFetchDone = false;
  $effect(() => {
    if (isRunning || finalFetchDone || !settings.repoPath) return;
    finalFetchDone = true;
    void (async () => {
      try {
        const result = await getTransport().request<{
          output_dir: string | null;
          files: Array<{ path: string; size: number }>;
        }>('GET', `/memos/${jobId}/artifacts`, { repoPath: settings.repoPath });
        outputDir = result.output_dir;
        for (const f of result.files) {
          const existing = flow.files.get(f.path);
          if (!existing || existing.size !== f.size) {
            flow.appendEvent({
              type: existing ? 'file_modified' : 'file_added',
              ts: new Date().toISOString(),
              path: f.path,
              size: f.size,
            } as never);
          }
        }
      } catch {
        // Silent — terminal-state UX shouldn't show errors from the cleanup probe.
      }
    })();
  });

  // ------------- tree construction -------------

  type FileNode = { kind: 'file'; name: string; fullPath: string; entry: FileEntry };
  type FolderNode = {
    kind: 'folder';
    name: string;
    fullPath: string;
    children: TreeNode[];
  };
  type TreeNode = FileNode | FolderNode;

  function buildTree(files: Map<string, FileEntry>): TreeNode[] {
    const root: FolderNode = { kind: 'folder', name: '', fullPath: '', children: [] };
    for (const entry of files.values()) {
      const parts = entry.path.split('/').filter(Boolean);
      let cursor: FolderNode = root;
      for (let i = 0; i < parts.length; i++) {
        const name = parts[i];
        const isFile = i === parts.length - 1;
        const childFullPath = parts.slice(0, i + 1).join('/');
        let child: TreeNode | undefined = cursor.children.find((c) => c.name === name);
        if (!child) {
          child = isFile
            ? { kind: 'file', name, fullPath: childFullPath, entry }
            : { kind: 'folder', name, fullPath: childFullPath, children: [] };
          cursor.children.push(child);
        } else if (isFile && child.kind === 'file') {
          child.entry = entry; // refresh size/status on update
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

  // Flatten the tree to a list of {node, depth} entries honoring the user's
  // collapse state. Rendering a flat list keeps the template simple — no
  // Svelte recursion gymnastics — and lets us virtualize later if needed.
  type FlatRow = { node: TreeNode; depth: number };

  function flatten(nodes: TreeNode[], depth: number, out: FlatRow[]) {
    for (const n of nodes) {
      out.push({ node: n, depth });
      if (n.kind === 'folder' && !collapsed.has(n.fullPath)) {
        flatten(n.children, depth + 1, out);
      }
    }
  }

  let tree = $derived(buildTree(flow.files));
  let rows = $derived.by(() => {
    const out: FlatRow[] = [];
    flatten(tree, 0, out);
    return out;
  });

  let totalFiles = $derived(flow.files.size);

  // ------------- formatters -------------

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  function shorten(p: string): string {
    const parts = p.split('/').filter(Boolean);
    if (parts.length <= 4) return p;
    return '…/' + parts.slice(-4).join('/');
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
</script>

<div class="browser">
  <header class="head">
    {#if outputDir}
      <code class="dir" title={outputDir}>{shorten(outputDir)}</code>
    {:else if isRunning}
      <span class="dir-empty">Waiting for output directory…</span>
    {:else}
      <span class="dir-empty">No output directory</span>
    {/if}
    <span class="count">{totalFiles} {totalFiles === 1 ? 'file' : 'files'}</span>
  </header>

  {#if initialFetchError}
    <p class="error">{initialFetchError}</p>
  {/if}

  <div class="tree">
    {#if rows.length === 0}
      <div class="empty">
        {isRunning
          ? 'Files will appear here as the orchestrator writes them.'
          : 'No files were produced.'}
      </div>
    {:else}
      {#each rows as { node, depth } (node.fullPath)}
        {#if node.kind === 'folder'}
          <button
            type="button"
            class="row folder"
            style:padding-left="{depth * 14 + 6}px"
            onclick={() => toggle(node.fullPath)}
          >
            <span class="caret">{collapsed.has(node.fullPath) ? '▶' : '▼'}</span>
            <span class="folder-name">{node.name}/</span>
            <span class="folder-count">{folderFileCount(node)}</span>
          </button>
        {:else}
          <div
            class="row file file-{node.entry.status}"
            style:padding-left="{depth * 14 + 22}px"
          >
            <span class="file-name" title={node.fullPath}>{node.name}</span>
            <span class="size">{formatSize(node.entry.size)}</span>
          </div>
        {/if}
      {/each}
    {/if}
  </div>
</div>

<style>
  .browser {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    background: #fafaf9;
    overflow: hidden;
  }

  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.85rem 1rem 0.6rem;
    background: #fafaf9;
    border-bottom: 1px solid #e5e7eb;
    flex-shrink: 0;
  }

  .dir {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 0.78rem;
    color: #5b21b6;
    background: #f5f3ff;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    border: 1px solid #ddd6fe;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 75%;
  }

  .dir-empty {
    color: #9ca3af;
    font-size: 0.85rem;
    font-style: italic;
  }

  .count {
    font-size: 0.78rem;
    color: #6b7280;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }

  .tree {
    flex: 1;
    overflow-y: auto;
    padding: 0.4rem 0;
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 0.82rem;
  }

  .empty {
    padding: 2rem 1rem;
    text-align: center;
    color: #6b7280;
    font-style: italic;
    font-family: system-ui, -apple-system, sans-serif;
  }

  .row {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    padding-top: 0.18rem;
    padding-bottom: 0.18rem;
    padding-right: 0.75rem;
    line-height: 1.3;
    width: 100%;
    text-align: left;
  }

  button.row {
    background: transparent;
    border: none;
    cursor: pointer;
    color: inherit;
    font: inherit;
  }

  button.row:hover {
    background: #f3f4f6;
  }

  .row.file:hover {
    background: #f3f4f6;
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

  /* Highlight states. The flow store fades these back to 'idle' after 3s.
     Animation runs on each entry so a re-fired event re-triggers the flash. */
  .file.file-fresh {
    background: #ecfccb;
    animation: flash-fresh 3s ease-out forwards;
  }

  .file.file-modified {
    background: #dbeafe;
    animation: flash-modified 3s ease-out forwards;
  }

  @keyframes flash-fresh {
    from {
      background: #84cc16;
      color: #1a2e05;
    }
    to {
      background: transparent;
    }
  }

  @keyframes flash-modified {
    from {
      background: #3b82f6;
      color: #f6f6f6;
    }
    to {
      background: transparent;
    }
  }

  .error {
    color: #c0392b;
    font-size: 0.85rem;
    margin: 0;
    padding: 0.4rem 0.6rem;
    background: #fef2f2;
    border-bottom: 1px solid #fca5a5;
    flex-shrink: 0;
  }

  @media (prefers-color-scheme: dark) {
    .browser {
      background: #1c1c1e;
    }

    .head {
      background: #1c1c1e;
      border-bottom-color: #2a2a2c;
    }

    .dir {
      background: #2a1f3d;
      border-color: #5b21b6;
      color: #c4b5fd;
    }

    .dir-empty {
      color: #6b7280;
    }

    .count {
      color: #9ca3af;
    }

    .empty {
      color: #9ca3af;
    }

    .caret {
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

    .size {
      color: #6b7280;
    }

    button.row:hover,
    .row.file:hover {
      background: #2a2a2c;
    }

    .file.file-fresh {
      background: #064e3b;
    }

    .file.file-modified {
      background: #1e3a8a;
    }

    @keyframes flash-fresh {
      from {
        background: #16a34a;
        color: #f6f6f6;
      }
      to {
        background: transparent;
      }
    }

    @keyframes flash-modified {
      from {
        background: #2563eb;
        color: #f6f6f6;
      }
      to {
        background: transparent;
      }
    }

    .error {
      background: #2a1c1c;
      border-color: #7f1d1d;
    }
  }
</style>
