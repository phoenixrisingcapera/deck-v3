<script lang="ts">
  import type { RenderSchema } from '$lib/api/smartDeckWorkspace';

  interface Props {
    renderSchema: RenderSchema | null;
    selectedElementId: string | null;
    instruction: string;
    hasSelectedSlide?: boolean;
    isGenerating?: boolean;
    message?: string;
    isError?: boolean;
    onSelectElement?: (elementId: string) => void;
    onInstructionChange?: (value: string) => void;
    onGenerateVariation?: () => void;
    onGenerateSlide?: () => void;
  }

  let {
    renderSchema,
    selectedElementId,
    instruction,
    hasSelectedSlide = false,
    isGenerating = false,
    message = '',
    isError = false,
    onSelectElement,
    onInstructionChange,
    onGenerateVariation,
    onGenerateSlide
  }: Props = $props();

  const elements = $derived(renderSchema?.elements ?? []);
  const selectedElement = $derived(elements.find((element) => element.id === selectedElementId) ?? null);

  function elementLabel(element: RenderSchema['elements'][number]) {
    if (element.type === 'text') return element.text?.trim().slice(0, 72) || 'Text element';
    if (element.type === 'chart_placeholder') return element.analyticsKey || 'Chart placeholder';
    if (element.type === 'image') return 'Image';
    return 'Shape';
  }
</script>

<section class="elements-panel" aria-label="Slide elements">
  <header>
    <div>
      <span class="eyebrow">Selected slide</span>
      <h3>Elements</h3>
    </div>
    <span class="count">{elements.length}</span>
  </header>

  {#if elements.length > 0}
    <div class="element-list">
      {#each elements as element, index (element.id)}
        <button
          type="button"
          class:active={element.id === selectedElementId}
          aria-pressed={element.id === selectedElementId}
          onclick={() => onSelectElement?.(element.id)}
        >
          <span class="element-number">{index + 1}</span>
          <span class="element-copy">
            <strong>{element.type.replaceAll('_', ' ')}</strong>
            <small>{elementLabel(element)}</small>
          </span>
          <span class="element-size">{Math.round(element.width)} × {Math.round(element.height)}</span>
        </button>
      {/each}
    </div>

    {#if selectedElement}
      <section class="breakdown">
        <h4>Element breakdown</h4>
        <dl>
          <div><dt>Type</dt><dd>{selectedElement.type.replaceAll('_', ' ')}</dd></div>
          <div><dt>Position</dt><dd>{Math.round(selectedElement.x)}, {Math.round(selectedElement.y)}</dd></div>
          <div><dt>Size</dt><dd>{Math.round(selectedElement.width)} × {Math.round(selectedElement.height)}</dd></div>
          {#if selectedElement.fontSize}<div><dt>Font size</dt><dd>{selectedElement.fontSize}px</dd></div>{/if}
          {#if selectedElement.fontWeight}<div><dt>Weight</dt><dd>{selectedElement.fontWeight}</dd></div>{/if}
          {#if selectedElement.colorToken}<div><dt>Text token</dt><dd>{selectedElement.colorToken}</dd></div>{/if}
          {#if selectedElement.fillToken}<div><dt>Fill token</dt><dd>{selectedElement.fillToken}</dd></div>{/if}
          {#if selectedElement.assetUrl}<div><dt>Asset</dt><dd>Connected</dd></div>{/if}
          {#if selectedElement.analyticsKey}<div><dt>Data key</dt><dd>{selectedElement.analyticsKey}</dd></div>{/if}
        </dl>
      </section>

      <label class="instruction-field">
        <span>Fit this element with AI</span>
        <textarea
          id="smart-deck-element-instruction"
          name="elementInstruction"
          rows="5"
          value={instruction}
          placeholder="Shorten the copy, improve hierarchy, and fit it cleanly inside its current bounds."
          oninput={(event) => onInstructionChange?.((event.currentTarget as HTMLTextAreaElement).value)}
        ></textarea>
      </label>
      <button
        type="button"
        class="generate"
        disabled={isGenerating || !instruction.trim()}
        onclick={() => onGenerateVariation?.()}
      >
        {isGenerating ? 'Generating variation…' : 'Generate element variation'}
      </button>
      <p class="review-note">The LLM creates a reviewable design version. Apply changes only after checking the preview.</p>
    {:else}
      <p class="empty">Select an element to inspect its extracted properties and generate a fitted variation.</p>
    {/if}
  {:else}
    <div class="empty-card">
      <strong>{hasSelectedSlide ? 'Generate this slide’s editable elements' : 'Select a slide first'}</strong>
      <p class="empty">{hasSelectedSlide ? 'Use the existing Smart Deck generation workflow to create the text, image, chart, and shape cards for this slide.' : 'Choose a slide from the navigator, then return to Elements.'}</p>
      <button type="button" class="generate" disabled={!hasSelectedSlide || isGenerating} onclick={() => onGenerateSlide?.()}>
        {isGenerating ? 'Generating slide elements…' : 'Generate slide elements'}
      </button>
    </div>
  {/if}

  {#if message}
    <p class="panel-message" class:is-error={isError} role="status" aria-live="polite">{message}</p>
  {/if}
</section>

<style>
  .elements-panel { display: grid; gap: 1rem; color: #f8fafc; }
  header { display: flex; align-items: center; justify-content: space-between; gap: .75rem; }
  h3, h4 { margin: 0; }
  .eyebrow { color: #94a3b8; font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; }
  .count { min-width: 2rem; padding: .3rem .55rem; border-radius: 999px; background: rgba(124,58,237,.18); color: #c4b5fd; text-align: center; }
  .element-list { display: grid; gap: .5rem; }
  .element-list button { width: 100%; display: grid; grid-template-columns: 1.6rem minmax(0,1fr) auto; gap: .55rem; align-items: center; padding: .7rem; border-radius: 12px; border: 1px solid rgba(255,255,255,.08); background: rgba(15,23,42,.72); color: #e2e8f0; text-align: left; cursor: pointer; }
  .element-list button.active { border-color: rgba(139,92,246,.75); background: rgba(124,58,237,.2); }
  .element-number { color: #a78bfa; font-size: .72rem; }
  .element-copy { min-width: 0; display: grid; gap: .15rem; }
  .element-copy strong { text-transform: capitalize; font-size: .8rem; }
  .element-copy small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #94a3b8; }
  .element-size { color: #64748b; font-size: .66rem; }
  .breakdown { display: grid; gap: .65rem; padding: .8rem; border-radius: 12px; background: rgba(15,23,42,.72); border: 1px solid rgba(255,255,255,.08); }
  dl { display: grid; gap: .4rem; margin: 0; }
  dl div { display: flex; justify-content: space-between; gap: .7rem; font-size: .75rem; }
  dt { color: #94a3b8; } dd { margin: 0; color: #e2e8f0; text-align: right; overflow-wrap: anywhere; }
  .instruction-field { display: grid; gap: .4rem; color: #cbd5e1; font-size: .78rem; }
  textarea { resize: vertical; min-height: 6rem; padding: .75rem; border-radius: 12px; border: 1px solid rgba(255,255,255,.1); background: rgba(15,23,42,.85); color: #f8fafc; font: inherit; }
  .generate { padding: .75rem; border: 0; border-radius: 12px; background: linear-gradient(135deg,#7c3aed,#0ea5e9); color: white; font-weight: 700; cursor: pointer; }
  .generate:disabled { opacity: .5; cursor: not-allowed; }
  .empty-card { display: grid; gap: .75rem; padding: .9rem; border-radius: 12px; border: 1px solid rgba(255,255,255,.08); background: rgba(15,23,42,.72); }
  .panel-message { margin: 0; padding: .7rem .8rem; border-radius: 10px; background: rgba(34,197,94,.12); color: #86efac; font-size: .76rem; line-height: 1.5; }
  .panel-message.is-error { background: rgba(239,68,68,.12); color: #fda4af; }
  .review-note, .empty { margin: 0; color: #94a3b8; font-size: .76rem; line-height: 1.5; }
</style>
