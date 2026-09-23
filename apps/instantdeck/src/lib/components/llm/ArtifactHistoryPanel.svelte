<script lang="ts">
  import type { ArtifactHistoryItem } from './artifactTypes';

  interface Props {
    title: string;
    emptyText?: string;
    items: ArtifactHistoryItem[];
    onLoad?: (item: ArtifactHistoryItem) => void;
    onInspect?: (item: ArtifactHistoryItem) => void;
    onLoadLatest?: (() => void) | undefined;
  }

  let {
    title,
    emptyText = 'No saved artifacts yet.',
    items,
    onLoad,
    onInspect,
    onLoadLatest,
  }: Props = $props();
</script>

<section class="artifact-history-panel">
  <div class="artifact-history-panel__head">
    <h4>{title}</h4>
    {#if onLoadLatest}
      <button type="button" class="artifact-history-panel__latest" onclick={() => onLoadLatest?.()} disabled={!items.length}>
        Load latest
      </button>
    {/if}
  </div>

  {#if items.length}
    <div class="artifact-history-panel__list">
      {#each items as item}
        <div class="artifact-history-panel__item">
          <button type="button" class="artifact-history-panel__load" onclick={() => onLoad?.(item)}>
            <strong>{item.title}</strong>
            {#if item.subtitle}<small>{item.subtitle}</small>{/if}
            {#if item.timestamp}<small>{item.timestamp}</small>{/if}
          </button>
          <button type="button" class="artifact-history-panel__inspect" onclick={() => onInspect?.(item)}>
            Details
          </button>
        </div>
      {/each}
    </div>
  {:else}
    <p class="artifact-history-panel__empty">{emptyText}</p>
  {/if}
</section>

<style>
  .artifact-history-panel {
    display: grid;
    gap: 0.5rem;
  }

  .artifact-history-panel__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .artifact-history-panel__head h4 {
    margin: 0;
    color: #cbd5e1;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .artifact-history-panel__latest,
  .artifact-history-panel__inspect,
  .artifact-history-panel__load {
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.03);
    color: #e2e8f0;
    cursor: pointer;
    font: inherit;
  }

  .artifact-history-panel__latest,
  .artifact-history-panel__inspect {
    padding: 0.35rem 0.7rem;
    font-size: 0.75rem;
  }

  .artifact-history-panel__latest:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .artifact-history-panel__list {
    display: grid;
    gap: 0.45rem;
  }

  .artifact-history-panel__item {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.5rem;
    align-items: start;
  }

  .artifact-history-panel__load {
    display: grid;
    gap: 0.2rem;
    text-align: left;
    width: 100%;
    padding: 0.55rem 0.65rem;
  }

  .artifact-history-panel__load strong {
    font-size: 0.78rem;
  }

  .artifact-history-panel__load small,
  .artifact-history-panel__empty {
    color: #94a3b8;
    font-size: 0.75rem;
  }

  .artifact-history-panel__empty {
    margin: 0;
  }
</style>
