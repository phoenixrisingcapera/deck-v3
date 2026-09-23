<script lang="ts">
  import type { SmartDeckUserSlideViewModel } from '$lib/features/smart-deck/user/smartDeckUserTypes';
  import SanitizedHtmlSlideRenderer from '$lib/components/smart-deck/SanitizedHtmlSlideRenderer.svelte';

  interface Props {
    slides: SmartDeckUserSlideViewModel[];
    selectedSlideId: string | null;
    selectedSourceSlideIds?: string[];
    onSelectSlide?: (slideId: string) => void;
    onToggleSourceSlideSelection?: (slideId: string) => void;
    onOpenSmartEdit?: (slideId: string) => void;
    onAddSlide?: () => void;
    addingSlide?: boolean;
    title?: string;
    description?: string;
    showSourceSelection?: boolean;
    showSearch?: boolean;
    belowToolbar?: boolean;
    visible?: boolean;
    interactionDisabledReason?: string | null;
  }

  let {
    slides,
    selectedSlideId,
    selectedSourceSlideIds = [],
    onSelectSlide,
    onToggleSourceSlideSelection,
    onOpenSmartEdit,
    onAddSlide,
    addingSlide = false,
    title = 'Active slides',
    description = 'Preview every slide in this deck.',
    showSourceSelection = true,
    showSearch = false,
    belowToolbar = false,
    visible = true,
    interactionDisabledReason = null
  }: Props = $props();
  let failedThumbUrls = $state<string[]>([]);
  let query = $state('');
  const visibleSlides = $derived(
    slides.filter((slide) => `${slide.number} ${slide.title}`.toLowerCase().includes(query.trim().toLowerCase()))
  );

  function miniatureUrl(slide: SmartDeckUserSlideViewModel) {
    if (slide.thumbnailUrl && !failedThumbUrls.includes(slide.thumbnailUrl)) return slide.thumbnailUrl;
    if (slide.hasGeneratedVersion) return null;
    if (slide.sourceThumbnailUrl && !failedThumbUrls.includes(slide.sourceThumbnailUrl)) return slide.sourceThumbnailUrl;
    return null;
  }

  function markFailed(url: string) {
    if (!failedThumbUrls.includes(url)) failedThumbUrls = [...failedThumbUrls, url];
  }
</script>

<aside
  id="global-deck-slide-navigator"
  class="global-deck-slide-navigator"
  data-deck-region="slides"
  data-below-toolbar={belowToolbar ? 'true' : undefined}
  hidden={!visible}
>
  <div class="global-deck-slide-navigator__header">
    <div>
      <h2>{title}</h2>
      <p>{description}</p>
    </div>
    {#if onAddSlide}
      <button type="button" disabled={addingSlide} onclick={() => onAddSlide?.()}>
        {addingSlide ? 'Adding...' : '+ Slide'}
      </button>
    {/if}
  </div>

  {#if showSearch}
    <label class="global-deck-slide-navigator__search">
      <span>Search slides</span>
      <input bind:value={query} type="search" placeholder="Search slides..." />
    </label>
  {/if}

  <div class="global-deck-slide-navigator__list" role="list">
    {#each visibleSlides as slide}
      {@const imageUrl = miniatureUrl(slide)}
      <button
        type="button"
        class:active={slide.id === selectedSlideId}
        aria-current={slide.id === selectedSlideId ? 'true' : undefined}
        aria-label={`Slide ${slide.number}: ${slide.title}`}
        aria-disabled={interactionDisabledReason ? 'true' : undefined}
        title={interactionDisabledReason ?? undefined}
        disabled={Boolean(interactionDisabledReason)}
        onclick={() => onSelectSlide?.(slide.id)}
        ondblclick={() => onOpenSmartEdit?.(slide.id)}
      >
        <div class="thumb">
          {#if showSourceSelection}
            <span class:included={selectedSourceSlideIds.includes(slide.id)} class="selection-chip">
              {selectedSourceSlideIds.includes(slide.id) ? 'Included' : 'Excluded'}
            </span>
            <span
              class:included={selectedSourceSlideIds.includes(slide.id)}
              class="selection-toggle"
              role="button"
              tabindex="0"
              aria-label={`${selectedSourceSlideIds.includes(slide.id) ? 'Remove' : 'Include'} slide ${slide.number} from full-deck regeneration`}
              onclick={(event) => {
                event.stopPropagation();
                onToggleSourceSlideSelection?.(slide.id);
              }}
              onkeydown={(event) => {
                if (event.key !== 'Enter' && event.key !== ' ') return;
                event.preventDefault();
                event.stopPropagation();
                onToggleSourceSlideSelection?.(slide.id);
              }}
            >
              {selectedSourceSlideIds.includes(slide.id) ? '✓' : '+'}
            </span>
          {/if}
          {#if slide.htmlSlide}
            <SanitizedHtmlSlideRenderer
              slide={slide.htmlSlide}
              mode="miniature"
              loading="lazy"
              label={`Slide ${slide.number}: ${slide.title} generated HTML miniature`}
            />
          {:else if imageUrl}
            <img src={imageUrl} alt={`${slide.title} thumbnail`} onerror={() => markFailed(imageUrl)} />
          {:else if slide.hasGeneratedVersion}
            <div class="generated-preview-state" role={slide.previewStatus === 'failed' ? 'alert' : 'status'}>
              {slide.previewStatus === 'failed' ? 'Generated preview failed' : 'Generated preview pending'}
            </div>
          {:else}
            <div class="thumb-placeholder">
              <span>{String(slide.number).padStart(2, '0')}</span>
              <strong>{slide.title}</strong>
            </div>
          {/if}
        </div>
      </button>
    {/each}
  </div>
</aside>

<style>
  .global-deck-slide-navigator {
    grid-column: 2;
    grid-row: 1 / -1;
    background: rgba(16, 24, 39, 0.9);
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    padding: 1rem;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .global-deck-slide-navigator[data-below-toolbar='true'] {
    grid-row: 2 / -1;
  }

  .global-deck-slide-navigator__header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 1rem;
  }

  .global-deck-slide-navigator__header h2 {
    margin: 0;
    font-size: 1rem;
    color: #f8fafc;
  }

  .global-deck-slide-navigator__header p {
    margin: 0.2rem 0 0;
    color: #94a3b8;
    font-size: 0.8rem;
  }

  .global-deck-slide-navigator__header button {
    height: 36px;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: rgba(15, 23, 42, 0.9);
    color: #f8fafc;
    padding: 0 0.75rem;
    cursor: pointer;
    white-space: nowrap;
  }

  .global-deck-slide-navigator__header button:disabled {
    cursor: wait;
    opacity: 0.65;
  }

  .global-deck-slide-navigator__search {
    display: grid;
    gap: 0.35rem;
    margin-bottom: 0.8rem;
    color: #94a3b8;
    font-size: 0.72rem;
  }

  .global-deck-slide-navigator__search input {
    width: 100%;
    min-height: 38px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    background: rgba(15, 23, 42, 0.86);
    color: #f8fafc;
    padding: 0 0.65rem;
  }

  .global-deck-slide-navigator__list {
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
    overflow: auto;
    padding-right: 0.2rem;
  }

  .global-deck-slide-navigator__list button {
    display: block;
    width: 100%;
    padding: 0.45rem;
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(15, 23, 42, 0.68);
    color: #f8fafc;
    text-align: left;
    cursor: pointer;
  }

  .global-deck-slide-navigator__list button.active {
    border-color: rgba(124, 58, 237, 0.9);
    background: linear-gradient(135deg, rgba(76, 29, 149, 0.45), rgba(14, 165, 233, 0.22));
    box-shadow: inset 0 0 0 1px rgba(56, 189, 248, 0.2);
  }

  .global-deck-slide-navigator__list button:disabled {
    cursor: not-allowed;
    opacity: 0.82;
  }

  .thumb {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    border-radius: 10px;
    overflow: hidden;
    background: #fff;
    box-shadow: 0 10px 20px rgba(2, 6, 23, 0.3);
  }

  .thumb img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .generated-preview-state {
    width: 100%;
    height: 100%;
    display: grid;
    place-items: center;
    padding: 0.5rem;
    background: #f8fafc;
    color: #475569;
    font-size: 0.68rem;
    text-align: center;
  }

  .selection-chip {
    position: absolute;
    left: 0.45rem;
    top: 0.45rem;
    z-index: 2;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.76);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #cbd5e1;
    font-size: 0.64rem;
    padding: 0.2rem 0.45rem;
  }

  .selection-chip.included {
    color: #dcfce7;
    border-color: rgba(34, 197, 94, 0.4);
    background: rgba(22, 101, 52, 0.76);
  }

  .selection-toggle {
    position: absolute;
    right: 0.45rem;
    top: 0.45rem;
    z-index: 2;
    width: 26px;
    height: 26px;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.16);
    background: rgba(15, 23, 42, 0.84);
    color: #f8fafc;
    display: grid;
    place-items: center;
    font-weight: 700;
  }

  .selection-toggle.included {
    border-color: rgba(34, 197, 94, 0.45);
    background: rgba(22, 101, 52, 0.9);
    color: #dcfce7;
  }

  .thumb-placeholder {
    width: 100%;
    height: 100%;
    padding: 0.45rem;
    background: linear-gradient(180deg, #ffffff, #f1f5f9);
    display: grid;
    align-content: space-between;
    color: #111827;
  }

  .thumb-placeholder span {
    font-size: 0.68rem;
    color: #475569;
  }

  .thumb-placeholder strong {
    font-size: 0.7rem;
    line-height: 1.1;
  }

  @media (max-width: 1200px) {
    .global-deck-slide-navigator {
      width: 220px;
    }
  }

  @media (max-width: 960px) {
    .global-deck-slide-navigator {
      display: none;
    }
  }
</style>
