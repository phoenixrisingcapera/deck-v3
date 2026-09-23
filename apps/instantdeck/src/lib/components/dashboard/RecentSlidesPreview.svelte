<script lang="ts">
  import SlidePreviewTile from '$components/dashboard/SlidePreviewTile.svelte';
  import type { DashboardDeckSummary, DashboardSlidePreview } from '$lib/types/workspace-dashboard';

  interface Props {
    deck: DashboardDeckSummary;
    slides: DashboardSlidePreview[];
  }

  let { deck, slides }: Props = $props();
</script>

<!-- Visual preview of the active deck; each tile links directly into Smart Deck with the selected slide id. -->
<section class="panel recent-slides">
  <div class="section-heading">
    <div>
      <div class="eyebrow">Deck preview</div>
      <h2>Recent slides · {deck.title}</h2>
    </div>
    <a class="link" href={`/decks/${deck.id}/smart-deck`}>Open Smart Deck</a>
  </div>

  {#if slides.length > 0}
    <div class="slide-grid">
      <!-- Show a compact sample of the latest slides; the first tile is larger to anchor the preview layout. -->
      {#each slides.slice(0, 6) as slide, index}
        <SlidePreviewTile {slide} size={index === 0 ? 'large' : 'medium'} active={index === 0} />
      {/each}
    </div>
  {:else}
    <div class="empty-preview">
      <strong>No slide previews yet</strong>
      <span>Open the current deck to generate visual slide previews.</span>
    </div>
  {/if}
</section>

<style>
  .recent-slides {
    padding: 1.25rem;
  }

  .section-heading {
    display: flex;
    justify-content: space-between;
    align-items: end;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  h2 {
    margin: 0.2rem 0 0;
    font-size: clamp(1.25rem, 1.8vw, 1.7rem);
  }

  .slide-grid {
    display: grid;
    grid-template-columns: minmax(280px, 1.1fr) repeat(2, minmax(160px, 0.7fr));
    gap: 0.85rem;
    align-items: stretch;
  }

  .empty-preview {
    min-height: 16rem;
    display: grid;
    place-content: center;
    gap: 0.45rem;
    text-align: center;
    border: 1px dashed var(--line);
    border-radius: 8px;
    color: var(--muted);
  }

  .empty-preview strong {
    color: var(--text);
  }

  .link {
    color: var(--muted);
    font-weight: 700;
  }

  @media (max-width: 780px) {
    .section-heading {
      align-items: start;
      flex-direction: column;
    }

    .slide-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
