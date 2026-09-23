<script lang="ts">
  import { safeDashboardImageUrl } from '$lib/dashboard/imagePolicy';
  import type { DashboardSlidePreview } from '$lib/types/workspace-dashboard';

  interface Props {
    slide: DashboardSlidePreview;
    size?: 'large' | 'medium' | 'small';
    active?: boolean;
  }

  let { slide, size = 'medium', active = false }: Props = $props();
  // Prefer the full generated preview image, then fall back to a thumbnail when only a smaller asset exists.
  const imageUrl = $derived(safeDashboardImageUrl(slide.previewImageUrl) ?? safeDashboardImageUrl(slide.thumbnailUrl));
</script>

<!-- The slide query parameter lets Smart Deck open with this slide preselected. -->
<a class:active class={`slide-tile ${size}`} href={`/decks/${slide.deckId}/smart-deck?slide=${slide.id}`}>
  <span class="slide-number">Slide {String(slide.slideNumber).padStart(2, '0')}</span>
  {#if imageUrl}
    <img src={imageUrl} alt={slide.title} />
  {:else}
    <!-- Text fallback keeps the dashboard usable before slide screenshots are generated. -->
    <div class="slide-fallback">
      <strong>{slide.title}</strong>
      <span>{slide.status === 'accepted' ? 'Accepted' : slide.status === 'edited' ? 'Edited' : 'Original'}</span>
    </div>
  {/if}
</a>

<style>
  .slide-tile {
    position: relative;
    display: block;
    overflow: hidden;
    min-height: 10rem;
    border: 1px solid var(--line);
    border-radius: 8px;
    background:
      linear-gradient(135deg, rgba(20, 184, 166, 0.18), transparent 38%),
      linear-gradient(165deg, rgba(59, 130, 246, 0.18), transparent 52%),
      var(--surface-soft);
    box-shadow: 0 20px 46px rgba(0, 0, 0, 0.18);
  }

  .slide-tile.large {
    min-height: 21rem;
    grid-row: span 2;
  }

  .slide-tile.small {
    min-height: 8.5rem;
  }

  .slide-tile.active {
    border-color: rgba(14, 165, 233, 0.85);
  }

  img {
    width: 100%;
    height: 100%;
    min-height: inherit;
    object-fit: cover;
    display: block;
  }

  .slide-number {
    position: absolute;
    z-index: 1;
    top: 0.75rem;
    left: 0.75rem;
    border: 1px solid rgba(148, 163, 184, 0.45);
    border-radius: 999px;
    background: rgba(2, 6, 23, 0.72);
    color: var(--text);
    padding: 0.28rem 0.55rem;
    font-size: 0.74rem;
    font-weight: 700;
  }

  .slide-fallback {
    min-height: inherit;
    display: grid;
    align-content: end;
    gap: 0.5rem;
    padding: 3rem 1rem 1rem;
  }

  .large .slide-fallback {
    padding: 4rem 1.25rem 1.25rem;
  }

  strong {
    font-size: 1rem;
    line-height: 1.15;
  }

  .large strong {
    font-size: 1.35rem;
  }

  span:not(.slide-number) {
    color: var(--muted);
    font-size: 0.82rem;
  }
</style>
