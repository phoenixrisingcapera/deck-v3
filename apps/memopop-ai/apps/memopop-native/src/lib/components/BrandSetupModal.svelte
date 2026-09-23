<script lang="ts">
  import { settings } from '$lib/stores/settings.svelte';
  import { flow } from '$lib/stores/flow.svelte';
  import { getTransport, type ApiError } from '$lib/transport';

  interface Props {
    firm: string;
  }

  let { firm }: Props = $props();

  type Step = 'prompt_url' | 'fetching' | 'confirm' | 'saving' | 'saved';
  let step = $state<Step>('prompt_url');

  let url = $state('');
  let errorMessage = $state<string | null>(null);

  // Editable fields populated from the fetch — every one a string the user can change.
  let companyName = $state('');
  let legalEntityName = $state('');
  let tagline = $state('');

  let primaryColor = $state('');
  let secondaryColor = $state('');
  let accentColor = $state('');
  let textDark = $state('');
  let textLight = $state('');
  let background = $state('');
  let backgroundAlt = $state('');

  let primaryColorDark = $state('');
  let secondaryColorDark = $state('');
  let backgroundDark = $state('');

  let fontFamily = $state('');
  let googleFontsUrl = $state('');
  let headerFontFamily = $state('');

  let logoLightUrl = $state('');
  let logoDarkUrl = $state('');
  let logoAlt = $state('');

  let confidenceNotes = $state('');

  function close() {
    flow.close();
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && (step === 'prompt_url' || step === 'confirm' || step === 'saved')) {
      close();
    }
  }

  function looksLikeUrl(s: string): boolean {
    const trimmed = s.trim();
    return /^https?:\/\/[^\s]+\.[^\s]+/.test(trimmed);
  }

  async function fetchBrand() {
    errorMessage = null;
    if (!looksLikeUrl(url)) {
      errorMessage = 'Enter a valid http:// or https:// URL.';
      return;
    }
    if (!settings.repoPath) {
      errorMessage = 'Orchestrator path not set. Open Settings to anchor the repo.';
      return;
    }
    step = 'fetching';
    try {
      const result = await getTransport().request<{ firm: string; config: any }>(
        'POST',
        '/actions/fetch-brand',
        {
          repoPath: settings.repoPath,
          firm,
          url: url.trim(),
        }
      );
      hydrateForm(result.config ?? {});
      step = 'confirm';
    } catch (e) {
      errorMessage = (e as ApiError)?.message ?? 'Failed to fetch brand info.';
      step = 'prompt_url';
    }
  }

  function hydrateForm(cfg: any) {
    const company = cfg.company ?? {};
    const colors = cfg.colors ?? {};
    const colorsDark = cfg.colors_dark ?? {};
    const fonts = cfg.fonts ?? {};
    const logo = cfg.logo ?? {};
    const meta = cfg._meta ?? {};

    companyName = company.name ?? '';
    legalEntityName = company.legal_entity_name ?? '';
    tagline = company.tagline ?? '';

    primaryColor = colors.primary ?? '';
    secondaryColor = colors.secondary ?? '';
    accentColor = colors.accent ?? '';
    textDark = colors.text_dark ?? '';
    textLight = colors.text_light ?? '';
    background = colors.background ?? '';
    backgroundAlt = colors.background_alt ?? '';

    primaryColorDark = colorsDark.primary ?? '';
    secondaryColorDark = colorsDark.secondary ?? '';
    backgroundDark = colorsDark.background ?? '';

    fontFamily = fonts.family ?? '';
    googleFontsUrl = fonts.google_fonts_url ?? '';
    headerFontFamily = fonts.header_family ?? '';

    logoLightUrl = logo.light_mode ?? '';
    logoDarkUrl = logo.dark_mode ?? '';
    logoAlt = logo.alt ?? '';

    confidenceNotes = meta.confidence_notes ?? '';
  }

  function buildConfigForSave(): any {
    const company: any = {
      name: companyName.trim() || undefined,
      legal_entity_name: legalEntityName.trim() || undefined,
      tagline: tagline.trim() || undefined,
      confidential_footer: 'This document is confidential and proprietary to {company_name}.',
    };

    const colors: any = {
      primary: primaryColor.trim() || undefined,
      secondary: secondaryColor.trim() || undefined,
      accent: accentColor.trim() || undefined,
      text_dark: textDark.trim() || undefined,
      text_light: textLight.trim() || undefined,
      background: background.trim() || undefined,
      background_alt: backgroundAlt.trim() || undefined,
    };

    const colorsDark: any = {
      primary: primaryColorDark.trim() || undefined,
      secondary: secondaryColorDark.trim() || undefined,
      background: backgroundDark.trim() || undefined,
    };

    const fonts: any = {
      family: fontFamily.trim() || undefined,
      google_fonts_url: googleFontsUrl.trim() || undefined,
      header_family: headerFontFamily.trim() || undefined,
      fallback: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      header_fallback: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      weight: 400,
      header_weight: 700,
    };

    const logo: any = {
      light_mode: logoLightUrl.trim() || undefined,
      dark_mode: logoDarkUrl.trim() || undefined,
      alt: logoAlt.trim() || companyName.trim() || undefined,
      width: '180px',
      height: '60px',
    };

    return {
      company: stripUndefined(company),
      colors: stripUndefined(colors),
      colors_dark: stripUndefined(colorsDark),
      fonts: stripUndefined(fonts),
      logo: stripUndefined(logo),
    };
  }

  function stripUndefined(o: any): any {
    const out: any = {};
    for (const [k, v] of Object.entries(o)) {
      if (v !== undefined && v !== '') out[k] = v;
    }
    return out;
  }

  async function saveBrand() {
    errorMessage = null;
    if (!settings.repoPath) {
      errorMessage = 'Orchestrator path not set.';
      return;
    }
    step = 'saving';
    try {
      await getTransport().request<{ firm: string; path: string }>(
        'POST',
        '/actions/save-brand',
        {
          repoPath: settings.repoPath,
          firm,
          config: buildConfigForSave(),
        }
      );
      step = 'saved';
    } catch (e) {
      errorMessage = (e as ApiError)?.message ?? 'Failed to save brand config.';
      step = 'confirm';
    }
  }

  function isValidHexOrEmpty(s: string): boolean {
    if (!s.trim()) return true;
    return /^#?[0-9a-fA-F]{3,8}$/.test(s.trim());
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="backdrop" role="dialog" aria-modal="true" aria-labelledby="brand-modal-title" tabindex="-1">
  <div class="modal">
    <header class="modal-head">
      <div class="head-meta">
        <span class="step-pill">Brand setup</span>
        <span class="firm-tag">{firm}</span>
      </div>
      {#if step !== 'fetching' && step !== 'saving'}
        <button type="button" class="close" onclick={close} aria-label="Close">✕</button>
      {/if}
    </header>

    {#if step === 'prompt_url'}
      <div class="body">
        <h2 id="brand-modal-title">Make memos look like your firm</h2>
        <p class="lede">
          Paste your firm's website. Claude reads the homepage (and a couple of linked pages
          if needed), then fills in colors, fonts, logos, and tagline. You'll review every field
          before anything saves.
        </p>

        <label class="field">
          <span class="label">Firm website</span>
          <!-- svelte-ignore a11y_autofocus -->
          <!-- The rule targets autofocus on page load, which yanks a screen
          reader away from the document. In a modal it is the opposite:
          the WAI dialog pattern expects focus to move into the dialog on
          open, and this is the first field. Escape returns the user. -->
          <input
            type="url"
            bind:value={url}
            placeholder="https://yourfirm.com"
            autofocus
            onkeydown={(e) => e.key === 'Enter' && fetchBrand()}
          />
        </label>

        {#if errorMessage}
          <p class="error">{errorMessage}</p>
        {/if}

        <p class="cost-note">
          ≈ 10–20 seconds. Uses your orchestrator's Anthropic API key (the same one that runs
          memos).
        </p>
      </div>

      <footer class="modal-foot">
        <button type="button" class="ghost" onclick={close}>Skip for now</button>
        <button type="button" class="cta" onclick={fetchBrand} disabled={!url.trim()}>
          Fetch brand →
        </button>
      </footer>
    {:else if step === 'fetching'}
      <div class="body fetching">
        <div class="spinner-large" aria-hidden="true"></div>
        <h2 id="brand-modal-title">Reading {url}…</h2>
        <p class="lede">
          Claude is fetching the homepage, possibly an /about page, and a stylesheet. This usually
          takes 10–20 seconds.
        </p>
      </div>
    {:else if step === 'confirm'}
      <div class="body">
        <h2 id="brand-modal-title">Review and edit</h2>
        <p class="lede">
          Every field is editable. Claude's best guesses are filled in below — change anything
          before saving.
        </p>

        {#if confidenceNotes}
          <p class="notes">
            <strong>From Claude:</strong> {confidenceNotes}
          </p>
        {/if}

        <div class="grid">
          <div class="section">
            <h3>Identity</h3>
            <label class="field">
              <span class="label">Official name</span>
              <input type="text" bind:value={companyName} placeholder="e.g., Sequoia Capital" />
            </label>
            <label class="field">
              <span class="label">Legal entity <span class="hint">(optional)</span></span>
              <input
                type="text"
                bind:value={legalEntityName}
                placeholder="e.g., Sequoia Capital Operations LLC"
              />
            </label>
            <label class="field">
              <span class="label">Tagline</span>
              <input type="text" bind:value={tagline} placeholder="A short marketing line" />
            </label>
          </div>

          <div class="section">
            <h3>Light-mode colors</h3>
            <div class="color-row">
              <label class="field-inline">
                <span class="label">Primary</span>
                {#if isValidHexOrEmpty(primaryColor) && primaryColor.trim()}
                  <span class="swatch" style="background: {primaryColor}"></span>
                {/if}
                <input type="text" bind:value={primaryColor} placeholder="#5b21b6" />
              </label>
              <label class="field-inline">
                <span class="label">Secondary</span>
                {#if isValidHexOrEmpty(secondaryColor) && secondaryColor.trim()}
                  <span class="swatch" style="background: {secondaryColor}"></span>
                {/if}
                <input type="text" bind:value={secondaryColor} placeholder="#a855f7" />
              </label>
              <label class="field-inline">
                <span class="label">Accent</span>
                {#if isValidHexOrEmpty(accentColor) && accentColor.trim()}
                  <span class="swatch" style="background: {accentColor}"></span>
                {/if}
                <input type="text" bind:value={accentColor} placeholder="#ec4899" />
              </label>
              <label class="field-inline">
                <span class="label">Text (dark)</span>
                {#if isValidHexOrEmpty(textDark) && textDark.trim()}
                  <span class="swatch" style="background: {textDark}"></span>
                {/if}
                <input type="text" bind:value={textDark} placeholder="#0f0f0f" />
              </label>
              <label class="field-inline">
                <span class="label">Background</span>
                {#if isValidHexOrEmpty(background) && background.trim()}
                  <span class="swatch" style="background: {background}"></span>
                {/if}
                <input type="text" bind:value={background} placeholder="#ffffff" />
              </label>
              <label class="field-inline">
                <span class="label">BG alt</span>
                {#if isValidHexOrEmpty(backgroundAlt) && backgroundAlt.trim()}
                  <span class="swatch" style="background: {backgroundAlt}"></span>
                {/if}
                <input type="text" bind:value={backgroundAlt} placeholder="#f9fafb" />
              </label>
            </div>
          </div>

          <div class="section">
            <h3>Dark-mode colors <span class="hint">(optional)</span></h3>
            <div class="color-row">
              <label class="field-inline">
                <span class="label">Primary</span>
                {#if isValidHexOrEmpty(primaryColorDark) && primaryColorDark.trim()}
                  <span class="swatch" style="background: {primaryColorDark}"></span>
                {/if}
                <input type="text" bind:value={primaryColorDark} placeholder="#a855f7" />
              </label>
              <label class="field-inline">
                <span class="label">Secondary</span>
                {#if isValidHexOrEmpty(secondaryColorDark) && secondaryColorDark.trim()}
                  <span class="swatch" style="background: {secondaryColorDark}"></span>
                {/if}
                <input type="text" bind:value={secondaryColorDark} placeholder="#c4b5fd" />
              </label>
              <label class="field-inline">
                <span class="label">Background</span>
                {#if isValidHexOrEmpty(backgroundDark) && backgroundDark.trim()}
                  <span class="swatch" style="background: {backgroundDark}"></span>
                {/if}
                <input type="text" bind:value={backgroundDark} placeholder="#1c1c1e" />
              </label>
            </div>
          </div>

          <div class="section">
            <h3>Fonts</h3>
            <label class="field">
              <span class="label">Body family</span>
              <input type="text" bind:value={fontFamily} placeholder="Inter" />
            </label>
            <label class="field">
              <span class="label">Header family</span>
              <input type="text" bind:value={headerFontFamily} placeholder="Space Grotesk" />
            </label>
            <label class="field">
              <span class="label">Google Fonts URL <span class="hint">(if applicable)</span></span>
              <input
                type="url"
                bind:value={googleFontsUrl}
                placeholder="https://fonts.googleapis.com/css2?family=..."
              />
            </label>
          </div>

          <div class="section">
            <h3>Logo</h3>
            <label class="field">
              <span class="label">Light-mode URL</span>
              <input
                type="url"
                bind:value={logoLightUrl}
                placeholder="https://yourfirm.com/logo-light.svg"
              />
              {#if logoLightUrl.trim()}
                <div class="logo-preview light"><img src={logoLightUrl} alt="logo preview" /></div>
              {/if}
            </label>
            <label class="field">
              <span class="label">Dark-mode URL <span class="hint">(optional)</span></span>
              <input
                type="url"
                bind:value={logoDarkUrl}
                placeholder="https://yourfirm.com/logo-dark.svg"
              />
              {#if logoDarkUrl.trim()}
                <div class="logo-preview dark"><img src={logoDarkUrl} alt="logo preview" /></div>
              {/if}
            </label>
            <label class="field">
              <span class="label">Alt text</span>
              <input type="text" bind:value={logoAlt} placeholder={companyName || firm} />
            </label>
          </div>
        </div>

        {#if errorMessage}
          <p class="error">{errorMessage}</p>
        {/if}
      </div>

      <footer class="modal-foot">
        <button type="button" class="ghost" onclick={close}>Cancel</button>
        <button type="button" class="cta" onclick={saveBrand}>Save brand →</button>
      </footer>
    {:else if step === 'saving'}
      <div class="body fetching">
        <div class="spinner-large" aria-hidden="true"></div>
        <h2 id="brand-modal-title">Saving…</h2>
      </div>
    {:else if step === 'saved'}
      <div class="body saved">
        <div class="check" aria-hidden="true">✓</div>
        <h2 id="brand-modal-title">Brand config saved</h2>
        <p class="lede">
          Written to <code>io/{firm}/configs/brand-{firm}-config.yaml</code>. Future memo exports
          will pick it up automatically.
        </p>
      </div>
      <footer class="modal-foot">
        <button type="button" class="cta" onclick={close}>Done</button>
      </footer>
    {/if}
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(15, 15, 15, 0.5);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1.5rem;
    z-index: 110;
  }

  .modal {
    background: white;
    border-radius: 14px;
    width: 100%;
    max-width: 720px;
    max-height: calc(100vh - 3rem);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 20px 60px rgba(15, 15, 15, 0.3);
  }

  .modal-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.1rem 1.5rem 0.5rem;
  }

  .head-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .step-pill {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 0.3rem 0.7rem;
    border-radius: 999px;
    background: linear-gradient(135deg, #ede9fe, #fef3c7);
    color: #5b21b6;
  }

  .firm-tag {
    font-size: 0.75rem;
    color: #5b21b6;
    background: #f3e8ff;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
    font-weight: 500;
  }

  .close {
    background: transparent;
    border: none;
    color: #6b7280;
    font-size: 1.1rem;
    cursor: pointer;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
  }

  .close:hover {
    background: #f3f4f6;
    color: #0f0f0f;
  }

  .body {
    padding: 0.5rem 1.5rem 1rem;
    overflow-y: auto;
    flex: 1;
  }

  h2 {
    margin: 0 0 0.5rem;
    font-size: 1.4rem;
    color: #0f0f0f;
  }

  .lede {
    color: #4b5563;
    line-height: 1.5;
    margin: 0 0 1rem;
    font-size: 0.95rem;
  }

  .notes {
    background: #f5f3ff;
    border: 1px solid #ddd6fe;
    color: #4b5563;
    font-size: 0.85rem;
    padding: 0.6rem 0.8rem;
    border-radius: 6px;
    margin: 0 0 1rem;
    line-height: 1.45;
  }

  .notes strong {
    color: #5b21b6;
  }

  .grid {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

  .section h3 {
    margin: 0 0 0.6rem;
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6b7280;
  }

  .field {
    display: block;
    margin-bottom: 0.65rem;
  }

  .field-inline {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex: 1;
    min-width: 200px;
    margin-bottom: 0.4rem;
  }

  .label {
    display: block;
    font-size: 0.82rem;
    font-weight: 500;
    margin-bottom: 0.3rem;
    color: #0f0f0f;
  }

  .field-inline .label {
    margin-bottom: 0;
    flex: 0 0 80px;
    font-weight: 400;
    color: #6b7280;
  }

  .hint {
    color: #9ca3af;
    font-weight: 400;
    font-size: 0.85em;
  }

  input[type='text'],
  input[type='url'] {
    width: 100%;
    padding: 0.5rem 0.7rem;
    border-radius: 6px;
    border: 1px solid #d1d5db;
    font: inherit;
    font-size: 0.9rem;
    background: white;
    color: #0f0f0f;
  }

  input[type='text']:focus,
  input[type='url']:focus {
    outline: 2px solid #c4b5fd;
    outline-offset: 0;
    border-color: #5b21b6;
  }

  .field-inline input {
    flex: 1;
    min-width: 0;
  }

  .color-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
  }

  .swatch {
    display: inline-block;
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid rgba(0, 0, 0, 0.15);
    flex-shrink: 0;
  }

  .logo-preview {
    margin-top: 0.4rem;
    padding: 0.6rem;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    display: inline-block;
  }

  .logo-preview.dark {
    background: #1c1c1e;
  }

  .logo-preview img {
    max-width: 200px;
    max-height: 60px;
    display: block;
  }

  .cost-note {
    margin: 1rem 0 0;
    color: #9ca3af;
    font-size: 0.78rem;
  }

  .error {
    color: #c0392b;
    font-size: 0.9rem;
    margin: 0.6rem 0 0;
    padding: 0.5rem 0.7rem;
    background: #fef2f2;
    border-radius: 6px;
    border: 1px solid #fca5a5;
  }

  .modal-foot {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.6rem;
    padding: 0.85rem 1.5rem 1.1rem;
    border-top: 1px solid #f3f4f6;
  }

  button.ghost {
    background: transparent;
    border: 1px solid #d1d5db;
    color: #4b5563;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font: inherit;
    cursor: pointer;
  }

  button.ghost:hover {
    background: #f3f4f6;
    color: #0f0f0f;
  }

  button.cta {
    background: #5b21b6;
    color: white;
    border: none;
    padding: 0.55rem 1.1rem;
    border-radius: 6px;
    font: inherit;
    font-weight: 500;
    cursor: pointer;
  }

  button.cta:hover:not(:disabled) {
    background: #4c1d95;
  }

  button.cta:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  .fetching,
  .saved {
    text-align: center;
    padding: 2rem 1.5rem 2rem;
  }

  .spinner-large {
    width: 40px;
    height: 40px;
    border: 3px solid #ede9fe;
    border-top-color: #5b21b6;
    border-radius: 50%;
    margin: 0 auto 1rem;
    animation: spin 0.9s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .check {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: #d1fae5;
    color: #065f46;
    font-size: 1.6rem;
    font-weight: 700;
    margin: 0 auto 1rem;
  }

  code {
    font-family: ui-monospace, SFMono-Regular, monospace;
    background: #f3f4f6;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
    font-size: 0.9em;
  }

  @media (prefers-color-scheme: dark) {
    .modal {
      background: #2a2a2c;
    }
    h2 {
      color: #f6f6f6;
    }
    .lede {
      color: #d1d5db;
    }
    .firm-tag {
      background: #2a1f3d;
      color: #c4b5fd;
    }
    .close {
      color: #9ca3af;
    }
    .close:hover {
      background: #1c1c1e;
      color: #f6f6f6;
    }
    .label {
      color: #f6f6f6;
    }
    .field-inline .label {
      color: #9ca3af;
    }
    input[type='text'],
    input[type='url'] {
      background: #1c1c1e;
      color: #f6f6f6;
      border-color: #3a3a3c;
    }
    .notes {
      background: #2a1f3d;
      border-color: #5b21b6;
      color: #d1d5db;
    }
    .notes strong {
      color: #c4b5fd;
    }
    .section h3 {
      color: #9ca3af;
    }
    .logo-preview {
      border-color: #3a3a3c;
    }
    .cost-note {
      color: #6b7280;
    }
    .error {
      background: #2a1c1c;
      border-color: #7f1d1d;
    }
    .modal-foot {
      border-top-color: #3a3a3c;
    }
    button.ghost {
      border-color: #3a3a3c;
      color: #d1d5db;
    }
    button.ghost:hover {
      background: #1c1c1e;
      color: #f6f6f6;
    }
    code {
      background: #1c1c1e;
    }
    .check {
      background: #052e1c;
      color: #6ee7b7;
    }
    .spinner-large {
      border-color: #2a1f3d;
      border-top-color: #c4b5fd;
    }
  }
</style>
