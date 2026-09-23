<script lang="ts">
  import { onMount } from 'svelte';
  import type { DeckGraph } from '$types/domain';
  import type { DesignVersion, SmartDeckWorkspacePayload } from '$lib/api/smartDeckWorkspace';
  import { mintInstantHtmlFullDeckCapability, waitForWorkflowJobCompletion } from '$lib/api/smartDeckWorkspace';
  import { openInstantHtmlPrintPlaceholder } from '$lib/config/instantHtmlRendererOrigin.js';
  import DeckWorkspaceRegistration from '$lib/components/decks/DeckWorkspaceRegistration.svelte';
  import { buildSmartDeckDesignContext } from '$lib/components/instant-deck/designFallback';
  import { instantDeckReconciliationState } from './reconciliationState';
  import { getDeckWorkflowStatus } from '$lib/api/deckService/workflow.client';
  import {
    generateInstantDeckVersion,
    getInstantDeckWorkspace,
    saveInstantDeckSelection,
    toInstantDeckSlideRail
  } from './instantDeckApi';

  interface Props {
    graph: DeckGraph;
    initialWorkspace: SmartDeckWorkspacePayload | null;
    initialSelectedVersionId?: string | null;
    initialSelectedGeneratedSlideId?: string | null;
    fallbackMessage?: string | null;
    fallbackActionHref?: string | null;
    fallbackActionLabel?: string | null;
  }

  let {
    graph,
    initialWorkspace,
    initialSelectedVersionId = null,
    initialSelectedGeneratedSlideId = null,
    fallbackMessage = null,
    fallbackActionHref = null,
    fallbackActionLabel = null
  }: Props = $props();

  const DEFAULT_PROMPT = 'Regenerate the complete deck with a stronger narrative, clearer evidence, and a consistent visual hierarchy appropriate to the source presentation.';
  const MAX_SOURCE_PAGES = 25;
  const ACTIVE_JOB_STATUSES = new Set(['queued', 'running']);

  const initialState = () => ({
    workspace: initialWorkspace,
    selectedVersionId: initialSelectedVersionId,
    selectedGeneratedSlideId: initialSelectedGeneratedSlideId
  });
  const initial = initialState();
  let workspace = $state<SmartDeckWorkspacePayload | null>(initial.workspace);
  let selectedVersionId = $state<string | null>(initial.selectedVersionId);
  let selectedGeneratedSlideId = $state<string | null>(initial.selectedGeneratedSlideId);
  let commandInFlight = $state(false);
  let reconciliationRequired = $state(true);
  let generationState = $state<'idle' | 'generating' | 'success' | 'error'>('idle');
  let generationMessage = $state('Checking your presentation…');
  let conversationState = $state<'idle' | 'sending' | 'error'>('idle');
  let conversationMessage = $state('');
  let printPreparing = $state(false);
  let printMessage = $state('');
  let analysisOpen = $state(false);
  let analysisTab = $state<'concerns' | 'next' | 'visual' | 'review' | 'sources'>('concerns');
  let generationIntentKey: string | null = null;
  let activeController: AbortController | null = null;

  const instantJobIds = $derived(new Set(
    workspace?.generationJobs
      .filter((job) => job.generationMode === 'instant_deck')
      .map((job) => job.id) ?? []
  ));
  const instantVersions = $derived(
    workspace?.designVersions.filter((version) => isInstantVersion(version)) ?? []
  );
  const selectedVersion = $derived(
    instantVersions.find((version) => version.id === selectedVersionId) ?? instantVersions[0] ?? null
  );
  const generatedSlides = $derived(
    toInstantDeckSlideRail(selectedVersion, workspace?.sourceSlides ?? [])
  );
  const selectedGeneratedSlide = $derived(
    generatedSlides.find((slide) => slide.id === selectedGeneratedSlideId) ?? generatedSlides[0] ?? null
  );
  const fullDeckHtml = $derived(generatedSlides.find((slide) => slide.htmlSlide)?.htmlSlide ?? null);
  const activeGeneration = $derived(
    workspace?.generationJobs.find((job) => ACTIVE_JOB_STATUSES.has(job.status)) ?? null
  );
  const busy = $derived(
    commandInFlight ||
    generationState === 'generating' ||
    Boolean(activeGeneration) ||
    (reconciliationRequired && generationState !== 'error')
  );
  const regenerateLabel = $derived(
    generationState === 'error' ? 'Check status' : reconciliationRequired
      ? 'Checking status...'
      : generationState === 'generating' || activeGeneration
        ? 'Regenerating...'
        : selectedVersion
          ? 'Regenerate'
          : 'Generate Instant Deck'
  );
  const critique = $derived(workspace?.investmentCritique ?? null);
  const sources = $derived(workspace?.sourceSummary?.sources ?? []);
  const visualDirection = $derived(workspace?.visualIntelligence?.visualDirection ?? null);
  const visualFindings = $derived(workspace?.visionReview?.findings ?? []);
  const concernItems = $derived([
    ...(critique?.severity.criticalForFundraising ?? []),
    ...(critique?.severity.important ?? []),
    ...(critique?.concerns ?? []),
    ...(critique?.investorObjections ?? [])
  ]);
  const nextItems = $derived([
    ...(critique?.missingProof ?? []),
    ...(critique?.recommendedChanges ?? [])
  ]);

  function isInstantVersion(version: DesignVersion) {
    return version.artifactType === 'full_html_deck.v1' ||
      version.renderMode === 'html_compiled.v1' ||
      Boolean(version.generationJobId && instantJobIds.has(version.generationJobId));
  }

  function orderedSourceSlideIds(current: SmartDeckWorkspacePayload) {
    return [...current.sourceSlides]
      .sort((left, right) => left.slideNumber - right.slideNumber)
      .map((slide) => slide.id);
  }

  async function printDeck() {
    if (!fullDeckHtml || fullDeckHtml.renderProofStatus !== 'ready' || printPreparing) return;
    printPreparing = true;
    printMessage = '';
    let placeholder: Window | null = null;
    try {
      placeholder = openInstantHtmlPrintPlaceholder(window.open.bind(window));
      const capability = await mintInstantHtmlFullDeckCapability(fullDeckHtml);
      placeholder.location.replace(capability.renderUrl);
      placeholder = null;
      printMessage = 'Deck opened for printing. Use browser Print and choose Save as PDF.';
    } catch (error) {
      placeholder?.close();
      printMessage = error instanceof Error ? error.message : 'The deck could not be opened for printing.';
    } finally {
      printPreparing = false;
    }
  }

  function resolvePersistedVersion(current: SmartDeckWorkspacePayload, requestedVersionId?: string | null) {
    const currentInstantJobIds = new Set(
      current.generationJobs.filter((job) => job.generationMode === 'instant_deck').map((job) => job.id)
    );
    const versions = current.designVersions.filter((version) =>
      version.artifactType === 'full_html_deck.v1' ||
      version.renderMode === 'html_compiled.v1' ||
      Boolean(version.generationJobId && currentInstantJobIds.has(version.generationJobId))
    );
    const preferred = requestedVersionId ?? current.preferences.activeDesignVersionId ?? current.activeDesignVersionId;
    return versions.find((version) => version.id === preferred) ?? versions[0] ?? null;
  }

  function applyWorkspace(current: SmartDeckWorkspacePayload, requestedVersionId?: string | null) {
    workspace = current;
    const version = resolvePersistedVersion(current, requestedVersionId ?? selectedVersionId);
    selectedVersionId = version?.id ?? null;
    const preferredGeneratedId = current.preferences.activeGeneratedSlideId ?? current.activeGeneratedSlideId ?? selectedGeneratedSlideId;
    selectedGeneratedSlideId = version?.generatedSlides.some((slide) => slide.id === preferredGeneratedId)
      ? preferredGeneratedId ?? null
      : version?.generatedSlides[0]?.id ?? null;
  }

  async function selectGeneratedSlide(generatedSlideId: string) {
    if (!workspace || !selectedVersion) return;
    const generated = selectedVersion.generatedSlides.find((slide) => slide.id === generatedSlideId);
    if (!generated) return;
    selectedGeneratedSlideId = generated.id;
    const sourceSlideId = generated.sourceSlideId ?? generated.sourceSlideIds?.[0] ?? null;
    try {
      await saveInstantDeckSelection(workspace.deck.id, {
        activeDesignVersionId: selectedVersion.id,
        activeGeneratedSlideId: generated.id,
        activeSourceSlideId: sourceSlideId
      });
    } catch (error) {
      generationState = 'error';
      generationMessage = error instanceof Error ? error.message : 'The selected generated slide could not be saved.';
    }
  }

  async function refreshAndFollowActive(signal: AbortSignal) {
    let current = await getInstantDeckWorkspace(graph.deck.id, signal);
    applyWorkspace(current);
    const active = current.generationJobs.find((job) => ACTIVE_JOB_STATUSES.has(job.status));
    if (!active) return { workspace: current, followedActiveOperation: false };

    generationState = 'generating';
    generationMessage = active.generationMode === 'instant_deck'
      ? 'Your Instant Deck generation is already in progress.'
      : 'Waiting for the active deck operation to finish.';
    const completed = await waitForWorkflowJobCompletion(
      active.id,
      'The active deck operation failed.',
      undefined,
      undefined,
      undefined,
      signal
    );
    current = completed.workspace ?? await getInstantDeckWorkspace(graph.deck.id, signal);
    applyWorkspace(current, completed.designVersion?.id ?? null);
    return { workspace: current, followedActiveOperation: true };
  }

  async function reconcile() {
    if (commandInFlight) return;
    commandInFlight = true;
    reconciliationRequired = true;
    generationMessage = 'Checking your presentation…';
    const controller = new AbortController();
    activeController = controller;
    try {
      const refreshed = await refreshAndFollowActive(controller.signal);
      // Reconciliation is the authority that no command is still active.
      // A terminal failure must not retain its idempotency identity and turn
      // the next visible Regenerate click into a replay of the failed job.
      generationIntentKey = null;
      reconciliationRequired = false;
      const workflow = await getDeckWorkflowStatus(graph.deck.id);
      if (controller.signal.aborted) return;
      const reconciled = instantDeckReconciliationState(refreshed.workspace.generationJobs, Boolean(selectedVersionId), workflow);
      generationState = reconciled.state;
      generationMessage = reconciled.state === 'idle' && selectedVersion ? 'Your presentation is ready.' : reconciled.message;
    } catch (error) {
      if (controller.signal.aborted) return;
      reconciliationRequired = true;
      generationState = 'error';
      generationMessage = error instanceof Error ? error.message : 'Instant Deck status could not be verified. Retry the status check.';
    } finally {
      commandInFlight = false;
      if (activeController === controller) activeController = null;
    }
  }

  async function generate(prompt = DEFAULT_PROMPT, baseDesignVersionId: string | null = null) {
    if (commandInFlight || generationState === 'generating' || activeGeneration) return false;
    commandInFlight = true;
    const controller = new AbortController();
    activeController = controller;
    try {
      const refreshed = await refreshAndFollowActive(controller.signal);
      if (refreshed.followedActiveOperation) {
        generationState = 'idle';
        generationMessage = 'The existing operation finished. Review its result before starting another generation.';
        return false;
      }
      const current = refreshed.workspace;
      const sourceSlideIds = orderedSourceSlideIds(current);
      if (!sourceSlideIds.length) throw new Error('Source extraction is not ready yet.');
      if (sourceSlideIds.length > MAX_SOURCE_PAGES) {
        throw new Error(`Instant Deck supports complete whole-deck generation for up to ${MAX_SOURCE_PAGES} source pages.`);
      }

      reconciliationRequired = false;
      generationState = 'generating';
      generationMessage = 'Redesigning your slides…';
      generationIntentKey ??= crypto.randomUUID();
      const result = await generateInstantDeckVersion(current.deck.id, {
        prompt: prompt.trim() || DEFAULT_PROMPT,
        userPrompt: prompt.trim() || DEFAULT_PROMPT,
        selectedSourceSlideIds: sourceSlideIds,
        activeSourceSlideId: sourceSlideIds[0],
        selectedElementId: null,
        audience: current.preferences.audience ?? current.deck.audience ?? graph.deck.audience ?? null,
        deckType: current.preferences.deckType ?? 'startup_pitch',
        selectedSubject: current.preferences.selectedSubject ?? 'unknown',
        latestBatchId: null,
        designContext: buildSmartDeckDesignContext({ graph }),
        idempotencyKey: generationIntentKey,
        generationMode: 'instant_deck',
        // Toolbar Regenerate starts a fresh source-grounded art direction.
        // A typed follow-up instruction may intentionally carry the selected
        // immutable version as its editing baseline.
        baseDesignVersionId
      }, controller.signal);
      applyWorkspace(result.workspace, result.designVersion?.id ?? null);
      if (!result.designVersion) {
        reconciliationRequired = true;
        generationState = 'error';
        generationMessage = 'Generation completed, but the new persisted DesignVersion is not visible yet. Check status before retrying.';
        return true;
      }
      const firstGeneratedSlide = result.designVersion.generatedSlides[0] ?? null;
      await saveInstantDeckSelection(current.deck.id, {
        activeDesignVersionId: result.designVersion.id,
        activeGeneratedSlideId: firstGeneratedSlide?.id ?? null,
        activeSourceSlideId: firstGeneratedSlide?.sourceSlideId ?? firstGeneratedSlide?.sourceSlideIds?.[0] ?? null
      });
      selectedVersionId = result.designVersion.id;
      selectedGeneratedSlideId = firstGeneratedSlide?.id ?? null;
      generationIntentKey = null;
      generationState = 'success';
      generationMessage = 'Your presentation is ready.';
      return true;
    } catch (error) {
      if (controller.signal.aborted) return false;
      reconciliationRequired = true;
      generationState = 'error';
      generationMessage = error instanceof Error ? error.message : 'Instant Deck generation failed. Check status before retrying.';
      return true;
    } finally {
      commandInFlight = false;
      if (activeController === controller) activeController = null;
    }
  }

  async function sendInstruction(instruction: string) {
    conversationState = 'sending';
    conversationMessage = '';
    const submitted = await generate(instruction, selectedVersionId);
    if (!submitted && !busy) {
      conversationState = 'error';
      conversationMessage = 'Another operation already owns this deck. Check status before trying again.';
      return;
    }
    conversationState = generationState === 'error' ? 'error' : 'idle';
    conversationMessage = generationState === 'error' ? generationMessage : '';
  }

  onMount(() => {
    void reconcile();
    return () => activeController?.abort();
  });
</script>

<DeckWorkspaceRegistration config={() => ({
  surface: 'instant-deck',
  sidebar: {
    items: [{ key: 'slides', icon: '▣', label: 'Slides' }],
    activeKey: 'slides',
    ariaLabel: 'Instant Deck'
  },
  navigator: {
    slides: generatedSlides,
    selectedSlideId: selectedGeneratedSlide?.id ?? null,
    selectedSourceSlideIds: [],
    onSelectSlide: (slideId) => void selectGeneratedSlide(slideId),
    title: 'Your redesigned slides',
    description: '',
    showSourceSelection: false,
    showSearch: false,
    belowToolbar: true,
    visible: true,
    interactionDisabledReason: busy ? 'Generation reconciliation is active.' : null
  },
  visualizer: {
    title: selectedGeneratedSlide?.title ?? workspace?.deck.title ?? graph.deck.title,
    subtitle: selectedVersion
      ? 'Your saved investor presentation'
      : 'Redesign your presentation for investors.',
    slide: selectedGeneratedSlide
      ? { title: selectedGeneratedSlide.title, slideNumber: selectedGeneratedSlide.number, previewImageUrl: selectedGeneratedSlide.previewUrl }
      : null,
    htmlSlide: selectedGeneratedSlide?.htmlSlide ?? fullDeckHtml,
    htmlDisplayMode: 'section',
    interactive: false,
    editable: false,
    emptyTitle: busy ? 'Generating your Instant Deck' : generationState === 'error' ? "We couldn't finish the Instant Deck" : 'No Instant Deck version yet',
    emptyText: busy
      ? 'Preparing your presentation.'
      : generationState === 'error' ? generationMessage : 'Create an investor redesign from your uploaded deck.'
  },
  chat: {
    messages: workspace?.messages ?? [],
    state: conversationState,
    message: conversationMessage,
    onSend: (instruction) => void sendInstruction(instruction),
    title: 'Instant Deck direction',
    eyebrow: 'Whole-deck generation',
    description: 'Describe what you would like to improve in your presentation.',
    emptyText: 'The source document remains evidence; your instruction controls the redesign.',
    placeholder: 'Describe the complete deck redesign…',
    sendLabel: 'Generate',
    sendingLabel: 'Generating…',
    retryAvailable: generationState === 'error',
    onRetry: () => void reconcile()
  }
})}>
  <header class="instant-deck-toolbar">
    <div class="instant-deck-toolbar__status" role="status" aria-live="polite">
      <span class:busy aria-hidden="true">●</span>
      <span>{generationMessage}</span>
    </div>
    <div class="instant-deck-toolbar__actions">
      {#if critique || sources.length || visualDirection || workspace?.visionReview}
        <button type="button" onclick={() => analysisOpen = !analysisOpen} aria-expanded={analysisOpen}>
          How this story was built
        </button>
      {/if}
      {#if fullDeckHtml?.renderProofStatus === 'ready'}
        <button type="button" disabled={printPreparing} onclick={() => void printDeck()}>Print / Save as PDF</button>
      {/if}
      <button
        type="button"
        class="primary"
        disabled={busy}
        onclick={() => void (reconciliationRequired || generationState === 'error' ? reconcile() : generate())}
      >{regenerateLabel}</button>
      {#if generationState === 'error'}
        <button type="button" onclick={() => void reconcile()}>Retry status</button>
      {/if}
    </div>
  </header>
  {#if printMessage}<p role="status">{printMessage}</p>{/if}

  {#if analysisOpen}
    <aside class="ai-vc-panel" aria-label="Investor reasoning used to build this deck">
      <div class="ai-vc-panel__heading">
        <div>
          <strong>Investor reasoning used in this deck</strong>
          <p>This internal analysis shaped the investment narrative, slide architecture and visual direction. It is not included in the export.</p>
        </div>
        <button type="button" aria-label="Close investor reasoning" onclick={() => analysisOpen = false}>×</button>
      </div>
      <div class="ai-vc-tabs" role="tablist" aria-label="Investor reasoning sections">
        <button class:active={analysisTab === 'concerns'} role="tab" aria-selected={analysisTab === 'concerns'} onclick={() => analysisTab = 'concerns'}>Investor concerns</button>
        <button class:active={analysisTab === 'next'} role="tab" aria-selected={analysisTab === 'next'} onclick={() => analysisTab = 'next'}>What to prove next</button>
        <button class:active={analysisTab === 'visual'} role="tab" aria-selected={analysisTab === 'visual'} onclick={() => analysisTab = 'visual'}>Visual direction</button>
        <button class:active={analysisTab === 'review'} role="tab" aria-selected={analysisTab === 'review'} onclick={() => analysisTab = 'review'}>Visual review</button>
        <button class:active={analysisTab === 'sources'} role="tab" aria-selected={analysisTab === 'sources'} onclick={() => analysisTab = 'sources'}>Sources</button>
      </div>
      <div class="ai-vc-panel__content" role="tabpanel">
        {#if analysisTab === 'concerns'}
          {#if concernItems.length}
            <ul>{#each concernItems as item}<li>{item}</li>{/each}</ul>
          {:else}<p>No investor concerns have been recorded for this redesign.</p>{/if}
        {:else if analysisTab === 'next'}
          {#if nextItems.length}
            <ul>{#each nextItems as item}<li>{item}</li>{/each}</ul>
          {:else}<p>{critique?.nextAction ?? 'No additional proof request has been recorded.'}</p>{/if}
        {:else if analysisTab === 'visual'}
          {#if visualDirection}
            <h3>{visualDirection.design_thesis || visualDirection.concept || 'Visual direction'}</h3>
            <dl class="visual-direction-list">
              {#if visualDirection.typography_direction}<div><dt>Typography</dt><dd>{visualDirection.typography_direction}</dd></div>{/if}
              {#if visualDirection.color_strategy}<div><dt>Colour</dt><dd>{visualDirection.color_strategy}</dd></div>{/if}
              {#if visualDirection.imagery_strategy}<div><dt>Imagery</dt><dd>{visualDirection.imagery_strategy}</dd></div>{/if}
              {#if visualDirection.data_visualization_direction}<div><dt>Data</dt><dd>{visualDirection.data_visualization_direction}</dd></div>{/if}
              {#if visualDirection.diagram_language}<div><dt>Diagrams</dt><dd>{visualDirection.diagram_language}</dd></div>{/if}
            </dl>
          {:else}<p>Visual direction will appear after narrative reconstruction.</p>{/if}
        {:else if analysisTab === 'review'}
          <p class="ai-vc-panel__note">Rendered-pixel visual findings are advisory and never block export.</p>
          {#if visualFindings.length}
            <ul>{#each visualFindings as finding}<li><strong>{finding.dimension.replaceAll('_', ' ')}</strong> — {finding.issue}</li>{/each}</ul>
          {:else}<p>No rendered visual-quality concerns have been recorded.</p>{/if}
        {:else}
          <p class="ai-vc-panel__note">Verified research sources are shown here for review and are not added to the exported deck.</p>
          {#if sources.length}
            <ul class="source-list">
              {#each sources as source}
                <li>
                  <a href={source.url} target="_blank" rel="noreferrer">{source.publisher ?? source.url}</a>
                  {#if source.topic}<span>{source.topic.replaceAll('_', ' ')}</span>{/if}
                  {#if source.summary}<p>{source.summary}</p>{/if}
                </li>
              {/each}
            </ul>
          {:else}<p>No verified external sources were used. Unsupported external claims are omitted.</p>{/if}
        {/if}
      </div>
    </aside>
  {/if}

  {#if !workspace && fallbackMessage}
    <section class="instant-deck-notice" role="status">
      <strong>Instant Deck is still preparing</strong>
      <p>{fallbackMessage}</p>
      {#if fallbackActionHref}<a href={fallbackActionHref}>{fallbackActionLabel ?? 'View processing'}</a>{/if}
    </section>
  {/if}
</DeckWorkspaceRegistration>

<style>
  .instant-deck-toolbar {
    grid-column: 2 / -1;
    grid-row: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0 0.85rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(7, 11, 22, 0.9);
  }
  .instant-deck-toolbar__status,
  .instant-deck-toolbar__actions { display: flex; align-items: center; gap: .6rem; min-width: 0; }
  .instant-deck-toolbar__status { color: #dbeafe; font-size: .82rem; overflow: hidden; }
  .instant-deck-toolbar__status > span:nth-child(2) { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .instant-deck-toolbar__status > span:first-child { color: #34d399; }
  .instant-deck-toolbar__status > span:first-child.busy { color: #38bdf8; }
  .instant-deck-toolbar button,
  .instant-deck-notice a { min-height: 34px; display: inline-flex; align-items: center; justify-content: center; border: 1px solid rgba(255,255,255,.12); border-radius: 9px; padding: .45rem .8rem; color: #f8fafc; background: rgba(15,23,42,.95); font: inherit; font-weight: 700; text-decoration: none; }
  .instant-deck-toolbar button.primary { border-color: transparent; background: #0284c7; }
  .instant-deck-toolbar button:disabled { cursor: not-allowed; opacity: .58; }
  .instant-deck-notice { position: absolute; z-index: 5; inset: 1rem; display: grid; align-content: center; justify-items: center; gap: .65rem; padding: 2rem; border: 1px solid rgba(255,255,255,.1); border-radius: 16px; background: rgba(7,11,22,.96); text-align: center; }
  .instant-deck-notice p { max-width: 46rem; margin: 0; color: #94a3b8; }
  .ai-vc-panel { position: absolute; z-index: 8; top: 4.25rem; right: 1rem; bottom: 1rem; width: min(30rem, calc(100% - 2rem)); overflow: hidden; display: flex; flex-direction: column; border: 1px solid rgba(148,163,184,.24); border-radius: 14px; background: rgba(7,11,22,.98); box-shadow: 0 24px 80px rgba(0,0,0,.45); color: #e2e8f0; }
  .ai-vc-panel__heading { display: flex; justify-content: space-between; gap: 1rem; padding: 1rem; border-bottom: 1px solid rgba(148,163,184,.16); }
  .ai-vc-panel__heading p, .ai-vc-panel__content p { margin: .35rem 0 0; color: #94a3b8; font-size: .82rem; line-height: 1.5; }
  .ai-vc-panel__heading button { align-self: flex-start; border: 0; background: transparent; color: #cbd5e1; font-size: 1.35rem; cursor: pointer; }
  .ai-vc-tabs { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); border-bottom: 1px solid rgba(148,163,184,.16); }
  .ai-vc-tabs button { padding: .75rem .45rem; border: 0; border-bottom: 2px solid transparent; background: transparent; color: #94a3b8; font: inherit; font-size: .72rem; font-weight: 700; cursor: pointer; }
  .ai-vc-tabs button.active { border-bottom-color: #38bdf8; color: #f8fafc; }
  .ai-vc-panel__content { overflow: auto; padding: 1rem; }
  .ai-vc-panel__content h3 { margin: 0 0 1rem; color: #f8fafc; font-size: 1rem; line-height: 1.4; }
  .visual-direction-list { display: grid; gap: .8rem; margin: 0; }
  .visual-direction-list div { display: grid; gap: .2rem; padding-bottom: .8rem; border-bottom: 1px solid rgba(148,163,184,.12); }
  .visual-direction-list dt { color: #7dd3fc; font-size: .7rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  .visual-direction-list dd { margin: 0; color: #dbeafe; font-size: .84rem; line-height: 1.5; }
  .ai-vc-panel__content ul { margin: 0; padding-left: 1.15rem; display: grid; gap: .75rem; }
  .ai-vc-panel__content li { color: #dbeafe; font-size: .85rem; line-height: 1.45; }
  .source-list { list-style: none; padding-left: 0 !important; }
  .source-list li { padding: .8rem; border: 1px solid rgba(148,163,184,.14); border-radius: 10px; background: rgba(15,23,42,.7); }
  .source-list a { color: #7dd3fc; font-weight: 700; overflow-wrap: anywhere; }
  .source-list span { display: block; margin-top: .25rem; color: #94a3b8; font-size: .72rem; text-transform: capitalize; }
  .ai-vc-panel__note { margin-top: 0 !important; margin-bottom: 1rem !important; }
  @media (max-width: 760px) {
    .instant-deck-toolbar { align-items: stretch; flex-direction: column; padding: .55rem .7rem; }
    .instant-deck-toolbar__status { flex-wrap: wrap; }
    .instant-deck-toolbar__actions button { flex: 1; }
    .ai-vc-tabs { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }
</style>
