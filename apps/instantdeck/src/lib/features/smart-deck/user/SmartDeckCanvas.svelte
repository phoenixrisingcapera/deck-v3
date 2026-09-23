<script lang="ts">
  import GeneratedSlideRenderer from '$lib/components/smart-deck/GeneratedSlideRenderer.svelte';
  import type { SmartDeckEditorMode, SmartDeckUserSlideViewModel } from './smartDeckUserTypes';
  import type { RenderSchema } from '$lib/api/smartDeckWorkspace';

  interface Props {
    slide: SmartDeckUserSlideViewModel | null;
    mode: SmartDeckEditorMode;
    renderSchema?: RenderSchema | null;
    designTokens?: Record<string, string> | null;
    selectedElementId?: string | null;
    onSelectElement?: (elementId: string) => void;
    onImproveSlide?: () => void;
    focusedGeneration?: boolean;
  }

  let {
    slide,
    mode,
    renderSchema = null,
    designTokens = null,
    selectedElementId = null,
    onSelectElement,
    onImproveSlide,
    focusedGeneration = false
  }: Props = $props();
</script>

<section class="deck-canvas-area" data-deck-region="visualizer" aria-label="Selected slide visualizer">
  <div class="slide-canvas-shell">
    <!-- DISABLED: Element toolbar shows only a static "not available" message that confuses users.
         Re-enable when real editing controls are implemented. -->
    <!-- <SmartDeckElementToolbar visible={mode === 'edit' && Boolean(selectedElementId)} /> -->

    <div class="slide-canvas" class:is-play={mode === 'play'} class:is-preview={mode === 'preview'}>
      {#if focusedGeneration && !renderSchema}
        <div class="slide-empty-state slide-empty-state--generation">
          <strong>Add your prompt to generate your deck, or describe the change you want.</strong>
          <p>The source miniatures remain available for reference while the LLM prepares a complete new version.</p>
        </div>
      {:else if renderSchema}
        <GeneratedSlideRenderer
          {renderSchema}
          {designTokens}
          selectedElementId={null}
          interactive={false}
        />
      {:else if slide?.previewUrl}
        <img class="slide-preview-image" src={slide.previewUrl} alt={`${slide.title} preview`} />
      {:else}
        <div class="slide-empty-state">
          {#if slide?.hasGeneratedVersion}
            <strong>Generated slide format unavailable</strong>
            <p>The saved LLM output for this slide does not yet include a render schema or preview image that the Smart Deck canvas can display truthfully.</p>
            <p class="preview-only-note">Regenerate the deck or open Smart Edit only after a real generated slide preview is available.</p>
          {:else}
            <!-- DISABLED: The prior empty state said no slide was selected even
                 when the selectors had a real slide but no generated visual. -->
            <!-- <strong>Select a slide to start editing</strong> -->
            <strong>{slide ? 'Create an editable version of this slide' : 'Select a slide to start editing'}</strong>
            <p>{slide ? 'Use the AI assistant to generate an investor-ready layout and narrative for the selected slide.' : 'Choose a slide from the navigator to begin.'}</p>
            <p class="preview-only-note">Use the whole-deck prompt to regenerate all active slides.</p>
          {/if}
        </div>
      {/if}
    </div>

  </div>
</section>

<style>
  .deck-canvas-area {
    grid-column: 3;
    grid-row: 2;
    min-width: 0;
    min-height: 0;
    background: linear-gradient(180deg, rgba(8, 13, 27, 0.98), rgba(10, 17, 33, 0.95));
    padding: 1.5rem;
    overflow: auto;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .slide-canvas-shell {
    width: min(100%, 1040px);
    position: relative;
  }

  .slide-canvas {
    width: min(100%, 960px);
    aspect-ratio: 16 / 9;
    margin: 0 auto;
    border-radius: 8px;
    background: white;
    color: #111827;
    box-shadow: 0 40px 80px rgba(2, 6, 23, 0.45);
    overflow: hidden;
    position: relative;
    display: grid;
    place-items: center;
    pointer-events: none;
  }

  .slide-canvas :global(.render-stage),
  .slide-canvas :global(.render-empty) {
    width: 100%;
    height: 100%;
    max-width: none;
    border: none;
    box-shadow: none;
    border-radius: 0;
  }

  .slide-canvas.is-play :global(.render-element:hover),
  .slide-canvas.is-play :global(.render-element.selected),
  .slide-canvas.is-preview :global(.render-element:hover),
  .slide-canvas.is-preview :global(.render-element.selected) {
    border-color: transparent;
    box-shadow: none;
  }

  .slide-preview-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .slide-empty-state {
    display: grid;
    justify-items: center;
    gap: 0.9rem;
    text-align: center;
    max-width: 28rem;
    padding: 2rem;
  }

  .slide-empty-state strong {
    font-size: 1.3rem;
  }

  .slide-empty-state p {
    margin: 0;
    color: #475569;
    line-height: 1.6;
  }

  .slide-empty-state button {
    height: 42px;
    border-radius: 10px;
    border: none;
    padding: 0 1rem;
    color: white;
    background: linear-gradient(135deg, #7c3aed, #0ea5e9);
    box-shadow: 0 14px 28px rgba(76, 29, 149, 0.28);
    cursor: pointer;
  }

  .slide-empty-state button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  @media (max-width: 960px) {
    .deck-canvas-area {
      grid-column: 2;
      grid-row: 2;
      padding: 1rem;
    }
  }

  @media (max-width: 720px) {
    .deck-canvas-area {
      grid-column: 1;
      grid-row: 3;
      padding: 0.9rem;
    }

    .slide-canvas-shell {
      width: 100%;
    }

    .slide-canvas { width: 100%; }
  }
</style>
