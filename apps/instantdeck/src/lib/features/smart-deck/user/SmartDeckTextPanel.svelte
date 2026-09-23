<script lang="ts">
  interface Props {
    hasGeneratedSlide: boolean;
    designTokens?: Record<string, string> | null;
    saving?: boolean;
    message?: string;
    onSave?: (input: { headingFont: string; bodyFont: string }) => void | Promise<void>;
  }

  let { hasGeneratedSlide, designTokens = null, saving = false, message = '', onSave }: Props = $props();
  const FONT_OPTIONS = [
    { value: 'Inter, Arial, sans-serif', label: 'Inter / Arial' },
    { value: 'Arial, sans-serif', label: 'Arial' },
    { value: 'Verdana, sans-serif', label: 'Verdana' },
    { value: "'Trebuchet MS', Arial, sans-serif", label: 'Trebuchet' },
    { value: 'Georgia, serif', label: 'Georgia' },
    { value: "'Times New Roman', serif", label: 'Times New Roman' },
    { value: "'Courier New', monospace", label: 'Courier New' }
  ] as const;

  let headingFont = $state('Inter, Arial, sans-serif');
  let bodyFont = $state('Inter, Arial, sans-serif');

  $effect(() => {
    headingFont = designTokens?.['brand.headingFont'] ?? 'Inter, Arial, sans-serif';
    bodyFont = designTokens?.['brand.bodyFont'] ?? 'Inter, Arial, sans-serif';
  });
</script>

<section class="text-panel">
  <header>
    <span>Slide typography</span>
    <h2>Text styles</h2>
    <p>Choose heading and body fonts for the active generated slide. Changes are saved to this slide and reflected by the mounted renderer tokens.</p>
  </header>

  {#if hasGeneratedSlide}
    <div class="preview" style={`--heading-font:${headingFont};--body-font:${bodyFont}`}>
      <strong>Investor-ready heading</strong>
      <p>Clear supporting copy with a consistent executive reading rhythm.</p>
    </div>
    <label>
      <span>Heading font</span>
      <select id="smart-deck-heading-font" name="headingFont" bind:value={headingFont}>
        {#each FONT_OPTIONS as option}<option value={option.value}>{option.label}</option>{/each}
      </select>
    </label>
    <label>
      <span>Body font</span>
      <select id="smart-deck-body-font" name="bodyFont" bind:value={bodyFont}>
        {#each FONT_OPTIONS as option}<option value={option.value}>{option.label}</option>{/each}
      </select>
    </label>
    <button type="button" disabled={saving} onclick={() => void onSave?.({ headingFont, bodyFont })}>{saving ? 'Saving…' : 'Apply fonts to slide'}</button>
  {:else}
    <div class="empty"><strong>Generate a slide first</strong><p>Typography can be applied after the selected slide has a generated version.</p></div>
  {/if}
  {#if message}<p class="message" role="status">{message}</p>{/if}
</section>

<style>
  .text-panel, header, label { display: grid; gap: .7rem; }
  header > span { color: #38bdf8; font-size: .72rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  h2, p { margin: 0; }
  header p, .message, .empty p { color: #94a3b8; line-height: 1.45; }
  .preview, .empty { display: grid; gap: .55rem; padding: 1rem; border: 1px solid rgba(255,255,255,.1); border-radius: 12px; background: rgba(15,23,42,.78); }
  .preview strong { font-family: var(--heading-font); color: #f8fafc; font-size: 1.2rem; }
  .preview p { font-family: var(--body-font); color: #cbd5e1; }
  label span { color: #cbd5e1; font-size: .78rem; font-weight: 700; }
  select { width: 100%; min-height: 42px; border: 1px solid rgba(255,255,255,.1); border-radius: 10px; background: rgba(15,23,42,.9); color: #f8fafc; padding: .65rem; font: inherit; }
  button { min-height: 42px; border: 0; border-radius: 10px; background: linear-gradient(135deg,#7c3aed,#0ea5e9); color: white; font-weight: 800; cursor: pointer; }
  button:disabled { opacity: .55; cursor: not-allowed; }
</style>
