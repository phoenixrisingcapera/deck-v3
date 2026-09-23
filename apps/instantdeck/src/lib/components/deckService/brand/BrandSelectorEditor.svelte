<!-- Purpose: manual brand-profile editing form and save/ cancel action controls. -->
<script lang="ts">
  import { getBrandFieldStatusLabel, type BrandProfile } from '$lib/types/deckService-brand';

  let {
    brandProfile,
    saving = false,
    saveError = '',
    onSave,
    onCancel
  }: {
    brandProfile: BrandProfile;
    saving?: boolean;
    saveError?: string;
    onSave: (payload: {
      primaryColor: string;
      secondaryColor: string;
      accentColor: string;
      backgroundColor: string;
      textColor: string;
      visualStyle: string;
      fontCandidates: string[];
    }) => void;
    onCancel: () => void;
  } = $props();

  let primaryColor = $state('#3B82F6');
  let secondaryColor = $state('#0F172A');
  let accentColor = $state('#7C3AED');
  let backgroundColor = $state('#081225');
  let textColor = $state('#E5EEF8');
  let visualStyle = $state('Modern, technical, confident');
  let fontCandidatesText = $state('');

  $effect(() => {
    primaryColor = brandProfile.primaryColor ?? '#3B82F6';
    secondaryColor = brandProfile.secondaryColor ?? '#0F172A';
    accentColor = brandProfile.accentColor ?? '#7C3AED';
    backgroundColor = brandProfile.backgroundColor ?? '#081225';
    textColor = brandProfile.textColor ?? '#E5EEF8';
    visualStyle = brandProfile.visualStyle ?? 'Modern, technical, confident';
    fontCandidatesText = (brandProfile.fontCandidates ?? []).join(', ');
  });

  // Parse form input and emit the normalized brand-profile payload.
  function submit() {
    onSave({
      primaryColor,
      secondaryColor,
      accentColor,
      backgroundColor,
      textColor,
      visualStyle: visualStyle.trim(),
      fontCandidates: fontCandidatesText
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean)
    });
  }
</script>

<section class="selector-card">
  <div class="selector-head">
    <div>
      <div class="eyebrow">Brand selector</div>
      <strong>Review and tune the extracted brand</strong>
    </div>
    <span>Persisted to brand profile</span>
  </div>

  <div class="color-grid">
    <label>
      <span>Primary</span>
      <small>{getBrandFieldStatusLabel(brandProfile, 'primaryColor')}</small>
      <input id="brand-selector-primary" name="primaryColor" bind:value={primaryColor} type="color" />
    </label>
    <label>
      <span>Secondary</span>
      <small>{getBrandFieldStatusLabel(brandProfile, 'secondaryColor')}</small>
      <input id="brand-selector-secondary" name="secondaryColor" bind:value={secondaryColor} type="color" />
    </label>
    <label>
      <span>Accent</span>
      <small>{getBrandFieldStatusLabel(brandProfile, 'accentColor')}</small>
      <input id="brand-selector-accent" name="accentColor" bind:value={accentColor} type="color" />
    </label>
    <label>
      <span>Background</span>
      <small>{getBrandFieldStatusLabel(brandProfile, 'backgroundColor')}</small>
      <input id="brand-selector-background" name="backgroundColor" bind:value={backgroundColor} type="color" />
    </label>
    <label>
      <span>Text</span>
      <small>{getBrandFieldStatusLabel(brandProfile, 'textColor')}</small>
      <input id="brand-selector-text" name="textColor" bind:value={textColor} type="color" />
    </label>
  </div>

  <label class="field">
    <span>Visual style</span>
    <input id="brand-selector-visual-style" name="visualStyle" bind:value={visualStyle} type="text" placeholder="Modern, technical, confident" />
  </label>

  <label class="field">
    <span>Typography candidates</span>
    <small>{getBrandFieldStatusLabel(brandProfile, 'fontCandidates')}</small>
    <input id="brand-selector-fonts" name="fontCandidates" bind:value={fontCandidatesText} type="text" placeholder="Satoshi, IBM Plex Sans" />
  </label>

  {#if saveError}
    <p class="error-copy">{saveError}</p>
  {/if}

  <div class="selector-actions">
    <button class="button secondary" type="button" onclick={onCancel} disabled={saving}>Cancel</button>
    <button class="button" type="button" onclick={submit} disabled={saving}>
      {saving ? 'Saving brand...' : 'Save brand selection'}
    </button>
  </div>
</section>

<style>
  .selector-card {
    display: grid;
    gap: 0.95rem;
    border: 1px solid var(--line);
    border-radius: 20px;
    padding: 1rem;
    background: rgba(255, 255, 255, 0.02);
  }

  .selector-head,
  .selector-actions {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .selector-head span,
  .field span,
  label span {
    color: var(--muted);
    font-size: 0.84rem;
  }

  label small {
    color: var(--muted);
    font-size: 0.72rem;
  }

  .color-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 0.75rem;
  }

  label,
  .field {
    display: grid;
    gap: 0.4rem;
  }

  input[type='color'] {
    width: 100%;
    min-height: 3rem;
    border-radius: 14px;
    border: 1px solid var(--line);
    background: transparent;
    padding: 0.25rem;
  }

  input[type='text'] {
    width: 100%;
    border-radius: 16px;
    border: 1px solid var(--line-strong);
    padding: 0.85rem 0.95rem;
    background: var(--surface-input);
    color: var(--ink);
  }

  .error-copy {
    margin: 0;
    color: var(--danger);
  }

  @media (max-width: 960px) {
    .color-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
</style>
