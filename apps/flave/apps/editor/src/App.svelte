<script lang="ts">
  import { parseMarkdown } from '@lossless-group/lfm';
  import { FlaveMarkdown } from '@flave/render';
  import { codemirror, type Lang } from './codemirror';
  import FileTree from './FileTree.svelte';
  import MetricCard from './MetricCard.svelte';
  import Badge from './Badge.svelte';
  import { workspaceFs, languageOf, isTheme, type FsNode } from './workspace-fs';

  // The trigger-pack registry. Adding syntax is this line plus a component.
  const packs = { 'metric-card': MetricCard, badge: Badge };

  const DEFAULT_DOC = 'content/welcome.md';
  const DEFAULT_THEME = 'themes/lossless.css';

  let railView = $state<'files' | 'chat'>('files');   // D-27: one rail, toggled
  let showSource = $state(true);

  let tree = $state<FsNode[]>([]);
  let openPath = $state<string | null>(null);
  let source = $state('');            // the open file's text
  let docSource = $state('');         // the last markdown seen — what Document renders
  let themeCss = $state('');
  let status = $state('');

  const lang = $derived<Lang>(openPath ? languageOf(openPath) : 'markdown');

  // ── Boot: tree, a document, and the theme ────────────────────────────────
  $effect(() => {
    (async () => {
      try {
        tree = await workspaceFs.tree();
        themeCss = await workspaceFs.read(DEFAULT_THEME).catch(() => '');
        await open(DEFAULT_DOC);
        status = workspaceFs.kind === 'tauri' ? '' : 'in-memory workspace — launch the desktop app for real files';
      } catch (err) {
        status = String(err);
      }
    })();
  });

  async function open(path: string) {
    try {
      const text = await workspaceFs.read(path);
      openPath = path;
      source = text;
      if (languageOf(path) === 'markdown') docSource = text;
      if (isTheme(path)) themeCss = text;
      showSource = true;
    } catch (err) {
      status = String(err);
    }
  }

  // ── Edits: update the live surfaces, then persist ────────────────────────
  let saveTimer: ReturnType<typeof setTimeout> | undefined;
  function edited(value: string) {
    source = value;
    if (openPath && languageOf(openPath) === 'markdown') docSource = value;
    if (openPath && isTheme(openPath)) themeCss = value;

    clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
      if (!openPath) return;
      try {
        await workspaceFs.write(openPath, value);
        status = `saved ${openPath}`;
        setTimeout(() => { if (status.startsWith('saved')) status = ''; }, 1200);
      } catch (err) {
        status = String(err);
      }
    }, 400);
  }

  // ── The theme is applied as a live stylesheet the app owns ───────────────
  $effect(() => {
    const css = themeCss;
    let el = document.getElementById('flave-theme') as HTMLStyleElement | null;
    if (!el) {
      el = document.createElement('style');
      el.id = 'flave-theme';
      document.head.appendChild(el);
    }
    el.textContent = css;
  });

  // ── Render the document ──────────────────────────────────────────────────
  let treeAst = $state<any>(null);
  let token = 0;
  $effect(() => {
    const src = docSource;
    const mine = ++token;
    parseMarkdown(src).then((t) => { if (mine === token) treeAst = t; });
  });
</script>

<div class="shell">
  <header class="menubar">
    <span class="brand">flave</span>
    <nav class="menus" aria-label="Main">
      <!-- Phase 1: each becomes a named capability invocation. -->
      <button type="button" disabled>File</button>
      <button type="button" disabled>Edit</button>
      <button type="button" disabled>Insert</button>
      <button type="button" disabled>Format</button>
    </nav>
    {#if status}<span class="status">{status}</span>{/if}
    <label class="toggle">
      <input type="checkbox" bind:checked={showSource} />
      Source
    </label>
  </header>

  <main class="panes" class:panes--two={!showSource}>
    <section class="pane pane--rail" aria-label={railView === 'files' ? 'Files' : 'Agent chat'}>
      <!-- D-27: one rail, two surfaces, never both. -->
      <div class="rail__switch" role="tablist">
        <button
          type="button" role="tab" aria-selected={railView === 'files'}
          class:is-active={railView === 'files'} onclick={() => (railView = 'files')}
        >Files</button>
        <button
          type="button" role="tab" aria-selected={railView === 'chat'}
          class:is-active={railView === 'chat'} onclick={() => (railView = 'chat')}
        >Chat</button>
      </div>

      <div class="rail__body">
        {#if railView === 'files'}
          <FileTree nodes={tree} selected={openPath} onopen={open} />
        {:else}
          <p class="placeholder">
            Phase 1. At v0 the agent is Claude Code in a terminal beside the
            editor — it writes trigger-packs into the workspace and this pane
            hot-reloads them.
          </p>
        {/if}
      </div>
    </section>

    {#if showSource}
      <section class="pane pane--source" aria-label="Source">
        <p class="pane__label">{openPath ?? 'Source'}</p>
        <div class="cm-host" use:codemirror={{ doc: source, lang, onChange: edited }}></div>
      </section>
    {/if}

    <section class="pane pane--rendered" aria-label="Rendered document">
      <p class="pane__label">Document</p>
      <article class="rendered">
        {#if treeAst}<FlaveMarkdown node={treeAst} {packs} />{/if}
      </article>
    </section>
  </main>
</div>
