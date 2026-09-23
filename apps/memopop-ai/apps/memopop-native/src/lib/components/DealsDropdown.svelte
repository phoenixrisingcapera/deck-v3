<script lang="ts">
  import { goto } from '$app/navigation';
  import { settings } from '$lib/stores/settings.svelte';
  import { getTransport } from '$lib/transport';
  import { openPath } from '@tauri-apps/plugin-opener';

  interface Deal {
    name: string;
    deal_dir: string;
    latest_version: string | null;
    version_count: number;
  }

  let deals = $state<Deal[]>([]);
  let isOpen = $state(false);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let containerEl = $state<HTMLElement | null>(null);

  async function refresh() {
    if (!settings.activeFirm || !settings.repoPath) return;
    loading = true;
    error = null;
    try {
      const result = await getTransport().request<{ deals: Deal[] }>(
        'GET',
        `/firms/${encodeURIComponent(settings.activeFirm)}/deals`,
        { repoPath: settings.repoPath }
      );
      deals = result.deals;
    } catch (e) {
      error = (e as { message?: string })?.message ?? 'Failed to load deals';
    } finally {
      loading = false;
    }
  }

  function toggle() {
    isOpen = !isOpen;
    if (isOpen) refresh();
  }

  async function revealDeal(deal: Deal) {
    try {
      // openPath hands the directory to the OS with its default handler —
      // Finder on macOS, Explorer on Windows, etc.
      await openPath(deal.deal_dir);
    } catch (e) {
      error = `Couldn't open ${deal.name}: ${e}`;
      return;
    }
    isOpen = false;
  }

  function openWorkspace(deal: Deal) {
    if (!settings.activeFirm) return;
    isOpen = false;
    // Workspace defaults to the most recent version (resolved server-side
    // when the route loads). The route doesn't need a ?v= param up front.
    goto(
      `/deals/${encodeURIComponent(settings.activeFirm)}/${encodeURIComponent(deal.name)}`
    );
  }

  // Click-outside dismissal. Bound to the window so opening another part of
  // the UI dismisses the popover too.
  function handleDocClick(e: MouseEvent) {
    if (!isOpen || !containerEl) return;
    if (!containerEl.contains(e.target as Node)) {
      isOpen = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && isOpen) {
      isOpen = false;
    }
  }
</script>

<svelte:window onclick={handleDocClick} onkeydown={handleKeydown} />

{#if settings.activeFirm}
  <div class="container" bind:this={containerEl}>
    <button
      type="button"
      class="trigger"
      class:open={isOpen}
      onclick={toggle}
      aria-haspopup="menu"
      aria-expanded={isOpen}
      title="Deals under {settings.activeFirm}"
    >
      <span>Deals</span>
      <span class="caret" aria-hidden="true">▾</span>
    </button>

    {#if isOpen}
      <div class="popover" role="menu">
        <header class="head">
          <span class="firm-label">{settings.activeFirm}</span>
          <span class="hint">click a deal to reveal in Finder</span>
        </header>

        {#if loading}
          <div class="status">Loading…</div>
        {:else if error}
          <div class="status status-error">{error}</div>
        {:else if deals.length === 0}
          <div class="status">No deals yet for {settings.activeFirm}</div>
        {:else}
          <ul>
            {#each deals as d (d.name)}
              <li class="row">
                <button
                  type="button"
                  class="finder-icon"
                  onclick={() => revealDeal(d)}
                  title="Reveal {d.name} in Finder"
                  aria-label="Reveal {d.name} in Finder"
                >
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M1.75 4.25 A1 1 0 0 1 2.75 3.25 H6 L7.5 5 H13.25 A1 1 0 0 1 14.25 6 V12.25 A1 1 0 0 1 13.25 13.25 H2.75 A1 1 0 0 1 1.75 12.25 Z" />
                  </svg>
                </button>
                <button
                  type="button"
                  class="deal-go"
                  onclick={() => openWorkspace(d)}
                  title="Open {d.name} workspace"
                >
                  <span class="deal-name">{d.name}</span>
                  <span class="meta">
                    {#if d.version_count > 0}
                      {d.version_count}
                      {d.version_count === 1 ? 'run' : 'runs'}
                      {#if d.latest_version}
                        <span class="latest" title="Most recently modified version">
                          · {d.latest_version}
                        </span>
                      {/if}
                    {:else}
                      <span class="no-runs">no runs yet</span>
                    {/if}
                  </span>
                  <span class="go-arrow" aria-hidden="true">→</span>
                </button>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .container {
    position: relative;
  }

  .trigger {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.3rem 0.65rem 0.3rem 0.75rem;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 999px;
    color: #4b5563;
    font: inherit;
    font-size: 0.85rem;
    font-weight: 500;
    cursor: pointer;
  }

  .trigger:hover {
    background: #f3f4f6;
    color: #0f0f0f;
  }

  .trigger.open {
    background: #f3e8ff;
    color: #5b21b6;
    border-color: #ddd6fe;
  }

  .caret {
    font-size: 0.65rem;
    line-height: 1;
    color: currentColor;
    opacity: 0.7;
  }

  .popover {
    position: absolute;
    top: calc(100% + 0.4rem);
    right: 0;
    min-width: 280px;
    max-width: 380px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.12);
    z-index: 20;
    overflow: hidden;
  }

  .head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.6rem 0.85rem 0.55rem;
    border-bottom: 1px solid #f3f4f6;
    background: #fafaf9;
  }

  .firm-label {
    font-size: 0.78rem;
    font-weight: 600;
    color: #5b21b6;
  }

  .hint {
    font-size: 0.7rem;
    color: #9ca3af;
    font-style: italic;
  }

  .status {
    padding: 1rem 0.85rem;
    font-size: 0.85rem;
    color: #6b7280;
    text-align: center;
  }

  .status-error {
    color: #c0392b;
    background: #fef2f2;
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 0.25rem 0;
    max-height: 320px;
    overflow-y: auto;
  }

  /* Each row has two independent click targets:
     • the Finder icon on the far left → reveals the deal folder
     • the rest of the row (name + meta + arrow) → opens the workspace
     Hovering each target highlights only that target so the affordance
     reads clearly. */
  .row {
    display: flex;
    align-items: stretch;
  }

  .finder-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    flex-shrink: 0;
    background: transparent;
    border: none;
    cursor: pointer;
    color: #9ca3af;
    padding: 0;
  }

  .finder-icon:hover {
    background: #ede9fe;
    color: #5b21b6;
  }

  .deal-go {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.55rem;
    flex: 1;
    min-width: 0;
    padding: 0.5rem 0.85rem 0.5rem 0.45rem;
    background: transparent;
    border: none;
    text-align: left;
    cursor: pointer;
    font: inherit;
    color: inherit;
  }

  .deal-go:hover {
    background: #f5f3ff;
  }

  .deal-go:hover .go-arrow {
    color: #5b21b6;
    transform: translateX(2px);
  }

  .deal-name {
    font-weight: 500;
    color: #0f0f0f;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-width: 0;
  }

  .meta {
    font-size: 0.72rem;
    color: #6b7280;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }

  .go-arrow {
    flex-shrink: 0;
    color: #c4b5fd;
    font-size: 0.95rem;
    line-height: 1;
    transition: color 0.15s, transform 0.15s;
  }

  .latest {
    font-family: ui-monospace, SFMono-Regular, monospace;
    color: #5b21b6;
  }

  .no-runs {
    font-style: italic;
    color: #9ca3af;
  }

  @media (prefers-color-scheme: dark) {
    .trigger {
      color: #d1d5db;
    }

    .trigger:hover {
      background: #2a2a2c;
      color: #f6f6f6;
    }

    .trigger.open {
      background: #2a1f3d;
      color: #c4b5fd;
      border-color: #5b21b6;
    }

    .popover {
      background: #1c1c1e;
      border-color: #2a2a2c;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
    }

    .head {
      background: #2a2a2c;
      border-bottom-color: #3a3a3c;
    }

    .firm-label {
      color: #c4b5fd;
    }

    .hint {
      color: #6b7280;
    }

    .status {
      color: #9ca3af;
    }

    .status-error {
      color: #fca5a5;
      background: #2a1c1c;
    }

    .deal-go:hover {
      background: #2a1f3d;
    }

    .deal-go:hover .go-arrow {
      color: #c4b5fd;
    }

    .finder-icon {
      color: #6b7280;
    }

    .finder-icon:hover {
      background: #2a1f3d;
      color: #c4b5fd;
    }

    .go-arrow {
      color: #5b21b6;
    }

    .deal-name {
      color: #f6f6f6;
    }

    .meta {
      color: #9ca3af;
    }

    .latest {
      color: #c4b5fd;
    }

    .no-runs {
      color: #6b7280;
    }
  }
</style>
