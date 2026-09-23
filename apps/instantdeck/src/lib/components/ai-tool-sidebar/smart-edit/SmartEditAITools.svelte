<script lang="ts">
  type SuggestionView = {
    text: string;
    reason: string;
    status: string;
    generated: string;
  };

  interface Props {
    contextLabel: string;
    selectedTargetLabel: string;
    instruction: string;
    workspaceStatus: string;
    workflowStatus: string | null;
    workflowIntentSummary: string;
    workflowMissingInputs: string[];
    suggestion: SuggestionView | null;
    suggestionIsPending: boolean;
    suggestionIsNoChange: boolean;
    smartEditStatus: 'idle' | 'generating' | 'saving' | 'saved' | 'failed';
    smartEditError: string;
    fieldSaved: boolean;
    fieldPreviewReady: boolean;
    fieldStatus: string;
    fieldError: string;
    currentWorkflowRunId: string | null;
    loadingLatestRun: boolean;
    hasSelectedSlide: boolean;
    hasSelectedBlock: boolean;
    hasSelectedElement: boolean;
    canReviewVisualVariation: boolean;
    variationState: 'idle' | 'generating' | 'ready' | 'saving' | 'discarding' | 'error';
    variationBusy: boolean;
    variationMessage: string;
    variationError: string;
    origin: string | null;
    panelElement?: HTMLElement | null;
    onRefreshResult: () => void;
    onInstructionChange: (instruction: string) => void;
    onApplySavedDraft: () => void;
    onCreateRevision: () => void;
    onDismissRevision: () => void;
    onAcceptRevision: () => void;
    onRegenerateElement: () => void;
    onRegenerateSlide: () => void;
    onSelectBackground: () => void;
    onSelectSlideContent: () => void;
    onSelectSlideRedesign: () => void;
    onDiscardVariation: () => void;
    onSaveVariation: () => void;
    onReturnToOrigin: () => void;
  }

  let {
    contextLabel,
    selectedTargetLabel,
    instruction,
    workspaceStatus,
    workflowStatus,
    workflowIntentSummary,
    workflowMissingInputs,
    suggestion,
    suggestionIsPending,
    suggestionIsNoChange,
    smartEditStatus,
    smartEditError,
    fieldSaved,
    fieldPreviewReady,
    fieldStatus,
    fieldError,
    currentWorkflowRunId,
    loadingLatestRun,
    hasSelectedSlide,
    hasSelectedBlock,
    hasSelectedElement,
    canReviewVisualVariation,
    variationState,
    variationBusy,
    variationMessage,
    variationError,
    origin,
    panelElement = $bindable(null),
    onRefreshResult,
    onInstructionChange,
    onApplySavedDraft,
    onCreateRevision,
    onDismissRevision,
    onAcceptRevision,
    onRegenerateElement,
    onRegenerateSlide,
    onSelectBackground,
    onSelectSlideContent,
    onSelectSlideRedesign,
    onDiscardVariation,
    onSaveVariation,
    onReturnToOrigin
  }: Props = $props();
</script>

<div class="smart-edit-tools">
  <section class="tool-section" aria-labelledby="revision-title">
    <div class="section-head">
      <div>
        <span>Revision</span>
        <strong id="revision-title">Review selected content</strong>
      </div>
      <span class="context-chip">{contextLabel}</span>
    </div>

    <div class="review-state" aria-live="polite">
      <span>{fieldSaved ? 'Draft saved for review' : fieldPreviewReady ? 'Impact preview ready' : workspaceStatus}</span>
      <div class="inline-actions">
        {#if currentWorkflowRunId}
          <button type="button" class="text-action" onclick={onRefreshResult} disabled={loadingLatestRun}>
            {loadingLatestRun ? 'Loading...' : 'Refresh result'}
          </button>
        {/if}
        <button type="button" class="text-action" onclick={onApplySavedDraft} disabled={!fieldSaved || fieldStatus === 'applying'}>
          {fieldStatus === 'applying' ? 'Applying...' : 'Apply saved draft'}
        </button>
      </div>
    </div>

    {#if workflowStatus || suggestion}
      <div class="result-card">
        <span>Revision status</span>
        <strong>{suggestion?.generated ?? workflowStatus ?? 'Awaiting generation'}</strong>
        <p>{workflowIntentSummary}</p>
        {#if workflowMissingInputs.length}
          <div class="missing-inputs">
            {#each workflowMissingInputs as item}<span>{item}</span>{/each}
          </div>
        {/if}
      </div>
    {/if}

    {#if suggestion}
      <div class="result-card result-card--suggestion">
        <span>Suggested revision</span>
        <p>{suggestionIsNoChange ? 'No text change is recommended for this section. Your existing text remains unchanged.' : suggestion.text}</p>
        <small>{suggestion.reason}</small>
      </div>
    {/if}

    <label class="tool-instruction">
      <span>Edit instruction</span>
      <textarea
        rows="5"
        value={instruction}
        maxlength="500"
        aria-describedby="smart-edit-instruction-help smart-edit-instruction-count"
        placeholder="Describe the reviewable slide, element, or text change."
        oninput={(event) => onInstructionChange((event.currentTarget as HTMLTextAreaElement).value)}
      ></textarea>
      <small id="smart-edit-instruction-help">Describe the selected slide, element, or text change that should become a reviewable candidate.</small>
      <small id="smart-edit-instruction-count">{instruction.length}/500</small>
    </label>

    <div class="action-grid">
      <button type="button" onclick={onCreateRevision} disabled={!hasSelectedBlock || smartEditStatus === 'generating' || !instruction.trim()}>
        {smartEditStatus === 'generating' ? 'Creating...' : 'Create revision'}
      </button>
      {#if !suggestionIsNoChange}
        <button type="button" onclick={onDismissRevision} disabled={!hasSelectedBlock || !suggestionIsPending || smartEditStatus === 'saving'}>Dismiss</button>
        <button type="button" class="primary" onclick={onAcceptRevision} disabled={!hasSelectedBlock || !suggestionIsPending || smartEditStatus === 'saving'}>
          {smartEditStatus === 'saving' ? 'Saving...' : 'Accept change'}
        </button>
      {/if}
    </div>
    {#if smartEditError}<p class="error" aria-live="polite">{smartEditError}</p>{/if}
    {#if fieldError}<p class="error" aria-live="polite">{fieldError}</p>{/if}
  </section>

  <section bind:this={panelElement} class="tool-section" aria-labelledby="variation-title" tabindex="-1">
    <div class="section-head">
      <div>
        <span>Visual variation</span>
        <strong id="variation-title">{selectedTargetLabel}</strong>
      </div>
      <span class="context-chip">{canReviewVisualVariation ? 'Unsaved' : 'Saved'}</span>
    </div>
    <p class="muted">{variationMessage || 'Create a reviewable visual variation without changing the saved version.'}</p>
    <div class="prompt-starters" aria-label="Visual variation prompt starters">
      <button type="button" onclick={onSelectBackground}>Background</button>
      <button type="button" onclick={onSelectSlideContent}>Slide content</button>
      <button type="button" onclick={onSelectSlideRedesign}>Full slide</button>
    </div>
    <div class="action-grid action-grid--variation">
      <button type="button" onclick={onRegenerateElement} disabled={!hasSelectedElement || variationBusy || !instruction.trim()}>
        {variationState === 'generating' && hasSelectedElement ? 'Generating element...' : 'Regenerate element'}
      </button>
      <button type="button" onclick={onRegenerateSlide} disabled={!hasSelectedSlide || variationBusy || !instruction.trim()}>
        {variationState === 'generating' && !hasSelectedElement ? 'Generating slide...' : 'Regenerate slide'}
      </button>
      <button type="button" onclick={onDiscardVariation} disabled={!canReviewVisualVariation || variationBusy}>
        {variationState === 'discarding' ? 'Discarding...' : 'Discard variation'}
      </button>
      <button type="button" class="primary" onclick={onSaveVariation} disabled={!canReviewVisualVariation || variationBusy}>
        {variationState === 'saving' ? 'Saving...' : 'Save this version'}
      </button>
    </div>
    {#if variationError}<p class="error" aria-live="polite">{variationError}</p>{/if}
  </section>

  {#if origin}
    <button type="button" class="return-action" onclick={onReturnToOrigin}>
      Return to {origin === 'smart-deck' ? 'Smart Deck' : origin === 'due-diligence' ? 'Due Diligence' : 'workspace'}
    </button>
  {/if}
</div>

<style>
  .smart-edit-tools {
    display: grid;
    gap: 0.85rem;
  }

  .tool-section {
    display: grid;
    gap: 0.75rem;
    padding: 0.85rem;
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 14px;
    background: rgba(15, 23, 42, 0.72);
  }

  .section-head,
  .review-state {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.65rem;
  }

  .section-head > div {
    min-width: 0;
    display: grid;
    gap: 0.15rem;
  }

  .section-head > div > span,
  .result-card > span,
  .tool-instruction > span {
    color: #818cf8;
    font-size: 0.66rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .section-head strong {
    color: #f8fafc;
    font-size: 0.88rem;
  }

  .context-chip,
  .missing-inputs span {
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 999px;
    padding: 0.28rem 0.5rem;
    color: #cbd5e1;
    font-size: 0.7rem;
    white-space: nowrap;
  }

  .review-state {
    align-items: flex-start;
    padding-block: 0.65rem;
    border-block: 1px solid rgba(148, 163, 184, 0.14);
    color: #94a3b8;
    font-size: 0.76rem;
  }

  .inline-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.55rem;
    flex-wrap: wrap;
  }

  button {
    min-height: 38px;
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 10px;
    background: rgba(30, 41, 59, 0.72);
    color: #e2e8f0;
    padding: 0.5rem 0.65rem;
    font: inherit;
    font-size: 0.74rem;
    font-weight: 700;
    cursor: pointer;
  }

  button:disabled {
    cursor: not-allowed;
    opacity: 0.45;
  }

  button.primary {
    border-color: rgba(99, 102, 241, 0.72);
    background: #4f46e5;
    color: white;
  }

  .text-action {
    min-height: auto;
    border: 0;
    background: transparent;
    color: #818cf8;
    padding: 0;
  }

  .result-card,
  .tool-instruction {
    display: grid;
    gap: 0.35rem;
    padding: 0.75rem;
    border: 1px solid rgba(148, 163, 184, 0.14);
    border-radius: 12px;
    background: rgba(2, 6, 23, 0.34);
  }

  .result-card--suggestion {
    border-color: rgba(129, 140, 248, 0.28);
  }

  .result-card p,
  .muted {
    margin: 0;
    color: #cbd5e1;
    font-size: 0.78rem;
    line-height: 1.45;
  }

  .result-card small,
  .muted {
    color: #94a3b8;
  }

  .tool-instruction textarea {
    min-height: 7rem;
    resize: vertical;
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 10px;
    background: rgba(2, 6, 23, 0.48);
    color: #f8fafc;
    padding: 0.65rem;
    font: inherit;
  }

  .tool-instruction small {
    justify-self: end;
    color: #64748b;
  }

  .missing-inputs {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }

  .action-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.5rem;
  }

  .prompt-starters {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }

  .prompt-starters button {
    min-height: 32px;
    border-radius: 999px;
    padding: 0.35rem 0.55rem;
  }

  .action-grid--variation {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .error {
    margin: 0;
    color: #fca5a5;
    font-size: 0.78rem;
  }

  .return-action {
    width: 100%;
    background: transparent;
  }

  @media (max-width: 1100px) {
    .action-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
