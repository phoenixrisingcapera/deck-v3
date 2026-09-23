<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';

  const safeDestinations = [
    // DISABLED: /welcome was omitted, so an error on the canonical signed-in
    // welcome route incorrectly sent the user to the public marketing page.
    // { match: /^\/(dashboard|smart-deck|decks|templates|insights|team|settings)(\/|$)/, href: '/dashboard' }
    { match: /^\/(welcome|dashboard|smart-deck|decks|templates|insights|team|settings)(\/|$)/, href: '/dashboard' }
  ];

  type FailureTicketReport = {
    route?: string | null;
    pageUrl?: string | null;
    apiPath?: string | null;
    statusCode?: number | null;
    userId?: string | null;
    userEmail?: string | null;
    deckId?: string | null;
    errorName?: string | null;
    errorMessage?: string | null;
    errorStack?: string | null;
    context?: Record<string, unknown>;
    severity?: 'low' | 'medium' | 'high' | 'critical';
    source?: 'frontend' | 'api' | 'backend' | 'loader' | 'fallback';
    requestId?: string | null;
  };

  async function reportFailureTicket(report: FailureTicketReport) {
    try {
      await fetch('/api/support/failure-tickets/report', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(report)
      });
    } catch {
      // Reporting must never make the user-facing failure worse.
    }
  }

  let redirecting = $state(false);

  function fallbackHref(pathname: string) {
    return safeDestinations.find((item) => item.match.test(pathname))?.href ?? '/';
  }

  onMount(() => {
    const current = $page.url.pathname;
    const href = fallbackHref(current);
    const errorValue = $page.error;
    const errorRecord = errorValue && typeof errorValue === 'object'
      ? (errorValue as unknown as Record<string, unknown>)
      : {};
    const errorMessage = typeof errorRecord.message === 'string' ? errorRecord.message : 'Page failed to load.';

    void reportFailureTicket({
      route: current,
      pageUrl: $page.url.href,
      statusCode: $page.status,
      errorName: typeof errorRecord.name === 'string' ? errorRecord.name : 'PageError',
      errorMessage,
      severity: $page.status >= 500 ? 'high' : 'medium',
      source: 'frontend',
      context: {
        fallbackHref: href
      }
    });

    redirecting = true;
    const redirectTimer = window.setTimeout(() => {
      void goto(href, { replaceState: true });
    }, 1200);

    // Cancel the fallback if the user has already left the error page. Without
    // this cleanup, the stale timer can override their newer navigation.
    return () => window.clearTimeout(redirectTimer);
  });
</script>

<svelte:head>
  <title>We hit a snag | Deck AIStack</title>
</svelte:head>

<main class="error-page">
  <section class="message">
    <p class="eyebrow">Deck AIStack</p>
    <h1>We hit a snag.</h1>
    <p>Your work is safe. We have recorded the issue for review and are taking you back to a stable page.</p>
    {#if redirecting}
      <p class="muted">Redirecting now...</p>
    {:else}
      <a href="/">Go home</a>
    {/if}
  </section>
</main>

<style>
  .error-page {
    min-height: 100vh;
    display: grid;
    place-items: center;
    padding: 2rem;
    background: var(--bg, #f8fafc);
    color: var(--text, #172033);
  }

  .message {
    width: min(100%, 36rem);
    display: grid;
    gap: 0.75rem;
  }

  .eyebrow,
  .muted {
    color: var(--text-muted, #64748b);
  }

  .eyebrow {
    margin: 0;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0;
    text-transform: uppercase;
  }

  h1,
  p {
    margin: 0;
  }

  h1 {
    font-size: clamp(2rem, 4vw, 3rem);
  }

  a {
    color: var(--accent, #2563eb);
    font-weight: 700;
  }
</style>
