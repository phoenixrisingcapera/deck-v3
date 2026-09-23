<script lang="ts">
  type DueDiligenceRailSlide = {
    id: string;
    slideIndex?: number;
    slideNumber?: number;
    title: string;
    previewUrl?: string | null;
    previewImageUrl?: string | null;
    thumbnailUrl?: string | null;
  };

  interface Props {
    slides: DueDiligenceRailSlide[];
    selectedSlideId: string | null;
    selectedSourceSlideIds?: string[];
    onSelectSlide?: (slideId: string) => void;
    onToggleSourceSlideSelection?: (slideId: string) => void;
    onOpenSmartEdit?: (slideId: string) => void;
  }

  let { slides, selectedSlideId, selectedSourceSlideIds = [], onSelectSlide, onToggleSourceSlideSelection, onOpenSmartEdit }: Props = $props();
  let failedThumbUrls = $state<string[]>([]);

  function miniatureUrl(slide: DueDiligenceRailSlide) {
    if (slide.thumbnailUrl && !failedThumbUrls.includes(slide.thumbnailUrl)) return slide.thumbnailUrl;
    if (slide.previewUrl && !failedThumbUrls.includes(slide.previewUrl)) return slide.previewUrl;
    if (slide.previewImageUrl && !failedThumbUrls.includes(slide.previewImageUrl)) return slide.previewImageUrl;
    return null;
  }

  function markFailed(url: string) {
    if (!failedThumbUrls.includes(url)) failedThumbUrls = [...failedThumbUrls, url];
  }
</script>

<aside id="dd-slide-rail" class="dd-slide-rail">
  <div class="dd-slide-rail__header">
    <h2>Slides</h2>
    <p>Browse deck slides.</p>
  </div>

  <div class="dd-slide-rail__list" role="list">
    {#each slides as slide}
      {@const imageUrl = miniatureUrl(slide)}
      {@const num = slide.slideNumber ?? (slide.slideIndex ?? 0) + 1}
      <div
        class="dd-slide-card"
        class:active={slide.id === selectedSlideId}
        role="button"
        tabindex="0"
        aria-current={slide.id === selectedSlideId ? 'true' : undefined}
        aria-label={`Slide ${num}: ${slide.title}`}
        onclick={() => onSelectSlide?.(slide.id)}
        ondblclick={() => onOpenSmartEdit?.(slide.id)}
        onkeydown={(event) => {
          if (event.key !== 'Enter' && event.key !== ' ') return;
          event.preventDefault();
          onSelectSlide?.(slide.id);
        }}
      >
        <div class="dd-thumb">
          <span class:included={selectedSourceSlideIds.includes(slide.id)} class="dd-selection-chip">
            {selectedSourceSlideIds.includes(slide.id) ? 'Included' : 'Excluded'}
          </span>
          <button
            type="button"
            class:included={selectedSourceSlideIds.includes(slide.id)}
            class="dd-selection-toggle"
            aria-label={`${selectedSourceSlideIds.includes(slide.id) ? 'Remove' : 'Include'} slide ${num} from deck redesign`}
            onclick={(event) => {
              event.stopPropagation();
              onToggleSourceSlideSelection?.(slide.id);
            }}
          >
            {selectedSourceSlideIds.includes(slide.id) ? '✓' : '+'}
          </button>
          {#if imageUrl}
            <img src={imageUrl} alt={`${slide.title} thumbnail`} onerror={() => markFailed(imageUrl)} />
          {:else}
            <div class="dd-thumb-placeholder">
              <span>{String(num).padStart(2, '0')}</span>
            </div>
          {/if}
        </div>
      </div>
    {/each}
  </div>
</aside>

<style>
  .dd-slide-rail {
    grid-column: 2;
    grid-row: 1;
    background: rgba(16, 24, 39, 0.9);
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    padding: 0.75rem 0.6rem;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
  }

  .dd-slide-rail__header {
    margin-bottom: 0.75rem;
  }

  .dd-slide-rail__header h2 {
    margin: 0;
    font-size: 0.72rem;
    color: #f8fafc;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .dd-slide-rail__header p {
    margin: 0.15rem 0 0;
    color: #64748b;
    font-size: 0.65rem;
  }

  .dd-slide-rail__list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    overflow: auto;
    flex: 1;
  }

  .dd-slide-card {
    display: block;
    width: 100%;
    padding: 0.4rem;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(15, 23, 42, 0.68);
    color: #f8fafc;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
  }

  .dd-slide-card:hover {
    border-color: rgba(255, 255, 255, 0.15);
  }

  .dd-slide-card.active {
    border-color: rgba(245, 158, 11, 0.9);
    background: linear-gradient(135deg, rgba(120, 53, 15, 0.45), rgba(245, 158, 11, 0.22));
    box-shadow: inset 0 0 0 1px rgba(245, 158, 11, 0.2);
  }

  .dd-thumb {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    border-radius: 6px;
    overflow: hidden;
    background: #fff;
    box-shadow: 0 4px 10px rgba(2, 6, 23, 0.3);
  }

  .dd-thumb img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .dd-selection-chip {
    position: absolute;
    left: 0.35rem;
    top: 0.35rem;
    z-index: 2;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.76);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #cbd5e1;
    font-size: 0.62rem;
    padding: 0.18rem 0.42rem;
  }

  .dd-selection-chip.included {
    color: #fef3c7;
    border-color: rgba(245, 158, 11, 0.45);
    background: rgba(120, 53, 15, 0.84);
  }

  .dd-selection-toggle {
    position: absolute;
    right: 0.35rem;
    top: 0.35rem;
    z-index: 2;
    width: 24px;
    height: 24px;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.16);
    background: rgba(15, 23, 42, 0.84);
    color: #f8fafc;
    display: grid;
    place-items: center;
    font-weight: 700;
  }

  .dd-selection-toggle.included {
    border-color: rgba(245, 158, 11, 0.5);
    background: rgba(120, 53, 15, 0.9);
    color: #fef3c7;
  }

  .dd-thumb-placeholder {
    width: 100%;
    height: 100%;
    padding: 0.3rem;
    background: linear-gradient(180deg, #ffffff, #f1f5f9);
    display: grid;
    align-content: center;
    justify-items: center;
    color: #111827;
  }

  .dd-thumb-placeholder span {
    font-size: 0.72rem;
    color: #475569;
    font-weight: 600;
  }

  @media (max-width: 960px) {
    .dd-slide-rail {
      grid-column: 1;
      grid-row: 2;
      border-right: none;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      padding: 0.5rem 0.6rem;
      flex-direction: row;
      overflow-x: auto;
      overflow-y: hidden;
      gap: 0.4rem;
    }

    .dd-slide-rail__header {
      display: none;
    }

    .dd-slide-rail__list {
      flex-direction: row;
      flex: unset;
    }

    .dd-slide-rail__list button {
      min-width: 64px;
      width: 64px;
    }
  }
</style>
