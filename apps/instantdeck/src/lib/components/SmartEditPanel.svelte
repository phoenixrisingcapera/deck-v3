<script lang="ts">
  import SmartEditCommandBox from '$components/SmartEditCommandBox.svelte';
  import SmartEditSuggestionCard from '$components/SmartEditSuggestionCard.svelte';
  import type { DeckSlideBlock, SmartEditSuggestion } from '$types/domain';

  interface Props {
    deckId: string;
    slideId: string;
    selectedBlock?: DeckSlideBlock;
    suggestions: SmartEditSuggestion[];
  }

  let { deckId, slideId, selectedBlock, suggestions }: Props = $props();
</script>

<section class="smart-panel">
  <SmartEditCommandBox
    {deckId}
    {slideId}
    blockId={selectedBlock?.id}
    selectedText={selectedBlock?.rawText}
  />
  {#if !selectedBlock}
    <div class="panel empty-state">
      <strong>No block selected</strong>
      <p class="muted">Choose a text block to reveal its classification and launch a Smart Edit instruction.</p>
    </div>
  {/if}
  <div class="suggestions">
    {#each suggestions as suggestion}
      <SmartEditSuggestionCard {deckId} {suggestion} />
    {/each}
  </div>
</section>

<style>
  .smart-panel {
    display: grid;
    gap: 1rem;
    align-content: start;
  }

  .suggestions {
    display: grid;
    gap: 0.9rem;
  }

  .empty-state {
    padding: 1rem;
  }
</style>
