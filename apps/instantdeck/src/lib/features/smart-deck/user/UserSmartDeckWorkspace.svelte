<!-- CANONICAL USER SMART DECK WORKSPACE: mounted by /decks/[deckId]/smart-deck. -->
<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import type { DeckGraph } from '$types/domain';
  import type { SmartDeckWorkspacePayload } from '$lib/api/smartDeckWorkspace';
  import type { RenderSchema } from '$lib/api/smartDeckWorkspace';
  import type { DeckShellProperties, DeckWorkspacePreferences, DeckShellToolId } from '$lib/contracts';
  import {
    SMART_DECK_APP_RAIL_ITEMS,
    SMART_DECK_AUDIENCE_OPTIONS,
    SMART_DECK_DECK_TYPE_OPTIONS,
    SMART_DECK_GOAL_OPTIONS,
    SMART_DECK_QUICK_ACTIONS
  } from './smartDeckUserStore';
  import {
    applyUserSmartDeckVersion,
    createUserSmartDeckSlide,
    discardUserSmartDeckVersion,
    generateSmartDeckVersion,
    generateUserElementVariation,
    loadUserGeneratedSlideCode,
    updateUserGeneratedSlideTypography,
    persistUserSmartDeckPreferences,
    persistUserSmartDeckSelection,
    refreshUserSmartDeckWorkspace,
    resolveSmartDeckVersionId,
    retryFailedSmartDeckSlides,
    toInstantDeckGeneratedSlideRail,
    toSmartDeckUserViewModel
  } from './smartDeckUserApi';
  import DeckWorkspaceRegistration from '$lib/components/decks/DeckWorkspaceRegistration.svelte';
  import SmartDeckFilmstrip from './SmartDeckFilmstrip.svelte';
  import SmartDeckTopBar from './SmartDeckTopBar.svelte';
  import SmartDeckAITools from '$lib/components/ai-tool-sidebar/smart-deck/SmartDeckAITools.svelte';
  import InstantDeckAITools from '$lib/components/ai-tool-sidebar/instant-deck/InstantDeckAITools.svelte';
  import InstantDeckResultActions from '$lib/components/ai-tool-sidebar/instant-deck/InstantDeckResultActions.svelte';
  import SmartDeckDataPanel from './SmartDeckDataPanel.svelte';
  import SmartDeckBrandPanel from './SmartDeckBrandPanel.svelte';
  import SmartDeckTextPanel from './SmartDeckTextPanel.svelte';
  import SmartDeckMediaPanel from './SmartDeckMediaPanel.svelte';
  import SmartDeckSettingsPanel from './SmartDeckSettingsPanel.svelte';
  import SmartDeckElementsPanel from './SmartDeckElementsPanel.svelte';
  import SmartDeckCreateSlideModal from './SmartDeckCreateSlideModal.svelte';
  import WorkspaceAiProviderModal from '$lib/components/WorkspaceAiProviderModal.svelte';
  import type {
    SmartDeckAIGenerationState,
    SmartDeckCanvasState,
    SmartDeckEditorMode,
    SmartDeckInspectorTab,
    SmartDeckUserSaveState
  } from './smartDeckUserTypes';
  import type { SmartDeckDeckType, SmartDeckSubject } from '$lib/types/smart-deck-subjects';
  import DeckMapPanel from './DeckMapPanel.svelte';
  import { buildSmartDeckDesignContext } from '$lib/components/instant-deck/designFallback';
  import type { BrandProfile } from '$lib/types/deckService-brand';
  import { createSlideRedesignRun, createSmartDeckAssistantRun, mintInstantHtmlFullDeckCapability, waitForSlideRedesignRun, waitForWorkflowJobCompletion } from '$lib/api/smartDeckWorkspace';
  import { createProvisionalHtmlDeckExport } from '$lib/api/deckService/workflow.client';
  import { buildSmartEditHandoffUrl, resolveExactSmartEditHandoffIdentity } from './smartEditHandoffIdentity.js';
  import { createGeneratedCodeRequestGuard, createLatestSelectionPersistence, describeInstantVersionCompletion, generationIdentityStillCurrent, mergeSelectionIntoLiveWorkspace, reconcileCompletedInstantGenerationReadModel, resolveExactGeneratedHandoff, resolveLatestCompletedInstantGeneration, resolvePersistedGeneratedSelection, resolveRecoveredWorkspaceSelection, sameOrderedSourceSlideIds, selectionResponseMatches } from './generatedSlideIdentity.js';
  import { openInstantHtmlPrintPlaceholder } from '$lib/config/instantHtmlRendererOrigin.js';

  interface Props {
    workspaceLabel?: string;
    currentDeckLabel?: string;
    graph: DeckGraph;
    initialWorkspace: SmartDeckWorkspacePayload | null;
    initialProperties?: DeckShellProperties | null;
    initialWorkspacePreferences?: DeckWorkspacePreferences | null;
    initialSelectedSlideId?: string | null;
    initialSelectedVersionId?: string | null;
    initialSelectedGeneratedSlideId?: string | null;
    instantMode?: boolean;
    fallbackMessage?: string | null;
    fallbackActionHref?: string | null;
    fallbackActionLabel?: string | null;
  }

  let {
    workspaceLabel = 'Deck workspace',
    currentDeckLabel = '',
    graph,
    initialWorkspace,
    initialProperties = null,
    initialWorkspacePreferences = null,
    initialSelectedSlideId = null,
    initialSelectedVersionId = null,
    initialSelectedGeneratedSlideId = null,
    instantMode = false,
    fallbackMessage = null,
    fallbackActionHref = null,
    fallbackActionLabel = null
  }: Props = $props();

  const INSTANT_DECK_PROMPT = 'Regenerate the complete deck with a stronger narrative, clearer evidence, and a consistent investor-ready visual hierarchy.';
  const DESIGN_BACKGROUND_OPTIONS = [
    {
      key: 'brand_spotlight',
      label: 'Brand Spotlight',
      summary: 'Brand-faithful layered background with stronger contrast and premium focus.',
      prompt: 'Use vision to redesign the background of the current slide with a brand-faithful spotlight treatment. Reuse the strongest source-slide visual cues, preserve supported content, increase contrast, and return a reviewable visual version.'
    },
    {
      key: 'editorial_depth',
      label: 'Editorial Depth',
      summary: 'Editorial image-led background with subtle depth and clear reading lanes.',
      prompt: 'Use vision to redesign the background of the current slide with an editorial, image-led composition. Keep the supported content readable, preserve source-grounded meaning, and return a reviewable visual version.'
    },
    {
      key: 'executive_minimal',
      label: 'Executive Minimal',
      summary: 'Minimal executive backdrop with fewer distractions and cleaner hierarchy.',
      prompt: 'Use vision to redesign the background of the current slide into an executive minimal backdrop. Reduce visual noise, keep all supported content readable, and return a reviewable visual version.'
    },
    {
      key: 'data_forward',
      label: 'Data Forward',
      summary: 'Subtle gradient and structural texture suited to metrics and charts.',
      prompt: 'Use vision to redesign the background of the current slide with a data-forward treatment using subtle structure, gradients, and brand cues. Preserve supported content and return a reviewable visual version.'
    }
  ] as const;

  // DISABLED: Previous explicit prop-capture locals preserved for traceability.
  // Reason: The initializer object below avoids Svelte 5 initial-value warnings with less duplicated state.
  // const _iw = initialWorkspace;
  // const _g = graph;

  function initialUserSmartDeckState() {
    const selectedElementId = initialWorkspace?.preferences.selectedElementId ?? null;
    const selectedSlideId = initialSelectedSlideId ?? initialWorkspace?.preferences.activeSourceSlideId ?? initialWorkspace?.sourceSlides[0]?.id ?? graph.slides[0]?.id ?? null;
    return {
      workspace: initialWorkspace,
      selectedSlideId,
      selectedVersionId: resolveSmartDeckVersionId({ workspace: initialWorkspace, requestedVersionId: initialSelectedVersionId, selectedSlideId, generatedOnly: instantMode }),
      selectedGeneratedSlideId: instantMode
        ? initialSelectedGeneratedSlideId ?? initialWorkspace?.preferences.activeGeneratedSlideId ?? null
        : null,
      selectedElementId,
      audience: initialWorkspace?.preferences.audience ?? initialWorkspace?.deck.audience ?? graph.deck.audience ?? SMART_DECK_AUDIENCE_OPTIONS[0],
      deckType: initialWorkspace?.preferences.deckType ?? 'startup_pitch',
      goal: initialWorkspace?.preferences.selectedSubject ?? 'unknown',
      prompt: instantMode ? INSTANT_DECK_PROMPT : '',
      // Legacy `research` preferences predate the consolidated Due Diligence
      // workspace. Normalize them before first render so Smart Deck always has
      // a visible tool surface and its permanent inspector.
      // Instant Deck is an entry mode, not a separate route. It must always
      // open on the slide visualizer without overwriting the user's persisted
      // normal Smart Deck tool preference.
      activeTool: instantMode || initialWorkspacePreferences?.activeTool === 'research' || initialWorkspacePreferences?.activeTool === 'design'
        ? 'slides'
        : (initialWorkspacePreferences?.activeTool ?? 'slides')
    };
  }

  function asRenderableSchema(value: Record<string, unknown> | null | undefined): RenderSchema | null {
    return value && Array.isArray(value.elements)
      ? value as unknown as RenderSchema
      : null;
  }

  function resolveActiveGeneration(currentWorkspace: SmartDeckWorkspacePayload | null) {
    const generationJobs = currentWorkspace?.generationJobs ?? [];
    const activeJob = generationJobs.find((job) => ['queued', 'running'].includes(job.status)) ?? null;
    // generationJobs is the canonical active-work owner. Workspace-level flags
    // are only a conservative read-model lag hint when that job is not visible.
    // Once the canonical job collection contains a terminal generation, a
    // stale workspace-level `generating` flag must not lock Regenerate
    // forever. The lag hint is only authoritative before any job is visible.
    const hasLaggingActiveHint = !activeJob && generationJobs.length === 0 && Boolean(currentWorkspace && (
      ['queued', 'running'].includes(currentWorkspace.generatedWorkspaceStatus ?? '') ||
      currentWorkspace.workspace.status === 'generating'
    ));
    return { activeJob, hasLaggingActiveHint };
  }

  function isAbortError(error: unknown) {
    return error instanceof DOMException && error.name === 'AbortError';
  }

  const initialState = initialUserSmartDeckState();
  const MAX_INSTANT_SOURCE_PAGES = 25;

  let workspace = $state<SmartDeckWorkspacePayload | null>(initialState.workspace);
  let selectedSlideId = $state<string | null>(initialState.selectedSlideId);
  let selectedVersionId = $state<string | null>(initialState.selectedVersionId);
  let selectedInstantReviewGeneratedSlideId = $state<string | null>(initialState.selectedGeneratedSlideId);
  let mode = $state<SmartDeckEditorMode>('edit');
  let inspectorTab = $state<SmartDeckInspectorTab>('ask_ai');
  let saveState = $state<SmartDeckUserSaveState>('saved');
  let generationState = $state<SmartDeckAIGenerationState>('idle');
  let generationMessage = $state('');
  let instantStatusUnresolved = $state(false);
  const hasActiveInstantGeneration = $derived(Boolean(
    instantMode && (
      resolveActiveGeneration(workspace).activeJob ||
      resolveActiveGeneration(workspace).hasLaggingActiveHint
    )
  ));
  const needsInstantStatusCheck = $derived(Boolean(instantMode && (
    instantStatusUnresolved || hasActiveInstantGeneration
  )));
  let selectedElementId = $state<string | null>(initialState.selectedElementId);
  let activeTool = $state<DeckShellToolId>(initialState.activeTool);
  let audience = $state<string | null>(initialState.audience);
  let deckType = $state<SmartDeckDeckType>(initialState.deckType);
  let goal = $state<SmartDeckSubject>(initialState.goal);
  let prompt = $state(initialState.prompt);
  let aiTaskLabel = $state('Whole deck');
  let addingSlide = $state(false);
  let createSlideModalOpen = $state(false);
  let createSlideRole = $state('appendix');
  let createSlideTitle = $state('');
  let createSlideNarrative = $state('');
  let createSlideError = $state('');
  let providerModalOpen = $state(false);
  let typographySaving = $state(false);
  let typographyMessage = $state('');
  let elementInstruction = $state('Fit this element cleanly inside its current bounds, improve hierarchy, and preserve source-grounded meaning.');
  const getInitialCompactSlideRailOpen = () => initialWorkspace?.preferences.slideRailOpen ?? true;
  let compactSlideRailOpen = $state(getInitialCompactSlideRailOpen());
  let conversationState = $state<'idle' | 'sending' | 'error'>('idle');
  let conversationMessage = $state('');
  let latestAssistantRun = $state<import('$lib/api/smartDeckWorkspace').SmartDeckAssistantRunResponse | null>(null);
  let saveInsightState = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
  let saveInsightMessage = $state('');
  let workspaceRecoveryPromise: Promise<SmartDeckWorkspacePayload | null> | null = null;
  let workspaceRecoveryController: AbortController | null = null;
  let workspaceRecoveryError = $state('');
  // Reconciliation and submission share one reactive mutex. This must be
  // visible to every control: SSR can contain a terminal workspace snapshot
  // while the first browser refresh discovers an active durable operation.
  // During that gap Regenerate must not look enabled and then return before
  // transport without telling the user why.
  let instantCommandInFlight = $state(false);
  let instantPollingController: AbortController | null = null;
  let instantGenerationIntentKey: string | null = null;
  let instantCompletedGenerationJobId: string | null = null;
  let designState = $state<SmartDeckAIGenerationState>('idle');
  let designMessage = $state('');
  let designBusyOptionKey = $state<string | null>(null);
  let htmlExportState = $state<'idle' | 'preparing' | 'ready' | 'error'>('idle');
  let htmlExportMessage = $state('');
  let generatedDesignOptions = $state<Array<{ slideId: string; key: string; label: string; versionId: string }>>([]);
  const generatedCodeRequestGuard = createGeneratedCodeRequestGuard();
  const selectionPersistence = createLatestSelectionPersistence();

  type SelectionInput = Parameters<typeof persistUserSmartDeckSelection>[1];

  async function persistLatestSelection(input: SelectionInput, applyLatest: () => void) {
    if (!workspace) return false;
    saveState = 'saving';
    const deckId = workspace.deck.id;
    const result = await selectionPersistence.submit(async () => {
      const response = await persistUserSmartDeckSelection(deckId, input);
      if (!selectionResponseMatches(
        response as unknown as Record<string, unknown>,
        input as unknown as Record<string, unknown>
      )) {
        throw new Error('Saved selection did not match the requested version and slide.');
      }
      return response;
    });
    if (result.status === 'superseded') return false;
    if (result.status === 'failed') {
      saveState = 'unsaved';
      generationState = 'error';
      generationMessage = result.error instanceof Error ? result.error.message : 'The selected version and slide could not be saved.';
      return false;
    }
    const persistedSelection = result.response;
    if (!persistedSelection) {
      saveState = 'unsaved';
      generationState = 'error';
      generationMessage = 'The selected version and slide could not be confirmed.';
      return false;
    }
    const nextWorkspace = mergeSelectionIntoLiveWorkspace(
      workspace as unknown as Record<string, unknown>,
      { deckId, designVersionId: persistedSelection.activeDesignVersionId },
      persistedSelection as unknown as Record<string, unknown>
    ) as SmartDeckWorkspacePayload | null;
    if (!nextWorkspace) {
      saveState = 'unsaved';
      generationState = 'error';
      generationMessage = 'The saved selection no longer belongs to the current deck and version.';
      return false;
    }
    workspace = nextWorkspace;
    applyLatest();
    saveState = 'saved';
    return true;
  }

  const recoveryBaseline = {
    audience: initialState.audience,
    deckType: initialState.deckType,
    goal: initialState.goal
  };

  function applyRecoveredWorkspace(nextWorkspace: SmartDeckWorkspacePayload) {
    workspace = nextWorkspace;
    const recoveredVersionId = resolveSmartDeckVersionId({ workspace: nextWorkspace, requestedVersionId: initialSelectedVersionId ?? nextWorkspace.preferences.activeDesignVersionId, selectedSlideId: nextWorkspace.preferences.activeSourceSlideId ?? null, generatedOnly: instantMode });
    const recoveredVersion = nextWorkspace.designVersions.find((version) => version.id === recoveredVersionId) ?? null;
    const recoveredSelection = resolveRecoveredWorkspaceSelection(
      nextWorkspace.designVersions,
      recoveredVersion?.id ?? null,
      nextWorkspace.preferences.activeGeneratedSlideId ?? nextWorkspace.activeGeneratedSlideId,
      nextWorkspace.sourceSlides.map((slide) => slide.id),
      nextWorkspace.preferences.activeSourceSlideId
    );
    if (instantMode && recoveredSelection.generatedSlideId) {
      selectedInstantReviewGeneratedSlideId = recoveredSelection.generatedSlideId;
      selectedSlideId = recoveredSelection.sourceSlideId;
    } else {
      selectedSlideId = selectedSlideId ?? nextWorkspace.preferences.activeSourceSlideId ?? nextWorkspace.sourceSlides[0]?.id ?? graph.slides[0]?.id ?? null;
    }
    selectedVersionId = instantMode ? recoveredSelection.versionId ?? recoveredVersionId : selectedVersionId ?? recoveredVersionId;
    selectedElementId = selectedElementId ?? nextWorkspace.preferences.selectedElementId ?? null;
    // Replace degraded graph/default context with persisted workspace context,
    // but do not overwrite a choice the user made while recovery was pending.
    if (audience === recoveryBaseline.audience) {
      audience = nextWorkspace.preferences.audience ?? nextWorkspace.deck.audience ?? audience;
    }
    if (deckType === recoveryBaseline.deckType) {
      deckType = nextWorkspace.preferences.deckType ?? deckType;
    }
    if (goal === recoveryBaseline.goal) {
      goal = nextWorkspace.preferences.selectedSubject ?? goal;
    }
    workspaceRecoveryError = '';
    return nextWorkspace;
  }

  async function recoverSmartDeckWorkspace() {
    if (workspace) return workspace;
    if (!workspaceRecoveryPromise) {
      // SSR intentionally times out slow workspace reads so the route can mount
      // in degraded mode. Retry that same canonical proxy once in the browser;
      // generation and the background recovery share this promise so they do
      // not create a request storm while the backend finishes its first read.
      const controller = new AbortController();
      workspaceRecoveryController = controller;
      workspaceRecoveryPromise = refreshUserSmartDeckWorkspace(graph.deck.id, controller.signal)
        .then(applyRecoveredWorkspace)
        .catch((error) => {
          if (!controller.signal.aborted) {
            workspaceRecoveryError = error instanceof Error ? error.message : 'Smart Deck workspace could not be loaded.';
          }
          return null;
        })
        .finally(() => {
          workspaceRecoveryPromise = null;
          if (workspaceRecoveryController === controller) workspaceRecoveryController = null;
        });
    }
    return workspaceRecoveryPromise;
  }

  onMount(() => {
    if (instantMode) void reconcileInstantDeckStatus();
    else if (!workspace) void recoverSmartDeckWorkspace();
    return () => {
      workspaceRecoveryController?.abort();
      instantPollingController?.abort();
    };
  });

  const CREATE_SLIDE_ROLE_OPTIONS = [
    {
      value: 'problem',
      label: 'Problem',
      title: 'Problem',
      brief: 'Explain the painful operational or strategic problem, why it matters now, and what proof should make the urgency credible.'
    },
    {
      value: 'solution',
      label: 'Solution',
      title: 'Solution',
      brief: 'Describe the product or workflow solution, how it works, and which visual structure should make the value proposition obvious.'
    },
    {
      value: 'traction',
      label: 'Traction',
      title: 'Traction',
      brief: 'Show traction with the strongest available metric, timeframe, comparison baseline, and why that momentum matters for investors.'
    },
    {
      value: 'team',
      label: 'Team',
      title: 'Team',
      brief: 'Present the founder, executives, advisors, and board members with the experience that best proves this team can execute.'
    },
    {
      value: 'appendix',
      label: 'Appendix / Board',
      title: 'Board update',
      brief: 'Create a clear supporting slide for board, diligence, or appendix review with concise proof and a clean executive layout.'
    }
  ] as const;

  let canvasState = $state<SmartDeckCanvasState>({
    renderSchema: null,
    designTokens: null,
    validationStatus: null,
    selectedElementId: initialState.selectedElementId,
  });

  const viewModel = $derived(
    toSmartDeckUserViewModel({
      workspace,
      graph,
      selectedSlideId,
      selectedVersionId,
      selectedElementId,
      generatedOnly: instantMode
    })
  );

  const selectedSlide = $derived(viewModel.selectedSlide);
  const selectedSourceSlideIds = $derived.by(() => {
    const requested = workspace?.preferences.selectedSourceSlideIds ?? [];
    const available = new Set(viewModel.slides.map((slide) => slide.id));
    const normalized = requested.filter((slideId) => available.has(slideId));
    return normalized.length > 0 ? normalized : viewModel.slides.map((slide) => slide.id);
  });
  const selectedVersion = $derived(viewModel.selectedVersion);
  const instantDeckGeneratedSlides = $derived(
    toInstantDeckGeneratedSlideRail(selectedVersion?.designVersion ?? null, workspace?.sourceSlides ?? [])
  );
  const railSlides = $derived(instantMode ? instantDeckGeneratedSlides : viewModel.slides);
  const DeckAITools = $derived(instantMode ? InstantDeckAITools : SmartDeckAITools);
  const appRailItems = $derived(
    instantMode ? SMART_DECK_APP_RAIL_ITEMS.filter((item) => item.key === 'slides') : SMART_DECK_APP_RAIL_ITEMS.filter((item) => item.key !== 'design')
  );
  const focusedGeneration = $derived(viewModel.generatedVersions.length === 0);
  const selectedInstantCanvasIdentity = $derived.by(() => {
    if (!instantMode) return null;
    if (!selectedVersion || selectedVersion.id !== selectedVersionId) return null;
    const handoff = resolveExactGeneratedHandoff(
      selectedVersion.designVersion.generatedSlides,
      selectedInstantReviewGeneratedSlideId,
      selectedSlide?.id ?? null,
      (workspace?.sourceSlides ?? []).map((slide) => slide.id)
    );
    return handoff.generatedSlide && handoff.sourceSlideId
      ? { designVersionId: selectedVersion.id, generatedSlideId: handoff.generatedSlide.id, sourceSlideId: handoff.sourceSlideId }
      : null;
  });
  const exactSelectedInstantGeneratedSlide = $derived(selectedInstantCanvasIdentity && selectedVersion && selectedVersion.id === selectedInstantCanvasIdentity.designVersionId ? selectedVersion.designVersion.generatedSlides.find((slide) => slide.id === selectedInstantCanvasIdentity.generatedSlideId) ?? null : null);
  const selectedGeneratedSlide = $derived.by(() => {
    if (instantMode) {
      if (selectedVersion?.designVersion.renderMode === 'html_compiled.v1') {
        return selectedVersion.designVersion.generatedSlides.find((slide) => slide.id === selectedInstantReviewGeneratedSlideId)
          ?? null;
      }
      return exactSelectedInstantGeneratedSlide;
    }
    const selectedSourceSlideId = selectedSlide?.sourceSlideId ?? selectedSlide?.id ?? null;
    if (!selectedVersion || !selectedSourceSlideId) return null;
    const matches = selectedVersion.designVersion.generatedSlides.filter((slide) => slide.sourceSlideId === selectedSourceSlideId || (slide.sourceSlideIds ?? []).includes(selectedSourceSlideId));
    return matches.length === 1 ? matches[0] : null;
  });
  const selectedCanvasIdentity = $derived.by(() => {
    if (instantMode) return selectedInstantCanvasIdentity;
    const sourceSlideId = selectedSlide?.sourceSlideId ?? selectedSlide?.id ?? null;
    if (!selectedVersion || selectedVersion.id !== selectedVersionId || !sourceSlideId || !selectedGeneratedSlide) return null;
    return {
      designVersionId: selectedVersion.id,
      generatedSlideId: selectedGeneratedSlide.id,
      sourceSlideId
    };
  });
  // The main Instant visualizer consumes the same exact identity object as the
  // selected shared-rail item, so version/artifact/section selection cannot drift.
  const selectedHtmlSlide = $derived(
    instantDeckGeneratedSlides.find((slide) => slide.id === selectedGeneratedSlide?.id)?.htmlSlide ?? null
  );
  const fullDeckHtmlDocument = $derived(
    instantMode ? instantDeckGeneratedSlides.find((slide) => slide.htmlSlide)?.htmlSlide ?? null : selectedHtmlSlide
  );
  const activeGeneratedSlideId = $derived(instantMode ? selectedGeneratedSlide?.id ?? null : selectedGeneratedSlide?.id ?? selectedSlide?.generatedSlideId ?? null);
  const selectedCanvasSlide = $derived(instantMode && selectedGeneratedSlide ? { title: selectedGeneratedSlide.title ?? selectedSlide?.title ?? 'Generated slide', slideNumber: selectedGeneratedSlide.slideNumber ?? selectedSlide?.number ?? 1, previewImageUrl: selectedGeneratedSlide.previewImageUrl ?? selectedGeneratedSlide.preview_image_url ?? selectedGeneratedSlide.previewUrl ?? selectedGeneratedSlide.preview_url ?? selectedGeneratedSlide.thumbnailUrl ?? selectedGeneratedSlide.thumbnail_url ?? null } : instantMode ? null : selectedSlide);
  const selectedRenderElementId = $derived(
    selectedSlide?.persistedElements.find((element) => element.id === selectedElementId)?.elementKey ??
    selectedSlide?.persistedElements.find((element) => element.elementKey === selectedElementId)?.elementKey ??
    selectedElementId
  );
  const llmArtifacts = $derived(
    ((((graph as DeckGraph & { llmArtifacts?: Array<Record<string, unknown>>; llm_artifacts?: Array<Record<string, unknown>> }).llmArtifacts ??
      (graph as DeckGraph & { llmArtifacts?: Array<Record<string, unknown>>; llm_artifacts?: Array<Record<string, unknown>> }).llm_artifacts) ??
      []) as Array<Record<string, unknown>>)
  );
  const failedGeneration = $derived(
    workspace?.generationJobs.find((job) => job.coverageComplete === false && (job.failedSlideIds?.length ?? 0) > 0) ?? null
  );
  const selectedVersionJob = $derived(
    selectedVersion?.designVersion.generationJobId
      ? workspace?.generationJobs.find((job) => job.id === selectedVersion.designVersion.generationJobId) ?? null
      : null
  );
  const canApplySelectedVersion = $derived(
    Boolean(selectedVersionId) && selectedVersionJob?.coverageComplete !== false
  );
  const slideGeneratedDesignOptions = $derived(
    selectedSlide
      ? generatedDesignOptions
          .filter((option) => option.slideId === selectedSlide.id)
          .map(({ key, label, versionId }) => ({ key, label, versionId }))
      : []
  );

  $effect(() => {
    canvasState.selectedElementId = selectedRenderElementId;
  });

  $effect(() => {
    const isLatestGeneratedCodeRequest = generatedCodeRequestGuard.begin();
    const generatedSlideId = activeGeneratedSlideId;
    const embeddedRenderSchema = asRenderableSchema(selectedGeneratedSlide?.renderSchema ?? null);
    const embeddedDesignTokens = selectedGeneratedSlide?.designTokens ?? null;
    const embeddedValidationStatus = selectedGeneratedSlide?.validationStatus ?? null;
    if (!workspace?.deck.id || !generatedSlideId) {
      canvasState.renderSchema = null;
      canvasState.designTokens = null;
      canvasState.validationStatus = null;
      return;
    }
    if (selectedGeneratedSlide?.renderMode === 'html_compiled.v1') {
      canvasState.renderSchema = null;
      canvasState.designTokens = selectedGeneratedSlide.designTokens ?? null;
      canvasState.validationStatus = selectedGeneratedSlide.validationStatus ?? null;
      return;
    }

    canvasState.renderSchema = embeddedRenderSchema;
    canvasState.designTokens = embeddedDesignTokens;
    canvasState.validationStatus = embeddedValidationStatus;

    void loadUserGeneratedSlideCode(workspace.deck.id, generatedSlideId)
      .then((code) => {
        if (!isLatestGeneratedCodeRequest() || generatedSlideId !== activeGeneratedSlideId) return;
        canvasState.renderSchema = code.renderSchema;
        canvasState.designTokens = code.designTokens ?? null;
        canvasState.validationStatus = code.validationStatus;
      })
      .catch(() => {
        if (!isLatestGeneratedCodeRequest() || generatedSlideId !== activeGeneratedSlideId) return;
        canvasState.renderSchema = embeddedRenderSchema;
        canvasState.designTokens = embeddedDesignTokens;
        canvasState.validationStatus = embeddedValidationStatus;
      });
  });

  async function persistPreferences() {
    if (!workspace) return;
    saveState = 'saving';
    try {
      await persistUserSmartDeckPreferences(workspace.deck.id, {
        audience,
        deckType,
        selectedSubject: goal
      });
      saveState = 'saved';
    } catch {
      saveState = 'unsaved';
    }
  }

  async function selectSlide(slideId: string) {
    if (selectedSlideId === slideId) return true;
    if (!workspace) return false;
    const nextIdentity = instantMode
      ? null
      : resolveExactSmartEditHandoffIdentity({
          designVersions: workspace.designVersions,
          selectedVersionId,
          sourceSlideId: slideId
        });
    const nextSlide = toSmartDeckUserViewModel({ workspace, graph, selectedSlideId: slideId, selectedVersionId }).selectedSlide;
    return persistLatestSelection({
      activeDesignVersionId: selectedVersionId,
      activeSourceSlideId: slideId,
      activeGeneratedSlideId: instantMode ? nextSlide?.generatedSlideId ?? null : nextIdentity?.generatedSlideId ?? null,
      selectedElementId: null,
      selectedSourceSlideIds
    }, () => {
      selectedSlideId = slideId;
      selectedElementId = null;
      inspectorTab = mode === 'edit' ? 'map' : inspectorTab;
    });
  }

  async function toggleSourceSlideSelection(slideId: string) {
    if (!workspace) return;
    const nextSelected = selectedSourceSlideIds.includes(slideId)
      ? selectedSourceSlideIds.filter((id) => id !== slideId)
      : [...selectedSourceSlideIds, slideId];
    if (nextSelected.length === 0) return;

    await persistLatestSelection({
        activeSourceSlideId: selectedSlideId,
        activeGeneratedSlideId: viewModel.selectedSlide?.generatedSlideId ?? null,
        selectedElementId,
        selectedSourceSlideIds: nextSelected
      }, () => {});
  }

  async function openSmartEdit(slideId: string) {
    if (selectedSlideId !== slideId) {
      if (!(await selectSlide(slideId))) return;
    }
    if (instantMode) {
      const requestedGeneratedSlideId = selectedCanvasIdentity?.sourceSlideId === slideId && selectedCanvasIdentity.designVersionId === selectedVersionId
        ? selectedCanvasIdentity.generatedSlideId
        : null;
      const identity = resolveExactSmartEditHandoffIdentity({ designVersions: workspace?.designVersions ?? [], selectedVersionId, sourceSlideId: slideId, requestedGeneratedSlideId });
      if (!identity || (selectedSlide?.id === slideId && (!selectedCanvasIdentity || identity.designVersionId !== selectedCanvasIdentity.designVersionId || identity.generatedSlideId !== selectedCanvasIdentity.generatedSlideId))) return;
      await goto(buildSmartEditHandoffUrl(viewModel.deckId, identity, { origin: 'instant-deck' }));
      return;
    } else {
      const handoffVersionId = resolveSmartDeckVersionId({ workspace, requestedVersionId: selectedVersionId, selectedSlideId: slideId });
      const identity = resolveExactSmartEditHandoffIdentity({
        designVersions: workspace?.designVersions ?? [],
        selectedVersionId: handoffVersionId,
        sourceSlideId: slideId
      });
      if (!identity) return;
      await goto(buildSmartEditHandoffUrl(viewModel.deckId, identity));
    }
  }

  async function openInstantGeneratedSlide(generatedSlideId: string) {
    if (!instantMode || !selectedVersionId || selectedVersion?.id !== selectedVersionId) return;
    const generatedSlide = selectedVersion.designVersion.generatedSlides.find((slide) => slide.id === generatedSlideId);
    const sourceSlideId = generatedSlide?.sourceSlideId ?? null;
    if (!generatedSlide) return;

    if (selectedVersion.designVersion.renderMode === 'html_compiled.v1') {
      await persistLatestSelection({
        activeDesignVersionId: selectedVersionId,
        activeSourceSlideId: sourceSlideId,
        activeGeneratedSlideId: generatedSlide.id,
        selectedElementId: null
      }, () => {
        selectedInstantReviewGeneratedSlideId = generatedSlide.id;
        selectedSlideId = sourceSlideId;
        selectedElementId = null;
      });
      return;
    }

    if (!sourceSlideId) return;

    selectedSlideId = sourceSlideId;
    selectedElementId = null;
    const params = new URLSearchParams({
      designVersionId: selectedVersionId,
      generatedSlideId: generatedSlide.id,
      slide: sourceSlideId,
      origin: 'instant-deck'
    });
    await goto(`/decks/${viewModel.deckId}/smart-edit?${params.toString()}`);
  }

  function reviewAdjacentInstantSlide(direction: -1 | 1) {
    if (!instantMode || instantDeckGeneratedSlides.length < 2) return;
    const index = instantDeckGeneratedSlides.findIndex((slide) => slide.id === activeGeneratedSlideId);
    if (index < 0) return;
    const next = instantDeckGeneratedSlides[index + direction];
    if (next) void openInstantGeneratedSlide(next.id);
  }

  async function selectVersion(versionId: string) {
    if (!instantMode) {
      selectedVersionId = versionId;
      generationState = 'idle';
      generationMessage = '';
      mode = versionId === workspace?.designVersions.find((version) => version.isActive)?.id ? 'edit' : 'preview';
      return;
    }
    if (!workspace) return;
    const nextVersion = workspace.designVersions.find((version) => version.id === versionId) ?? null;
    if (!nextVersion) {
      saveState = 'unsaved';
      generationState = 'error';
      generationMessage = 'The selected design version is no longer available.';
      return;
    }
    let nextGeneratedSlideId: string | null = null;
    let nextSourceSlideId = selectedSlideId;
    const persistedSelection = resolvePersistedGeneratedSelection(
      nextVersion.generatedSlides,
      workspace.preferences.activeGeneratedSlideId ?? workspace.activeGeneratedSlideId
    ).generatedSlide;
    const requestedSourceId = nextSourceSlideId;
    const sourceSelection = requestedSourceId
      ? nextVersion.generatedSlides.filter((slide) => slide.sourceSlideId === requestedSourceId || (slide.sourceSlideIds ?? []).includes(requestedSourceId))
      : [];
    const nextSelection = persistedSelection ?? (sourceSelection.length === 1 ? sourceSelection[0] : null) ?? nextVersion.generatedSlides[0] ?? null;
    nextGeneratedSlideId = nextSelection?.id ?? null;
    nextSourceSlideId = nextSelection?.sourceSlideId ?? nextSelection?.sourceSlideIds?.[0] ?? null;
    await persistLatestSelection({
      activeDesignVersionId: versionId,
      activeSourceSlideId: nextSourceSlideId,
      activeGeneratedSlideId: nextGeneratedSlideId,
      selectedElementId: null
    }, () => {
      selectedVersionId = versionId;
      selectedInstantReviewGeneratedSlideId = nextGeneratedSlideId;
      selectedSlideId = nextSourceSlideId;
      selectedElementId = null;
      generationState = 'idle';
      generationMessage = '';
      mode = versionId === workspace?.designVersions.find((version) => version.isActive)?.id ? 'edit' : 'preview';
    });
  }

  function openAi() {
    inspectorTab = 'ask_ai';
  }

  function selectAiTask(task: 'background' | 'slide_content' | 'whole_deck') {
    const tasks = {
      background: {
        label: 'Background · current slide · vision',
        prompt: 'Use vision to redesign the background of the current slide. Preserve all supported content, improve contrast and hierarchy, and return a reviewable visual version.'
      },
      slide_content: {
        label: 'Content · current slide · LLM',
        prompt: 'Redesign the current slide content with concise, source-grounded investor logic while preserving supported facts and returning a reviewable slide version.'
      },
      whole_deck: {
        label: 'Whole deck · LLM',
        prompt: INSTANT_DECK_PROMPT
      }
    } as const;
    const selectedTask = tasks[task];
    aiTaskLabel = selectedTask.label;
    prompt = selectedTask.prompt;
    generationState = 'idle';
    generationMessage = 'Review the prepared prompt, then submit when ready.';
    openAi();
    queueMicrotask(() => document.getElementById('smart-deck-ai-prompt')?.focus());
  }

  async function improveSelectedSlide() {
    const improvementPrompt = 'Improve this slide with investor-ready logic, concise proof, and a clean executive visual hierarchy.';
    prompt = improvementPrompt;
    generationState = 'idle';
    activeTool = 'ai_tools';
    // DISABLED: The button previously stopped after preparing a prompt, which
    // made the primary "Improve this slide" action look wired without actually
    // starting the reviewable generation workflow.
    // generationMessage = selectedSlide
    //   ? 'Improvement brief ready. Review it, then generate a version.'
    //   : 'Select a slide before generating an improved version.';
    openAi();
    if (!selectedSlide) {
      generationMessage = 'Select a slide before generating an improved version.';
      return;
    }
    generationMessage = 'Starting an investor-ready version for this slide...';
    await generateVersionForSlide(selectedSlide.id, improvementPrompt);
  }

  async function persistShellPreferences(input: { activeTool?: DeckShellToolId; selectedSlideId?: string | null }) {
    if (!workspace) return;
    try {
      await fetch(`/api/decks/${workspace.deck.id}/workspace`, {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(input)
      });
    } catch {
      // The Smart Deck state contract remains authoritative if optional shell preference persistence degrades.
    }
  }

  function activateTool(key: DeckShellToolId) {
    if (key === 'research') {
      openResearchTool();
      return;
    }
    if (key === 'settings') {
      void goto('/settings');
      return;
    }
    if (key === 'design') {
      if (!instantMode) {
        const params = new URLSearchParams({ panel: 'design', origin: 'smart-deck' });
        if (selectedSlide?.id) params.set('slide', selectedSlide.id);
        if (selectedVersion?.id) params.set('designVersionId', selectedVersion.id);
        if (selectedGeneratedSlide?.id) params.set('generatedSlideId', selectedGeneratedSlide.id);
        void goto(`/decks/${viewModel.deckId}/smart-edit?${params.toString()}`);
        return;
      }
      activeTool = 'design';
      inspectorTab = 'design';
      void persistShellPreferences({ activeTool: key });
      return;
    }
    if (key === 'elements') {
      if (!selectedCanvasIdentity) return;
      void goto(buildSmartEditHandoffUrl(viewModel.deckId, selectedCanvasIdentity, {
        panel: 'elements',
        origin: instantMode ? 'instant-deck' : 'smart-deck'
      }));
      return;
    }
    if (key === 'text') {
      void goto(`/decks/${viewModel.deckId}/smart-edit?panel=text&origin=smart-deck`);
      return;
    }
    if (key === 'media') {
      void goto(`/decks/${viewModel.deckId}/smart-edit?panel=media&origin=smart-deck`);
      return;
    }
    if (key === 'smart_edit') {
      void goto(`/decks/${viewModel.deckId}/smart-edit?origin=smart-deck`);
      return;
    }
    if (key === 'due_diligence') {
      void goto(`/decks/${viewModel.deckId}/due-diligence`);
      return;
    }
    activeTool = key;
    void persistShellPreferences({ activeTool: key });
    if (key === 'ai_tools') {
      inspectorTab = 'ask_ai';
    }
  }

  async function generateBackgroundDesignOption(optionKey: string) {
    const option = DESIGN_BACKGROUND_OPTIONS.find((entry) => entry.key === optionKey);
    if (!option) return;
    const readyWorkspace = workspace ?? (await recoverSmartDeckWorkspace());
    if (!readyWorkspace || !selectedSlide || !selectedGeneratedSlide) {
      designState = 'error';
      designMessage = workspaceRecoveryError || 'Select a generated slide before designing the background.';
      return;
    }
    const generationIdentity = {
      slideId: selectedSlide.id,
      generatedSlideId: selectedGeneratedSlide.id,
      versionId: selectedGeneratedSlide.designVersionId
    };

    designState = 'generating';
    designBusyOptionKey = option.key;
    designMessage = `Generating ${option.label}...`;
    activeTool = 'design';
    inspectorTab = 'design';

    try {
      const accepted = await createSlideRedesignRun({
        deckId: readyWorkspace.deck.id,
        currentSlideId: generationIdentity.slideId,
        generatedSlideId: generationIdentity.generatedSlideId,
        baseDesignVersionId: generationIdentity.versionId,
        instruction: option.prompt,
        audience,
        taskContext: 'background_vision',
        targetKind: 'background'
      });
      const completed = await waitForSlideRedesignRun(accepted.runId, readyWorkspace.deck.id, generationIdentity.slideId);
      if (!completed.visionExecution?.executed || completed.visionExecution.status !== 'ready') {
        throw new Error('Background vision did not return verified execution evidence.');
      }
      const completedWorkspace = completed.workspace ?? (await refreshUserSmartDeckWorkspace(readyWorkspace.deck.id));
      const nextVersionId = completed.designVersionId ?? completed.design_version_id ?? null;
      if (!nextVersionId) {
        throw new Error('Background option completed without a reviewable design version.');
      }
      const identityStillCurrent = generationIdentityStillCurrent(generationIdentity, {
        slideId: selectedSlide?.id ?? null,
        generatedSlideId: selectedGeneratedSlide?.id ?? null,
        versionId: selectedGeneratedSlide?.designVersionId ?? null
      });
      workspace = completedWorkspace;
      generatedDesignOptions = [
        ...generatedDesignOptions.filter((entry) => !(entry.slideId === generationIdentity.slideId && entry.key === option.key)),
        { slideId: generationIdentity.slideId, key: option.key, label: option.label, versionId: nextVersionId }
      ];
      if (!identityStillCurrent) {
        designState = 'idle';
        designMessage = 'Background option finished for the slide you left. Return to that slide to review it.';
        return;
      }
      selectedVersionId = resolveSmartDeckVersionId({
        workspace,
        requestedVersionId: nextVersionId,
        selectedSlideId: generationIdentity.slideId,
        generatedOnly: instantMode
      });
      mode = 'preview';
      designState = 'success';
      designMessage = `${option.label} is ready to review as a candidate version.`;
    } catch (error) {
      designState = 'error';
      designMessage = error instanceof Error ? error.message : 'Background option could not be generated.';
    } finally {
      designBusyOptionKey = null;
    }
  }

  function openDeckMapTool() {
    activeTool = 'deck_map';
    void persistShellPreferences({ activeTool: 'deck_map' });
  }

  function openResearchTool() {
    void goto(`/decks/llm-report?deckId=${encodeURIComponent(viewModel.deckId)}#market-research`);
  }

  function toggleCompactSlideRail() {
    compactSlideRailOpen = !compactSlideRailOpen;
  }

  async function applyBrandGeneration(nextPrompt: string, brandProfile: BrandProfile) {
    if (!selectedSlide) throw new Error('Select a slide before applying the active brand.');
    prompt = nextPrompt;
    openAi();
    await generateVersionForSlide(selectedSlide.id, nextPrompt, buildSmartDeckDesignContext({
      graph,
      hasBrandProfile: true,
      hasLogo: Boolean(brandProfile.logoUrl || brandProfile.logoStorageKey),
      hasCompanyUrl: Boolean(brandProfile.companyWebsiteUrl)
    }));
    if (generationState === 'error') throw new Error(generationMessage || 'The branded version could not be generated.');
  }

  async function openSelectedSmartEdit() {
    if (!workspace || !selectedCanvasIdentity) return;
    const params = new URLSearchParams({
      origin: instantMode ? 'instant-deck' : 'smart-deck',
      designVersionId: selectedCanvasIdentity.designVersionId,
      generatedSlideId: selectedCanvasIdentity.generatedSlideId,
    });
    const sourceSlideId = selectedCanvasIdentity.sourceSlideId;
    if (sourceSlideId) params.set('slide', sourceSlideId);
    await goto(`/decks/${workspace.deck.id}/smart-edit?${params.toString()}`);
  }

  async function prepareCompiledHtmlExport(action: 'download' | 'print') {
    if (!workspace || !selectedVersion || selectedVersion.designVersion.renderMode !== 'html_compiled.v1') return;
    htmlExportState = 'preparing';
    htmlExportMessage = action === 'print' ? 'Preparing secure renderer access for browser print…' : 'Preparing the immutable provisional HTML download…';
    let printPlaceholder: Window | null = null;
    try {
      if (action === 'print') {
        printPlaceholder = openInstantHtmlPrintPlaceholder(window.open.bind(window));
        if (!fullDeckHtmlDocument) throw new Error('The exact compiled deck identity is unavailable for printing.');
        const capability = await mintInstantHtmlFullDeckCapability(fullDeckHtmlDocument);
        printPlaceholder.location.replace(capability.renderUrl);
        printPlaceholder = null;
        htmlExportMessage = 'Secure deck opened at the renderer origin. Use browser Print and choose Save as PDF.';
      } else {
        const exported = await createProvisionalHtmlDeckExport(workspace.deck.id, selectedVersion.id);
        const downloadUrl = `/api/decks/${workspace.deck.id}/exports/${exported.id}/download`;
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = '';
        link.click();
        htmlExportMessage = 'Immutable provisional HTML download ready.';
      }
      htmlExportState = 'ready';
    } catch (error) {
      printPlaceholder?.close();
      htmlExportState = 'error';
      htmlExportMessage = error instanceof Error ? error.message : 'The exact HTML export could not be prepared.';
    }
  }

  async function saveTypography(input: { headingFont: string; bodyFont: string }) {
    if (!workspace || !activeGeneratedSlideId || typographySaving) return;
    typographySaving = true;
    typographyMessage = '';
    saveState = 'saving';
    try {
      const result = await updateUserGeneratedSlideTypography(workspace.deck.id, activeGeneratedSlideId, input);
      canvasState.designTokens = result.generatedSlide.designTokens ?? canvasState.designTokens;
      saveState = 'saved';
      typographyMessage = 'Typography saved to this slide.';
    } catch (error) {
      saveState = 'unsaved';
      typographyMessage = error instanceof Error ? error.message : 'Typography could not be saved.';
    } finally {
      typographySaving = false;
    }
  }

  function openCreateSlideModal() {
    createSlideError = '';
    createSlideRole = 'appendix';
    const defaultRole = CREATE_SLIDE_ROLE_OPTIONS.find((option) => option.value === 'appendix') ?? CREATE_SLIDE_ROLE_OPTIONS[0];
    createSlideTitle = defaultRole.title;
    createSlideNarrative = defaultRole.brief;
    createSlideModalOpen = true;
  }

  function updateCreateSlideRole(nextRole: string) {
    createSlideRole = nextRole;
    const matched = CREATE_SLIDE_ROLE_OPTIONS.find((option) => option.value === nextRole);
    if (!matched) return;
    createSlideTitle = matched.title;
    createSlideNarrative = matched.brief;
  }

  async function addSlide() {
    if (!workspace || addingSlide) return;
    if (!createSlideTitle.trim() || !createSlideNarrative.trim()) {
      createSlideError = 'Add a slide title and the initial design brief.';
      return;
    }
    addingSlide = true;
    createSlideError = '';
    generationMessage = '';
    try {
      const created = await createUserSmartDeckSlide(workspace.deck.id, {
        title: createSlideTitle.trim(),
        role: createSlideRole,
        rawText: createSlideNarrative.trim()
      });
      workspace = await refreshUserSmartDeckWorkspace(workspace.deck.id);
      const selectionSaved = await persistLatestSelection({
        activeSourceSlideId: created.slide.id,
        selectedSourceSlideIds: [created.slide.id],
        activeGeneratedSlideId: null,
        selectedElementId: null
      }, () => {
        selectedSlideId = created.slide.id;
        selectedElementId = null;
        activeTool = 'slides';
        prompt = createSlideNarrative.trim();
        generationState = 'idle';
        generationMessage = 'New slide saved. Generating the first version...';
        inspectorTab = 'ask_ai';
      });
      if (!selectionSaved) throw new Error(generationMessage || 'The new slide selection could not be saved.');
      createSlideModalOpen = false;
      await generateVersionForSlide(created.slide.id, createSlideNarrative.trim());
    } catch (error) {
      generationState = 'error';
      createSlideError = error instanceof Error ? error.message : 'Slide could not be created.';
      generationMessage = createSlideError;
      saveState = 'unsaved';
    } finally {
      addingSlide = false;
    }
  }

  function applyQuickAction(nextPrompt: string, nextGoal: SmartDeckSubject) {
    prompt = nextPrompt;
    goal = nextGoal;
    inspectorTab = 'ask_ai';
  }

  function applyCompletedGenerationWorkspace(nextWorkspace: SmartDeckWorkspacePayload, designVersionId?: string | null) {
    workspace = nextWorkspace;
    selectedVersionId = resolveSmartDeckVersionId({ workspace: nextWorkspace, requestedVersionId: designVersionId, selectedSlideId, generatedOnly: instantMode });
    selectedSlideId = nextWorkspace.preferences.activeSourceSlideId ?? selectedSlideId;
    if (instantMode) {
      const completedSelection = resolveRecoveredWorkspaceSelection(
        nextWorkspace.designVersions,
        selectedVersionId,
        nextWorkspace.preferences.activeGeneratedSlideId ?? nextWorkspace.activeGeneratedSlideId,
        nextWorkspace.sourceSlides.map((slide) => slide.id),
        nextWorkspace.preferences.activeSourceSlideId
      );
      selectedInstantReviewGeneratedSlideId = completedSelection.generatedSlideId;
      if (completedSelection.generatedSlideId) selectedSlideId = completedSelection.sourceSlideId;
    }
    mode = 'preview';
    generationState = 'success';
    if (instantMode) {
      const completedVersion = nextWorkspace.designVersions.find((version) => version.id === selectedVersionId) ?? null;
      generationMessage = completedVersion
        ? describeInstantVersionCompletion(completedVersion, nextWorkspace.generationJobs, nextWorkspace).message
        : 'Generation completed, but the exact persisted design version is not yet visible.';
    } else {
      generationMessage = 'Version ready';
    }
    if (instantMode) {
      instantStatusUnresolved = false;
      instantGenerationIntentKey = null;
      instantCompletedGenerationJobId = null;
    }
  }

  function isMatchingInstantDeckJob(job: SmartDeckWorkspacePayload['generationJobs'][number], readyWorkspace: SmartDeckWorkspacePayload) {
    return job.generationMode === 'instant_deck' &&
      sameOrderedSourceSlideIds(job.selectedSourceSlideIds, orderedInstantSourceSlideIds(readyWorkspace));
  }

  function orderedInstantSourceSlideIds(currentWorkspace: SmartDeckWorkspacePayload) {
    return [...currentWorkspace.sourceSlides]
      .sort((left, right) => left.slideNumber - right.slideNumber)
      .map((slide) => slide.id);
  }

  function latestCompletedMatchingInstantDeck(currentWorkspace: SmartDeckWorkspacePayload) {
    return resolveLatestCompletedInstantGeneration(
      currentWorkspace.generationJobs,
      currentWorkspace.designVersions,
      orderedInstantSourceSlideIds(currentWorkspace)
    );
  }

  function waitForInstantDeckRefresh(signal?: AbortSignal, delay = 750) {
    return new Promise<void>((resolve, reject) => {
      if (signal?.aborted) {
        reject(signal.reason ?? new DOMException('Reconciliation was cancelled.', 'AbortError'));
        return;
      }
      const timeout = window.setTimeout(() => {
        signal?.removeEventListener('abort', abort);
        resolve();
      }, delay);
      const abort = () => {
        window.clearTimeout(timeout);
        reject(signal?.reason ?? new DOMException('Reconciliation was cancelled.', 'AbortError'));
      };
      signal?.addEventListener('abort', abort, { once: true });
    });
  }

  async function reconcileCompletedMatchingInstantDeck(
    currentWorkspace: SmartDeckWorkspacePayload,
    signal?: AbortSignal,
    knownCompletedJob?: SmartDeckWorkspacePayload['generationJobs'][number],
    exactCompletedJobId: string | null = knownCompletedJob?.id ?? instantCompletedGenerationJobId
  ): Promise<'resolved' | 'unresolved' | 'none'> {
    const initialResolution = exactCompletedJobId
      ? {
          jobId: exactCompletedJobId,
          versionId: currentWorkspace.designVersions.find((version) => version.generationJobId === exactCompletedJobId)?.id ?? null
        }
      : latestCompletedMatchingInstantDeck({
          ...currentWorkspace,
          generationJobs: knownCompletedJob
            ? [...currentWorkspace.generationJobs.filter((job) => job.id !== knownCompletedJob.id), knownCompletedJob]
            : currentWorkspace.generationJobs
        });
    if (!initialResolution) return 'none';
    if (initialResolution.versionId) {
      applyCompletedGenerationWorkspace(currentWorkspace, initialResolution.versionId);
      return 'resolved';
    }

    instantStatusUnresolved = true;
    generationState = 'generating';
    generationMessage = 'Generation completed. Reconciling the final Instant Deck…';
    const result = await reconcileCompletedInstantGenerationReadModel({
      initialWorkspace: currentWorkspace,
      sourceSlideIds: orderedInstantSourceSlideIds(currentWorkspace),
      knownCompletedJobs: knownCompletedJob ? [knownCompletedJob] : [],
      exactCompletedJobId,
      refreshWorkspace: async (refreshSignal) => {
        const refreshed = await refreshUserSmartDeckWorkspace(currentWorkspace.deck.id, refreshSignal);
        workspace = refreshed;
        return refreshed;
      },
      waitForRefresh: (refreshSignal) => waitForInstantDeckRefresh(refreshSignal),
      signal
    });
    if (result.status === 'resolved' && result.resolution?.versionId) {
      applyCompletedGenerationWorkspace(result.workspace, result.resolution.versionId);
      return 'resolved';
    }
    instantStatusUnresolved = true;
    generationState = 'generating';
    generationMessage = 'Generation completed. The final Instant Deck is still reconciling. Check status to continue without starting another generation.';
    return 'unresolved';
  }

  async function followActiveGeneration(readyWorkspace: SmartDeckWorkspacePayload, signal?: AbortSignal, applyCompletedMatch = false) {
    let currentWorkspace = readyWorkspace;
    let { activeJob, hasLaggingActiveHint } = resolveActiveGeneration(currentWorkspace);

    for (let attempt = 0; !activeJob && hasLaggingActiveHint && attempt < 5; attempt += 1) {
      try {
        if (attempt > 0) await waitForInstantDeckRefresh(signal);
        signal?.throwIfAborted();
        currentWorkspace = await refreshUserSmartDeckWorkspace(currentWorkspace.deck.id, signal);
        workspace = currentWorkspace;
        ({ activeJob, hasLaggingActiveHint } = resolveActiveGeneration(currentWorkspace));
      } catch (error) {
        if (isAbortError(error)) return true;
        instantStatusUnresolved = true;
        generationState = 'error';
        generationMessage = error instanceof Error ? error.message : 'The active deck redesign could not be loaded.';
        return true;
      }
    }
    if (!activeJob && hasLaggingActiveHint) {
      // Keep the durable active state, but do not leave the browser permanently
      // disabled when the workspace read model precedes job visibility. The
      // enabled Check status action re-runs this reconciliation and cannot POST
      // while the backend still reports active work.
      instantStatusUnresolved = true;
      generationState = 'idle';
      generationMessage = 'The active redesign is still being registered. Check status to reconnect without starting another generation.';
      return true;
    }
    instantStatusUnresolved = false;
    if (!activeJob) {
      if (!applyCompletedMatch) return false;
      const completedStatus = await reconcileCompletedMatchingInstantDeck(
        currentWorkspace,
        signal,
        undefined,
        instantCompletedGenerationJobId
      );
      return completedStatus !== 'none';
    }

    const matchesInstantDeckRequest = isMatchingInstantDeckJob(activeJob, currentWorkspace);
    generationState = 'generating';
    generationMessage = matchesInstantDeckRequest
      ? 'Your Instant Deck redesign is already in progress.'
      : 'Waiting for the active redesign before starting Instant Deck.';
    try {
      const completed = await waitForWorkflowJobCompletion(
        activeJob.id,
        'The active deck redesign failed.',
        undefined,
        undefined,
        (progress) => {
          if (progress.status === 'status_unavailable') {
            generationMessage = 'Live status is temporarily unavailable. Reconnecting to the same redesign…';
          }
        },
        signal
      );
      const nextWorkspace = completed.workspace ?? (await refreshUserSmartDeckWorkspace(currentWorkspace.deck.id));
      if (matchesInstantDeckRequest) {
        instantCompletedGenerationJobId = activeJob.id;
        await reconcileCompletedMatchingInstantDeck(
          nextWorkspace,
          signal,
          { ...activeJob, status: 'completed' }
        );
      } else {
        workspace = nextWorkspace;
        generationState = 'idle';
        generationMessage = 'The earlier redesign finished. Starting your Instant Deck request…';
      }
    } catch (error) {
      if (isAbortError(error)) return true;
      instantStatusUnresolved = true;
      generationState = 'error';
      generationMessage = error instanceof Error ? error.message : 'The active deck redesign failed.';
      // Fail closed: an uncertain or failed active job must never be followed
      // by a second automatic generation in the same mount.
      return true;
    }
    return matchesInstantDeckRequest;
  }

  async function regenerateInstantDeck() {
    if (instantCommandInFlight || generationState === 'generating' || hasActiveInstantGeneration) return false;
    instantCommandInFlight = true;
    const controller = new AbortController();
    instantPollingController = controller;
    try {
      aiTaskLabel = 'Instant Deck · Whole deck';
      inspectorTab = 'ask_ai';

      const readyWorkspace = await refreshUserSmartDeckWorkspace(graph.deck.id, controller.signal);
      workspace = readyWorkspace;
      if (await followActiveGeneration(readyWorkspace, controller.signal)) return false;

      const orderedSourceSlideIds = orderedInstantSourceSlideIds(readyWorkspace);
      if (orderedSourceSlideIds.length > MAX_INSTANT_SOURCE_PAGES) {
        generationState = 'error';
        generationMessage = `Instant Deck supports complete whole-deck generation for up to ${MAX_INSTANT_SOURCE_PAGES} source pages.`;
        return true;
      }

      instantGenerationIntentKey ??= crypto.randomUUID();
      await generateVersionWithPrompt(
        prompt.trim() || INSTANT_DECK_PROMPT,
        instantGenerationIntentKey,
        orderedSourceSlideIds,
        controller.signal
      );
      return true;
    } catch (error) {
      if (isAbortError(error)) return false;
      instantStatusUnresolved = true;
      generationState = 'error';
      generationMessage = error instanceof Error ? error.message : 'Instant Deck status could not be verified.';
      return true;
    } finally {
      instantCommandInFlight = false;
      if (instantPollingController === controller) instantPollingController = null;
    }
  }

  async function reconcileInstantDeckStatus() {
    if (instantCommandInFlight) return;
    instantCommandInFlight = true;
    const controller = new AbortController();
    instantPollingController = controller;
    try {
      const currentWorkspace = await refreshUserSmartDeckWorkspace(graph.deck.id, controller.signal);
      // SSR may intentionally mount without workspace data after a bounded read timeout.
      // Reconciliation must restore persisted selection state, not only swap payloads.
      if (workspace) workspace = currentWorkspace;
      else applyRecoveredWorkspace(currentWorkspace);
      const followed = await followActiveGeneration(currentWorkspace, controller.signal, true);
      if (!followed) {
        instantStatusUnresolved = false;
        generationState = 'idle';
        generationMessage = instantGenerationIntentKey
          ? 'No active redesign is visible. Regenerate will safely retry the same request.'
          : 'No active redesign is running.';
      }
    } catch (error) {
      if (isAbortError(error)) return;
      instantStatusUnresolved = true;
      generationState = 'error';
      generationMessage = error instanceof Error ? error.message : 'Instant Deck status could not be verified.';
    } finally {
      instantCommandInFlight = false;
      if (instantPollingController === controller) instantPollingController = null;
    }
  }

  async function generateVersionWithPrompt(generationPrompt: string, idempotencyKey?: string, requestedSourceSlideIds = selectedSourceSlideIds, signal?: AbortSignal) {
    if (!generationPrompt.trim()) {
      generationState = 'error';
      generationMessage = 'Add a prompt before generating a version.';
      return;
    }

    generationState = 'generating';
    generationMessage = workspace ? '' : 'Finishing your Smart Deck workspace...';
    const readyWorkspace = workspace ?? (await recoverSmartDeckWorkspace());
    const readySourceSlideId = requestedSourceSlideIds.includes(selectedSlideId ?? '')
      ? selectedSlideId
      : readyWorkspace?.preferences.activeSourceSlideId && requestedSourceSlideIds.includes(readyWorkspace.preferences.activeSourceSlideId)
        ? readyWorkspace.preferences.activeSourceSlideId
        : requestedSourceSlideIds[0] ?? null;
    if (!readyWorkspace || !readySourceSlideId) {
      generationState = 'error';
      generationMessage = workspaceRecoveryError || fallbackMessage || 'Smart Deck is still preparing your workspace. Try again shortly.';
      return;
    }
    const requestedBaseDesignVersionId = instantMode
      ? readyWorkspace.designVersions.some((version) => version.id === selectedVersionId) ? selectedVersionId : null
      : null;

    generationMessage = instantMode
      ? `Generating the complete ${requestedSourceSlideIds.length}-page deck in one whole-deck request…`
      : '';
    inspectorTab = 'ask_ai';

    try {
      const result = await generateSmartDeckVersion(readyWorkspace.deck.id, {
        prompt: generationPrompt,
        userPrompt: generationPrompt,
        selectedSourceSlideIds: requestedSourceSlideIds,
        activeSourceSlideId: readySourceSlideId,
        selectedElementId,
        audience,
        deckType,
        selectedSubject: goal,
        latestBatchId: null,
        designContext: buildSmartDeckDesignContext({ graph }),
        idempotencyKey,
        generationMode: instantMode ? 'instant_deck' : 'standard',
        outputContract: instantMode ? 'full_html_deck.v1' : 'render_schema.v1',
        baseDesignVersionId: requestedBaseDesignVersionId
      }, instantMode ? { signal } : undefined);
      if (instantMode) {
        instantCompletedGenerationJobId = result.generationJobId;
        if (result.designVersion?.id) {
          applyCompletedGenerationWorkspace(result.workspace, result.designVersion.id);
        } else if ((await reconcileCompletedMatchingInstantDeck(result.workspace, signal, undefined, result.generationJobId)) === 'none') {
          workspace = result.workspace;
          instantStatusUnresolved = true;
          generationState = 'idle';
          generationMessage = 'Generation completed. The final Instant Deck is still reconciling. Check status to continue without starting another generation.';
        }
      } else {
        applyCompletedGenerationWorkspace(result.workspace, result.designVersion?.id ?? null);
      }
    } catch (error) {
      if (isAbortError(error)) return;
      if (instantMode) instantStatusUnresolved = true;
      generationState = 'error';
      generationMessage = error instanceof Error ? error.message : 'Could not generate. Try again.';
    }
  }

  async function generateVersion() {
    await generateVersionWithPrompt(prompt);
  }

  async function sendConversation(instruction: string) {
    conversationMessage = '';
    saveInsightState = 'idle';
    saveInsightMessage = '';
    if (instantMode) {
      if (instantCommandInFlight || generationState === 'generating' || hasActiveInstantGeneration) {
        conversationState = 'error';
        conversationMessage = 'An Instant Deck redesign is already in progress. Check status before sending another request.';
        return;
      }
      conversationState = 'sending';
      prompt = instruction;
      const submitted = await regenerateInstantDeck();
      if (!submitted) {
        conversationState = 'error';
        conversationMessage = generationState === 'error'
          ? generationMessage
          : 'Another Instant Deck redesign was already active. Your request was not submitted; review its result, then send again.';
        return;
      }
      conversationState = generationState === 'error' ? 'error' : 'idle';
      conversationMessage = generationState === 'error' ? generationMessage : '';
      return;
    }
    if (!workspace) {
      conversationState = 'error';
      conversationMessage = workspaceRecoveryError || fallbackMessage || 'Smart Deck is still preparing your workspace. Try again shortly.';
      return;
    }
    conversationState = 'sending';
    try {
      latestAssistantRun = await createSmartDeckAssistantRun({
        deckId: workspace.deck.id,
        instruction,
        currentSlideId: selectedSlide?.id ?? null,
        audience
      });
      workspace = await refreshUserSmartDeckWorkspace(workspace.deck.id);
      conversationState = 'idle';
    } catch (error) {
      conversationState = 'error';
      conversationMessage = error instanceof Error ? error.message : 'Assistant conversation failed.';
    }
  }

  function assistantPromptSlug() {
    const basis = latestAssistantRun?.intentType ?? 'saved-response';
    return String(basis)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 80) || 'saved-response';
  }

  async function saveAssistantResponse() {
    if (!workspace || !latestAssistantRun?.savedArtifactId || !selectedSlide?.id) return;
    saveInsightState = 'saving';
    saveInsightMessage = '';
    try {
      const response = await fetch(`/api/decks/${workspace.deck.id}/saved-response-exports`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          slideId: selectedSlide.id,
          promptSlug: assistantPromptSlug(),
          assistantArtifactId: latestAssistantRun.savedArtifactId
        })
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(typeof payload?.message === 'string' ? payload.message : 'Could not save this response.');
      }
      saveInsightState = 'saved';
      saveInsightMessage = 'Saved to export.';
    } catch (error) {
      saveInsightState = 'error';
      saveInsightMessage = error instanceof Error ? error.message : 'Could not save this response.';
    }
  }

  async function retryFailedSlides() {
    if (!workspace || !failedGeneration || generationState === 'generating') return;
    generationState = 'generating';
    generationMessage = `Retrying ${failedGeneration.failedSlideIds?.length ?? 0} failed slide(s)…`;
    try {
      const receipt = await retryFailedSmartDeckSlides(workspace.deck.id, failedGeneration.id);
      const completed = await waitForWorkflowJobCompletion(receipt.jobId, 'Failed-slide retry failed.');
      if (completed.status !== 'completed') throw new Error(completed.errorMessage ?? 'Failed-slide retry did not complete.');
      workspace = await refreshUserSmartDeckWorkspace(workspace.deck.id);
      generationState = 'success';
      generationMessage = 'Failed slides retried. Successful slides were preserved.';
    } catch (error) {
      generationState = 'error';
      generationMessage = error instanceof Error ? error.message : 'Failed slides could not be retried.';
    }
  }

  async function generateVersionForSlide(slideId: string, nextPrompt: string, designContext = buildSmartDeckDesignContext({ graph })) {
    if (!nextPrompt.trim()) {
      generationState = 'error';
      generationMessage = 'Add a prompt before generating a version.';
      return;
    }

    generationState = 'generating';
    generationMessage = workspace ? '' : 'Finishing your Smart Deck workspace...';
    const readyWorkspace = workspace ?? (await recoverSmartDeckWorkspace());
    if (!readyWorkspace) {
      generationState = 'error';
      generationMessage = workspaceRecoveryError || fallbackMessage || 'Smart Deck is still preparing your workspace. Try again shortly.';
      return;
    }
    generationMessage = '';
    inspectorTab = 'ask_ai';

    try {
      const result = await generateSmartDeckVersion(readyWorkspace.deck.id, {
        prompt: nextPrompt,
        userPrompt: nextPrompt,
        selectedSourceSlideIds: [slideId],
        activeSourceSlideId: slideId,
        selectedElementId: null,
        audience,
        deckType,
        selectedSubject: goal,
        latestBatchId: null,
        designContext,
        generationMode: instantMode ? 'instant_deck' : 'standard'
      });
      workspace = result.workspace;
      selectedVersionId = resolveSmartDeckVersionId({ workspace: result.workspace, requestedVersionId: result.designVersion?.id ?? null, selectedSlideId: slideId, generatedOnly: instantMode });
      selectedSlideId = result.workspace.preferences.activeSourceSlideId ?? slideId;
      mode = 'preview';
      generationState = 'success';
      generationMessage = 'Version ready';
    } catch (error) {
      generationState = 'error';
      generationMessage = error instanceof Error ? error.message : 'Could not generate. Try again.';
    }
  }

  async function applySelectedVersion() {
    if (!workspace || !selectedVersionId || !canApplySelectedVersion) return;
    const shouldOpenSmartEditAfterApply = instantMode || focusedGeneration;
    saveState = 'saving';
    try {
      await applyUserSmartDeckVersion(workspace.deck.id, selectedVersionId);
      workspace = await refreshUserSmartDeckWorkspace(workspace.deck.id);
      selectedVersionId = resolveSmartDeckVersionId({ workspace, requestedVersionId: selectedVersionId, selectedSlideId, generatedOnly: instantMode });
      mode = 'edit';
      saveState = 'saved';
      generationState = 'success';
      generationMessage = 'Changes applied';
      if (shouldOpenSmartEditAfterApply) {
        const params = new URLSearchParams({ origin: instantMode ? 'instant-deck' : 'smart-deck' });
        const slideId = workspace.preferences.activeSourceSlideId ?? selectedSlideId;
        if (slideId) params.set('slide', slideId);
        if (selectedVersionId) params.set('designVersionId', selectedVersionId);
        const requestedGeneratedSlideId = selectedCanvasIdentity?.designVersionId === selectedVersionId && selectedCanvasIdentity.sourceSlideId === slideId
          ? selectedCanvasIdentity.generatedSlideId
          : null;
        const identity = instantMode ? resolveExactSmartEditHandoffIdentity({ designVersions: workspace.designVersions, selectedVersionId, sourceSlideId: slideId, requestedGeneratedSlideId }) : null;
        if (identity) params.set('generatedSlideId', identity.generatedSlideId);
        if (!instantMode || identity) await goto(`/decks/${workspace.deck.id}/smart-edit?${params.toString()}`);
      }
    } catch (error) {
      saveState = 'unsaved';
      generationState = 'error';
      generationMessage = error instanceof Error ? error.message : 'Could not apply this version.';
    }
  }

  async function discardSelectedVersion() {
    if (!workspace || !selectedVersionId) return;
    saveState = 'saving';
    try {
      await discardUserSmartDeckVersion(workspace.deck.id, selectedVersionId);
      workspace = await refreshUserSmartDeckWorkspace(workspace.deck.id);
      selectedVersionId = resolveSmartDeckVersionId({ workspace, selectedSlideId, generatedOnly: instantMode });
      saveState = 'saved';
      generationState = 'idle';
      generationMessage = '';
    } catch (error) {
      saveState = 'unsaved';
      generationState = 'error';
      generationMessage = error instanceof Error ? error.message : 'Could not discard this version.';
    }
  }

  function keepSelectedVersion() {
    generationState = 'success';
    generationMessage = 'Version kept in generated versions';
  }

  async function keepAndEditInstantVersion() {
    if (!instantMode || !selectedCanvasIdentity) return;
    keepSelectedVersion();
    await openSelectedSmartEdit();
  }

  async function selectElement(renderElementId: string) {
    const persistedElement = selectedSlide?.persistedElements.find((element) => element.elementKey === renderElementId);
    if (!persistedElement) {
      selectedElementId = null;
      generationState = 'error';
      generationMessage = 'This visual element is not linked to a persisted editable element. Generate a new slide version to repair it.';
      return;
    }
    if (!workspace) return;
    await persistLatestSelection({
      activeDesignVersionId: selectedVersionId,
      activeSourceSlideId: selectedSlideId,
      activeGeneratedSlideId,
      selectedElementId: persistedElement.id
    }, () => {
      selectedElementId = persistedElement.id;
      inspectorTab = 'map';
    });
  }

  async function generateSelectedElementVariation() {
    if (!workspace || !activeGeneratedSlideId || !selectedElementId) {
      generationState = 'error';
      generationMessage = 'Select a generated slide element before creating a variation.';
      return;
    }
    if (!elementInstruction.trim()) {
      generationState = 'error';
      generationMessage = 'Add an element fitting instruction.';
      return;
    }

    generationState = 'generating';
    generationMessage = 'Generating a reviewable element variation…';
    try {
      const variation = await generateUserElementVariation(
        workspace.deck.id,
        activeGeneratedSlideId,
        selectedElementId,
        elementInstruction.trim()
      );
      workspace = variation.workspace ?? (await refreshUserSmartDeckWorkspace(workspace.deck.id));
      selectedVersionId = resolveSmartDeckVersionId({ workspace, requestedVersionId: variation.designVersion?.id ?? selectedVersionId, selectedSlideId, generatedOnly: instantMode });
      selectedElementId = variation.element.id;
      canvasState.renderSchema = (await loadUserGeneratedSlideCode(workspace.deck.id, variation.generatedSlide?.id ?? activeGeneratedSlideId)).renderSchema;
      mode = 'preview';
      inspectorTab = 'ask_ai';
      generationState = 'success';
      generationMessage = 'Element variation ready. Review the preview, then apply or discard the design version.';
    } catch (error) {
      generationState = 'error';
      generationMessage = error instanceof Error ? error.message : 'Could not generate the element variation.';
    }
  }

</script>
{#snippet instantDeckSmartEditHandoff()}{#if instantMode}<section class="instant-deck-edit-handoff" aria-label="Generated slide review controls"><div class="instant-deck-review-actions"><button type="button" disabled={instantDeckGeneratedSlides.findIndex((slide) => slide.id === activeGeneratedSlideId) <= 0} onclick={() => reviewAdjacentInstantSlide(-1)}>Previous generated slide</button><button type="button" disabled={instantDeckGeneratedSlides.findIndex((slide) => slide.id === activeGeneratedSlideId) >= instantDeckGeneratedSlides.length - 1} onclick={() => reviewAdjacentInstantSlide(1)}>Next generated slide</button></div>{#if selectedHtmlSlide}<p>This exact compiled HTML section is read-only here. Smart Edit receives the exact version and generated-section identity; HTML canvas editing is not enabled in this slice.</p><div class="instant-deck-ready-actions"><button type="button" class="instant-deck-edit-action" disabled={!selectedCanvasIdentity} onclick={() => void openSelectedSmartEdit()}>Modify in Smart Edit</button>{#if selectedHtmlSlide.renderProofStatus === 'ready'}<button type="button" disabled={htmlExportState === 'preparing'} onclick={() => void prepareCompiledHtmlExport('download')}>Download provisional HTML</button><button type="button" disabled={htmlExportState === 'preparing'} onclick={() => void prepareCompiledHtmlExport('print')}>Print / Save as PDF</button>{/if}</div>{#if htmlExportMessage}<span class:error={htmlExportState === 'error'} class="instant-deck-export-message" role={htmlExportState === 'error' ? 'alert' : 'status'}>{htmlExportMessage}</span>{/if}{:else}<p>This generated deck stays editable in Smart Edit.</p><button type="button" class="instant-deck-edit-action" disabled={!selectedCanvasIdentity} onclick={() => void openSelectedSmartEdit()}>Modify in Smart Edit</button>{/if}</section>{/if}{/snippet}

{#snippet instantDeckResultActionPanel()}
  {#if instantMode}
    <InstantDeckResultActions
      deckId={viewModel.deckId}
      designVersionId={selectedVersionId}
      generatedSlideId={activeGeneratedSlideId}
      sourceSlideId={selectedCanvasIdentity?.sourceSlideId ?? selectedSlideId}
      artifactId={selectedVersion?.designVersion.htmlArtifact?.id ?? null}
      canEdit={Boolean(selectedCanvasIdentity)}
      generating={instantCommandInFlight || generationState === 'generating' || hasActiveInstantGeneration}
      onKeepAndEdit={keepAndEditInstantVersion}
      onGenerateAnother={regenerateInstantDeck}
    />
  {/if}
{/snippet}

<DeckWorkspaceRegistration config={() => ({
  surface: instantMode ? 'instant-deck' : 'smart-deck',
  sidebar: {
    items: appRailItems,
    activeKey: activeTool,
    onItemChange: (key) => activateTool(key as DeckShellToolId)
  },
  navigator: {
    slides: railSlides,
    selectedSlideId: instantMode ? activeGeneratedSlideId : selectedSlide?.id ?? null,
    selectedSourceSlideIds: instantMode ? [] : selectedSourceSlideIds,
    onSelectSlide: instantMode ? openInstantGeneratedSlide : selectSlide,
    onToggleSourceSlideSelection: instantMode ? undefined : toggleSourceSlideSelection,
    onOpenSmartEdit: instantMode && selectedVersion?.designVersion.renderMode !== 'html_compiled.v1' ? openInstantGeneratedSlide : instantMode ? undefined : openSmartEdit,
    onAddSlide: instantMode || focusedGeneration ? undefined : openCreateSlideModal,
    addingSlide,
    belowToolbar: true,
    title: instantMode ? 'Generated version slides' : 'Active slides',
    description: instantMode ? 'Select exact generated sections for read-only review.' : 'Preview every slide included in regeneration.',
    showSourceSelection: !instantMode,
    visible: activeTool === 'slides' && compactSlideRailOpen
  },
  visualizer: {
    title: selectedSlide?.title ?? 'Deck overview',
    subtitle: instantMode && workspace?.savedDeckVersionNumber
      ? `Reviewing Version ${workspace.savedDeckVersionNumber} · Actual LLM-generated slide design.`
      : 'Actual generated slide design for the selected deck slide.',
    slide: focusedGeneration ? null : selectedCanvasSlide,
    renderSchema: canvasState.renderSchema,
    htmlSlide: fullDeckHtmlDocument,
    htmlDisplayMode: instantMode && fullDeckHtmlDocument ? 'full-document' : 'section',
    designTokens: canvasState.designTokens,
    selectedElementId: selectedRenderElementId,
    onSelectElement: selectElement,
    onActivateCanvas: instantMode && selectedCanvasIdentity && !selectedHtmlSlide ? openSelectedSmartEdit : undefined,
    interactive: false,
    emptyTitle: focusedGeneration
      ? instantMode ? 'Generating your Instant Deck' : 'Generate the complete deck'
      : 'No generated slide visual available',
    emptyText: focusedGeneration
      ? instantMode
        ? 'The LLM-generated slides will appear here when the persisted Instant Deck version is ready.'
        : 'Add your prompt to generate the complete deck or describe the whole-deck change you want.'
      : 'Generate a version before opening visual review and editing.',
    children: instantMode ? instantDeckResultActionPanel : undefined
  },
  chat: {
    messages: workspace?.messages ?? [],
    state: conversationState,
    message: conversationMessage,
    latestAssistantRun,
    saveInsightState,
    saveInsightMessage,
    onSend: sendConversation,
    onSaveInsight: saveAssistantResponse
  }
})}>
    <div class="smart-deck-user-shell__header-band" aria-hidden="true"></div>
    <!-- The canonical product rail stays visible before and after generation.
         Focused generation controls content density; it must not hide navigation. -->
    <SmartDeckTopBar
      deckName={viewModel.deckName}
    slides={instantMode ? railSlides : viewModel.slides}
    {mode}
    {saveState}
      deckId={viewModel.deckId}
    selectedVersionId={selectedVersion?.id ?? null}
    instantResultOnly={instantMode}
    originalDeckHref={null}
    regenerateLabel={instantMode ? (needsInstantStatusCheck ? 'Check status' : 'Regenerate') : null}
    regenerating={instantCommandInFlight || generationState === 'generating' || hasActiveInstantGeneration}
    regeneratingLabel={instantCommandInFlight && generationState !== 'generating' ? 'Checking status...' : 'Regenerating...'}
    onRegenerate={instantMode ? () => void (needsInstantStatusCheck ? reconcileInstantDeckStatus() : regenerateInstantDeck()) : undefined}
    selectedSlideId={instantMode ? activeGeneratedSlideId : selectedSlide?.id ?? null}
    onModeChange={(nextMode) => {
      mode = nextMode;
      if (nextMode === 'play' || nextMode === 'preview') selectedElementId = null;
      if (nextMode === 'edit') inspectorTab = 'map';
    }}
    onSlideChange={instantMode ? openInstantGeneratedSlide : selectSlide}
    onOpenSettings={() => void goto('/settings')}
  />

  {#if failedGeneration}
    <div class="smart-deck-retry-failed" role="status">
      <span>{failedGeneration.failedSlideIds?.length ?? 0} slide(s) need retry.</span>
      <button type="button" disabled={generationState === 'generating'} onclick={() => void retryFailedSlides()}>Retry failed slides</button>
    </div>
  {/if}

  {#if activeTool === 'slides' && compactSlideRailOpen}
    <!-- DISABLED: The shared deck-surface header already owns workspace/deck
         identity; repeating it here caused visible text overlap. -->
  {:else if activeTool === 'deck_map'}
    <aside class="deck-expanded-tool-panel" aria-label="Deck Map workspace">
      <div class="deck-expanded-tool-panel__head"><strong>Deck Map</strong><button type="button" onclick={() => activateTool('slides')}>Back to Slides</button></div>
      <DeckMapPanel {graph} contextSlides={viewModel.deckMapContext.slides} readyForLlm={viewModel.deckMapContext.readyForLlm} />
    </aside>
  {:else if activeTool === 'elements'}
    <aside class="deck-left-panel">
      <div class="deck-left-panel__head"><strong>Elements</strong><button type="button" onclick={() => activateTool('slides')}>Back to Slides</button></div>
      <SmartDeckElementsPanel
        renderSchema={canvasState.renderSchema}
        selectedElementId={selectedRenderElementId}
        instruction={elementInstruction}
        hasSelectedSlide={Boolean(selectedSlide)}
        isGenerating={generationState === 'generating'}
        message={generationMessage}
        isError={generationState === 'error'}
        onSelectElement={(elementId) => void selectElement(elementId)}
        onInstructionChange={(value) => {
          elementInstruction = value;
          generationState = 'idle';
          generationMessage = '';
        }}
        onGenerateVariation={() => void generateSelectedElementVariation()}
        onGenerateSlide={() => void improveSelectedSlide()}
      />
    </aside>
  {:else if activeTool === 'data'}
    <aside class="deck-left-panel">
      <div class="deck-left-panel__head"><strong>Data</strong><button type="button" onclick={() => activateTool('slides')}>Back to Slides</button></div>
      <SmartDeckDataPanel deckId={viewModel.deckId} {initialProperties} />
    </aside>
  {:else if activeTool === 'brand'}
    <aside id="smart-deck-brand-panel" class="deck-left-panel" aria-label="Brand tool panel">
      <div class="deck-left-panel__head"><strong>Brand</strong><button type="button" onclick={() => activateTool('slides')}>Back to Slides</button></div>
      <SmartDeckBrandPanel deckId={viewModel.deckId} onApplyBrand={applyBrandGeneration} />
    </aside>
  {:else if activeTool === 'text'}
    <aside class="deck-left-panel">
      <div class="deck-left-panel__head"><strong>Text</strong><button type="button" onclick={() => activateTool('slides')}>Back to Slides</button></div>
      <SmartDeckTextPanel
        hasGeneratedSlide={Boolean(activeGeneratedSlideId)}
        designTokens={canvasState.designTokens}
        saving={typographySaving}
        message={typographyMessage}
        onSave={saveTypography}
      />
    </aside>
  {:else if activeTool === 'media'}
    <aside class="deck-left-panel" aria-label="Media library">
      <div class="deck-left-panel__head"><strong>Media</strong><button type="button" onclick={() => activateTool('slides')}>Back to Slides</button></div>
      <SmartDeckMediaPanel deckId={viewModel.deckId} />
    </aside>
  {:else if activeTool === 'ai_tools' || activeTool === 'design'}
    <DeckAITools
      surface={instantMode ? 'instant-deck' : 'smart-deck'}
      activeTab={inspectorTab}
      {selectedSlide}
      selectedElementId={selectedRenderElementId}
      renderSchema={canvasState.renderSchema}
      {audience}
      {deckType}
      {goal}
      {prompt}
      {generationState}
      {generationMessage}
      generatedVersions={viewModel.generatedVersions}
      selectedVersionId={selectedVersion?.id ?? null}
      {selectedVersion}
      {canApplySelectedVersion}
      validationStatus={canvasState.validationStatus}
      designTokens={canvasState.designTokens}
      {typographySaving}
      {typographyMessage}
      {designState}
      {designMessage}
      {designBusyOptionKey}
      designOptions={DESIGN_BACKGROUND_OPTIONS.map(({ key, label, summary }) => ({ key, label, summary }))}
      generatedDesignOptions={slideGeneratedDesignOptions}
      audienceOptions={SMART_DECK_AUDIENCE_OPTIONS}
      deckTypeOptions={SMART_DECK_DECK_TYPE_OPTIONS}
      goalOptions={SMART_DECK_GOAL_OPTIONS}
      quickActions={SMART_DECK_QUICK_ACTIONS}
      {graph}
      taskLabel={aiTaskLabel}
      {focusedGeneration}
      onClose={() => activateTool('slides')}
      onTabChange={(nextTab) => (inspectorTab = nextTab)}
      onAudienceChange={(value) => {
        audience = value;
        void persistPreferences();
      }}
      onDeckTypeChange={(value) => {
        deckType = value;
        void persistPreferences();
      }}
      onGoalChange={(value) => {
        goal = value;
        void persistPreferences();
      }}
      onPromptChange={(value) => {
        prompt = value;
        generationState = 'idle';
        generationMessage = '';
      }}
      onQuickAction={applyQuickAction}
      onGenerate={instantMode ? regenerateInstantDeck : generateVersion}
      onApply={applySelectedVersion}
      onKeep={keepSelectedVersion}
      onDiscard={discardSelectedVersion}
      onSelectVersion={selectVersion}
      onOpenSmartEdit={() => void openSelectedSmartEdit()}
      onSelectElement={(elementId) => void selectElement(elementId)}
      onSaveTypography={saveTypography}
      onGenerateBackgroundOption={(optionKey) => void generateBackgroundDesignOption(optionKey)}
      onSelectBackground={() => selectAiTask('background')}
      onSelectSlideContent={() => selectAiTask('slide_content')}
      onSelectWholeDeck={() => selectAiTask('whole_deck')}
    />
  {:else if activeTool === 'settings'}
    <aside class="deck-left-panel">
      <div class="deck-left-panel__head"><strong>Settings</strong><button type="button" onclick={() => activateTool('slides')}>Back to Slides</button></div>
      <SmartDeckSettingsPanel
        {audience}
        {deckType}
        {goal}
        onConfigureProvider={() => (providerModalOpen = true)}
      />
    </aside>
  {/if}

  {#if activeTool === 'slides'}
    <button
      type="button"
      class="smart-deck-slide-rail-toggle"
      aria-expanded={compactSlideRailOpen}
      aria-controls="global-deck-slide-navigator"
      onclick={toggleCompactSlideRail}
    >
      {compactSlideRailOpen ? 'Hide slide rail' : 'Show slide rail'}
    </button>
  {/if}

  {#if activeTool !== 'deck_map' && activeTool !== 'research'}
    <SmartDeckFilmstrip
      slides={railSlides}
      selectedSlideId={instantMode ? activeGeneratedSlideId : selectedSlide?.id ?? null}
      onSelectSlide={instantMode ? openInstantGeneratedSlide : selectSlide}
      onOpenSmartEdit={instantMode ? openInstantGeneratedSlide : openSmartEdit}
      onAddSlide={instantMode ? undefined : openCreateSlideModal}
      {addingSlide}
      addSlideLabel="+"
      responsiveOnly={activeTool === 'slides'}
    />
  {/if}

  {#if !workspace && fallbackMessage}
    <div class="smart-deck-user-shell__notice">
      <strong>Workspace is still preparing</strong>
      <p>{fallbackMessage}</p>
      {#if fallbackActionHref}
        <a href={fallbackActionHref}>{fallbackActionLabel ?? 'View processing'}</a>
      {/if}
    </div>
  {/if}
</DeckWorkspaceRegistration>

{#if providerModalOpen}
  <WorkspaceAiProviderModal
    workspaceId={graph.deck.workspaceId}
    forceOpen={true}
    allowSkip={false}
    onClose={() => (providerModalOpen = false)}
    onConfigured={() => (providerModalOpen = false)}
  />
{/if}

<SmartDeckCreateSlideModal
  open={createSlideModalOpen}
  loading={addingSlide}
  title={createSlideTitle}
  narrative={createSlideNarrative}
  selectedRole={createSlideRole}
  roleOptions={CREATE_SLIDE_ROLE_OPTIONS}
  onTitleChange={(value) => (createSlideTitle = value)}
  onNarrativeChange={(value) => (createSlideNarrative = value)}
  onRoleChange={updateCreateSlideRole}
  onClose={() => {
    if (addingSlide) return;
    createSlideModalOpen = false;
  }}
  onSubmit={() => void addSlide()}
  errorMessage={createSlideError}
/>

<style>
  .instant-deck-edit-handoff { display:flex; align-items:center; justify-content:space-between; gap:.8rem; padding:.85rem 1rem; border:1px solid var(--line); border-radius:12px; }
  .instant-deck-edit-handoff p { margin:0; color:var(--muted); }
  .instant-deck-edit-action { padding:.55rem .9rem; border-radius:9px; border:1px solid var(--accent); color:white; background:var(--accent); font:inherit; font-weight:700; }
  .instant-deck-edit-action:disabled { opacity:.55; }
  .instant-deck-ready-actions { display:flex; align-items:center; gap:.5rem; flex-wrap:wrap; }
  .instant-deck-ready-actions button { padding:.55rem .75rem; border-radius:9px; border:1px solid var(--line); color:white; background:rgba(255,255,255,.06); font:inherit; font-weight:650; }
  .instant-deck-ready-actions button:disabled { opacity:.55; }
  .instant-deck-export-message { color:var(--muted); font-size:.82rem; }
  .instant-deck-export-message.error { color:#fca5a5; }
  .smart-deck-user-shell__header-band {
    position: absolute;
    inset: 0 0 auto 0;
    height: 64px;
    background: linear-gradient(180deg, rgba(7, 11, 22, 0.5), rgba(7, 11, 22, 0));
    pointer-events: none;
  }

  .smart-deck-user-shell__notice {
    position: absolute;
    top: 88px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 25;
    display: grid;
    gap: 0.5rem;
    padding: 1rem 1.1rem;
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(15, 23, 42, 0.94);
    box-shadow: 0 24px 48px rgba(2, 6, 23, 0.35);
  }

  .smart-deck-user-shell__notice p {
    margin: 0;
    color: #94a3b8;
  }

  .smart-deck-user-shell__notice a {
    color: #c4b5fd;
    text-decoration: none;
  }

  .smart-deck-retry-failed {
    position: fixed;
    top: 72px;
    right: 360px;
    z-index: 20;
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding: 0.5rem 0.7rem;
    border: 1px solid rgba(251, 191, 36, 0.3);
    border-radius: 10px;
    background: rgba(69, 26, 3, 0.92);
    color: #fde68a;
    font-size: 0.78rem;
  }

  .smart-deck-retry-failed button {
    border: 1px solid rgba(253, 230, 138, 0.35);
    border-radius: 8px;
    padding: 0.35rem 0.55rem;
    background: rgba(255, 255, 255, 0.08);
    color: #fff7ed;
    cursor: pointer;
  }

  .deck-left-panel {
    grid-column: 2;
    grid-row: 2 / 4;
    overflow-y: auto;
    padding: 0.85rem 0.8rem;
    background: rgba(7, 11, 22, 0.6);
    border-right: 1px solid rgba(255, 255, 255, 0.06);
    display: grid;
    align-content: start;
  }

  .deck-expanded-tool-panel {
    grid-column: 2;
    grid-row: 2 / 4;
    min-width: 0;
    min-height: 0;
    overflow: auto;
    padding: 1rem;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(8, 13, 27, 0.98);
    z-index: 12;
  }

  .deck-expanded-tool-panel :global(.deck-map),
  .deck-expanded-tool-panel :global(.market-research) {
    width: 100%;
    max-width: none;
  }

  .deck-expanded-tool-panel__head,
  .deck-left-panel__head {
    position: sticky;
    top: 0;
    z-index: 2;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    padding: 0 0 0.85rem;
    background: rgba(8, 13, 27, 0.98);
  }

  .deck-expanded-tool-panel__head button,
  .deck-left-panel__head button {
    min-height: 36px;
    padding: 0 0.8rem;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    background: rgba(15, 23, 42, 0.92);
    color: #e2e8f0;
    cursor: pointer;
  }

  .smart-deck-slide-rail-toggle {
    position: absolute;
    top: 78px;
    left: 88px;
    z-index: 18;
    min-height: 38px;
    padding: 0 0.85rem;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(15, 23, 42, 0.92);
    color: #e2e8f0;
    font: inherit;
    cursor: pointer;
  }

  @media (max-width: 960px) {
    .deck-expanded-tool-panel,
    .deck-left-panel {
      position: relative;
      grid-column: 2;
      grid-row: 2;
      width: 100%;
      min-width: 0;
      min-height: 0;
      z-index: 12;
      box-shadow: none;
    }

    .deck-expanded-tool-panel {
      padding: 0.85rem;
    }

    .deck-left-panel {
      border-right: 1px solid rgba(255, 255, 255, 0.1);
    }

    .smart-deck-slide-rail-toggle {
      display: none;
    }
  }

  @media (max-width: 720px) {
    .deck-expanded-tool-panel,
    .deck-left-panel {
      position: relative;
      grid-column: 1;
      grid-row: 3;
      width: 100%;
      min-width: 0;
      min-height: 0;
    }

    .smart-deck-user-shell__notice {
      top: 150px;
      width: min(calc(100vw - 2rem), 30rem);
    }

  }
</style>
