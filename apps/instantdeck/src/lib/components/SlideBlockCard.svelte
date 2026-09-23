<script lang="ts">
  import BlockClassificationBadge from '$components/smart-edit/BlockClassificationBadge.svelte';
  import type { BlockClassification, DeckSlideBlock } from '$types/domain';

  interface Props {
    block: DeckSlideBlock;
    classification?: BlockClassification;
    selected?: boolean;
    href?: string;
  }

  let { block, classification, selected = false, href = '' }: Props = $props();
</script>

<a class:selected class="panel block-card" href={href}>
  <div class="meta">
    <strong>Block {block.blockIndex + 1}</strong>
    <span class="muted">{block.blockType}</span>
  </div>
  <p>{block.rawText}</p>
  {#if classification}
    <BlockClassificationBadge
      semanticTag={classification.semanticTag}
      diligenceCategory={classification.diligenceCategory}
    />
  {/if}
</a>

<style>
  .block-card {
    display: grid;
    gap: 0.75rem;
    padding: 1rem;
    border-radius: var(--radius-md);
  }

  .block-card.selected {
    border-color: rgba(15, 118, 110, 0.3);
    background: rgba(15, 118, 110, 0.08);
  }

  .meta {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
  }

  p {
    margin: 0;
  }
</style>
