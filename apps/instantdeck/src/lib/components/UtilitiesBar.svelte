<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import AppLogo from '$components/AppLogo.svelte';
  import ThemeToggle from '$components/ThemeToggle.svelte';
  import { redirectToSignInAfterAuthExpiry } from '$lib/api/apiError';
  import { workspaceDashboardSchema } from '$lib/dashboard/workspaceDashboardSchema';
  import { sessionState } from '$lib/stores/session';

  type UtilitiesBarPlacement = 'sidebar' | 'footer';

  interface Props {
    placement?: UtilitiesBarPlacement;
  }

  let { placement = 'sidebar' }: Props = $props();
  let readyDeck = $state<{ id: string; title: string; slideCount: number } | null>(null);
  const showWorkspaceMode = $derived(placement === 'footer' && page.url.pathname === '/decks/new');
  const instantDeckMode = $derived(page.url.searchParams.get('instant') !== '0');

  function toggleWorkspaceMode() {
    const nextUrl = new URL(page.url);
    if (instantDeckMode) {
      nextUrl.searchParams.set('instant', '0');
    } else {
      nextUrl.searchParams.delete('instant');
    }
    void goto(`${nextUrl.pathname}${nextUrl.search}${nextUrl.hash}`, {
      keepFocus: true,
      noScroll: true,
      replaceState: true
    });
  }

  const connectedLabel = $derived.by(() => {
    if ($sessionState.status === 'loading') return 'Checking session';
    if ($sessionState.user) return 'Connected';
    return 'Signed out';
  });

  const identityLabel = $derived(
    $sessionState.user?.id ?? $sessionState.user?.email?.split('@')[0] ?? 'Not signed in'
  );
  const roleLabel = $derived($sessionState.user?.role ?? 'Anonymous');
  const avatarLabel = $derived($sessionState.user?.email?.slice(0, 2).toUpperCase() ?? '--');

  onMount(() => {
    let stopped = false;
    let interval: number | undefined;

    function stopForAuthExpired() {
      if (stopped) return;
      stopped = true;
      if (interval !== undefined) window.clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      sessionState.clear();
      redirectToSignInAfterAuthExpiry();
    }

    async function refreshReadyDeck() {
      // DISABLED: Waiting for the client session store delayed the first
      // readiness check even though this authenticated route already has cookies.
      // if (document.visibilityState === 'hidden' || !$sessionState.user) return;
      if (document.visibilityState === 'hidden') return;

      try {
        const response = await fetch('/api/workspace/dashboard');
        if (response.status === 401) {
          stopForAuthExpired();
          return;
        }
        if (!response.ok || stopped) return;

        const parsed = workspaceDashboardSchema.safeParse(await response.json());
        if (!parsed.success || stopped) return;

        const deck = parsed.data.decks.find((candidate) => candidate.status === 'ready_to_review');
        readyDeck = deck
          ? { id: deck.id, title: deck.title, slideCount: deck.slideCount }
          : null;
      } catch {
        // Session and connectivity state already communicate request failures.
      }
    }

    void refreshReadyDeck();
    interval = window.setInterval(refreshReadyDeck, 20_000);
    const handleVisibilityChange = () => {
      void refreshReadyDeck();
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      stopped = true;
      if (interval !== undefined) window.clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  });
</script>

<div class="app-utilities" class:app-utilities--footer={placement === 'footer'} class:app-utilities--sidebar={placement === 'sidebar'} data-utilities-placement={placement}>
  <div class="app-utilities__brand">
    <AppLogo size="sm" alt="Deck logo" />
    <div>
      <strong>Deck</strong>
      <p>Product utilities</p>
    </div>
  </div>
  <div class="app-utilities__actions" aria-live="polite">
    {#if readyDeck}
      <!-- DISABLED: role="status" and aria-live="polite" were initially set
           on this link, but an interactive link cannot use the status role. -->
      <a
        class="app-utilities__ready"
        href={`/decks/${readyDeck.id}/smart-deck`}
        aria-label={`${readyDeck.title}: ${readyDeck.slideCount} slides ready to review`}
      >
        <span class="app-utilities__ready-dot"></span>
        <span><strong>Slides ready</strong><small>Review {readyDeck.title}</small></span>
      </a>
    {/if}
    {#if showWorkspaceMode}
      <button
        type="button"
        class="app-utilities__workspace-mode"
        class:app-utilities__workspace-mode--instant={instantDeckMode}
        aria-pressed={instantDeckMode}
        aria-label={`New deck mode: ${instantDeckMode ? 'Instant Deck' : 'Smart Deck'}. Activate to switch modes.`}
        onclick={toggleWorkspaceMode}
      >
        <span class="app-utilities__workspace-switch" aria-hidden="true"><i></i></span>
        <span><small>New deck mode</small><strong>{instantDeckMode ? 'Instant Deck' : 'Smart Deck'}</strong></span>
      </button>
    {/if}
    <button type="button" class="app-utilities__status" class:app-utilities__status--offline={!$sessionState.user}>
      <span class="app-utilities__status-dot"></span>
      {connectedLabel}
    </button>
    <ThemeToggle />
    <a class="pill app-utilities__billing" href="/app/billing">
      {$sessionState.billingPlan === 'pro' ? 'Pro Plan' : 'Free Plan'}
    </a>
    <button type="button" class="app-topbar__menu">
      <span class="app-avatar">{avatarLabel}</span>
      <span class="app-topbar__identity">
        <strong>{identityLabel}</strong>
        <small>{roleLabel}</small>
      </span>
    </button>
  </div>
</div>

<style>
  :global(.app-shell__footer-utilities) {
    position: relative;
    z-index: 20;
    width: 100%;
    overflow: visible;
  }

  :global(.app-shell__footer-utilities) :global(.app-utilities--footer) {
    display: flex;
    justify-content: flex-end;
    min-width: max-content;
    padding: 0.42rem 1rem;
    border-top: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
    background: color-mix(in srgb, var(--surface) 88%, var(--bg));
  }

  :global(.app-shell__footer-utilities) :global(.app-utilities--footer) :global(.app-utilities__brand) {
    /* DISABLED: Branding duplicated the persistent sidebar brand. */
    /* display: grid; grid-template-columns: 32px minmax(0, 1fr); gap: 0.65rem; align-items: center; */
    display: none;
  }

  :global(.app-shell__footer-utilities) :global(.app-utilities--footer) :global(.app-utilities__actions) {
    display: flex;
    flex-wrap: nowrap;
    gap: 0.5rem;
    justify-content: flex-end;
    align-items: center;
  }

  :global(.app-shell__footer-utilities) :global(.app-utilities--footer) :global(.app-utilities__actions > *) {
    /* DISABLED: Full-width actions forced the persistent bar into a tall card. */
    /* width: 100%; justify-content: flex-start; */
    min-height: 38px;
  }

  :global(.app-shell__footer-utilities) :global(.app-utilities--footer) :global(.app-topbar__menu) {
    /* DISABLED: The expanded identity consumed unnecessary persistent space. */
    /* display: grid; grid-template-columns: 32px minmax(0, 1fr); gap: 0.55rem; */
    display: flex;
    grid-template-columns: 32px minmax(0, 1fr);
    gap: 0.55rem;
    border-radius: 14px;
    padding: 0.28rem 0.42rem;
  }

  :global(.app-shell__footer-utilities) :global(.app-utilities--footer) :global(.app-topbar__identity) {
    display: grid;
  }

  .app-utilities__status--offline {
    /* DISABLED: Dark-only status colors became unreadable in light mode. */
    /* border-color: rgba(248, 113, 113, 0.36); background: rgba(127, 29, 29, 0.18); color: #fecaca; */
    border-color: color-mix(in srgb, var(--danger) 36%, var(--border));
    background: var(--danger-soft);
    color: var(--danger);
  }

  .app-utilities__workspace-mode {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.3rem 0.65rem;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--surface);
    color: var(--text);
    text-align: left;
  }

  .app-utilities__workspace-mode > span:last-child {
    display: grid;
    gap: 0.05rem;
  }

  .app-utilities__workspace-mode small {
    color: var(--text-muted);
    font-size: 0.66rem;
  }

  .app-utilities__workspace-mode strong {
    font-size: 0.76rem;
  }

  .app-utilities__workspace-switch {
    display: flex;
    align-items: center;
    width: 1.9rem;
    height: 1.05rem;
    padding: 0.12rem;
    border-radius: 999px;
    background: var(--bg-subtle);
    box-shadow: inset 0 0 0 1px var(--border);
  }

  .app-utilities__workspace-switch i {
    width: 0.8rem;
    height: 0.8rem;
    border-radius: 50%;
    background: var(--text-muted);
    transition: transform 160ms ease, background 160ms ease;
  }

  .app-utilities__workspace-mode--instant .app-utilities__workspace-switch {
    background: var(--accent-soft);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent) 45%, var(--border));
  }

  .app-utilities__workspace-mode--instant .app-utilities__workspace-switch i {
    transform: translateX(0.85rem);
    background: var(--accent);
  }

  .app-utilities__ready {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
    padding: 0.35rem 0.65rem;
    border: 1px solid color-mix(in srgb, var(--success) 42%, var(--border));
    border-radius: 14px;
    background: color-mix(in srgb, var(--success) 12%, var(--surface));
    color: var(--text);
  }

  .app-utilities__ready span:not(.app-utilities__ready-dot) {
    display: grid;
  }

  .app-utilities__ready small {
    max-width: 15rem;
    overflow: hidden;
    color: var(--text-muted);
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .app-utilities__ready-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--success);
    box-shadow: 0 0 0 4px color-mix(in srgb, var(--success) 16%, transparent);
  }

  @media (max-width: 1200px) {
    :global(.app-shell__footer-utilities) {
      width: 100%;
      overflow-x: auto;
      overscroll-behavior-inline: contain;
      scrollbar-width: thin;
    }

    :global(.app-shell__footer-utilities) :global(.app-utilities--footer) :global(.app-utilities__actions) {
      width: auto;
      justify-content: flex-start;
    }

  }

  @media (max-width: 720px) {
    :global(.app-shell__footer-utilities) :global(.app-utilities--footer) :global(.app-topbar__identity) {
      display: none;
    }
  }
</style>
