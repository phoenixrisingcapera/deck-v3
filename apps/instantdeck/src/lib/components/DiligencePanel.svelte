<script lang="ts">
  import FindingCard from '$components/FindingCard.svelte';
  import type { AnalysisFinding } from '$types/domain';

  interface Props {
    findings: AnalysisFinding[];
    title?: string;
    emptyText?: string;
  }

  let {
    findings,
    title = 'Diligence Findings',
    emptyText = 'No findings yet. Run analysis to populate diligence gaps.'
  }: Props = $props();
</script>

<aside class="panel diligence-panel">
  <div class="header">
      <div class="eyebrow">{title}</div>
    <span>{findings.length}</span>
  </div>
  {#if findings.length}
    {#each findings as finding}
      <FindingCard {finding} />
    {/each}
  {:else}
    <p class="muted">{emptyText}</p>
  {/if}
</aside>

<style>
  .diligence-panel {
    padding: 1rem;
    display: grid;
    gap: 0.8rem;
    align-content: start;
  }

  .header {
    display: flex;
    justify-content: space-between;
    color: var(--muted);
  }
</style>
