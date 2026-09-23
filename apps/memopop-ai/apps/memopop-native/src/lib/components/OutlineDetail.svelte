<script lang="ts">
  import { getTransport, type ApiError } from '$lib/transport';
  import { settings } from '$lib/stores/settings.svelte';
  import { flow } from '$lib/stores/flow.svelte';
  import type { Outline } from '$lib/types';

  interface Props {
    outline: Outline;
  }

  let { outline }: Props = $props();

  type SectionInfo = {
    number?: number | string;
    name: string;
    filename?: string;
    guiding_question_count: number;
    word_target?: { min?: number; max?: number; ideal?: number };
  };

  let loading = $state(false);
  let error = $state<string | null>(null);
  let sections = $state<SectionInfo[]>([]);

  $effect(() => {
    if (settings.repoPath) {
      void load();
    }
  });

  async function load() {
    if (!settings.repoPath) return;
    loading = true;
    error = null;
    try {
      const res = await getTransport().request<{ raw: unknown }>(
        'GET',
        `/outlines/${outline.id}`,
        { repoPath: settings.repoPath }
      );
      const raw = res.raw as Record<string, unknown>;
      const rawSections = (raw?.sections as unknown[]) ?? [];
      sections = rawSections.map((s) => parseSection(s));
    } catch (e) {
      const err = e as ApiError;
      error = err.message ?? 'Failed to load outline detail';
    } finally {
      loading = false;
    }
  }

  function parseSection(s: unknown): SectionInfo {
    const obj = s as Record<string, unknown>;
    const guiding = (obj?.guiding_questions as unknown[]) ?? [];
    return {
      number: (obj?.number as number | string) ?? undefined,
      name: (obj?.name as string) ?? '(unnamed)',
      filename: (obj?.filename as string) ?? undefined,
      guiding_question_count: Array.isArray(guiding) ? guiding.length : 0,
      word_target: (obj?.word_target as SectionInfo['word_target']) ?? undefined,
    };
  }

  function close() {
    flow.close();
  }

  function tryOnCompany() {
    flow.startTrying(outline, !!settings.activeFirm);
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) close();
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') close();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- The backdrop is decorative: it exists to dim the page and to catch a
     click-outside. The dialog is the .modal panel below, which is where the
     dialog role, aria-modal and the label now live. Marking this
     presentational is what makes the click-without-keydown correct rather
     than suppressed — Escape closes via the window handler above. -->
<div class="backdrop" onclick={handleBackdropClick} role="presentation">
  <div class="modal" role="dialog" aria-modal="true" aria-labelledby="outline-detail-title" tabindex="-1">
    <header class="modal-head">
      <div class="head-meta">
        <span class="badge {outline.outline_type === 'fund_commitment' ? 'fund' : 'direct'}">
          {outline.type_label}
        </span>
        {#if outline.firm}
          <span class="firm">{outline.firm}</span>
        {/if}
      </div>
      <button type="button" class="close" onclick={close} aria-label="Close">
        ✕
      </button>
    </header>

    <h2 id="outline-detail-title">{outline.title}</h2>

    {#if outline.description}
      <p class="description">{outline.description}</p>
    {/if}

    <div class="modal-body">
      {#if loading}
        <p class="state">Loading section breakdown…</p>
      {:else if error}
        <p class="state error">{error}</p>
      {:else if sections.length === 0}
        <p class="state">No sections found.</p>
      {:else}
        <h3>
          {sections.length} sections,
          {sections.reduce((acc, s) => acc + s.guiding_question_count, 0)} guiding questions
        </h3>
        <ol class="sections">
          {#each sections as section, i (i)}
            <li class="section">
              <div class="section-number">
                {section.number ?? i + 1}
              </div>
              <div class="section-meta">
                <div class="section-name">{section.name}</div>
                <div class="section-detail">
                  {section.guiding_question_count} guiding question{section.guiding_question_count === 1 ? '' : 's'}
                  {#if section.word_target?.ideal}
                    · ~{section.word_target.ideal} words
                  {/if}
                </div>
              </div>
            </li>
          {/each}
        </ol>
      {/if}
    </div>

    <footer class="modal-foot">
      <button type="button" class="ghost" onclick={close}>Cancel</button>
      <button type="button" class="cta" onclick={tryOnCompany}>
        Try this on a company →
      </button>
    </footer>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(15, 15, 15, 0.4);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    z-index: 100;
  }

  .modal {
    background: white;
    border-radius: 14px;
    width: 100%;
    max-width: 680px;
    max-height: calc(100vh - 4rem);
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 50px rgba(15, 15, 15, 0.25);
  }

  .modal-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.25rem 1.5rem 0.5rem;
  }

  .head-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .badge {
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
  }

  .badge.direct {
    background: #ecfdf5;
    color: #065f46;
  }

  .badge.fund {
    background: #eff6ff;
    color: #1e40af;
  }

  .firm {
    font-size: 0.75rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .close {
    background: transparent;
    border: none;
    color: #6b7280;
    font-size: 1.2rem;
    cursor: pointer;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
  }

  .close:hover {
    background: #f3f4f6;
    color: #0f0f0f;
  }

  h2 {
    font-size: 1.5rem;
    margin: 0 1.5rem 0.5rem;
    line-height: 1.25;
  }

  .description {
    color: #4b5563;
    margin: 0 1.5rem 1rem;
    line-height: 1.5;
  }

  .modal-body {
    overflow-y: auto;
    padding: 0.5rem 1.5rem 1rem;
    flex: 1;
  }

  .modal-body h3 {
    font-size: 0.9rem;
    font-weight: 600;
    color: #6b7280;
    margin: 0.5rem 0 1rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .sections {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .section {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.65rem 0.85rem;
    background: #f9fafb;
    border-radius: 8px;
  }

  .section-number {
    flex-shrink: 0;
    width: 1.75rem;
    height: 1.75rem;
    border-radius: 50%;
    background: white;
    border: 1px solid #e5e5e5;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.85rem;
    font-weight: 600;
    color: #5b21b6;
  }

  .section-meta {
    flex: 1;
  }

  .section-name {
    font-weight: 500;
    line-height: 1.3;
  }

  .section-detail {
    font-size: 0.8rem;
    color: #6b7280;
    margin-top: 0.15rem;
  }

  .state {
    text-align: center;
    color: #6b7280;
    padding: 2rem 0;
  }

  .state.error {
    color: #c0392b;
  }

  .modal-foot {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    padding: 1rem 1.5rem 1.25rem;
    border-top: 1px solid #f3f4f6;
  }

  button.ghost {
    background: transparent;
    border: 1px solid #d1d5db;
    color: #4b5563;
    padding: 0.55rem 1rem;
    border-radius: 8px;
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
    border-radius: 8px;
    font: inherit;
    font-weight: 500;
    cursor: pointer;
  }

  button.cta:hover {
    background: #4c1d95;
  }

  @media (prefers-color-scheme: dark) {
    .modal {
      background: #2a2a2c;
    }

    .description {
      color: #d1d5db;
    }

    .modal-body h3 {
      color: #9ca3af;
    }

    .section {
      background: #1c1c1e;
    }

    .section-number {
      background: #2a2a2c;
      border-color: #3a3a3c;
      color: #c4b5fd;
    }

    .section-detail {
      color: #9ca3af;
    }

    .badge.direct {
      background: #064e3b;
      color: #a7f3d0;
    }

    .badge.fund {
      background: #1e3a8a;
      color: #bfdbfe;
    }

    .firm {
      color: #9ca3af;
    }

    .close {
      color: #9ca3af;
    }

    .close:hover {
      background: #1c1c1e;
      color: #f6f6f6;
    }

    .state {
      color: #9ca3af;
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
  }
</style>
