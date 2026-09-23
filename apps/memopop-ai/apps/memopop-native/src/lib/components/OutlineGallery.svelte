<script lang="ts">
  import { settings } from '$lib/stores/settings.svelte';
  import { outlines } from '$lib/stores/outlines.svelte';
  import { flow } from '$lib/stores/flow.svelte';
  import OutlineCard from './OutlineCard.svelte';
  import type { Outline } from '$lib/types';

  $effect(() => {
    if (settings.repoPath) {
      void outlines.load(settings.repoPath);
    }
  });

  function handlePreview(outline: Outline) {
    flow.showDetail(outline);
  }

  function handleTry(outline: Outline) {
    flow.startTrying(outline, !!settings.activeFirm);
  }

  function retry() {
    if (settings.repoPath) {
      void outlines.load(settings.repoPath, true);
    }
  }
</script>

<section class="gallery">
  <header class="gallery-head">
    <h1>Choose an outline</h1>
    <p class="lede">
      Each outline is a battle-tested structure for a particular kind of
      investment memo. Pick one to see what it covers, then run it on a
      company.
    </p>
  </header>

  {#if outlines.loading}
    <div class="state loading">Loading outlines…</div>
  {:else if outlines.error}
    <div class="state error">
      <p>{outlines.error}</p>
      <button type="button" onclick={retry}>Try again</button>
    </div>
  {:else if outlines.outlines.length === 0}
    <div class="state empty">
      <p>
        No outlines found in <code>templates/outlines/</code>. Did you point at
        the orchestrator repo root?
      </p>
    </div>
  {:else}
    <div class="grid">
      {#each outlines.outlines as outline (outline.id)}
        <OutlineCard {outline} onpreview={handlePreview} ontry={handleTry} />
      {/each}
    </div>
  {/if}
</section>

<style>
  .gallery {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2.5rem 1.5rem;
  }

  .gallery-head {
    max-width: 720px;
    margin-bottom: 2rem;
  }

  h1 {
    font-size: 1.75rem;
    margin: 0 0 0.5rem;
  }

  .lede {
    color: #6b7280;
    margin: 0;
    line-height: 1.6;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 1.25rem;
  }

  .state {
    padding: 3rem;
    text-align: center;
    border: 1px dashed #d1d5db;
    border-radius: 12px;
    color: #6b7280;
  }

  .state.error {
    color: #c0392b;
    border-color: #fca5a5;
    background: #fef2f2;
  }

  .state button {
    margin-top: 1rem;
    padding: 0.5rem 1rem;
    border: 1px solid currentColor;
    background: transparent;
    color: inherit;
    border-radius: 6px;
    font: inherit;
    cursor: pointer;
  }

  code {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 0.85em;
    background: #f3f4f6;
    padding: 0.1rem 0.3rem;
    border-radius: 3px;
  }

  @media (prefers-color-scheme: dark) {
    .lede {
      color: #9ca3af;
    }

    .state {
      border-color: #3a3a3c;
      color: #9ca3af;
    }

    .state.error {
      background: #2a1c1c;
      border-color: #7f1d1d;
    }

    code {
      background: #1c1c1e;
    }
  }
</style>
