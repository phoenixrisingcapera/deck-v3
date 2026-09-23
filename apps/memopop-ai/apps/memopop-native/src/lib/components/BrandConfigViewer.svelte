<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { settings } from '$lib/stores/settings.svelte';
  import { flow } from '$lib/stores/flow.svelte';
  import { getTransport } from '$lib/transport';

  // Mirrors the brand-{firm}-config.yaml shape produced by the brand-setup
  // flow. Every section is optional; the viewer renders sensible empty states
  // when fields are missing.
  interface BrandConfig {
    company?: {
      name?: string;
      conventional_name?: string;
      tagline?: string;
      confidential_footer?: string;
    };
    colors?: BrandColors;
    colors_dark?: BrandColors;
    fonts?: {
      family?: string;
      fallback?: string;
      google_fonts_url?: string;
      weight?: number | string;
      header_family?: string;
      header_fallback?: string;
      header_fonts_dir?: string;
      header_weight?: number | string;
    };
    logo?: {
      light_mode?: string;
      dark_mode?: string;
      width?: string;
      height?: string;
      alt?: string;
    };
    _meta?: Record<string, unknown>;
  }

  interface BrandColors {
    primary?: string;
    secondary?: string;
    accent?: string;
    text_dark?: string;
    text_light?: string;
    background?: string;
    background_alt?: string;
  }

  const COLOR_KEYS: Array<keyof BrandColors> = [
    'primary',
    'secondary',
    'accent',
    'text_dark',
    'text_light',
    'background',
    'background_alt',
  ];

  let firm = $derived(settings.activeFirm);

  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let configMissing = $state(false);
  let config = $state<BrandConfig>({});
  let configPath = $state<string | null>(null);

  // Per-save status — flips between idle / saving / saved / error. Surfaced
  // as a small inline pill so the user has confidence the YAML is being
  // written without a heavy modal.
  let saveStatus = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
  let saveStatusMsg = $state<string>('');
  let savedBlinkTimeout: ReturnType<typeof setTimeout> | null = null;

  onMount(async () => {
    await load();
  });

  async function load() {
    if (!firm || !settings.repoPath) {
      loading = false;
      return;
    }
    loading = true;
    loadError = null;
    configMissing = false;
    try {
      const result = await getTransport().request<{
        firm: string;
        path: string;
        config: BrandConfig;
      }>('GET', `/firms/${encodeURIComponent(firm)}/brand-config`, {
        repoPath: settings.repoPath,
      });
      config = result.config ?? {};
      configPath = result.path;
    } catch (e) {
      const status = (e as { status?: number })?.status;
      if (status === 404) {
        configMissing = true;
      } else {
        loadError =
          (e as { message?: string })?.message ?? 'Failed to load brand config';
      }
    } finally {
      loading = false;
    }
  }

  // The save endpoint deep-merges with whatever's on disk, so each save can
  // send the full current `config` and won't clobber out-of-band edits to
  // unrelated fields. We send the whole tree on every save for simplicity —
  // a brand config is small (<5KB).
  async function save() {
    if (!firm || !settings.repoPath) return;
    if (savedBlinkTimeout) {
      clearTimeout(savedBlinkTimeout);
      savedBlinkTimeout = null;
    }
    saveStatus = 'saving';
    saveStatusMsg = 'Saving…';
    try {
      await getTransport().request('POST', '/actions/save-brand', {
        repoPath: settings.repoPath,
        firm,
        config,
      });
      saveStatus = 'saved';
      saveStatusMsg = 'Saved';
      savedBlinkTimeout = setTimeout(() => {
        if (saveStatus === 'saved') {
          saveStatus = 'idle';
          saveStatusMsg = '';
        }
      }, 1800);
    } catch (e) {
      saveStatus = 'error';
      saveStatusMsg =
        (e as { message?: string })?.message ?? 'Save failed';
    }
  }

  function startBrandSetup() {
    if (!firm) return;
    flow.startBrandSetup(firm);
    goto('/');
  }

  // --- Dark-mode helpers ---

  // True when colors_dark either doesn't exist or has every key matching the
  // light value (which suggests no real dark theme — just an echo).
  let darkLooksUntuned = $derived.by(() => {
    if (!config.colors) return false;
    if (!config.colors_dark) return true;
    let echoes = 0;
    let total = 0;
    for (const k of COLOR_KEYS) {
      const lv = config.colors[k];
      const dv = config.colors_dark[k];
      if (!lv) continue;
      total++;
      if (!dv || lv.toLowerCase() === dv.toLowerCase()) echoes++;
    }
    return total > 0 && echoes / total >= 0.5; // half or more aren't tuned
  });

  function mirrorLightToDark() {
    if (!config.colors) return;
    const proposed: BrandColors = {
      primary: config.colors.primary,
      secondary: config.colors.secondary,
      accent: config.colors.accent,
      // Swap fg / bg for a basic dark theme. Users will refine.
      text_dark: '#f6f6f6',
      text_light: '#9ca3af',
      background: '#1c1c1e',
      background_alt: '#2a2a2c',
    };
    config.colors_dark = { ...config.colors_dark, ...proposed };
    void save();
  }

  // Hex normalization on blur — tolerates uppercase/no-#/3-char shorthand.
  function normalizeHex(value: string): string | null {
    let v = value.trim();
    if (!v) return '';
    if (!v.startsWith('#')) v = '#' + v;
    const hex = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/;
    if (!hex.test(v)) return null;
    if (v.length === 4) {
      // #rgb → #rrggbb
      v = '#' + v.slice(1).split('').map((c) => c + c).join('');
    }
    return v.toLowerCase();
  }

  function setColor(palette: 'colors' | 'colors_dark', key: keyof BrandColors, raw: string) {
    const norm = normalizeHex(raw);
    if (norm === null) {
      // Reject silently — keep prior value, the input retains the bad text.
      // Could surface a per-field error; deferring.
      return;
    }
    if (!config[palette]) config[palette] = {};
    config[palette]![key] = norm;
    void save();
  }

  function setCompany(field: keyof NonNullable<BrandConfig['company']>, value: string) {
    if (!config.company) config.company = {};
    config.company[field] = value;
    void save();
  }

  function setLogoField(field: keyof NonNullable<BrandConfig['logo']>, value: string) {
    if (!config.logo) config.logo = {};
    config.logo[field] = value;
    void save();
  }

  function setFontField(field: keyof NonNullable<BrandConfig['fonts']>, value: string) {
    if (!config.fonts) config.fonts = {};
    if (field === 'weight' || field === 'header_weight') {
      const n = Number.parseInt(value, 10);
      if (!Number.isNaN(n)) {
        config.fonts[field] = n;
      } else if (value === '') {
        config.fonts[field] = undefined;
      }
    } else {
      config.fonts[field] = value;
    }
    void save();
  }

  function colorLabel(key: keyof BrandColors): string {
    return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }
</script>

<section class="page">
  <header class="page-head">
    <button type="button" class="back" onclick={() => goto('/settings')}>
      ← Settings
    </button>
    <div class="title-block">
      <h1>Brand Config</h1>
      <p class="subtitle">
        {#if firm}
          Live editor for <code class="firm">{firm}</code>'s
          <code class="path">brand-{firm}-config.yaml</code>
        {:else}
          No active firm selected.
        {/if}
      </p>
    </div>
    <div class="save-pill save-{saveStatus}">
      {#if saveStatus === 'saving'}
        ● {saveStatusMsg}
      {:else if saveStatus === 'saved'}
        ✓ {saveStatusMsg}
      {:else if saveStatus === 'error'}
        ⚠ {saveStatusMsg}
      {:else}
        Edits save on blur
      {/if}
    </div>
  </header>

  {#if !firm}
    <div class="empty">
      <p>Pick an active firm in <a href="/settings">Settings</a> to view its brand config.</p>
    </div>
  {:else if loading}
    <div class="empty"><p>Loading brand config…</p></div>
  {:else if loadError}
    <div class="empty">
      <p class="error">{loadError}</p>
    </div>
  {:else if configMissing}
    <div class="empty empty-cta">
      <p><strong>No brand config yet for {firm}.</strong></p>
      <p class="hint">Run brand setup once to populate from your firm's website.</p>
      <button type="button" class="cta" onclick={startBrandSetup}>
        Run brand setup →
      </button>
    </div>
  {:else}
    <!-- IDENTITY -->
    <section class="block">
      <h2>Identity</h2>
      <div class="grid two">
        <label class="field">
          <span class="field-label">Display name</span>
          <input
            type="text"
            value={config.company?.name ?? ''}
            placeholder="Alpha Partners"
            onblur={(e) => setCompany('name', e.currentTarget.value)}
          />
          {#if config.company?.conventional_name}
            <span class="field-note">
              Canonical: <code>{config.company.conventional_name}</code>
            </span>
          {/if}
        </label>
        <label class="field">
          <span class="field-label">Tagline</span>
          <input
            type="text"
            value={config.company?.tagline ?? ''}
            placeholder="Short one-liner shown in memo headers"
            onblur={(e) => setCompany('tagline', e.currentTarget.value)}
          />
        </label>
        <label class="field span2">
          <span class="field-label">Confidential footer</span>
          <input
            type="text"
            value={config.company?.confidential_footer ?? ''}
            placeholder="This document is confidential and proprietary to {'{company_name}'}"
            onblur={(e) => setCompany('confidential_footer', e.currentTarget.value)}
          />
          <span class="field-note">
            Use <code>{'{company_name}'}</code> as a placeholder for the deal name.
          </span>
        </label>
      </div>
    </section>

    <!-- LOGO -->
    <section class="block">
      <h2>Logo</h2>
      <div class="logos">
        <div class="logo-card logo-light">
          <div class="logo-card-head">
            <span class="logo-card-label">Light mode</span>
          </div>
          <div class="logo-preview" style:background={config.colors?.background ?? '#ffffff'}>
            {#if config.logo?.light_mode}
              <img
                src={config.logo.light_mode}
                alt={config.logo.alt ?? ''}
                style:max-width={config.logo.width ?? '180px'}
                style:max-height={config.logo.height ?? '60px'}
              />
            {:else}
              <span class="placeholder">No logo</span>
            {/if}
          </div>
          <input
            type="text"
            class="logo-url"
            value={config.logo?.light_mode ?? ''}
            placeholder="https://…/logo-light.svg"
            onblur={(e) => setLogoField('light_mode', e.currentTarget.value)}
          />
        </div>

        <div class="logo-card logo-dark">
          <div class="logo-card-head">
            <span class="logo-card-label">Dark mode</span>
          </div>
          <div class="logo-preview" style:background={config.colors_dark?.background ?? '#0f0f0f'}>
            {#if config.logo?.dark_mode}
              <img
                src={config.logo.dark_mode}
                alt={config.logo.alt ?? ''}
                style:max-width={config.logo.width ?? '180px'}
                style:max-height={config.logo.height ?? '60px'}
              />
            {:else}
              <span class="placeholder placeholder-dark">No dark-mode logo</span>
            {/if}
          </div>
          <input
            type="text"
            class="logo-url"
            value={config.logo?.dark_mode ?? ''}
            placeholder="https://…/logo-dark.svg"
            onblur={(e) => setLogoField('dark_mode', e.currentTarget.value)}
          />
        </div>
      </div>

      <div class="logo-meta">
        <label class="field">
          <span class="field-label">Width</span>
          <input
            type="text"
            value={config.logo?.width ?? ''}
            placeholder="180px"
            onblur={(e) => setLogoField('width', e.currentTarget.value)}
          />
        </label>
        <label class="field">
          <span class="field-label">Height</span>
          <input
            type="text"
            value={config.logo?.height ?? ''}
            placeholder="60px"
            onblur={(e) => setLogoField('height', e.currentTarget.value)}
          />
        </label>
        <label class="field">
          <span class="field-label">Alt text</span>
          <input
            type="text"
            value={config.logo?.alt ?? ''}
            placeholder="Alpha Partners Logo"
            onblur={(e) => setLogoField('alt', e.currentTarget.value)}
          />
        </label>
      </div>
    </section>

    <!-- COLORS -->
    <section class="block">
      <div class="block-head">
        <h2>Colors</h2>
        {#if darkLooksUntuned}
          <button type="button" class="mirror-btn" onclick={mirrorLightToDark}>
            Mirror light → dark
          </button>
        {/if}
      </div>

      <div class="palettes">
        <!-- LIGHT PALETTE -->
        <div class="palette palette-light">
          <h3>Light</h3>
          {#each COLOR_KEYS as key (key)}
            <div class="swatch-row">
              <span
                class="swatch"
                style:background={config.colors?.[key] ?? 'transparent'}
                style:border={config.colors?.[key] ? 'none' : '1px dashed #d1d5db'}
              ></span>
              <span class="swatch-label">{colorLabel(key)}</span>
              <input
                type="text"
                class="hex-input"
                value={config.colors?.[key] ?? ''}
                placeholder="#______"
                onblur={(e) => setColor('colors', key, e.currentTarget.value)}
              />
            </div>
          {/each}
        </div>

        <!-- DARK PALETTE -->
        <div class="palette palette-dark">
          <h3>
            Dark
            {#if darkLooksUntuned}
              <span class="warn-badge" title="Dark palette echoes light or is missing values">
                needs tuning
              </span>
            {/if}
          </h3>
          {#each COLOR_KEYS as key (key)}
            <div class="swatch-row">
              <span
                class="swatch"
                style:background={config.colors_dark?.[key] ?? 'transparent'}
                style:border={config.colors_dark?.[key] ? 'none' : '1px dashed #6b7280'}
              ></span>
              <span class="swatch-label">{colorLabel(key)}</span>
              <input
                type="text"
                class="hex-input"
                value={config.colors_dark?.[key] ?? ''}
                placeholder="#______"
                onblur={(e) => setColor('colors_dark', key, e.currentTarget.value)}
              />
            </div>
          {/each}
        </div>
      </div>
    </section>

    <!-- FONTS -->
    <section class="block">
      <h2>Fonts</h2>
      <div class="fonts-grid">
        <label class="field">
          <span class="field-label">Body family</span>
          <input
            type="text"
            value={config.fonts?.family ?? ''}
            placeholder="Inter"
            onblur={(e) => setFontField('family', e.currentTarget.value)}
          />
        </label>
        <label class="field">
          <span class="field-label">Body weight</span>
          <input
            type="text"
            value={config.fonts?.weight?.toString() ?? ''}
            placeholder="400"
            onblur={(e) => setFontField('weight', e.currentTarget.value)}
          />
        </label>
        <label class="field span2">
          <span class="field-label">Body Google Fonts URL</span>
          <input
            type="text"
            value={config.fonts?.google_fonts_url ?? ''}
            placeholder="https://fonts.googleapis.com/…"
            onblur={(e) => setFontField('google_fonts_url', e.currentTarget.value)}
          />
        </label>
        <label class="field">
          <span class="field-label">Header family</span>
          <input
            type="text"
            value={config.fonts?.header_family ?? ''}
            placeholder="Halcom"
            onblur={(e) => setFontField('header_family', e.currentTarget.value)}
          />
        </label>
        <label class="field">
          <span class="field-label">Header weight</span>
          <input
            type="text"
            value={config.fonts?.header_weight?.toString() ?? ''}
            placeholder="700"
            onblur={(e) => setFontField('header_weight', e.currentTarget.value)}
          />
        </label>
      </div>

      {#if config.fonts?.family}
        <div class="font-preview">
          <span
            class="sample-body"
            style:font-family="{config.fonts.family}, {config.fonts.fallback ?? 'sans-serif'}"
            style:font-weight={config.fonts.weight ?? 400}
          >
            The quick brown fox jumps over the lazy dog — body sample
          </span>
          {#if config.fonts.header_family}
            <span
              class="sample-header"
              style:font-family="{config.fonts.header_family}, {config.fonts.header_fallback ?? 'serif'}"
              style:font-weight={config.fonts.header_weight ?? 700}
            >
              Heading Sample · {config.company?.name ?? firm}
            </span>
          {/if}
        </div>
      {/if}
    </section>

    {#if configPath}
      <p class="path-note">
        Source of truth: <code>{configPath}</code>
      </p>
    {/if}
  {/if}
</section>

<style>
  .page {
    max-width: 920px;
    margin: 2.5rem auto;
    padding: 0 1.5rem 4rem;
  }

  .page-head {
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .back {
    background: transparent;
    border: 1px solid #d1d5db;
    color: #4b5563;
    padding: 0.4rem 0.8rem;
    border-radius: 6px;
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
  }

  .back:hover {
    background: #f3f4f6;
    color: #0f0f0f;
  }

  .title-block h1 {
    margin: 0 0 0.2rem;
    font-size: 1.5rem;
  }

  .subtitle {
    margin: 0;
    color: #6b7280;
    font-size: 0.9rem;
  }

  .firm,
  .path {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 0.85em;
    color: #5b21b6;
    background: #f5f3ff;
    padding: 0.05rem 0.3rem;
    border-radius: 3px;
  }

  .save-pill {
    font-size: 0.78rem;
    padding: 0.3rem 0.65rem;
    border-radius: 999px;
    font-variant-numeric: tabular-nums;
    transition: background 0.2s, color 0.2s;
  }

  .save-idle {
    background: #f3f4f6;
    color: #9ca3af;
  }

  .save-saving {
    background: #fef3c7;
    color: #92400e;
  }

  .save-saved {
    background: #dcfce7;
    color: #166534;
  }

  .save-error {
    background: #fee2e2;
    color: #991b1b;
  }

  .empty {
    margin: 4rem auto;
    text-align: center;
    color: #6b7280;
    max-width: 480px;
  }

  .empty-cta {
    background: #fafaf9;
    border: 1px dashed #e5e7eb;
    border-radius: 12px;
    padding: 2rem;
  }

  .error {
    color: #c0392b;
  }

  .hint {
    color: #9ca3af;
    font-size: 0.9rem;
  }

  .cta {
    background: #5b21b6;
    color: white;
    border: none;
    padding: 0.55rem 1.2rem;
    border-radius: 8px;
    font: inherit;
    font-weight: 500;
    cursor: pointer;
    margin-top: 0.5rem;
  }

  .cta:hover {
    background: #4c1d95;
  }

  .block {
    margin-bottom: 2.5rem;
    padding: 1.5rem;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
  }

  .block-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
  }

  h2 {
    margin: 0 0 1rem;
    font-size: 1.05rem;
    font-weight: 600;
    color: #0f0f0f;
  }

  .block-head h2 {
    margin: 0;
  }

  h3 {
    margin: 0 0 0.85rem;
    font-size: 0.85rem;
    font-weight: 600;
    color: #4b5563;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .warn-badge {
    background: #fef3c7;
    color: #92400e;
    font-size: 0.65rem;
    padding: 0.1rem 0.45rem;
    border-radius: 999px;
    text-transform: none;
    letter-spacing: 0;
    font-weight: 500;
  }

  .grid.two {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }

  .field.span2 {
    grid-column: 1 / -1;
  }

  .field-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .field input {
    padding: 0.5rem 0.7rem;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    font: inherit;
    font-size: 0.9rem;
    background: #fafaf9;
  }

  .field input:focus {
    outline: 2px solid #c4b5fd;
    border-color: #5b21b6;
    background: white;
  }

  .field-note {
    font-size: 0.72rem;
    color: #9ca3af;
  }

  .field-note code {
    font-family: ui-monospace, SFMono-Regular, monospace;
    background: #f3f4f6;
    padding: 0.05rem 0.25rem;
    border-radius: 3px;
  }

  /* Logos */
  .logos {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .logo-card {
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .logo-card-head {
    padding: 0.5rem 0.85rem;
    background: #fafaf9;
    border-bottom: 1px solid #e5e7eb;
  }

  .logo-card-label {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6b7280;
  }

  .logo-preview {
    flex: 1;
    min-height: 100px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1rem;
  }

  .logo-preview img {
    object-fit: contain;
  }

  .placeholder {
    font-size: 0.85rem;
    color: #9ca3af;
    font-style: italic;
  }

  .placeholder-dark {
    color: #6b7280;
  }

  .logo-url {
    border: none;
    border-top: 1px solid #e5e7eb;
    padding: 0.5rem 0.85rem;
    font: inherit;
    font-size: 0.78rem;
    font-family: ui-monospace, SFMono-Regular, monospace;
    background: #fafaf9;
  }

  .logo-url:focus {
    outline: 2px solid #c4b5fd;
    background: white;
  }

  .logo-meta {
    display: grid;
    grid-template-columns: 1fr 1fr 2fr;
    gap: 1rem;
  }

  /* Colors */
  .palettes {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
  }

  .palette {
    padding: 1rem;
    border-radius: 8px;
  }

  .palette-light {
    background: #fafaf9;
  }

  .palette-dark {
    background: #1c1c1e;
  }

  .palette-dark h3 {
    color: #d1d5db;
  }

  .swatch-row {
    display: grid;
    grid-template-columns: 28px 1fr 110px;
    align-items: center;
    gap: 0.65rem;
    padding: 0.3rem 0;
  }

  .swatch {
    width: 24px;
    height: 24px;
    border-radius: 6px;
    box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.08);
  }

  .swatch-label {
    font-size: 0.82rem;
    color: #4b5563;
  }

  .palette-dark .swatch-label {
    color: #d1d5db;
  }

  .hex-input {
    padding: 0.35rem 0.5rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font: inherit;
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 0.78rem;
    background: white;
    color: #0f0f0f;
  }

  .palette-dark .hex-input {
    background: #2a2a2c;
    border-color: #3a3a3c;
    color: #f6f6f6;
  }

  .hex-input:focus {
    outline: 2px solid #c4b5fd;
    border-color: #5b21b6;
  }

  .mirror-btn {
    background: #fef3c7;
    color: #92400e;
    border: 1px solid #fde68a;
    padding: 0.35rem 0.85rem;
    border-radius: 6px;
    font: inherit;
    font-size: 0.82rem;
    font-weight: 500;
    cursor: pointer;
  }

  .mirror-btn:hover {
    background: #fde68a;
  }

  /* Fonts */
  .fonts-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .font-preview {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 1rem 1.25rem;
    background: #fafaf9;
    border-radius: 8px;
    border: 1px solid #e5e7eb;
  }

  .sample-body {
    font-size: 1rem;
    color: #0f0f0f;
  }

  .sample-header {
    font-size: 1.5rem;
    color: #0f0f0f;
  }

  .path-note {
    margin-top: 1.5rem;
    font-size: 0.78rem;
    color: #9ca3af;
    text-align: center;
  }

  .path-note code {
    font-family: ui-monospace, SFMono-Regular, monospace;
    background: #f3f4f6;
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
  }

  @media (prefers-color-scheme: dark) {
    .back {
      border-color: #3a3a3c;
      color: #d1d5db;
    }
    .back:hover {
      background: #2a2a2c;
      color: #f6f6f6;
    }
    .title-block h1 {
      color: #f6f6f6;
    }
    .subtitle {
      color: #9ca3af;
    }
    .firm,
    .path {
      background: #2a1f3d;
      color: #c4b5fd;
    }
    .save-idle {
      background: #2a2a2c;
      color: #6b7280;
    }
    .save-saving {
      background: #3f2f0a;
      color: #fcd34d;
    }
    .save-saved {
      background: #052e1c;
      color: #6ee7b7;
    }
    .save-error {
      background: #2a1c1c;
      color: #fca5a5;
    }
    .empty {
      color: #9ca3af;
    }
    .empty-cta {
      background: #1c1c1e;
      border-color: #3a3a3c;
    }
    .block {
      background: #1c1c1e;
      border-color: #2a2a2c;
    }
    h2 {
      color: #f6f6f6;
    }
    h3 {
      color: #d1d5db;
    }
    .field-label {
      color: #9ca3af;
    }
    .field input {
      background: #2a2a2c;
      border-color: #3a3a3c;
      color: #f6f6f6;
    }
    .field input:focus {
      background: #1c1c1e;
    }
    .field-note {
      color: #6b7280;
    }
    .field-note code {
      background: #2a2a2c;
    }
    .logo-card {
      border-color: #2a2a2c;
    }
    .logo-card-head {
      background: #2a2a2c;
      border-bottom-color: #3a3a3c;
    }
    .logo-card-label {
      color: #9ca3af;
    }
    .placeholder {
      color: #6b7280;
    }
    .logo-url {
      background: #2a2a2c;
      border-top-color: #3a3a3c;
      color: #d1d5db;
    }
    .logo-url:focus {
      background: #1c1c1e;
    }
    .palette-light {
      background: #2a2a2c;
    }
    .palette-light h3,
    .palette-light .swatch-label {
      color: #d1d5db;
    }
    .hex-input {
      background: #1c1c1e;
      border-color: #3a3a3c;
      color: #f6f6f6;
    }
    .font-preview {
      background: #1c1c1e;
      border-color: #2a2a2c;
    }
    .sample-body,
    .sample-header {
      color: #f6f6f6;
    }
    .path-note {
      color: #6b7280;
    }
    .path-note code {
      background: #2a2a2c;
    }
    .mirror-btn {
      background: #3f2f0a;
      color: #fcd34d;
      border-color: #b45309;
    }
    .mirror-btn:hover {
      background: #b45309;
      color: #fef3c7;
    }
  }
</style>
