<!-- Purpose: renders an individual generated slide from render schema and maps brand tokens/assets for safe display. The visualizer must not substitute source or LLM summary text for a slide render. -->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import GeneratedSlideRenderer from '$lib/components/smart-deck/GeneratedSlideRenderer.svelte';
  import SanitizedHtmlSlideRenderer from '$lib/components/smart-deck/SanitizedHtmlSlideRenderer.svelte';
  import type { HtmlCompiledSlideRenderIdentity, RenderSchema } from '$lib/api/smartDeckWorkspace';

  export type DeckVisualizerMode = 'schema-first' | 'image-first';

  export type VisualizerSlide = {
    title: string;
    slideIndex?: number | null;
    slideNumber?: number | null;
    number?: number | null;
    role?: string | null;
    previewImageUrl?: string | null;
    previewUrl?: string | null;
    thumbnailUrl?: string | null;
    extractedText?: string | null;
    rawText?: string | null;
  };

  interface Props {
    title: string;
    subtitle?: string;
    slide?: VisualizerSlide | null;
    renderSchema?: RenderSchema | null;
    htmlSlide?: HtmlCompiledSlideRenderIdentity | null;
    htmlDisplayMode?: 'section' | 'full-document';
    designTokens?: Record<string, string> | null;
    selectedElementId?: string | null;
    lockedElementIds?: string[];
    onSelectElement?: (elementId: string) => void;
    onActivateElement?: (elementId: string) => void;
    onActivateCanvas?: () => void;
    onChangeElementGeometry?: (elementId: string, geometry: { x: number; y: number; width: number; height: number }) => void;
    interactive?: boolean;
    visualMode?: DeckVisualizerMode;
    editable?: boolean;
    emptyTitle?: string;
    emptyText?: string;
    children?: Snippet;
  }

  let {
    title,
    subtitle = '',
    slide = null,
    renderSchema = null,
    htmlSlide = null,
    htmlDisplayMode = 'section',
    designTokens = null,
    selectedElementId = null,
    lockedElementIds = [],
    onSelectElement,
    onActivateElement,
    onActivateCanvas,
    onChangeElementGeometry,
    visualMode = 'schema-first',
    editable = false,
    emptyTitle = 'No slide available',
    emptyText = 'Select a slide to load the shared visualizer surface.',
    interactive = true,
    children
  }: Props = $props();

  const slideLabel = $derived(
    htmlSlide && htmlDisplayMode === 'full-document'
      ? 'Complete deck'
      : slide ? `Slide ${String(slide.slideIndex ?? slide.slideNumber ?? slide.number ?? 0).padStart(2, '0')}` : 'No slide selected'
  );
  const slideTitle = $derived(slide?.title ?? emptyTitle);
  const slideSource = $derived(slide ? slideImageUrl(slide) : null);
  const hasRenderableSchema = $derived(Boolean(renderSchema?.elements?.length));

  // Resolve safe slide image source URLs and normalize relative artifact paths.
  function slideImageUrl(currentSlide: VisualizerSlide) {
    const url = currentSlide.previewImageUrl ?? currentSlide.previewUrl ?? currentSlide.thumbnailUrl ?? null;
    if (!url) return null;
    if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('/') || url.startsWith('data:')) {
      return url;
    }
    return `/${url}`;
  }
</script>

<article
  class="global-deck-visualizer"
  data-deck-region="visualizer"
  data-display-mode={htmlSlide && htmlDisplayMode === 'full-document' ? 'full-document' : 'section'}
  aria-label="Selected slide visualizer"
>
  <header class="surface-header">
    <div>
      <div class="eyebrow">Deck preview</div>
      <h3>{title}</h3>
      {#if subtitle}
        <p>{subtitle}</p>
      {/if}
    </div>
    <span class="surface-pill">{slideLabel}</span>
  </header>

  <!-- svelte-ignore a11y_no_static_element_interactions -- visible CTA is the keyboard path -->
  <div class="surface-frame" class:surface-frame--html-section={Boolean(htmlSlide && htmlDisplayMode === 'section')} class:surface-frame--full-document={Boolean(htmlSlide && htmlDisplayMode === 'full-document')} class:surface-frame--activatable={Boolean(onActivateCanvas)} ondblclick={() => onActivateCanvas?.()}>
    {#if visualMode === 'image-first' && slideSource}
      <img src={slideSource} alt="" loading="lazy" />
    {:else if htmlSlide}
      <SanitizedHtmlSlideRenderer slide={htmlSlide} mode={htmlDisplayMode === 'full-document' ? 'full-document' : 'visualizer'} loading="eager" label={htmlDisplayMode === 'full-document' ? `${title} complete generated HTML deck` : `${slideTitle} generated HTML preview`} />
    {:else if hasRenderableSchema}
      <GeneratedSlideRenderer
        renderSchema={renderSchema}
        designTokens={designTokens}
        selectedElementId={selectedElementId}
        {lockedElementIds}
        {onSelectElement}
        {onActivateElement}
        {onChangeElementGeometry}
        {interactive}
        {editable}
      />
    {:else if slideSource}
      <img src={slideSource} alt="" loading="lazy" />
    {:else if slide}
      <div class="surface-empty">
        <strong>{slideTitle}</strong>
        <p>{emptyText}</p>
      </div>
    {:else}
      <div class="surface-empty">
        <strong>{emptyTitle}</strong>
        <p>{emptyText}</p>
      </div>
    {/if}
  </div>

  {#if children}
    <div class="surface-content">
      {@render children()}
    </div>
  {/if}

</article>

<style>
  .global-deck-visualizer {
    display: grid;
    gap: 0.9rem;
    padding: 0;
    width: min(100%, 1040px);
    justify-self: center;
    min-width: 0;
  }

  .surface-header {
    display: flex;
    justify-content: space-between;
    align-items: start;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .surface-header h3 {
    margin: 0.25rem 0 0;
  }

  .surface-header p {
    margin: 0.3rem 0 0;
    color: var(--muted);
  }

  .surface-pill {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 0.45rem 0.75rem;
    border: 1px solid var(--line);
    background: rgba(255, 255, 255, 0.04);
    white-space: nowrap;
  }

  .surface-frame {
    min-height: 320px;
    aspect-ratio: 16 / 9;
    border-radius: 18px;
    overflow: hidden;
    border: 1px solid var(--line);
    background: #fff;
    box-shadow: 0 24px 70px rgba(0, 0, 0, 0.42);
  }
  .surface-frame--html-section { width: 100%; min-height: 0; }
  .surface-frame--html-section :global(.html-slide) { min-height: 0; }
  .surface-frame--activatable { cursor: pointer; }
  .surface-frame--full-document { aspect-ratio: auto; height: clamp(520px, 72vh, 920px); min-height: 0; }

  .surface-frame :global(.render-stage),
  .surface-frame :global(.render-empty) {
    width: 100%;
    min-height: 320px;
  }

  .surface-frame img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
    background: rgba(0, 0, 0, 0.16);
  }

  .surface-content {
    display: grid;
    gap: 0.9rem;
  }

  .surface-empty {
    min-height: 320px;
    display: grid;
    align-content: center;
    justify-items: start;
    gap: 0.35rem;
    padding: 1.2rem;
    color: #0f172a;
    background: #fff;
  }

  .surface-empty p {
    margin: 0;
    color: #475569;
  }

  @media (max-width: 720px) {
    .global-deck-visualizer[data-display-mode='full-document'] {
      height: 100%;
      max-height: 100%;
      grid-template-rows: auto minmax(0, 1fr) auto;
      overflow: hidden;
    }

    .global-deck-visualizer[data-display-mode='full-document'] .surface-frame--full-document {
      height: 100%;
      min-height: 0;
    }
  }

</style>
