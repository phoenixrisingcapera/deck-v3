<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
import { page } from '$app/state';
import { deckProductApiPath } from '$lib/contracts';
import type { SaveConfirmation } from '@deck-aistack-codes/shared';
import AppShell from '$components/AppShell.svelte';
import DeckLoaderOverlay from '$components/DeckLoaderOverlay.svelte';
import UploadDeck from '$components/UploadDeck.svelte';
import DeveloperVisibilityCard from '$components/visibility/DeveloperVisibilityCard.svelte';
import { createDependencyStatus, createDeveloperToolsPayload, createDeveloperVisibilityItems } from '$lib/developer-tools/payload';
import { isApiAuthError, readApiJsonOrThrow, toApiErrorBannerModel, type ApiErrorBannerModel } from '$lib/api/apiError';
  import type {
    WorkspaceDeckRecord,
    UploadedDeckListItem
  } from '$lib/components/deckService/upload/uploaded-decks-list.types';
  import { mapWorkspaceDeckRecordToListItem } from '$lib/components/deckService/upload/uploaded-decks-list.types';
  import type { SaveConfirmationBannerModel } from '$lib/contracts/types';
  import BrandLoader from '$lib/components/deckService/brand/BrandLoader.svelte';
  import BrandProfileCard from '$lib/components/deckService/brand/BrandProfileCard.svelte';
  import {
    getDeckWorkflowStatus,
    type SmartDeckProcessingStatus,
    type DeckExtractionStatus,
    type WorkflowSourceAsset,
    type WorkflowSourceSlide
  } from '$lib/api/deckService/workflow.client';
  import type { DeckUploadStatus } from '$lib/components/deckService/upload/upload-deck.types';
  import { deckServiceClient } from '$lib/api/deckServiceClient';
  import { normalizeSaveConfirmation } from '$lib/utils/saveConfirmation';
  import { hasBrandSignals, type BrandGuidelinesStatus, type BrandProfile, type BrandStatus } from '$lib/types/deckService-brand';
  type DeckUploadStage = 'creating' | 'requesting_upload' | 'uploading' | 'confirming' | 'processing' | 'ready';
  type FirstBatchSourceType = 'url_branding' | 'logo_branding';
  type FirstBatchReceipt = {
    deckId: string;
    batchId: string;
    sourceType: FirstBatchSourceType;
    hasSourceFile?: boolean | null;
    nextUrl?: string | null;
    confirmation?: SaveConfirmation | null;
  };
  type DeckUploadSession = {
    acceptedFileTypes: string[];
    maxFileSizeBytes: number | null;
  };
  type PreferredWorkspace = 'smart_deck' | 'instant_deck';
  type UploadErrorPayload = {
    message?: unknown;
    detail?: unknown;
    error?: unknown;
    requestId?: unknown;
  };
  type ExtractBrandResponse = {
    brandProfile: BrandProfile | null;
  };
  type UpdateBrandProfileResponse = {
    brandProfile: BrandProfile | null;
  };
  type WorkspaceDecksState = {
    decks: WorkspaceDeckRecord[];
    isLoading: boolean;
    error: string | null;
    errorBanner: ApiErrorBannerModel | null;
    selectedDeckId: string | null;
  };

  const acceptedDeckTypes =
    '.pdf,.ppt,.pptx,application/pdf,application/vnd.ms-powerpoint,application/vnd.openxmlformats-officedocument.presentationml.presentation';
  const acceptedLogoTypes = '.png,.jpg,.jpeg,.gif,.webp,image/png,image/jpeg,image/gif,image/webp';
  const acceptedGuidelineTypes =
    '.pdf,.doc,.docx,.md,.txt,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/markdown,text/plain';
  const uploadSessionPath = deckProductApiPath('/decks/upload-session');
  const uploadDeckPath = deckProductApiPath('/decks/upload');
  const firstBatchPath = deckProductApiPath('/decks/first-batch');

  const firstBatchMode = $derived.by(() => {
    // Optional query mode lets the intake page start from brand/context inputs
    // instead of a deck file. Default flow remains deck upload first.
    const mode = page.url.searchParams.get('firstBatch');
    if (mode === 'url_branding' || mode === 'logo_branding' || mode === 'supporting_context') return mode;
    return 'slide_miniatures';
  });
  const showHeroStepper = false;

  let deckFile = $state<File | null>(null);
  const preferredWorkspace = $derived<PreferredWorkspace>(
    page.url.searchParams.get('instant') === '0' ? 'smart_deck' : 'instant_deck'
  );
  // Deck upload state is split deliberately: source-file save status, backend
  // extraction status, and UI progress are not the same thing.
  let deckId = $state('');
  let deck_upload_status = $state<DeckUploadStatus>('idle');
  let deckSourceFileStatus = $state('');
  let deckOriginalFileUrl = $state('');
  let deck_extraction_status = $state<DeckExtractionStatus>('idle');
  let deckStatusSteps = $state<Array<{ key: string; label: string; status: string }>>([]);
  let uploadProgress = $state(0);
  let uploadError = $state('');
  let deckUploadStage = $state<DeckUploadStage | 'idle' | 'failed'>('idle');
  let deckDragActive = $state(false);
  let deckStatusSummary = $state('');
  let uploadConfirmation = $state<SaveConfirmation | null>(null);
  const workspaceDecksState = $state<WorkspaceDecksState>({
    decks: [],
    isLoading: true,
    error: null,
    errorBanner: null,
    selectedDeckId: null
  });
  let workspaceDecksLoadInFlight: Promise<void> | null = null;
  let workspaceDecksLastLoadedAt = 0;
  let persistedSourceSlides = $state<WorkflowSourceSlide[]>([]);
  let persistedSourceLoading = $state(false);
  let persistedSourceError = $state('');
  let latestProcessingStatus = $state<SmartDeckProcessingStatus | null>(null);
  let deckLoaderTransitioning = $state(false);
  let lastWorkspaceDeckStatusKey = '';
  let authExpired = $state(false);
  let authExpiredMessage = $state('');
  let pageMountedAt = $state('');
  let uploadRequestId = $state('');
  let uploadFailureTicketId = $state('');
  let queueFailureTicketId = $state('');
  let uploadSessionRequestId = $state('');
  let uploadSessionLoadedAt = $state('');

  let companyUrl = $state('');
  let logoFile = $state<File | null>(null);
  let brandGuidelinesFile = $state<File | null>(null);
  let logoDragActive = $state(false);
  let guidelinesDragActive = $state(false);
  let brand_status = $state<BrandStatus>('idle');
  let brandGuidelinesStatus = $state<BrandGuidelinesStatus>('idle');
  let brandError = $state('');
  let brandApproved = $state(false);
  let brandProfile = $state<BrandProfile | null>(null);
  let brandModalOpen = $state(false);
  let editingBrand = $state(false);
  let savingBrand = $state(false);
  let brandSaveError = $state('');
  let localLogoPreviewUrl = $state('');
  let autoBrandExtractionDecks = new Set<string>();
  let brandExtractionInFlightKeys = new Set<string>();
  let completedBrandExtractionKeys = new Set<string>();

  function formatFileSize(size: number) {
    return formatDeckFileSize(size) ?? '0 KB';
  }

  function formatDeckFileSize(size: number | null | undefined): string | null {
    if (typeof size !== 'number' || Number.isNaN(size) || size <= 0) return null;
    if (size < 1024 * 1024) {
      return `${Math.max(1, Math.round(size / 1024))} KB`;
    }

    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }

  function formatDeckUploadDate(value: string | null | undefined): string | null {
    if (!value) return null;

    const timestamp = new Date(value).getTime();
    if (Number.isNaN(timestamp)) return null;

    const deltaSeconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
    if (deltaSeconds < 60) return 'Just now';

    const deltaMinutes = Math.round(deltaSeconds / 60);
    if (deltaMinutes < 60) return `${deltaMinutes}m ago`;

    const deltaHours = Math.round(deltaMinutes / 60);
    if (deltaHours < 24) return `${deltaHours}h ago`;

    const deltaDays = Math.round(deltaHours / 24);
    if (deltaDays < 7) return `${deltaDays}d ago`;

    return new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric' }).format(new Date(timestamp));
  }

  function sourceFileStatusLabel(hasSourceFile: boolean | null | undefined): string {
    return hasSourceFile === false ? 'missing' : 'saved';
  }

  const workspaceDecks = $derived.by<UploadedDeckListItem[]>(() =>
    // Convert raw workspace deck records into row models with formatted date,
    // size, selection, and status labels for the reusable list component.
    workspaceDecksState.decks.map((deck) =>
      mapWorkspaceDeckRecordToListItem(deck, {
        formatDeckFileSize,
        formatDeckUploadDate,
        selectedDeckId: deck.id === deckId ? deckId : workspaceDecksState.selectedDeckId
      })
    )
  );

  const workspaceDecksLoading = $derived(workspaceDecksState.isLoading);

  function latestDeckIdsToKeep(nextDeckId: string) {
    const orderedExisting = [...workspaceDecksState.decks]
      .filter((deck) => deck.id && deck.id !== nextDeckId)
      .sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime())
      .slice(0, 2)
      .map((deck) => deck.id);

    return [nextDeckId, ...orderedExisting];
  }

  async function softRemoveDeckFromBackend(deckId: string) {
    // Product API proxy: this marks old/stale intake decks as removed without
    // hard-deleting source artifacts that workers or admins may still inspect.
    const path = deckProductApiPath(`/decks/${deckId}/soft-delete`);
    const response = await fetch(path, { method: 'POST' });
    await readApiJsonOrThrow(response, 'Could not remove this deck.', path);
  }

  async function cleanupBrokenIntakeDecks(currentDeckIds: string[], reason = 'successful_intake_cleanup') {
    if (currentDeckIds.length === 0) return;

    // Best-effort cleanup must never block the successful upload handoff. The
    // backend owns the actual soft-delete policy and session scoping.
    const path = deckProductApiPath('/decks/intake-cleanup');

    try {
      const response = await fetch(path, {
        method: 'POST',
        headers: {
          'content-type': 'application/json'
        },
        body: JSON.stringify({
          currentDeckIds,
          reason
        })
      });
      await readApiJsonOrThrow(response, 'Could not clean up stale intake decks.', path);
    } catch {
      // Cleanup is intentionally silent. Stale rows should not block the current intake run.
    }
  }

  async function loadWorkspaceDecks(showLoading = false, forceReload = false) {
    // Poll workspace decks lightly to avoid noisy backend requests while still
    // refreshing after upload/retry/remove actions.
    const state = workspaceDecksState;
    const minIntervalMs = showLoading ? 0 : 8000;
    const now = Date.now();

    if (
      !forceReload &&
      !showLoading &&
      state.decks.length > 0 &&
      workspaceDecksLastLoadedAt > 0 &&
      now - workspaceDecksLastLoadedAt < minIntervalMs
    ) {
      return;
    }
    if (workspaceDecksLoadInFlight) {
      await workspaceDecksLoadInFlight;
      return;
    }

    const request = (async () => {
      if (showLoading) state.isLoading = true;
      state.error = null;
      state.errorBanner = null;

      try {
        const response = await fetch(deckProductApiPath('/decks'));
        const payload = await readApiJsonOrThrow<{ decks?: WorkspaceDeckRecord[] }>(
          response,
          'Could not load uploaded decks.',
          deckProductApiPath('/decks')
        );

        const decks = Array.isArray(payload?.decks) ? payload.decks : [];
        state.decks = decks;
        if (state.selectedDeckId && !decks.some((deck) => deck.id === state.selectedDeckId)) {
          state.selectedDeckId = null;
        }
        workspaceDecksLastLoadedAt = Date.now();
      } catch (error) {
        if (isAuthFailure(error)) {
          markAuthExpired(error);
          void goto(`/auth/sign-in?next=${encodeURIComponent(`${page.url.pathname}${page.url.search}`)}`);
          return;
        }
        const banner = toApiErrorBannerModel(error, 'Could not load uploaded decks.');
        if (state.decks.length === 0) {
          state.decks = [];
        }
        state.error = banner.message;
        state.errorBanner = banner;
      } finally {
        if (showLoading) state.isLoading = false;
        workspaceDecksLoadInFlight = null;
      }
    })();

    workspaceDecksLoadInFlight = request;
    await request;
  }

  function isAuthFailure(error: unknown): boolean {
    if (isApiAuthError(error)) return true;
    const message = error instanceof Error ? error.message : String(error ?? '');
    return /authentication|required|sign.?in|session.*expired|missing.*token|invalid.*token|revoked/i.test(message);
  }

  function markAuthExpired(error: unknown) {
    authExpired = true;
    authExpiredMessage = error instanceof Error ? error.message : 'Authentication required';
    uploadError = authExpiredMessage;
    persistedSourceError = authExpiredMessage;
    brandError = authExpiredMessage;
  }

  async function retryWorkspaceDeck(deckId: string) {
    const path = deckProductApiPath(`/decks/${deckId}/retry`);
    workspaceDecksState.error = null;
    workspaceDecksState.errorBanner = null;

    try {
      // Product API proxy: retry requests must go through the backend workflow
      // contract so the browser never attempts to restart workers itself.
      const response = await fetch(path, { method: 'POST' });
      const payload = await readApiJsonOrThrow(response, 'Could not retry this deck.', path);

      await loadWorkspaceDecks(true, true);
      return payload;
    } catch (error) {
      if (isAuthFailure(error)) {
        markAuthExpired(error);
        void goto(`/auth/sign-in?next=${encodeURIComponent(`${page.url.pathname}${page.url.search}`)}`);
        return null;
      }
      const banner = toApiErrorBannerModel(error, 'Could not retry this deck.');
      workspaceDecksState.error = banner.message;
      workspaceDecksState.errorBanner = banner;
      return null;
    }
  }

  async function removeWorkspaceDeck(deckId: string) {
    const previousDecks = [...workspaceDecksState.decks];
    const previousSelectedDeckId = workspaceDecksState.selectedDeckId;
    workspaceDecksState.error = null;
    workspaceDecksState.errorBanner = null;
    workspaceDecksState.decks = workspaceDecksState.decks.filter((deck) => deck.id !== deckId);
    if (workspaceDecksState.selectedDeckId === deckId) {
      workspaceDecksState.selectedDeckId = null;
    }

    try {
      await softRemoveDeckFromBackend(deckId);
      await loadWorkspaceDecks(true, true);
      return { ok: true };
    } catch (error) {
      const banner = toApiErrorBannerModel(error, 'Could not remove this deck.');
      workspaceDecksState.decks = previousDecks;
      workspaceDecksState.selectedDeckId = previousSelectedDeckId;
      workspaceDecksState.error = banner.message;
      workspaceDecksState.errorBanner = banner;
      return null;
    }
  }

  async function extractDeckBrand({
    deckId,
    companyUrl,
    logoFile,
    brandGuidelinesFile
  }: {
    deckId: string;
    companyUrl: string;
    logoFile: File | null;
    brandGuidelinesFile?: File | null;
  }): Promise<ExtractBrandResponse> {
    const formData = new FormData();
    if (companyUrl.trim()) {
      formData.set('companyUrl', companyUrl.trim());
    }
    if (logoFile) {
      formData.set('logoFile', logoFile);
    }
    if (brandGuidelinesFile) {
      formData.set('brandGuidelinesFile', brandGuidelinesFile);
    }

    const path = deckProductApiPath(`/decks/${deckId}/workflows/brand-extraction`);
    const response = await fetch(path, {
      method: 'POST',
      body: formData
    });

    return readApiJsonOrThrow<ExtractBrandResponse>(response, 'Brand extraction failed.', path);
  }

  function brandExtractionSignature({
    deckId,
    companyUrl,
    logoFile,
    brandGuidelinesFile
  }: {
    deckId: string;
    companyUrl: string;
    logoFile: File | null;
    brandGuidelinesFile?: File | null;
  }) {
    return JSON.stringify({
      deckId,
      companyUrl: companyUrl.trim().toLowerCase(),
      logo: logoFile ? [logoFile.name, logoFile.size, logoFile.lastModified] : null,
      guidelines: brandGuidelinesFile ? [brandGuidelinesFile.name, brandGuidelinesFile.size, brandGuidelinesFile.lastModified] : null
    });
  }

  async function updateDeckBrandProfile({
    deckId,
    brandProfile
  }: {
    deckId: string;
    brandProfile: Partial<BrandProfile>;
  }): Promise<UpdateBrandProfileResponse> {
    const path = deckProductApiPath(`/decks/${deckId}/brand-profile`);
    const response = await fetch(path, {
      method: 'PATCH',
      headers: {
        'content-type': 'application/json'
      },
      body: JSON.stringify(brandProfile)
    });

    return readApiJsonOrThrow<UpdateBrandProfileResponse>(response, 'Brand profile update failed.', path);
  }

  function resetBrandState() {
    if (localLogoPreviewUrl) {
      URL.revokeObjectURL(localLogoPreviewUrl);
      localLogoPreviewUrl = '';
    }
    companyUrl = '';
    logoFile = null;
    brandGuidelinesFile = null;
    brand_status = 'idle';
    brandGuidelinesStatus = 'idle';
    brandError = '';
    brandApproved = false;
    brandProfile = null;
    editingBrand = false;
    brandSaveError = '';
  }

  function extractUploadErrorMessage(payload: UploadErrorPayload | null, fallback = 'Deck upload failed.') {
    if (!payload || typeof payload !== 'object') return fallback;

    const detail = payload.detail;
    const detailRecord = detail && typeof detail === 'object' ? (detail as Record<string, unknown>) : null;
    const message =
      (typeof payload.message === 'string' && payload.message) ||
      (typeof detail === 'string' && detail) ||
      (typeof detailRecord?.message === 'string' && detailRecord.message) ||
      (typeof detailRecord?.error === 'string' && detailRecord.error) ||
      (typeof payload.error === 'string' && payload.error) ||
      fallback;
    const requestId =
      (typeof payload.requestId === 'string' && payload.requestId) ||
      (typeof detailRecord?.requestId === 'string' && detailRecord.requestId) ||
      '';
    const ticketId = typeof detailRecord?.ticketId === 'string' ? detailRecord.ticketId : '';
    const suffix = [requestId ? `request ${requestId}` : '', ticketId ? `ticket ${ticketId}` : '']
      .filter(Boolean)
      .join(', ');

    return suffix ? `${message} (${suffix})` : message;
  }

  async function loadDeckUploadSession(): Promise<DeckUploadSession> {
    const response = await fetch(deckProductApiPath('/decks/upload-session'), {
      method: 'POST'
    });
    const payload = await response.json().catch(() => null);

    if (!response.ok) {
      throw new Error(extractUploadErrorMessage(payload, 'Could not prepare the deck upload session.'));
    }

    const acceptedFileTypes = Array.isArray(payload?.acceptedFileTypes)
      ? payload.acceptedFileTypes
      : Array.isArray(payload?.accepted_file_types)
        ? payload.accepted_file_types
        : ['pdf', 'ppt', 'pptx'];
    uploadSessionRequestId =
      (payload && typeof payload === 'object' && typeof (payload as Record<string, unknown>).requestId === 'string'
        ? String((payload as Record<string, unknown>).requestId)
        : '') || response.headers.get('x-request-id') || '';
    uploadSessionLoadedAt = new Date().toISOString();

    return {
      acceptedFileTypes: acceptedFileTypes.map((value: unknown) => String(value).replace(/^\./, '').toLowerCase()),
      maxFileSizeBytes:
        typeof payload?.maxFileSizeBytes === 'number'
          ? payload.maxFileSizeBytes
          : typeof payload?.max_file_size_bytes === 'number'
            ? payload.max_file_size_bytes
            : null
    };
  }

  function validateDeckFileForSession(file: File, session: DeckUploadSession) {
    if (session.maxFileSizeBytes && file.size > session.maxFileSizeBytes) {
      throw new Error(`Deck upload is limited to ${formatFileSize(session.maxFileSizeBytes)}.`);
    }

    const extension = file.name.split('.').pop()?.toLowerCase() ?? '';
    if (session.acceptedFileTypes.length > 0 && !session.acceptedFileTypes.includes(extension)) {
      throw new Error(`Upload a ${session.acceptedFileTypes.map((type) => type.toUpperCase()).join(', ')} deck file.`);
    }
  }

  function formatUploadStageLabel(stage: DeckUploadStage | 'idle' | 'failed') {
    switch (stage) {
      case 'creating':
        return 'Creating deck';
      case 'requesting_upload':
        return 'Preparing upload';
      case 'uploading':
        return 'Uploading file';
      case 'confirming':
        return 'Confirming upload';
      case 'processing':
        return 'Processing deck';
      case 'ready':
        return 'Ready';
      case 'failed':
        return 'Failed';
      default:
        return 'Starting';
    }
  }

  async function saveDeck(file: File) {
    // This is the only upload path for the intake card. It calls the frontend
    // product proxy, receives a persisted deck id, then hands all processing
    // truth to workflow-state instead of opening Smart Deck directly.
    const websiteUrl = companyUrl.trim();
    deck_upload_status = 'uploading';
    deck_extraction_status = 'queued';
    deckStatusSteps = [];
    uploadProgress = 18;
    uploadError = '';
    deckUploadStage = 'creating';
    deckStatusSummary = '';
    deckId = '';
    deckSourceFileStatus = '';
    deckOriginalFileUrl = '';
    uploadConfirmation = null;
    persistedSourceSlides = [];
    persistedSourceLoading = false;
    persistedSourceError = '';
    uploadRequestId = '';
    uploadFailureTicketId = '';
    queueFailureTicketId = '';
    brandModalOpen = false;
    resetBrandState();

    try {
      const result = await deckServiceClient.uploadFirstDeck(
        file,
        {
          audience: preferredWorkspace === 'instant_deck' ? undefined : 'Investment Committee',
          purpose: preferredWorkspace === 'instant_deck' ? 'Presentation redesign' : 'Initial diligence review',
          websiteUrl,
          preferredWorkspace
        },
        {
          onStage: (stage) => {
            deckUploadStage = stage;
            if (stage === 'uploading') uploadProgress = 48;
            if (stage === 'confirming') uploadProgress = 72;
            if (stage === 'processing') uploadProgress = 88;
            if (stage === 'ready') uploadProgress = 96;
          }
        }
      );

      const nextDeckId = String(result.deckId ?? '');
      if (!nextDeckId) {
        throw new Error('Deck upload finished without a persisted deck id.');
      }

      const nextExtractionStatus = typeof result.deckExtractionStatus === 'string' ? result.deckExtractionStatus : 'queued';
      // Persisted deck id is the handoff token for processing page polling,
      // brand profile lookup, workspace deck list refresh, and cleanup.
      deckId = nextDeckId;
      lastWorkspaceDeckStatusKey = '';
      deck_upload_status = 'saved';
      deckSourceFileStatus = 'ready';
      deckOriginalFileUrl = '';
      deck_extraction_status = nextExtractionStatus as DeckExtractionStatus;
      uploadConfirmation = null;
      uploadProgress = 100;
      deckUploadStage = 'ready';
      uploadRequestId = typeof result.requestId === 'string' ? result.requestId : '';
      uploadFailureTicketId = typeof result.failureTicketId === 'string' ? result.failureTicketId : '';
      queueFailureTicketId = typeof result.queueFailureTicketId === 'string' ? result.queueFailureTicketId : '';
      if (result.queueError || nextExtractionStatus === 'failed') {
        uploadError = result.queueError || 'Background processing could not be queued.';
      }
      brandModalOpen = nextExtractionStatus !== 'failed';
      // Cleanup and workspace refresh are best-effort bookkeeping. They must not
      // delay the canonical processing route after the backend returns a deck id.
      void cleanupBrokenIntakeDecks(latestDeckIdsToKeep(nextDeckId), 'successful_upload_cleanup');
      void loadWorkspaceDecks(false, true);
      // These background refreshes keep the current page informative, but Smart
      // Deck opening is still handled by the processing route redirect below.
      void refreshDeckStatus(nextDeckId);
      void refreshBrandProfile(nextDeckId);
      
      // Auto-redirect to processing page after 2 seconds to show progress.
      // The processing page owns the readiness poll and eventual Smart Deck open.
      if (nextExtractionStatus !== 'failed') {
        // DISABLED: The prior handoff waited two seconds after also awaiting
        // cleanup and deck-list refresh.
        // Reason: Those delays did not contribute to durable processing state.
        // setTimeout(async () => {
        //   if (deckId && deck_upload_status === 'saved') await goto(`/decks/${deckId}/processing`);
        // }, 2000);
        deckLoaderTransitioning = true;
        try {
          await goto(processingHref(nextDeckId, preferredWorkspace));
        } catch (error) {
          deckLoaderTransitioning = false;
          // The persisted receipt remains visible so the user can continue manually.
        }
      }
    } catch (error) {
      deck_upload_status = 'failed';
      deck_extraction_status = 'failed';
      deckUploadStage = 'failed';
      uploadProgress = 0;
      uploadError = error instanceof Error ? error.message : 'Deck upload failed.';
    }
  }

  async function createSourceFirstBatch(sourceType: FirstBatchSourceType) {
    const formData = new FormData();
    formData.set('sourceType', sourceType);
    if (companyUrl.trim()) formData.set('websiteUrl', companyUrl.trim());
    if (logoFile) formData.set('logoFile', logoFile);

    const response = await fetch(deckProductApiPath('/decks/first-batch'), {
      method: 'POST',
      body: formData
    });

    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(typeof payload?.message === 'string' ? payload.message : 'First version creation failed.');
    }

    const receiptPayload = (payload && typeof payload === 'object' ? payload : null) as Record<string, unknown> | null;
    const receipt: FirstBatchReceipt = {
      deckId: String(receiptPayload?.deckId ?? ''),
      batchId: String(receiptPayload?.batchId ?? ''),
      sourceType: receiptPayload?.sourceType === 'logo_branding' ? 'logo_branding' : 'url_branding',
      hasSourceFile: typeof receiptPayload?.hasSourceFile === 'boolean'
        ? receiptPayload.hasSourceFile
        : typeof receiptPayload?.has_source_file === 'boolean'
          ? receiptPayload.has_source_file
          : null,
      nextUrl: typeof receiptPayload?.nextUrl === 'string' ? receiptPayload.nextUrl : null,
      confirmation: normalizeSaveConfirmation(receiptPayload?.confirmation as Record<string, unknown> | null | undefined, 'deck_properties_saved')
    };
    if (!receipt.deckId || !receipt.batchId) {
      throw new Error('First version finished without a persisted deck receipt.');
    }

    deckId = receipt.deckId;
    lastWorkspaceDeckStatusKey = '';
    deck_upload_status = 'saved';
    deckSourceFileStatus = sourceFileStatusLabel(receipt.hasSourceFile);
    deckOriginalFileUrl = receipt.sourceType;
    deck_extraction_status = 'ready';
    uploadConfirmation = receipt.confirmation ?? null;
    uploadProgress = 100;
    await cleanupBrokenIntakeDecks(latestDeckIdsToKeep(receipt.deckId), 'successful_first_batch_cleanup');
    await loadWorkspaceDecks(false, true);
    void refreshPersistedSourceInspection(receipt.deckId);
    return receipt;
  }

  async function refreshDeckStatus(nextDeckId: string) {
    try {
      const status = await getDeckWorkflowStatus(nextDeckId);
      latestProcessingStatus = status;
      const brandStatusValue = status.brandProfile?.status ?? brand_status;
      const rawDeckUploadStatus =
        status.sourceFileSaved
          ? 'saved'
          : status.status === 'failed'
            ? 'failed'
            : status.status === 'processing'
              ? 'uploading'
              : 'idle';
      const nextDeckUploadStatus =
        deck_upload_status === 'saved' && (rawDeckUploadStatus === 'uploading' || rawDeckUploadStatus === 'idle')
          ? 'saved'
          : rawDeckUploadStatus;
      const nextWorkspaceDeckStatusKey = JSON.stringify({
        uploadStatus: nextDeckUploadStatus,
        deckExtractionStatus: status.deckExtractionStatus,
        sourceFileStatus: status.sourceFileStatus ?? (status.sourceFileSaved ? 'saved' : ''),
        brandStatus: brandStatusValue
      });

      deck_upload_status = nextDeckUploadStatus;
      deckSourceFileStatus = status.sourceFileStatus ?? sourceFileStatusLabel(status.sourceFileSaved);
      deck_extraction_status = status.deckExtractionStatus;
      deckStatusSummary = status.message ?? '';
      deckStatusSteps = status.phases.map((phase) => ({
        key: phase.key,
        label: phase.label,
        status: phase.status
      }));
      if (status.latestConfirmation) {
        uploadConfirmation = normalizeSaveConfirmation(status.latestConfirmation, 'deck_upload_saved');
      }
      if (brandStatusValue === 'ready' || brandStatusValue === 'extracting' || brandStatusValue === 'failed' || brandStatusValue === 'idle') {
        brand_status = brandStatusValue as BrandStatus;
      }

      if (nextWorkspaceDeckStatusKey !== lastWorkspaceDeckStatusKey) {
        lastWorkspaceDeckStatusKey = nextWorkspaceDeckStatusKey;
        await loadWorkspaceDecks(false, true);
      }
    } catch (error) {
      if (isAuthFailure(error)) {
        markAuthExpired(error);
        void goto(`/auth/sign-in?next=${encodeURIComponent(`${page.url.pathname}${page.url.search}`)}`);
        return;
      }
      if (deck_upload_status === 'saved') {
        deckStatusSummary = 'Deck is saved. Processing status is still syncing.';
        return;
      }
    }
  }

  async function refreshBrandProfile(nextDeckId: string) {
    try {
      const status = latestProcessingStatus ?? (await getDeckWorkflowStatus(nextDeckId));
      const persistedProfile = status.brandProfile ?? null;
      if (persistedProfile) {
        brandProfile = persistedProfile;
        if (persistedProfile.brandGuidelinesStatus) {
          brandGuidelinesStatus = persistedProfile.brandGuidelinesStatus;
        }

        if (
          persistedProfile.status === 'ready' ||
          persistedProfile.status === 'extracting' ||
          persistedProfile.status === 'failed'
        ) {
          brand_status = persistedProfile.status;
        } else {
          brand_status = 'idle';
        }
        autoBrandExtractionDecks.delete(nextDeckId);
        return;
      }
    } catch (error) {
      if (isAuthFailure(error)) {
        markAuthExpired(error);
        void goto(`/auth/sign-in?next=${encodeURIComponent(`${page.url.pathname}${page.url.search}`)}`);
      }
      return;
    }

    if (!hasBrandSourceInput && !deckUploadComplete) {
      brand_status = 'idle';
      brandError = '';
      autoBrandExtractionDecks.delete(nextDeckId);
      return;
    }

    if (!deckId && !deckUploadComplete && !hasBrandSourceInput) {
      return;
    }

    if (!hasBrandSourceInput) {
      // Brand extraction is optional. When no URL/logo/guidelines were supplied,
      // Smart Deck generation falls back to presentation-derived/default design tokens.
      brand_status = 'idle';
      brandError = '';
      autoBrandExtractionDecks.add(nextDeckId);
      return;
    }

    const deckOnlyExtraction = false;
    const extractionInput = {
      deckId: nextDeckId,
      companyUrl: deckOnlyExtraction ? '' : companyUrl.trim(),
      logoFile: deckOnlyExtraction ? null : logoFile,
      brandGuidelinesFile: deckOnlyExtraction ? null : brandGuidelinesFile
    };
    const extractionKey = brandExtractionSignature(extractionInput);

    if (brandExtractionInFlightKeys.has(extractionKey) || completedBrandExtractionKeys.has(extractionKey) || autoBrandExtractionDecks.has(nextDeckId)) {
      return;
    }

    brandExtractionInFlightKeys.add(extractionKey);
    brand_status = 'extracting';
    brandError = '';
    try {
      const payload = await extractDeckBrand(extractionInput);

      brandProfile = payload?.brandProfile ?? null;
      brand_status =
        payload?.brandProfile?.status === 'ready'
          ? 'ready'
          : payload?.brandProfile?.status === 'failed'
            ? 'failed'
            : 'extracting';
      if (payload?.brandProfile?.brandGuidelinesStatus) {
        brandGuidelinesStatus = payload.brandProfile.brandGuidelinesStatus;
      }
      autoBrandExtractionDecks.add(nextDeckId);
      completedBrandExtractionKeys.add(extractionKey);
    } catch (error) {
      brand_status = 'failed';
      brandError = error instanceof Error ? error.message : 'Brand extraction failed.';
      if (brandGuidelinesFile) {
        brandGuidelinesStatus = 'failed';
      }
    } finally {
      brandExtractionInFlightKeys.delete(extractionKey);
    }
  }

  async function refreshPersistedSourceInspection(nextDeckId: string) {
    persistedSourceLoading = true;
    persistedSourceError = '';

    try {
      const status = latestProcessingStatus ?? (await getDeckWorkflowStatus(nextDeckId));
      persistedSourceSlides = status.sourceSlides ?? [];
    } catch (error) {
      if (isAuthFailure(error)) {
        markAuthExpired(error);
        void goto(`/auth/sign-in?next=${encodeURIComponent(`${page.url.pathname}${page.url.search}`)}`);
        return;
      }
      persistedSourceError =
        error instanceof Error ? error.message : 'Could not load the persisted source summary.';
    } finally {
      persistedSourceLoading = false;
    }
  }

  $effect(() => {
    if (deck_upload_status !== 'uploading') {
      return;
    }

    if (uploadProgress < 22) {
      uploadProgress = 22;
    }

    const timer = window.setInterval(() => {
      uploadProgress = Math.min(36, uploadProgress + Math.max(2, Math.round((40 - uploadProgress) / 5)));
    }, 420);

    return () => {
      window.clearInterval(timer);
    };
  });

  $effect(() => {
    if (authExpired || !deckId || deck_upload_status !== 'saved' || deck_extraction_status === 'ready' || deck_extraction_status === 'failed') {
      return;
    }

    const timer = window.setInterval(() => {
      void refreshDeckStatus(deckId);
    }, 3000);

    return () => {
      window.clearInterval(timer);
    };
  });

  $effect(() => {
    if (authExpired || !deckId || deck_upload_status !== 'saved' || deck_extraction_status !== 'ready') {
      return;
    }

    if (persistedSourceLoading) {
      return;
    }

    void refreshPersistedSourceInspection(deckId);
  });

  $effect(() => {
    if (authExpired || !deckId || deck_upload_status !== 'saved' || deck_extraction_status === 'ready' || deck_extraction_status === 'failed') {
      return;
    }

    const timer = window.setInterval(() => {
      uploadProgress = Math.min(92, uploadProgress + Math.max(1, Math.round((94 - uploadProgress) / 8)));
    }, 900);

    return () => {
      window.clearInterval(timer);
    };
  });

  $effect(() => {
    if (authExpired || !deckId || deck_upload_status !== 'saved') {
      return;
    }

    const shouldPollBrand = brandModalOpen || brand_status === 'extracting' || brand_status === 'idle';
    if (!shouldPollBrand) {
      return;
    }

    const timer = window.setInterval(() => {
      void refreshBrandProfile(deckId);
    }, 2500);

    return () => {
      window.clearInterval(timer);
    };
  });

  async function handleDeckSelection(event: Event) {
    const target = event.currentTarget as HTMLInputElement;
    const file = target.files?.[0] ?? null;
    await handleDeckFile(file);
  }

  async function handleDeckFile(file: File | null) {
    deckFile = file;
    deckDragActive = false;

    if (file) {
      try {
        const session = await loadDeckUploadSession();
        validateDeckFileForSession(file, session);
        await saveDeck(file);
      } catch (error) {
        deck_upload_status = 'failed';
        deck_extraction_status = 'failed';
        deckUploadStage = 'failed';
        uploadProgress = 0;
        uploadError = error instanceof Error ? error.message : 'Deck upload failed.';
      }
    }
  }

  function handleDeckDragEvent(event: DragEvent) {
    event.preventDefault();
    deckDragActive = true;
  }

  function handleDeckDragLeave(event: DragEvent) {
    event.preventDefault();
    deckDragActive = false;
  }

  async function handleDeckDrop(event: DragEvent) {
    event.preventDefault();
    const file = event.dataTransfer?.files?.[0] ?? null;
    await handleDeckFile(file);
  }

  function handleLogoDragEvent(event: DragEvent) {
    event.preventDefault();
    logoDragActive = true;
  }

  function handleLogoDragLeave(event: DragEvent) {
    event.preventDefault();
    logoDragActive = false;
  }

  function handleGuidelinesDragEvent(event: DragEvent) {
    event.preventDefault();
    guidelinesDragActive = true;
  }

  function handleGuidelinesDragLeave(event: DragEvent) {
    event.preventDefault();
    guidelinesDragActive = false;
  }

  async function handleLogoFile(file: File | null) {
    logoFile = file;
    logoDragActive = false;
    brandApproved = false;
    brandError = '';
    brandProfile = null;
    brand_status = 'idle';

    if (localLogoPreviewUrl) {
      URL.revokeObjectURL(localLogoPreviewUrl);
      localLogoPreviewUrl = '';
    }

    if (!file) {
      if (!companyUrl.trim() && !brandGuidelinesFile) {
        brandProfile = null;
        brand_status = 'idle';
      }
      return;
    }

    localLogoPreviewUrl = URL.createObjectURL(file);
  }

  async function handleGuidelinesFile(file: File | null) {
    brandGuidelinesFile = file;
    guidelinesDragActive = false;
    brandGuidelinesStatus = file ? 'uploaded' : 'idle';
    brandApproved = false;
    brandProfile = null;
    brand_status = 'idle';
  }

  async function handleLogoDrop(event: DragEvent) {
    event.preventDefault();
    const file = event.dataTransfer?.files?.[0] ?? null;
    await handleLogoFile(file);
  }

  async function handleGuidelinesDrop(event: DragEvent) {
    event.preventDefault();
    const file = event.dataTransfer?.files?.[0] ?? null;
    await handleGuidelinesFile(file);
  }

  function handleCompanyUrlChange(value: string) {
    companyUrl = value;
    brandApproved = false;
    brandProfile = null;
    brand_status = 'idle';
  }

  async function extractBrand() {
    if (!hasBrandSourceInput) {
      // Manual brand extraction also stays optional. An uploaded deck without
      // brand sources still proceeds through miniatures, Smart Deck activation,
      // and LLM generation using presentation/default design fallback rules.
      brand_status = 'idle';
      brandError = '';
      return;
    }

    if (!deckUploadComplete && !companyUrl.trim() && !logoFile && !brandGuidelinesFile) {
      return;
    }

    brand_status = 'extracting';
    brandError = '';
    brandApproved = false;
    editingBrand = false;
    brandSaveError = '';
    if (brandGuidelinesFile) {
      brandGuidelinesStatus = 'processing';
    }

    let activeExtractionKey: string | null = null;

    try {
      let targetDeckId = deckId;

      if (!targetDeckId) {
        if (logoFile) {
          const receipt = await createSourceFirstBatch('logo_branding');
          targetDeckId = receipt.deckId;
        } else if (companyUrl.trim()) {
          const receipt = await createSourceFirstBatch('url_branding');
          targetDeckId = receipt.deckId;
        }
      }

      if (!targetDeckId) {
        throw new Error('Load a company URL, logo, or uploaded deck before extracting brand signals.');
      }

      if (!deckUploadComplete && targetDeckId === deckId) {
        throw new Error('Wait for the deck upload receipt before extracting brand signals.');
      }

      if (!hasBrandSourceInput && !deckUploadComplete) {
        brand_status = 'idle';
        brandError = '';
        return;
      }

      const extractionInput = {
        deckId: targetDeckId,
        companyUrl,
        logoFile,
        brandGuidelinesFile
      };
      const extractionKey = brandExtractionSignature(extractionInput);
      if (brandExtractionInFlightKeys.has(extractionKey)) {
        return;
      }
      brandExtractionInFlightKeys.add(extractionKey);
      activeExtractionKey = extractionKey;

      const payload = await extractDeckBrand(extractionInput);

      brandProfile = payload?.brandProfile ?? null;
      brand_status =
        payload?.brandProfile?.status === 'ready'
          ? 'ready'
          : payload?.brandProfile?.status === 'failed'
            ? 'failed'
            : 'extracting';
      brandGuidelinesStatus = brandGuidelinesFile ? 'ready' : brandGuidelinesStatus;
      completedBrandExtractionKeys.add(extractionKey);
      await refreshBrandProfile(targetDeckId);
    } catch (error) {
      if (isAuthFailure(error)) {
        markAuthExpired(error);
        void goto(`/auth/sign-in?next=${encodeURIComponent(`${page.url.pathname}${page.url.search}`)}`);
        return;
      }
      brand_status = 'failed';
      brandGuidelinesStatus = brandGuidelinesFile ? 'failed' : brandGuidelinesStatus;
      brandError = error instanceof Error ? error.message : 'Brand extraction failed.';
    } finally {
      if (activeExtractionKey) {
        brandExtractionInFlightKeys.delete(activeExtractionKey);
      }
    }
  }

  async function saveBrandSelection(payload: {
    primaryColor: string;
    secondaryColor: string;
    accentColor: string;
    backgroundColor: string;
    textColor: string;
    visualStyle: string;
    fontCandidates: string[];
  }) {
    if (!brandProfile) {
      return;
    }

    savingBrand = true;
    brandSaveError = '';

    try {
      if (!deckId) {
        throw new Error('Upload or select a deck before saving brand selections so the profile can be persisted.');
      }

      const response = await updateDeckBrandProfile({
        deckId,
        brandProfile: {
          companyName: brandProfile.companyName,
          companyWebsiteUrl: companyUrl || brandProfile.companyWebsiteUrl,
          primaryColor: payload.primaryColor,
          secondaryColor: payload.secondaryColor,
          accentColor: payload.accentColor,
          backgroundColor: payload.backgroundColor,
          textColor: payload.textColor,
          palette: [
            payload.primaryColor,
            payload.secondaryColor,
            payload.accentColor,
            payload.backgroundColor,
            payload.textColor
          ],
          visualStyle: payload.visualStyle,
          fontCandidates: payload.fontCandidates,
          sourceMode: brandProfile.sourceMode ?? brandProfile.source
        }
      });

      brandProfile = response.brandProfile;
      if (
        response.brandProfile?.status === 'ready' ||
        response.brandProfile?.status === 'extracting' ||
        response.brandProfile?.status === 'failed'
      ) {
        brand_status = response.brandProfile.status;
      }
      editingBrand = false;
      brandApproved = true;
    } catch (error) {
      brandSaveError = error instanceof Error ? error.message : 'Brand profile update failed.';
    } finally {
      savingBrand = false;
    }
  }

  async function continueFromBrandReview() {
    brandApproved = true;
    brandModalOpen = false;
    if (deckId) {
      deckLoaderTransitioning = true;
      try {
        await goto(processingHref(deckId, preferredWorkspace));
      } catch (error) {
        if (isAuthFailure(error)) {
          markAuthExpired(error);
          void goto(`/auth/sign-in?next=${encodeURIComponent(`${page.url.pathname}${page.url.search}`)}`);
          return;
        }
        deckLoaderTransitioning = false;
        uploadError = error instanceof Error ? error.message : `Could not open ${preferredWorkspaceLabel}.`;
      }
    }
  }

  async function skipToSmartDeck() {
    brandModalOpen = false;
    if (deckId) {
      deckLoaderTransitioning = true;
      try {
        await goto(processingHref(deckId, preferredWorkspace));
      } catch (error) {
        if (isAuthFailure(error)) {
          markAuthExpired(error);
          void goto(`/auth/sign-in?next=${encodeURIComponent(`${page.url.pathname}${page.url.search}`)}`);
          return;
        }
        deckLoaderTransitioning = false;
        uploadError = error instanceof Error ? error.message : `Could not open ${preferredWorkspaceLabel}.`;
      }
    }
  }

  async function handleExistingDeckSelection(deck: UploadedDeckListItem) {
    if (!deck.id) {
      return;
    }

    workspaceDecksState.selectedDeckId = deck.id;
    deckId = deck.id;

    deckLoaderTransitioning = true;
    try {
      await goto(processingHref(deck.id, preferredWorkspace));
    } catch (error) {
      if (isAuthFailure(error)) {
        markAuthExpired(error);
        void goto(`/auth/sign-in?next=${encodeURIComponent(`${page.url.pathname}${page.url.search}`)}`);
        return;
      }
      deckLoaderTransitioning = false;
      uploadError = error instanceof Error ? error.message : `Could not open ${preferredWorkspaceLabel}.`;
    }
  }

  function processingHref(targetDeckId: string, workspaceMode: PreferredWorkspace) {
    return workspaceMode === 'instant_deck'
      ? `/decks/${targetDeckId}/processing?instant=1`
      : `/decks/${targetDeckId}/processing`;
  }
  const deckUploadComplete = $derived(Boolean(deckId && deck_upload_status === 'saved'));
  const preferredWorkspaceLabel = $derived(preferredWorkspace === 'instant_deck' ? 'Instant Deck' : 'Smart Deck');
  const continueButtonLabel = $derived(preferredWorkspace === 'instant_deck' ? 'Continue to Instant Deck' : 'Continue to Smart Deck');
  const brandStepReady = $derived(Boolean(brandProfile?.id && !brandProfile.id.startsWith('local_brand_') && hasBrandSignals(brandProfile)));
  const hasBrandSourceInput = $derived(companyUrl.trim().length > 0 || Boolean(logoFile) || Boolean(brandGuidelinesFile));
  const canExtractBrand = $derived(brand_status !== 'extracting' && (hasBrandSourceInput || deckUploadComplete));
  const canContinueFromBrandReview = $derived(deckUploadComplete && brandStepReady);
  const canContinueAfterUpload = $derived(deckUploadComplete);
  const deckLoaderOpen = $derived(deck_upload_status === 'uploading' || deckLoaderTransitioning);
  const deckLoaderTitle = $derived.by(() => {
    if (deckLoaderTransitioning) return 'Loading your workspace...';
    return 'Preparing your deck...';
  });
  const deckLoaderSubtitle = $derived.by(() => {
    if (deckLoaderTransitioning) {
      if (deck_extraction_status === 'ready') return `Opening ${preferredWorkspaceLabel} with the persisted source summary.`;
      if (deck_extraction_status === 'failed') return `Opening ${preferredWorkspaceLabel} with the saved source file and extraction status.`;
      return `Opening ${preferredWorkspaceLabel} while extraction continues in the background.`;
    }

    if (deckFile) return `${formatUploadStageLabel(deckUploadStage)} ${deckFile.name} before extraction starts.`;
    return 'Saving the source deck before extraction starts.';
  });
  const deckLoaderStatusLabel = $derived.by(() => {
    if (deckLoaderTransitioning) return 'Opening';
    return formatUploadStageLabel(deckUploadStage);
  });
  const deckLoaderSteps = $derived.by(() => [
    {
      label: 'Create deck',
      status:
        deckUploadStage === 'creating'
          ? 'running'
          : ['requesting_upload', 'uploading', 'confirming', 'processing', 'ready'].includes(deckUploadStage)
            ? 'complete'
            : deck_upload_status === 'failed'
              ? 'failed'
              : 'pending'
    },
    {
      label: 'Upload file',
      status:
        deckUploadStage === 'uploading'
          ? 'running'
          : ['confirming', 'processing', 'ready'].includes(deckUploadStage)
            ? 'complete'
            : deck_upload_status === 'failed'
              ? 'failed'
              : 'pending'
    },
    {
      label: 'Confirm upload',
      status:
        deckUploadStage === 'confirming'
          ? 'running'
          : ['processing', 'ready'].includes(deckUploadStage)
            ? 'complete'
            : deck_upload_status === 'failed'
              ? 'failed'
              : 'pending'
    },
    {
      label: 'Process deck',
      status:
        deckUploadStage === 'processing'
          ? 'running'
          : deckUploadStage === 'ready'
            ? 'complete'
            : deck_upload_status === 'failed'
              ? 'failed'
              : 'pending'
    },
    {
      label: 'Load workspace',
      status: deckLoaderTransitioning ? 'running' : deckUploadStage === 'ready' ? 'complete' : 'pending'
    }
  ] satisfies Array<{ label: string; status: 'pending' | 'running' | 'complete' | 'failed' }>);
  const active_step = $derived.by(() => {
    if (!deckUploadComplete) return 1;
    if (!brandStepReady) return 2;
    return 3;
  });

  const saveConfirmation = $derived.by<SaveConfirmationBannerModel | null>(() => {
    if (deck_upload_status === 'failed') {
      return {
        title: 'Deck save failed',
        message: uploadError || 'Try the upload again or choose a different file.',
        tone: 'danger'
      };
    }

    if (uploadConfirmation) {
      return {
        title: uploadConfirmation.title,
        message: uploadConfirmation.message,
        tone: uploadConfirmation.tone
      };
    }

    return null;
  });

  const stepStates = $derived([
    { label: firstBatchMode === 'slide_miniatures' ? 'Upload deck' : 'Create source version', complete: deckUploadComplete, active: active_step === 1 },
    { label: firstBatchMode === 'logo_branding' ? 'Load logo brand' : firstBatchMode === 'url_branding' ? 'Load URL brand' : 'Load brand', complete: brandStepReady, active: active_step === 2 },
    { label: 'Review brand', complete: brandApproved, active: active_step === 3 },
    { label: 'Choose style', complete: false, active: false },
    { label: preferredWorkspace === 'instant_deck' ? 'Create Instant Deck' : 'Create Smart Deck', complete: false, active: false }
  ]);
  const sourceSlides = $derived(persistedSourceSlides.slice(0, 4));
  const sourceMediaAssets = $derived(
    sourceSlides
      .flatMap((slide) =>
        Array.isArray(slide.assets)
          ? slide.assets.map((asset: WorkflowSourceAsset) => ({
              ...asset,
              slideIndex: slide.slideIndex
            }))
          : []
      )
      .filter((asset) => asset.assetType === 'embedded_image' && typeof asset.assetUrl === 'string')
      .slice(0, 4)
  );
  const sourceSlideCount = $derived(sourceSlides.length);
  const developerToolsPayload = $derived(
    createDeveloperToolsPayload({
      route: {
        canonicalPath: '/decks/new',
        routeStatus: authExpired ? 'mounted_but_degraded' : 'mounted_and_wired',
        routeNotice: null
      },
      subject: {
        workspaceId: null,
        deckId: deckId || null,
        audience: 'Investment Committee',
        activeDeckId: workspaceDecksState.selectedDeckId || null
      },
      load: {
        requestedAt: pageMountedAt || null,
        loadedAt: workspaceDecksLastLoadedAt ? new Date(workspaceDecksLastLoadedAt).toISOString() : uploadSessionLoadedAt || null,
        loadDurationMs: null
      },
      correlation: {
        backendStatus: null,
        requestId: (uploadRequestId || (latestProcessingStatus as { requestId?: string | null } | null)?.requestId) ?? null,
        ticketId: (uploadFailureTicketId || (latestProcessingStatus as { ticketId?: string | null } | null)?.ticketId) ?? null,
        backendPath: uploadDeckPath,
        message: uploadError || authExpiredMessage || null
      },
      workflow: {
        status: deckUploadStage,
        nextAction: latestProcessingStatus?.nextAction ?? null,
        activeStage: latestProcessingStatus?.activeStage ?? latestProcessingStatus?.processingStage ?? null,
        runId: null,
        jobId: null,
        canRetry: latestProcessingStatus?.canRetry ?? null,
        canOpenSmartDeck: latestProcessingStatus?.canOpenSmartDeck ?? null
      },
      artifacts: {
        sourceFileStatus: deckSourceFileStatus || null,
        sourceSlideCount: persistedSourceSlides.length,
        generatedSlideCount: null,
        latestExportId: null,
        latestExportType: null,
        activeDesignVersionId: null,
        activeGeneratedSlideId: null,
        knowledgePackageName: null,
        knowledgePackageVersion: null
      },
      degradation: {
        status: authExpired || deckUploadStage === 'failed' ? 'degraded' : 'ready',
        issues:
          authExpired || deckUploadStage === 'failed'
            ? [
                {
                  key: 'upload',
                  label: 'Upload',
                  status: null,
                  requestId: uploadRequestId || null,
                  ticketId: uploadFailureTicketId || queueFailureTicketId || null,
                  message: uploadError || authExpiredMessage || 'Upload flow is degraded.'
                }
              ]
            : [],
        actionHref: deckId ? `/decks/${deckId}/processing` : null,
        actionLabel: deckId ? 'View processing' : null
      },
      dependencies: [
        createDependencyStatus('upload-session', 'Upload session', {
          requestId: uploadSessionRequestId || null,
          backendPath: uploadSessionPath
        }),
        createDependencyStatus('upload', 'Upload', {
          requestId: uploadRequestId || null,
          ticketId: uploadFailureTicketId || null,
          backendPath: uploadDeckPath,
          message: uploadError || null
        }),
        createDependencyStatus('first-batch', 'First batch', {
          ticketId: queueFailureTicketId || null,
          backendPath: firstBatchPath
        }),
        createDependencyStatus('workflow-state', 'Workflow state', {
          requestId: (latestProcessingStatus as { requestId?: string | null } | null)?.requestId ?? null,
          ticketId: (latestProcessingStatus as { ticketId?: string | null } | null)?.ticketId ?? null,
          backendPath: deckId ? deckProductApiPath(`/decks/${deckId}/workflow-state`) : null
        })
      ]
    })
  );
  const developerVisibilityItems = $derived(
    createDeveloperVisibilityItems(developerToolsPayload, [
      { label: 'Workflow request id', value: (latestProcessingStatus as { requestId?: string | null } | null)?.requestId ?? null },
      { label: 'Workflow failure ticket', value: (latestProcessingStatus as { ticketId?: string | null } | null)?.ticketId ?? null },
      { label: 'Workflow next action', value: latestProcessingStatus?.nextAction ?? null },
      { label: 'First batch mode', value: firstBatchMode },
      { label: 'Page mounted at', value: pageMountedAt || null },
      { label: 'Workspace decks loaded at', value: workspaceDecksLastLoadedAt ? new Date(workspaceDecksLastLoadedAt).toISOString() : null },
      { label: 'Brand status', value: brand_status },
      { label: 'Upload session loaded at', value: uploadSessionLoadedAt || null },
      { label: 'Queue ticket', value: queueFailureTicketId || null },
      { label: 'Selected workspace row', value: workspaceDecksState.selectedDeckId || null },
      { label: 'Auth expired', value: authExpired }
    ])
  );

  onMount(() => {
    pageMountedAt = new Date().toISOString();
    void loadWorkspaceDecks(true, true);

    const previousBodyOverflow = document.body.style.overflow;
    const previousHtmlOverflow = document.documentElement.style.overflow;

    document.body.style.overflow = 'hidden';
    document.documentElement.style.overflow = 'hidden';

    return () => {
      if (localLogoPreviewUrl) {
        URL.revokeObjectURL(localLogoPreviewUrl);
      }
      document.body.style.overflow = previousBodyOverflow;
      document.documentElement.style.overflow = previousHtmlOverflow;
    };
  });
</script>

<AppShell
  title="New deck"
  activeNav="upload"
  showTopBar={false}
  showFooterUtilities={true}
  showTopBarCopy={false}
  compactTopBar={true}
  showTopBarSearch={false}
  deckLabel="Deck"
>
  <section class="upload-page">
    <div class="upload-page__header">
      <div class="eyebrow">Upload</div>
      <h2>Drop your deck</h2>
      <p class="muted">PDF or PowerPoint. AI analysis starts automatically.</p>

      {#if showHeroStepper}
        <ol class="upload-stepper" aria-label="Deck creation steps">
          {#each stepStates as step}
            <li class:active={step.active} class:complete={step.complete}>{step.label}</li>
          {/each}
        </ol>
      {/if}
    </div>

    <div class="upload-page__grid">
      <UploadDeck
        accept={acceptedDeckTypes}
        {deckId}
        {deckFile}
        {deckDragActive}
        deckUploadStatus={deck_upload_status}
        deckExtractionStatus={deck_extraction_status}
        {uploadError}
        {saveConfirmation}
        {canContinueAfterUpload}
        buttonLabel={continueButtonLabel}
        {workspaceDecks}
        workspaceDecksLoading={workspaceDecksLoading}
        onDeckSelection={handleDeckSelection}
        onDeckDragEnter={handleDeckDragEvent}
        onDeckDragLeave={handleDeckDragLeave}
        onDeckDrop={handleDeckDrop}
        onSelectDeck={handleExistingDeckSelection}
        onRetryDeck={(targetDeckId) => void retryWorkspaceDeck(targetDeckId)}
        onRemoveDeck={(targetDeckId) => void removeWorkspaceDeck(targetDeckId)}
        onContinue={() => (brandModalOpen = true)}
        {formatFileSize}
      />

      <div class="upload-page__brand-profile">
        <BrandProfileCard
          {companyUrl}
          {logoFile}
          logoPreviewUrl={localLogoPreviewUrl}
          {logoDragActive}
          {acceptedLogoTypes}
          brandStatus={brand_status}
          brandError={brandError}
          {brandProfile}
          {brandApproved}
          {deckUploadComplete}
          {hasBrandSourceInput}
          {canExtractBrand}
          canContinue={canContinueFromBrandReview}
          modeLabel={firstBatchMode}
          {formatFileSize}
          onCompanyUrlChange={handleCompanyUrlChange}
          onLogoDragEnter={handleLogoDragEvent}
          onLogoDragLeave={handleLogoDragLeave}
          onLogoDrop={handleLogoDrop}
          onLogoFileChange={handleLogoFile}
          onExtract={extractBrand}
          onReview={() => (brandModalOpen = true)}
          onContinue={continueFromBrandReview}
        />
      </div>
    </div>

    {#if deckId && deck_upload_status === 'saved'}
      <section class="panel source-panel">
        <div class="source-panel__head">
          <div class="eyebrow">Source</div>
          <span class="muted">
            {#if persistedSourceLoading}
              Loading...
            {:else if deck_extraction_status === 'ready'}
              {sourceSlideCount} slides extracted
            {:else}
              Processing...
            {/if}
          </span>
        </div>

        <div class="source-panel__meta">
          {#if deckSourceFileStatus}
            <span>File: {deckSourceFileStatus}</span>
          {/if}
          {#if deckStatusSummary}
            <span>{deckStatusSummary}</span>
          {/if}
          {#if deckOriginalFileUrl}
            <span>Source: {deckOriginalFileUrl}</span>
          {/if}
          {#if sourceMediaAssets.length > 0}
            <span>{sourceMediaAssets.length} embedded media previews</span>
          {/if}
        </div>

        {#if sourceSlides.length > 0}
          <div class="source-slides">
            {#each sourceSlides as slide}
              <div class="source-slide">
                <strong>{slide.slideIndex}. {slide.title}</strong>
                <small>{slide.blocks?.length ?? 0} blocks</small>
              </div>
            {/each}
          </div>
        {:else if persistedSourceError}
          <p class="muted">{persistedSourceError}</p>
        {:else}
          <p class="muted">Slides will appear here once extraction finishes.</p>
        {/if}

        {#if deckStatusSteps.length > 0}
          <div class="source-steps" aria-label="Processing phases">
            {#each deckStatusSteps as step}
              <span class="source-step" data-status={step.status}>{step.label}</span>
            {/each}
          </div>
        {/if}
      </section>
    {/if}

    <!-- DISABLED: The false guard hid required deck-scoped product diagnostics. -->
    <!-- {#if false} -->
    {#if true}
      <DeveloperVisibilityCard
        summary="Upload and intake diagnostics for the current workspace. Private cross-workspace telemetry stays in the admin console."
        items={developerVisibilityItems}
      />
    {/if}
  </section>

  {#if brandModalOpen}
  <BrandLoader
    openAsModal={brandModalOpen}
    modalTitle={brandStepReady ? 'Review brand' : 'Add brand'}
    modalSubtitle="Optional. Website, logo, or guidelines improve visual consistency."
    {companyUrl}
    {logoFile}
    logoPreviewUrl={localLogoPreviewUrl}
    {brandGuidelinesFile}
    {logoDragActive}
    {guidelinesDragActive}
    {acceptedLogoTypes}
    {acceptedGuidelineTypes}
    brandStatus={brand_status}
    deckExtractionStatus={deck_extraction_status}
    {brandGuidelinesStatus}
    brandError={brandError}
    {brandProfile}
    {brandApproved}
    {editingBrand}
    {savingBrand}
    brandSaveError={brandSaveError}
    {canExtractBrand}
    canContinue={canContinueFromBrandReview}
    canSkipToSmartDeck={deckUploadComplete}
    {formatFileSize}
    onCompanyUrlChange={(value) => {
      companyUrl = value;
      brandApproved = false;
      brandProfile = null;
      brand_status = 'idle';
    }}
    onLogoDragEnter={handleLogoDragEvent}
    onLogoDragLeave={handleLogoDragLeave}
    onLogoDrop={handleLogoDrop}
    onLogoFileChange={handleLogoFile}
    onGuidelinesDragEnter={handleGuidelinesDragEvent}
    onGuidelinesDragLeave={handleGuidelinesDragLeave}
    onGuidelinesDrop={handleGuidelinesDrop}
    onGuidelinesFileChange={handleGuidelinesFile}
    onExtract={extractBrand}
    onEdit={() => {
      editingBrand = !editingBrand;
      brandApproved = false;
      brandSaveError = '';
    }}
    onApprove={() => (brandApproved = true)}
    onContinue={continueFromBrandReview}
    onClose={() => (brandModalOpen = false)}
    onSaveBrand={saveBrandSelection}
    onSkipToSmartDeck={skipToSmartDeck}
  />
  {/if}

  <DeckLoaderOverlay
    open={deckLoaderOpen}
    title={deckLoaderTitle}
    subtitle={deckLoaderSubtitle}
    statusLabel={deckLoaderStatusLabel}
    progress={deckLoaderTransitioning ? Math.max(uploadProgress, 92) : uploadProgress}
    steps={deckLoaderSteps}
    errorMessage={deck_upload_status === 'failed' ? uploadError : ''}
  />
</AppShell>

<style>
  .upload-page { display: grid; gap: 16px; padding-bottom: 24px; }

  .upload-page__header { display: grid; gap: 6px; }
  .upload-page__header h2 { font-size: 20px; }
  .upload-page__header p { font-size: 13px; }

  .upload-stepper { display: flex; flex-wrap: wrap; gap: 8px; margin: 4px 0 0; padding: 0; list-style: none; }
  .upload-stepper li {
    padding: 4px 8px; border: 1px solid var(--border); border-radius: 999px;
    color: var(--text-muted); font-size: 11px;
  }
  .upload-stepper li.active { color: var(--text); border-color: var(--accent); }
  .upload-stepper li.complete { color: var(--text); }

  .upload-page__grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; align-items: start; }
  .upload-page__brand-profile {
    position: sticky;
    top: 16px;
    max-height: calc(100dvh - 128px);
    overflow-y: auto;
  }

  .source-panel { padding: 16px; display: grid; gap: 12px; }
  .source-panel__head { display: flex; justify-content: space-between; align-items: center; }
  .source-panel__meta { display: flex; flex-wrap: wrap; gap: 8px; font-size: 11px; color: var(--text-muted); }
  .source-slides { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; }
  .source-slide {
    padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius);
    background: var(--bg-subtle); display: grid; gap: 2px;
  }
  .source-slide strong { font-size: 13px; }
  .source-slide small { font-size: 11px; color: var(--text-muted); }
  .source-steps { display: flex; flex-wrap: wrap; gap: 6px; }
  .source-step {
    padding: 3px 7px; border: 1px solid var(--border); border-radius: 999px;
    color: var(--text-muted); font-size: 11px;
  }
  .source-step[data-status='complete'] { color: var(--text); }
  .source-step[data-status='failed'] { color: var(--danger); }

  @media (max-width: 900px) {
    .upload-page__grid { grid-template-columns: 1fr; }
    .upload-page__brand-profile {
      position: static;
      max-height: none;
      overflow: visible;
    }
  }
</style>
