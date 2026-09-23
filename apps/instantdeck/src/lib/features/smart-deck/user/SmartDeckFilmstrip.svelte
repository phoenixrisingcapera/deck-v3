<script lang="ts">
  import type { SmartDeckUserSlideViewModel } from './smartDeckUserTypes';
  import SanitizedHtmlSlideRenderer from '$lib/components/smart-deck/SanitizedHtmlSlideRenderer.svelte';

  interface Props {
    slides: SmartDeckUserSlideViewModel[];
    selectedSlideId: string | null;
    onSelectSlide?: (slideId: string) => void;
    onOpenSmartEdit?: (slideId: string) => void;
    onAddSlide?: () => void | Promise<void>;
    addingSlide?: boolean;
    addSlideLabel?: string;
    responsiveOnly?: boolean;
  }

  let { slides, selectedSlideId, onSelectSlide, onOpenSmartEdit, onAddSlide, addingSlide = false, addSlideLabel = '+', responsiveOnly = false }: Props = $props();
  let failedThumbIds = $state<string[]>([]);

  function markFailed(slideId: string) {
    if (!failedThumbIds.includes(slideId)) failedThumbIds = [...failedThumbIds, slideId];
  }
</script>

<section class="bottom-filmstrip" class:responsive-only={responsiveOnly} aria-label="Slide filmstrip">
  <div class="bottom-filmstrip__track">
    {#each slides as slide}
      <button
        type="button"
        class:active={slide.id === selectedSlideId}
        onclick={() => onSelectSlide?.(slide.id)}
        ondblclick={() => onOpenSmartEdit?.(slide.id)}
      >
        <div class="thumb">
          {#if slide.htmlSlide}
            <SanitizedHtmlSlideRenderer slide={slide.htmlSlide} mode="miniature" loading="lazy" label={`Slide ${slide.number}: ${slide.title} generated HTML miniature`} />
          {:else if slide.previewUrl && !failedThumbIds.includes(slide.id)}
            <img src={slide.previewUrl} alt={`${slide.title} preview`} onerror={() => markFailed(slide.id)} />
          {:else}
            <div class="thumb-placeholder">
              <span>{String(slide.number).padStart(2, '0')}</span>
            </div>
          {/if}
        </div>
        <strong>{String(slide.number).padStart(2, '0')}</strong>
      </button>
    {/each}

    <!-- DISABLED: The placeholder plus button never reached the persisted slide service.
         <button type="button" class="add" disabled title="Adding new slides will be enabled in a later pass.">+</button> -->
    <button
      type="button"
      class="add"
      disabled={addingSlide}
      title="Create a persisted slide and open Ask AI"
      aria-label="Create slide"
      onclick={() => void onAddSlide?.()}
    >{addingSlide ? '...' : addSlideLabel}</button>
  </div>
</section>

<style>
  .bottom-filmstrip {
    grid-column: 3;
    grid-row: 3;
    background: rgba(10, 17, 33, 0.96);
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding: 0.85rem 1rem;
    overflow: hidden;
  }

  .bottom-filmstrip__track {
    display: flex;
    gap: 0.65rem;
    align-items: center;
    overflow: auto;
  }

  .bottom-filmstrip__track button {
    flex: 0 0 auto;
    width: 78px;
    display: grid;
    gap: 0.35rem;
    justify-items: center;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(15, 23, 42, 0.75);
    color: #f8fafc;
    padding: 0.45rem;
  }

  .bottom-filmstrip__track button.active {
    border-color: rgba(124, 58, 237, 0.9);
    box-shadow: inset 0 0 0 1px rgba(14, 165, 233, 0.22);
  }

  .thumb {
    width: 100%;
    aspect-ratio: 16 / 9;
    border-radius: 8px;
    overflow: hidden;
    background: white;
  }

  .thumb img,
  .thumb-placeholder {
    width: 100%;
    height: 100%;
    display: block;
  }

  .thumb img {
    object-fit: cover;
  }

  .thumb-placeholder {
    display: grid;
    place-items: center;
    color: #334155;
    background: linear-gradient(180deg, #ffffff, #f1f5f9);
  }

  .add {
    width: 64px;
    height: 64px;
    font-size: 1.4rem;
  }

  .bottom-filmstrip.responsive-only {
    display: none;
  }

  @media (max-width: 960px) {
    .bottom-filmstrip {
      grid-column: 2;
      grid-row: 3;
    }

    .bottom-filmstrip.responsive-only {
      display: block;
    }
  }

  @media (max-width: 720px) {
    .bottom-filmstrip {
      grid-column: 1;
      grid-row: 5;
    }
  }
</style>
