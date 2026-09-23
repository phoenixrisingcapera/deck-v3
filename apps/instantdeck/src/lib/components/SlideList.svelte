<script lang="ts">
  import type { DeckSlide } from '$types/domain';

  interface Props {
    slides: DeckSlide[];
    selectedSlideId?: string;
    hrefBase: string;
  }

  let { slides, selectedSlideId, hrefBase }: Props = $props();

  function slideImageUrl(slide: DeckSlide) {
    return slide.previewUrl ?? slide.previewImageUrl ?? slide.thumbnailUrl ?? null;
  }
</script>

<aside class="panel slide-list">
  <div class="topline">
    <div class="eyebrow">Slides</div>
    <span>{slides.length}</span>
  </div>
  {#each slides as slide}
    {@const imageUrl = slideImageUrl(slide)}
    <a class:selected={slide.id === selectedSlideId} href={`${hrefBase}?slide=${slide.id}`}>
      <span class:has-image={Boolean(imageUrl)}>
        {#if imageUrl}
          <img src={imageUrl} alt="" loading="lazy" />
        {:else}
          {slide.slideNumber ?? slide.slideIndex}
        {/if}
      </span>
      <div>
        <strong>{slide.title}</strong>
        <small>{slide.role}</small>
      </div>
    </a>
  {/each}
</aside>

<style>
  .slide-list {
    padding: 1rem;
    display: grid;
    gap: 0.6rem;
    align-content: start;
    background: rgba(255,255,255,0.03);
  }

  .topline {
    display: flex;
    justify-content: space-between;
    color: var(--muted);
    margin-bottom: 0.3rem;
  }

  a {
    display: grid;
    grid-template-columns: 36px 1fr;
    gap: 0.75rem;
    padding: 0.75rem;
    border-radius: var(--radius-sm);
    border: 1px solid transparent;
  }

  a.selected {
    background: rgba(104, 161, 255, 0.12);
    border-color: rgba(104, 161, 255, 0.18);
  }

  span {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.06);
    display: grid;
    place-items: center;
    font-weight: 700;
    overflow: hidden;
  }

  span.has-image {
    background: #020617;
  }

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  small {
    display: block;
    color: var(--muted);
    text-transform: capitalize;
  }
</style>
