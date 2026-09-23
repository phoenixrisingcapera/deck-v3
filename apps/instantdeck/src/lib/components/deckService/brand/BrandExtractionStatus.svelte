<!-- Purpose: renders extraction status states and extraction progress copy for brand profiling. -->
<script lang="ts">
  import type { BrandStatus } from '$lib/types/deckService-brand';

  let {
    status,
    error = ''
  }: {
    status: BrandStatus;
    error?: string;
  } = $props();

  const stages = [
    'Collecting the website or logo input',
    'Preparing brand colours and visual signals',
    'Rendering the preview for review'
  ];
</script>

<section class="status-panel" aria-live="polite">
  <div class="status-panel__head">
    <strong>Extraction status</strong>
    <span>
      {#if status === 'extracting'}
        In progress
      {:else if status === 'ready'}
        Ready
      {:else if status === 'failed'}
        Needs attention
      {:else}
        Waiting
      {/if}
    </span>
  </div>

  {#if status === 'extracting'}
    <ol>
      {#each stages as stage, index}
        <li class:active={index < 2}>{stage}</li>
      {/each}
    </ol>
  {:else if status === 'ready'}
    <p>Brand profile generated. Review the extracted visual signals before continuing.</p>
  {:else if status === 'failed'}
    <p>{error || 'Brand extraction failed. Check the input and try again.'}</p>
  {:else}
    <p>Add a company website or logo, then run extraction when you are ready.</p>
  {/if}
</section>

<style>
  .status-panel {
    display: grid;
    gap: 0.75rem;
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 0.95rem;
    background: rgba(255, 255, 255, 0.02);
  }

  .status-panel__head {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    align-items: center;
  }

  .status-panel__head span,
  p,
  li {
    color: var(--muted);
    font-size: 0.84rem;
  }

  p,
  ol {
    margin: 0;
  }

  ol {
    display: grid;
    gap: 0.55rem;
    padding-left: 1rem;
  }

  li.active {
    color: var(--ink);
  }
</style>
