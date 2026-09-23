<script lang="ts">
  import SuggestionCard from '$components/SuggestionCard.svelte';
  import type { AdaptationSuggestion } from '$types/domain';

  interface Props {
    suggestions: AdaptationSuggestion[];
    audience?: string | null;
  }

  let { suggestions, audience = null }: Props = $props();
</script>

<section class="panel audience-recommendations">
  <div class="audience-recommendations__header">
    <div>
      <div class="eyebrow">Audience</div>
      <h2>Audience recommendations</h2>
      {#if audience}
        <p class="muted">Adaptation context for {audience}.</p>
      {/if}
    </div>
    <span>{suggestions.length}</span>
  </div>

  {#if suggestions.length > 0}
    <div class="audience-recommendations__stack">
      {#each suggestions as suggestion}
        <SuggestionCard {suggestion} />
      {/each}
    </div>
  {:else}
    <p class="muted">No audience recommendations yet.</p>
  {/if}
</section>

<style>
  .audience-recommendations {
    padding: 1rem;
    display: grid;
    gap: 0.9rem;
    align-content: start;
  }

  .audience-recommendations__header {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: start;
  }

  .audience-recommendations__header span {
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 0.35rem 0.65rem;
    color: var(--muted);
    background: var(--surface-soft);
    font-size: 0.82rem;
  }

  .audience-recommendations__stack {
    display: grid;
    gap: 0.8rem;
  }

  h2,
  p {
    margin: 0;
  }
</style>
