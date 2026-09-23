<script lang="ts">
  import ExportOptionCard from '$components/ExportOptionCard.svelte';
  import { deckProductApiPath } from '$lib/contracts';
  import { trackDeckEvent } from '$lib/analytics/deckAnalytics';
  import { createHtmlDeckExport, waitForWorkflowJobCompletion } from '$lib/api/deckService/workflow.client';
  import type { DeckExport } from '$types/domain';

  interface Props {
    deckId: string;
    designVersionId?: string | null;
    exports: DeckExport[];
    savedResponseGroups?: SavedResponseGroup[];
    savedResponsesError?: string | null;
  }

  interface SavedResponseItem {
    id: string;
    deckId: string;
    slideId: string;
    slideNumber: number;
    slideTitle: string;
    promptSlug: string;
    createdAt: string;
  }

  interface SavedResponseGroup {
    slideId: string;
    slideNumber: number;
    slideTitle: string;
    items: SavedResponseItem[];
  }

  interface SavedResponsePreview {
    id: string;
    deckId: string;
    slideId: string;
    promptSlug: string;
    markdownContent: string;
    createdAt: string;
  }

  let { deckId, designVersionId = null, exports, savedResponseGroups = [], savedResponsesError = null }: Props = $props();
  let exportRecords = $state<DeckExport[]>([]);
  let selectedExportType = $state<DeckExport['type']>('final_deck');
  let exportStatus = $state<'idle' | 'generating' | 'ready' | 'failed'>('idle');
  let exportError = $state<string | null>(null);
  let exportSuccessMessage = $state<string | null>(null);
  let includeFindings = $state(true);
  let includeSuggestions = $state(true);
  let includeSmartEdits = $state(true);
  let includeRejected = $state(false);
  let viewedTracked = $state(false);
  let selectedResponseSlideId = $state<string | null>(null);
  let selectedResponse = $state<SavedResponsePreview | null>(null);
  let responsePreviewState = $state<'idle' | 'loading' | 'ready' | 'failed'>('idle');
  let responsePreviewError = $state<string | null>(null);
  let responsePreviewRequestId = 0;

  type WorkflowExportRequest = {
    type?: string;
    exportType?: string;
    format?: string;
    designVersionId?: string | null;
    idempotencyKey: string;
  };

  type WorkflowCommandAcceptedResponse = {
    accepted: boolean;
    jobId: string;
    jobType: string;
    status: string;
    phase: string;
    workflowStateUrl: string;
    jobUrl: string;
  };

  $effect(() => {
    exportRecords = exports;
  });

  $effect(() => {
    if (!savedResponseGroups.some((group) => group.slideId === selectedResponseSlideId)) {
      selectedResponseSlideId = savedResponseGroups[0]?.slideId ?? null;
      selectedResponse = null;
      responsePreviewState = 'idle';
    }
  });

  const selectedResponseGroup = $derived(
    savedResponseGroups.find((group) => group.slideId === selectedResponseSlideId) ?? null
  );

  $effect(() => {
    if (!viewedTracked && deckId) {
      viewedTracked = true;
      void trackDeckEvent(deckId, {
        eventName: 'export.page.viewed',
        surface: 'export_page',
        entityType: 'deck',
        entityId: deckId,
        metadata: { existingExportCount: exportRecords.length }
      });
    }
  });

  const exportOptions = [
    {
      type: 'final_deck',
      title: 'Final deck package',
      detail: 'The latest accepted version of the deck, packaged for handoff and review.'
    },
    {
      type: 'diligence_report',
      title: 'Diligence report',
      detail: 'Findings, risks, and audience-fit commentary for investment review.'
    },
    {
      type: 'adapted_outline',
      title: 'Adapted outline',
      detail: 'A rewritten story structure for the selected audience.'
    },
    {
      type: 'change_log',
      title: 'Change log',
      detail: 'Accepted, rejected, and edited AI changes with review trace.'
    },
    {
      type: 'annotated_deck_report',
      title: 'Annotated report',
      detail: 'Slide-by-slide commentary across diligence, messaging, and Smart Edit.'
    }
  ];

  async function getDeckExports(deckId: string): Promise<DeckExport[]> {
    const response = await fetch(`/api/decks/${deckId}/exports`);
    if (!response.ok) {
      throw new Error(await response.text());
    }

    const payload = await response.json().catch(() => null);
    if (!payload || typeof payload !== 'object') {
      return [];
    }

    const exports = (payload as { exports?: DeckExport[] }).exports;
    return Array.isArray(exports) ? exports : [];
  }

  async function startExportWorkflow(deckId: string, payload: WorkflowExportRequest): Promise<WorkflowCommandAcceptedResponse> {
    const requestType = (payload.type ?? payload.exportType ?? '').trim();
    if (!requestType) {
      throw new Error('Export type is required.');
    }

    const response = await fetch(deckProductApiPath(`/decks/${deckId}/workflows/export`), {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        type: requestType,
        exportType: payload.exportType ?? requestType,
        format: payload.format,
        designVersionId: payload.designVersionId ?? null,
        idempotencyKey: payload.idempotencyKey
      })
    });

    const payloadJson = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(
        typeof payloadJson?.message === 'string'
          ? payloadJson.message
          : 'Could not start export workflow.'
      );
    }

    return payloadJson as WorkflowCommandAcceptedResponse;
  }

  function selectExportType(type: DeckExport['type']) {
    selectedExportType = type;
    void trackDeckEvent(deckId, {
      eventName: 'export.option.selected',
      surface: 'export_page',
      entityType: 'export_option',
      entityId: type,
      metadata: { exportType: type }
    });
  }

  function toggleInclusion(name: 'includeFindings' | 'includeSuggestions' | 'includeSmartEdits' | 'includeRejected', value: boolean) {
    if (name === 'includeFindings') includeFindings = value;
    if (name === 'includeSuggestions') includeSuggestions = value;
    if (name === 'includeSmartEdits') includeSmartEdits = value;
    if (name === 'includeRejected') includeRejected = value;
    void trackDeckEvent(deckId, {
      eventName: 'export.include_toggle.changed',
      surface: 'export_page',
      entityType: 'export_toggle',
      entityId: name,
      metadata: { name, value, exportType: selectedExportType }
    });
  }

  async function generateExport() {
    // DISABLED: this early return used to block export generation entirely.
    // The canonical export page now submits a real generation request and
    // exposes the generated file to the deck owner.
    // if (exportReleaseLocked) {
    //   exportStatus = 'failed';
    //   exportError = exportReleaseMessage;
    //   await trackDeckEvent(deckId, {
    //     eventName: 'export.generate.blocked_testing_mode',
    //     surface: 'export_page',
    //     entityType: 'export_option',
    //     entityId: selectedExportType,
    //     metadata: { exportType: selectedExportType }
    //   });
    //   return;
    // }

    exportStatus = 'generating';
    exportError = null;
    exportSuccessMessage = null;
    const clientEventId = `export_${crypto.randomUUID?.() ?? Date.now().toString(36)}`;
    await trackDeckEvent(deckId, {
      eventName: 'export.generate.clicked',
      surface: 'export_page',
      entityType: 'export_option',
      entityId: selectedExportType,
      metadata: {
        clientEventId,
        exportType: selectedExportType,
        includeFindings,
        includeSuggestions,
        includeSmartEdits,
        includeRejected
      }
    });
    try {
      if (selectedExportType === 'final_deck') {
        if (!designVersionId) throw new Error('Select an accepted design version before exporting HTML.');
        const nextExport = await createHtmlDeckExport(deckId, designVersionId);
        const latestExports = await getDeckExports(deckId);
        exportRecords = [nextExport, ...latestExports.filter((item) => item.id !== nextExport.id)];
        exportStatus = 'ready';
        exportSuccessMessage = 'Export generated. Your file is ready to download.';
        return;
      }
      const accepted = await startExportWorkflow(deckId, {
        type: selectedExportType,
        exportType: selectedExportType,
        idempotencyKey: clientEventId
      });
      const existingExportIds = new Set(exportRecords.map((item) => item.id));
      if (!accepted.jobId) {
        throw new Error('Export workflow did not return a job id.');
      }

      const job = await waitForWorkflowJobCompletion(accepted.jobId, 'Export generation failed.');
      if (job.status !== 'completed') {
        throw new Error('Export generation failed to complete.');
      }

      const latestExports = await getDeckExports(deckId);
      const jobOutput = (job.output ?? {}) as Record<string, unknown>;
      const jobExportId = typeof jobOutput.exportId === 'string' && jobOutput.exportId ? jobOutput.exportId : null;
      const candidateById = jobExportId
        ? latestExports.find((item) => item.id === jobExportId) ?? null
        : null;
      const candidateByType = latestExports
        .filter((item) => item.type === selectedExportType && !existingExportIds.has(item.id))
        .sort((a, b) => (Date.parse(b.createdAt) || 0) - (Date.parse(a.createdAt) || 0))[0];

      const nextExport = candidateById || candidateByType;
      if (!nextExport) {
        throw new Error('Export generation completed, but output could not be retrieved.');
      }

      exportRecords = [nextExport, ...latestExports.filter((item) => item.id !== nextExport.id)];
      exportStatus = 'ready';
      exportSuccessMessage = 'Export generated. Your file is ready to download.';
      await trackDeckEvent(deckId, {
        eventName: 'export.generate.succeeded',
        surface: 'export_page',
        entityType: 'deck_export',
        entityId: nextExport.id,
        metadata: { clientEventId, exportType: selectedExportType, releaseStatus: 'ready' }
      });
    } catch (error) {
      exportStatus = 'failed';
      exportError = error instanceof Error ? error.message : 'Export generation failed.';
      exportSuccessMessage = null;
      await trackDeckEvent(deckId, {
        eventName: 'export.generate.failed',
        surface: 'export_page',
        entityType: 'export_option',
        entityId: selectedExportType,
        metadata: { clientEventId, exportType: selectedExportType, message: exportError }
      });
    }
  }

  function trackDownload(item: DeckExport) {
    void trackDeckEvent(deckId, {
      eventName: 'export.download.clicked',
      surface: 'export_page',
      entityType: 'deck_export',
      entityId: item.id,
      metadata: { exportType: item.type }
    });
  }

  async function openSavedResponse(item: SavedResponseItem) {
    const requestId = ++responsePreviewRequestId;
    responsePreviewState = 'loading';
    responsePreviewError = null;
    selectedResponse = null;
    try {
      const response = await fetch(`/api/decks/${deckId}/saved-response-exports/${item.id}`);
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(typeof payload?.message === 'string' ? payload.message : 'Could not open saved response.');
      }
      if (requestId !== responsePreviewRequestId) return;
      selectedResponse = payload as SavedResponsePreview;
      responsePreviewState = 'ready';
    } catch (error) {
      if (requestId !== responsePreviewRequestId) return;
      responsePreviewState = 'failed';
      responsePreviewError = error instanceof Error ? error.message : 'Could not open saved response.';
    }
  }
</script>

<section class="export-panel">
  <div class="export-grid">
    <div class="section-stack">
      <section class="header">
        <div>
          <div class="eyebrow">Export</div>
          <h3>Create your presentation package</h3>
          <p class="muted">Choose an output, generate it, and download the finished file.</p>
        </div>
      </section>

      <div class="options">
        {#each exportOptions as option}
          <button
            class="option-button"
            type="button"
            class:selected={selectedExportType === option.type}
            onclick={() => selectExportType(option.type)}
          >
            <ExportOptionCard
              title={option.title}
              detail={option.detail}
              state={selectedExportType === option.type ? 'selected' : exportRecords.some((item) => item.type === option.type) ? 'ready' : 'idle'}
            />
          </button>
        {/each}
      </div>

      <section class="inclusion-panel">
        <!-- DISABLED: Inclusion choices were local-only and never reached the export workflow or renderer.
             They remain preserved here until the request schema and export service support them. -->
        {#if false}
        <div class="eyebrow">Planned export options</div>
        <label><input type="checkbox" checked={includeFindings} onchange={(event) => toggleInclusion('includeFindings', event.currentTarget.checked)} /> Due diligence findings</label>
        <label><input type="checkbox" checked={includeSuggestions} onchange={(event) => toggleInclusion('includeSuggestions', event.currentTarget.checked)} /> Audience recommendations</label>
        <label><input type="checkbox" checked={includeSmartEdits} onchange={(event) => toggleInclusion('includeSmartEdits', event.currentTarget.checked)} /> Smart Edit revisions</label>
        <label><input type="checkbox" checked={includeRejected} onchange={(event) => toggleInclusion('includeRejected', event.currentTarget.checked)} /> Dismissed suggestions</label>
        {/if}
        <div class="actions">
          <button class="button" type="button" disabled={exportStatus === 'generating'} onclick={generateExport}>
            {exportStatus === 'generating' ? 'Generating file...' : 'Generate file'}
          </button>
          <span class="muted">{selectedExportType.replace(/_/g, ' ')}</span>
        </div>
        {#if exportSuccessMessage}
          <p class="export-success">{exportSuccessMessage}</p>
        {/if}
        {#if exportError}
          <p class="export-error">{exportError}</p>
        {/if}
      </section>

      <section class="saved-responses" aria-label="Saved insight responses">
        <div class="saved-responses__head">
          <div>
            <div class="eyebrow">Saved responses</div>
            <strong>Markdown documents by slide</strong>
          </div>
          <span class="muted">{savedResponseGroups.reduce((count, group) => count + group.items.length, 0)} documents</span>
        </div>

        {#if savedResponsesError}
          <div class="saved-responses__degraded" role="status">{savedResponsesError}</div>
        {/if}

        {#if savedResponseGroups.length}
          <div class="saved-responses__slide-rail" role="tablist" aria-label="Slides with saved responses">
            {#each savedResponseGroups as group}
              <button type="button" role="tab" aria-selected={group.slideId === selectedResponseSlideId} class:active={group.slideId === selectedResponseSlideId} onclick={() => { responsePreviewRequestId += 1; selectedResponseSlideId = group.slideId; selectedResponse = null; responsePreviewState = 'idle'; }}>
                <span>Slide {group.slideNumber}</span>
                <strong>{group.slideTitle}</strong>
                <small>{group.items.length} saved</small>
              </button>
            {/each}
          </div>

          <div class="saved-responses__workspace">
            <div class="saved-responses__cards">
              {#each selectedResponseGroup?.items ?? [] as item}
                <button type="button" class="markdown-card" onclick={() => void openSavedResponse(item)}>
                  <span class="markdown-card__mark">MD</span>
                  <strong>{item.promptSlug}.md</strong>
                  <small>{new Date(item.createdAt).toLocaleString()}</small>
                </button>
              {/each}
            </div>

            <div class="saved-responses__preview" aria-live="polite">
              {#if responsePreviewState === 'loading'}
                <p class="muted">Opening markdown preview...</p>
              {:else if responsePreviewError}
                <p class="export-error">{responsePreviewError}</p>
              {:else if selectedResponse}
                <div class="saved-responses__preview-head">
                  <strong>{selectedResponse.promptSlug}.md</strong>
                  <span class="muted">In-app preview</span>
                </div>
                <pre>{selectedResponse.markdownContent}</pre>
              {:else}
                <p class="muted">Select a markdown card to preview the saved response and its Sources section.</p>
              {/if}
            </div>
          </div>
        {:else if !savedResponsesError}
          <div class="empty-state">
            <p class="muted">No saved responses yet. Use Save this response from the Smart Deck assistant to create the first markdown document.</p>
          </div>
        {/if}
      </section>
    </div>

    <aside class="completed-panel">
      <div class="eyebrow">Recent exports</div>
      <strong>Latest generated files</strong>
      {#if exportRecords.length}
        {#each exportRecords as item}
          <article class="export-item">
            <div class="topline">
              <strong>{item.type}{item.format === 'html' ? ' · HTML' : ''}</strong>
              <span class="muted">{new Date(item.createdAt).toLocaleString()}</span>
            </div>
            {#if item.designVersionId}
              <small class="muted">Design version: {item.designVersionId}</small>
            {/if}
            <a
              class="button secondary"
              href={`/api/decks/${deckId}/exports/${item.id}/download`}
              onclick={() => trackDownload(item)}
            >Download export</a>
          </article>
        {/each}
      {:else}
        <div class="empty-state">
          <p class="muted">No export records yet. Generate a diligence report or adapted outline to create the first review artifact.</p>
        </div>
      {/if}
    </aside>
  </div>
</section>

<style>
  .export-panel {
    padding: clamp(0.25rem, 1vw, 1rem);
  }

  .export-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
    gap: 1rem;
  }

  .header,
  .topline,
  .actions {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .options {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 1rem;
  }

  .option-button {
    display: block;
    padding: 0;
    border: 0;
    color: inherit;
    background: transparent;
    text-align: left;
    cursor: pointer;
  }

  .option-button:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 4px;
    border-radius: var(--radius-md);
  }

  .inclusion-panel,
  .saved-responses,
  .completed-panel,
  .export-item {
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    padding: 1rem;
    background: rgba(255,255,255,0.03);
  }

  .inclusion-panel {
    display: grid;
    gap: 0.8rem;
  }

  .inclusion-panel label {
    display: flex;
    align-items: center;
    gap: 0.65rem;
  }

  .completed-panel {
    display: grid;
    gap: 0.9rem;
    align-content: start;
  }

  .empty-state {
    border: 1px dashed var(--line);
    border-radius: 14px;
    padding: 1rem;
  }

  .export-error {
    margin: 0;
    color: #fecaca;
  }

  .export-success {
    margin: 0;
    color: #bbf7d0;
  }

  .saved-responses,
  .saved-responses__workspace,
  .saved-responses__cards,
  .saved-responses__preview {
    display: grid;
    gap: 0.9rem;
  }

  .saved-responses__head,
  .saved-responses__preview-head {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .saved-responses__slide-rail {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.75rem;
  }

  .saved-responses__slide-rail button,
  .markdown-card {
    display: grid;
    gap: 0.3rem;
    text-align: left;
    padding: 0.8rem;
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    background: rgba(255,255,255,0.02);
    color: inherit;
  }

  .saved-responses__slide-rail button.active {
    border-color: var(--accent);
  }

  .markdown-card__mark {
    font-size: 0.72rem;
    color: #93c5fd;
    font-weight: 700;
    text-transform: uppercase;
  }

  .saved-responses__preview pre {
    margin: 0;
    padding: 1rem;
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    background: rgba(15,23,42,0.6);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .saved-responses__degraded {
    padding: 0.75rem;
    border: 1px solid rgba(253, 164, 175, 0.3);
    border-radius: var(--radius-md);
    color: #fda4af;
  }

  pre {
    white-space: pre-wrap;
    margin: 0.8rem 0 0;
    font-family: inherit;
  }

  @media (max-width: 980px) {
    .export-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
