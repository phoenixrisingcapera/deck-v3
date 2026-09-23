<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { deckProductApiPath } from '$lib/contracts';
  import AppShell from '$components/AppShell.svelte';
  // DISABLED: DeveloperVisibilityCard and developer payload rendering were
  // removed from the normal product loader on 2026-07-27.
  // Reason: request IDs, worker stages, poll counts, and workflow internals
  // belong to admin/operator diagnostics rather than the user transition.
  // import DeveloperVisibilityCard from '$components/visibility/DeveloperVisibilityCard.svelte';
  // import { createDeveloperVisibilityItems } from '$lib/developer-tools/payload';
  import {
    getDeckWorkflowStatus,
    type SmartDeckProcessingStatus
  } from '$lib/api/deckService/workflow.client';
  // DISABLED: Role-gated developer diagnostics on the product processing page were removed on 2026-07-14.
  // Reason: Deck processing truth should stay visible on the canonical product route.
  // import { sessionState } from '$lib/stores/session';
  import type { PageData } from './$types';
  import type { SmartDeckProcessingStatusWithDiagnostics } from '$lib/api/deckService/workflow.client';
  import {
    beginProcessingRetry,
    createProcessingResponseError,
    isBackendUnavailableDiagnostic,
    isProcessingAuthFailure,
    isTerminalProcessingOutcome,
    mergeProcessingSnapshot,
    reconcileAuthoritativeProcessingStatus,
    shouldContinueProcessingPoll
  } from '$lib/api/deckService/processingPolling';
  import { navigateReadyProcessingWorkspace } from '$lib/api/deckService/processingNavigation';
  import { trackDeckEvent } from '$lib/analytics/deckAnalytics';

  let { data }: { data: PageData } = $props();

  const POLL_DELAY_MS = 3000;
  // DISABLED: A fixed 72-second poll limit incorrectly marked valid cold-worker
  // and large-deck runs as stalled. Polling now stops only on backend terminal state.
  // const MAX_POLL_ATTEMPTS = 24;

  let status = $state<SmartDeckProcessingStatusWithDiagnostics | null>(null);
  let errorMessage = $state('');
  let authExpired = $state(false);
  let actionInFlight = $state(false);
  let sourceExtractionStartAttempted = false;
  let pollingEpoch = $state(0);
  let scheduleNextPoll: ((delayMs?: number) => void) | null = null;

  type UserLoaderStep = 'upload' | 'read' | 'preview' | 'style' | 'understand' | 'research' | 'thesis' | 'story' | 'visual' | 'assets' | 'generate' | 'workspace';

  const USER_LOADER_STEPS: Array<{ key: UserLoaderStep; label: string }> = [
    { key: 'upload', label: 'Uploading your deck' },
    { key: 'read', label: 'Reading your slides' },
    { key: 'preview', label: 'Creating slide previews' },
    { key: 'style', label: 'Identifying your visual style' },
    { key: 'understand', label: 'Understanding your company' },
    { key: 'research', label: 'Researching market and competitors' },
    { key: 'thesis', label: 'Building the investment thesis' },
    { key: 'story', label: 'Reconstructing your story' },
    { key: 'visual', label: 'Planning the visual story' },
    { key: 'assets', label: 'Creating visual assets' },
    { key: 'generate', label: 'Designing your deck' },
    { key: 'workspace', label: 'Preparing your workspace' }
  ];

  const instantMode = $derived(page.url.searchParams.get('instant') === '1');
  const instantSmartDeckHref = $derived(
    instantMode
      ? `/decks/${data.deckId}/instant-deck`
      : `/decks/${data.deckId}/smart-deck`
  );
  const signInHref = $derived(
    `/auth/sign-in?next=${encodeURIComponent(`${page.url.pathname}${page.url.search}`)}`
  );

  function userLoaderStep(nextStatus: SmartDeckProcessingStatusWithDiagnostics | null): UserLoaderStep {
    if (instantMode && nextStatus?.factualReview) return 'workspace';
    const stage = String(nextStatus?.activeStage ?? nextStatus?.processingStage ?? '').toLowerCase();
    if (stage.includes('source_extraction')) return 'read';
    if (stage.includes('preview_render') || stage.includes('schema_validation')) return 'workspace';
    if (stage.includes('miniature') || stage.includes('preview')) return 'preview';
    if (stage.includes('brand')) return 'style';
    if (stage.includes('ai_vc_understanding')) return 'understand';
    if (stage.includes('ai_vc_research')) return 'research';
    if (stage.includes('ai_vc_analysis')) return 'thesis';
    if (stage.includes('visual_asset_planning')) return 'assets';
    if (stage.includes('visual_direction')) return 'visual';
    if (stage.includes('narrative_reconstruction')) return 'story';
    if (stage.includes('generation') || stage.includes('schema_validation') || stage.includes('preview_render')) return 'generate';
    if (stage.includes('smart_deck_context') || stage.includes('db_publisher') || stage.includes('publisher')) return 'workspace';
    return 'upload';
  }

  function isAuthFailure(error: unknown): boolean {
    return isProcessingAuthFailure(error);
  }

  function stopForAuthExpired(message = 'Session expired. Sign in again.') {
    authExpired = true;
    errorMessage = message;
  }

  function shouldContinuePolling(nextStatus: SmartDeckProcessingStatusWithDiagnostics | null): boolean {
    return shouldContinueProcessingPoll(nextStatus, { authExpired, instantMode });
  }

  function statusKey(nextStatus: SmartDeckProcessingStatus): string {
    return JSON.stringify({
      lifecycleStatus: nextStatus.status, nextAction: nextStatus.nextAction,
      canOpenSmartDeck: nextStatus.canOpenSmartDeck, canRetry: nextStatus.canRetry,
      activeStage: nextStatus.activeStage, message: nextStatus.message
    });
  }

  function hasActiveRunningJob(nextStatus: SmartDeckProcessingStatusWithDiagnostics): boolean {
    return (nextStatus.latestJobs ?? []).some((job) => {
      const jobStatus = String(job.status ?? '');
      return jobStatus === 'running' || jobStatus === 'queued';
    });
  }

  function shouldStartSourceExtraction(nextStatus: SmartDeckProcessingStatusWithDiagnostics | null): boolean {
    if (!nextStatus || sourceExtractionStartAttempted || authExpired) return false;
    if (nextStatus.canOpenSmartDeck || nextStatus.canRetry) return false;
    if (nextStatus.deckExtractionStatus === 'ready' || nextStatus.deckExtractionStatus === 'failed') return false;
    return !hasActiveRunningJob(nextStatus);
  }

  async function startSourceExtractionIfNeeded(nextStatus: SmartDeckProcessingStatusWithDiagnostics | null): Promise<boolean> {
    if (!shouldStartSourceExtraction(nextStatus)) return false;
    sourceExtractionStartAttempted = true;
    const response = await fetch(deckProductApiPath(`/decks/${data.deckId}/workflows/source-extraction`), { method: 'POST' });
    const payload = await response.json().catch(() => null);
    if (!response.ok) throw createProcessingResponseError(response, payload, 'Could not start extraction.');
    void trackDeckEvent(data.deckId, {
      eventName: 'product.processing.source_extraction_started',
      surface: 'processing',
      entityType: 'workflow',
      entityId: String(nextStatus?.activeJob?.jobId ?? ''),
      metadata: { activeStage: nextStatus?.activeStage, requestId: response.headers.get('x-request-id') }
    });
    return true;
  }

  async function handleSourceRetry() {
    if (actionInFlight || !data.deckId || authExpired || instantMode) return;
    actionInFlight = true; errorMessage = '';
    try {
      if (status?.canRetry || status?.nextAction === 'retry_job' || status?.status === 'failed' || status?.deckExtractionStatus === 'failed') {
        const previousStatus = status?.status;
        const response = await fetch(deckProductApiPath(`/decks/${data.deckId}/retry`), { method: 'POST' });
        const payload = await response.json().catch(() => null);
        if (!response.ok) throw createProcessingResponseError(response, payload, 'Could not retry.');
        if (status) status = beginProcessingRetry(status);
        pollingEpoch += 1;
        void trackDeckEvent(data.deckId, {
          eventName: 'product.processing.retry_requested',
          surface: 'processing',
          entityType: 'deck',
          entityId: data.deckId,
          metadata: { requestId: response.headers.get('x-request-id'), previousStatus }
        });
      }
      scheduleNextPoll?.(0);
    } catch (error) {
      if (isAuthFailure(error)) { stopForAuthExpired(); return; }
      errorMessage = error instanceof Error ? error.message : 'Something went wrong.';
    } finally { actionInFlight = false; }
  }

  onMount(() => {
    let cancelled = false; let inFlight = false; let navigating = false;
    let timeout: number | null = null; let lastKey = status ? statusKey(status) : '';

    const clearPoll = () => { if (timeout !== null) { window.clearTimeout(timeout); timeout = null; } };
    const navigateIfReady = (nextStatus: SmartDeckProcessingStatusWithDiagnostics | null) => {
      const previousEpoch = pollingEpoch;
      return navigateReadyProcessingWorkspace(nextStatus, {
        instantMode,
        href: instantSmartDeckHref,
        cancelled: () => cancelled || authExpired || navigating,
        beforeNavigate: () => { navigating = true; pollingEpoch += 1; clearPoll(); },
        navigationFailed: () => { navigating = false; pollingEpoch = previousEpoch; },
        navigate: goto
      });
    };

    const runPoll = async () => {
      if (cancelled || inFlight || navigating || actionInFlight) return;
      const requestEpoch = pollingEpoch;
      if (!shouldContinuePolling(status)) return;
      inFlight = true;
      try {
        const incoming = await getDeckWorkflowStatus(data.deckId);
        if (cancelled || navigating || requestEpoch !== pollingEpoch) return;
        const reconciledIncoming = instantMode ? reconcileAuthoritativeProcessingStatus(incoming) : incoming;
        const next = mergeProcessingSnapshot(status, reconciledIncoming);
        const nextKey = statusKey(next);
        // DISABLED: `if (nextKey !== lastKey) status = next;` ignored preview
        // count/URL changes when lifecycle fields did not change.
        status = next;
        lastKey = nextKey;
        errorMessage = '';
        if (await startSourceExtractionIfNeeded(next)) { scheduleNextPoll?.(0); return; }
        if (await navigateIfReady(next)) return;
        // DISABLED: the former fixed-attempt timeout stopped valid
        // large-deck and cold-worker runs after roughly 72 seconds.
        // Backend workflow state, not elapsed browser time, owns terminal state.
      } catch (error) {
        if (!cancelled) {
          if (isAuthFailure(error)) { stopForAuthExpired(); clearPoll(); return; }
          errorMessage = error instanceof Error ? error.message : 'Could not check status.';
        }
      } finally {
        inFlight = false;
        if (!cancelled && !navigating && requestEpoch === pollingEpoch && shouldContinuePolling(status)) scheduleNextPoll?.(POLL_DELAY_MS);
      }
    };

    scheduleNextPoll = (delayMs = 0) => {
      if (cancelled || authExpired) return; clearPoll();
      timeout = window.setTimeout(() => { void runPoll(); }, delayMs);
    };

    const initialStatus = status ?? data.initialStatus as SmartDeckProcessingStatusWithDiagnostics;
    status = instantMode ? reconcileAuthoritativeProcessingStatus(initialStatus) : initialStatus;
    lastKey = statusKey(status);
    void navigateIfReady(status).then((didNavigate) => {
      if (!didNavigate && !cancelled && shouldContinuePolling(status)) scheduleNextPoll?.(900);
    }).catch((error) => {
      if (!cancelled) errorMessage = error instanceof Error ? error.message : 'Could not open the ready workspace.';
      if (!cancelled && shouldContinuePolling(status)) scheduleNextPoll?.(POLL_DELAY_MS);
    });
    return () => { cancelled = true; scheduleNextPoll = null; clearPoll(); };
  });

  const isReady = $derived(Boolean(instantMode ? status?.canOpenInstantDeck : status?.canOpenSmartDeck));
  const statusUnavailable = $derived(isBackendUnavailableDiagnostic(status));
  const retryAllowed = $derived(Boolean(!instantMode && (status?.canRetry || status?.nextAction === 'retry_job')));
  const terminalOutcome = $derived(isTerminalProcessingOutcome(status, { instantMode }));
  const workflowFailed = $derived(Boolean(!statusUnavailable && !isReady && terminalOutcome));
  const canOpenFailedInstantDeck = $derived(Boolean(
    instantMode && workflowFailed && status?.canOpenSmartDeck && !status?.canOpenInstantDeck
  ));
  const needsRetry = $derived(Boolean(!instantMode && workflowFailed && retryAllowed));
  const requiresManualReview = $derived(Boolean(
    workflowFailed &&
    status?.nextAction === 'manual_review' &&
    !retryAllowed &&
    !canOpenFailedInstantDeck
  ));
  async function resumeSavedDraft() {
    const review = status?.factualReview;
    if (!review?.canResumeSavedReview || !review.generationJobId || actionInFlight) return;
    actionInFlight = true; errorMessage = '';
    try {
      const response = await fetch(deckProductApiPath(`/decks/${data.deckId}/workflows/retry-failed-slides`), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ priorGenerationJobId: review.generationJobId, idempotencyKey: `saved-review:${review.generationJobId}` })
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw createProcessingResponseError(response, payload, 'Could not continue the saved draft.');
      window.location.href = `/decks/${data.deckId}/processing?instant=1`;
    } catch (error) { errorMessage = error instanceof Error ? error.message : 'Could not continue the saved draft.'; }
    finally { actionInFlight = false; }
  }



  const failureMessage = $derived(
    instantMode ? 'Your work is saved. Continue below, or reopen the deck to try again.' : status?.errorMessage || status?.message || 'The requested deck could not be completed.'
  );
  const activeLoaderStep = $derived(userLoaderStep(status));
  const activeLabel = $derived(
    isReady
      ? 'Your deck is ready'
      : instantMode
        ? ['upload', 'read', 'preview', 'style'].includes(activeLoaderStep) ? 'Reading your deck' : activeLoaderStep === 'generate' ? 'Redesigning your slides' : 'Preparing your presentation'
        : USER_LOADER_STEPS.find((step) => step.key === activeLoaderStep)?.label ?? 'Preparing your deck'
  );
  const availablePreviews = $derived((status?.sourceSlides ?? []).filter((slide) => slide.previewImageUrl || slide.thumbnailUrl || slide.previewUrl));
  // DISABLED: The former visibilityItems and processingDiagnosticsItems
  // rendered internal workflow and correlation fields directly to users.
  // Canonical status remains available in `status` for control flow only.
</script>

<AppShell
  title="Processing"
  activeNav="upload"
  showTopBarSearch={false}
  compactSidebar={true}
>
  <section class="panel processing" aria-live="polite" data-sveltekit-preload-data="off">
    {#if workflowFailed && status?.factualReview?.canResumeSavedReview}
      <aside class="panel">
        <p>Your redesign is saved. Continue preparing it for viewing and download.</p>
        <button class="btn" disabled={actionInFlight} onclick={resumeSavedDraft}>Continue saved redesign</button>
      </aside>
    {/if}
    {#if status?.publicResearch}
      <p class="muted" role="status">{status.publicResearch.message}</p>
      {#if status.publicResearch.sources.length > 0 || status.publicResearch.limitations.length > 0}
        <details class="research-summary">
          <summary>Research summary ({status.publicResearch.verifiedClaimCount} verified {status.publicResearch.verifiedClaimCount === 1 ? 'finding' : 'findings'})</summary>
          {#if status.publicResearch.sources.length > 0}
            <p class="muted">Verified public sources</p>
            <ul>
              {#each status.publicResearch.sources as source}
                <li>
                  <a href={source.url} target="_blank" rel="noreferrer">{source.publisher}</a>
                  <span class="muted"> — {source.topic.replaceAll('_', ' ')}</span>
                </li>
              {/each}
            </ul>
          {/if}
          {#if status.publicResearch.limitations.length > 0}
            <p class="muted">Limitations</p>
            <ul>
              {#each status.publicResearch.limitations as limitation}
                <li>{limitation}</li>
              {/each}
            </ul>
          {/if}
        </details>
      {/if}
    {/if}
    {#if status?.aiVcStrategy?.status === 'source_only_fallback'}
      <p class="muted" role="status">The investor analysis was unavailable. Your deck is continuing from verified source evidence.</p>
    {:else if status?.aiVcStrategy?.status === 'ready' && status.aiVcStrategy.recoveryUsed}
      <p class="muted" role="status">Investor analysis recovered and is shaping the redesigned narrative.</p>
    {/if}
    <div class="processing__head">
      <div>
        {#if authExpired}
          <h2>Session expired</h2>
          <p class="muted">Sign in again to continue.</p>
        {:else if statusUnavailable}
          <h2>Progress connection interrupted</h2>
          <p class="muted">{isReady ? 'Your last confirmed deck is ready. Live status is reconnecting.' : 'Your last confirmed progress is preserved while live status reconnects.'}</p>
        {:else if isReady}
          <h2>Your deck is ready</h2>
          <p class="muted">Opening your workspace now.</p>
        {:else if workflowFailed}
          <h2>{canOpenFailedInstantDeck ? "We couldn't finish the Instant Deck" : "We couldn't finish preparing this deck"}</h2>
          <p class="muted">{failureMessage}</p>
        {:else}
          <h2>Preparing your deck</h2>
          <p class="muted">{activeLabel}</p>
        {/if}
      </div>
      <span class="processing__status" class:ready={isReady} class:failed={workflowFailed || authExpired}>
        {authExpired ? 'Sign-in required' : statusUnavailable ? 'Reconnecting' : isReady ? 'Ready' : workflowFailed ? 'Needs attention' : 'In progress'}
      </span>
    </div>

    {#if authExpired}
      <div class="processing__auth">
        <a class="button" href={signInHref}>Sign in again</a>
      </div>
    {:else}
      {#if !workflowFailed && !statusUnavailable}
        <section class="loader" aria-label="Deck preparation progress">
          <div class="loader__visual" aria-hidden="true">
            <span class="loader__orbit"></span>
            <span class="loader__core"></span>
          </div>
          <p class="loader__message" role="status">{activeLabel}</p>
          <p class="muted">Workspace opens automatically.</p>
        </section>
      {/if}

      {#if !instantMode && availablePreviews.length}
        <section class="processing__previews" aria-label="Available slide previews">
          <div class="processing__previews-head">
            <strong>Source slide previews</strong>
            <span>{availablePreviews.length} available</span>
          </div>
          <div class="processing__preview-grid">
            {#each availablePreviews as slide}
              <figure>
                <img
                  src={slide.previewImageUrl ?? slide.thumbnailUrl ?? slide.previewUrl ?? ''}
                  alt={slide.title || `Slide ${(slide.slideIndex ?? 0) + 1}`}
                  loading="eager"
                />
                <figcaption>{slide.title || `Slide ${(slide.slideIndex ?? 0) + 1}`}</figcaption>
              </figure>
            {/each}
          </div>
        </section>
      {/if}

      <div class="processing__actions">
        {#if isReady}
          <a class="button" href={instantSmartDeckHref}>Open workspace</a>
        {:else if statusUnavailable}
          <button class="button" type="button" onclick={() => scheduleNextPoll?.(0)}>Try again</button>
          {#if isReady}<a class="button secondary" href={instantSmartDeckHref}>Open workspace</a>{/if}
          <a class="button secondary" href="/decks">Return to decks</a>
        {:else if needsRetry}
          <button type="button" class="button" onclick={handleSourceRetry} disabled={actionInFlight}>
            {actionInFlight ? 'Retrying...' : 'Retry preparation'}
          </button>
          {#if canOpenFailedInstantDeck}
            <a class="button secondary" href={instantSmartDeckHref}>View Instant Deck status</a>
          {/if}
          <a class="button secondary" href="/decks/new">New deck</a>
        {:else if canOpenFailedInstantDeck}
          <a class="button" href={instantSmartDeckHref}>View Instant Deck status</a>
          <a class="button secondary" href="/decks">Return to decks</a>
          <p class="manual-review-copy" role="status">Your uploaded source is safe. This generation failed and did not publish a deck.</p>
        {:else if requiresManualReview}
          <p class="manual-review-copy" role="status">Automatic preparation could not continue. Return to your decks and contact support if the issue persists.</p>
          <a class="button secondary" href="/decks">Return to decks</a>
        {/if}
      </div>
    {/if}

    {#if errorMessage}
      <p class="error-copy">{errorMessage}</p>
    {/if}

    <!-- DISABLED: Unconditional product-route developer diagnostics were
    replaced by the user loader on 2026-07-27. Operational diagnostics remain
    available through canonical admin tooling and the server payload. -->
  </section>
</AppShell>

<style>
  .processing {
    display: grid; gap: 20px; width: min(760px, 100%); margin: 0 auto; padding: 28px;
  }

  .processing__head {
    display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;
  }

  .processing__head h2 { font-size: 18px; }
  .processing__head p { font-size: 13px; margin-top: 4px; }

  .processing__status {
    padding: 4px 10px; border-radius: var(--radius-full);
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.05em; white-space: nowrap;
    border: 1px solid var(--border); color: var(--text-muted); background: var(--bg-subtle);
  }

  .processing__previews { display: grid; gap: 10px; }
  .processing__previews-head { display: flex; justify-content: space-between; font-size: 12px; color: var(--text-muted); }
  .processing__preview-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .processing__preview-grid figure { margin: 0; overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--bg-subtle); }
  .processing__preview-grid img { display: block; width: 100%; aspect-ratio: 16 / 9; object-fit: cover; }
  .processing__preview-grid figcaption { padding: 7px 9px; overflow: hidden; font-size: 11px; color: var(--text-muted); text-overflow: ellipsis; white-space: nowrap; }
  .processing__status.ready { color: var(--success); border-color: var(--success); }
  .processing__status.failed { color: var(--danger); border-color: var(--danger); }

  .loader { display: grid; justify-items: center; gap: 10px; padding: 10px 8px 2px; text-align: center; }
  .loader__visual { position: relative; width: 56px; height: 56px; }
  .loader__orbit { position: absolute; inset: 0; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: loader-spin 1.1s linear infinite; }
  .loader__core { position: absolute; inset: 18px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 18px var(--accent-soft); animation: loader-pulse 1.6s ease-in-out infinite; }
  .loader__message { margin: 0; font-size: 15px; font-weight: 650; }
  .loader .muted { max-width: 320px; margin: 0; font-size: 12px; }

  @keyframes loader-spin { to { transform: rotate(360deg); } }
  @keyframes loader-pulse { 50% { transform: scale(0.8); opacity: 0.65; } }

  @media (prefers-reduced-motion: reduce) {
    .loader__orbit, .loader__core { animation: none; }
  }

  @media (max-width: 640px) {
    .processing { padding: 20px 16px; }
    .processing__head { align-items: center; }
    .processing__preview-grid { grid-template-columns: 1fr; }
  }

  .processing__auth { display: flex; gap: 8px; }

  .processing__actions { display: flex; gap: 8px; flex-wrap: wrap; }
  .manual-review-copy { flex-basis: 100%; margin: 0; color: var(--text-muted); font-size: 13px; }
  button:disabled { opacity: 0.5; cursor: wait; }
</style>
