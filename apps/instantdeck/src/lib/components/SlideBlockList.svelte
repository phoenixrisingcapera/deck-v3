<script lang="ts">
  import SlideBlockCard from '$components/SlideBlockCard.svelte';
  import type { BlockClassification, DeckSlideBlock } from '$types/domain';

  interface Props {
    blocks: DeckSlideBlock[];
    classifications: BlockClassification[];
    selectedBlockId?: string;
    hrefBase: string;
    slideId: string;
  }

  let { blocks, classifications, selectedBlockId, hrefBase, slideId }: Props = $props();

  function classificationFor(blockId: string) {
    return classifications.find((item) => item.blockId === blockId);
  }
</script>

<section class="block-list">
  {#each blocks as block}
    <SlideBlockCard
      block={block}
      classification={classificationFor(block.id)}
      selected={block.id === selectedBlockId}
      href={`${hrefBase}?slide=${slideId}&block=${block.id}`}
    />
  {/each}
</section>

<style>
  .block-list {
    display: grid;
    gap: 0.9rem;
  }
</style>
