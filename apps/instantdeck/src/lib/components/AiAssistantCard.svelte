<script lang="ts">
  import InfoBubble from '$components/smart-deck/InfoBubble.svelte';

  type AssistantSlideOption = {
    id: string;
    title: string;
  };

  type AssistantIntentType =
    | 'market_size'
    | 'market_research'
    | 'financial_projection'
    | 'competitor_landscape'
    | 'customer_persona'
    | 'investor_objections'
    | 'narrative_flow'
    | 'slide_critique'
    | 'due_diligence_risks'
    | 'missing_evidence'
    | 'rewrite_for_vc'
    | 'create_design_version';

  type AssistantScope = 'current_slide' | 'selected_slides' | 'whole_deck';
  type AssistantAudience = 'pre_seed' | 'seed_vc' | 'series_a' | 'corporate' | 'internal';
  type AssistantOutputType = 'insight' | 'design_version' | 'critique' | 'research';

  interface AssistantInsight {
    title: string;
    summary: string;
    content: Record<string, unknown>;
    confidence: 'low' | 'medium' | 'high';
    assumptions: string[];
    missingEvidence: string[];
    suggestedSlideUpdate?: string | null;
    recommendedAction: 'save_insight' | 'add_to_slide' | 'create_version' | 'none';
  }

  interface AssistantRun {
    runId: string;
    deckId: string;
    intentType: AssistantIntentType;
    scope: AssistantScope;
    status: 'queued' | 'running' | 'completed' | 'failed';
    outputType: AssistantOutputType;
    provider?: string;
    model?: string | null;
    inputContext?: Record<string, unknown>;
    insight?: AssistantInsight;
    savedArtifactId?: string | null;
    errorMessage?: string | null;
  }

  interface CreateAssistantRunRequest {
    deckId: string;
    intentType: AssistantIntentType;
    scope: AssistantScope;
    currentSlideId?: string | null;
    selectedSlideIds?: string[];
    instruction?: string;
    audience?: AssistantAudience | string | null;
  }

  const assistantIntents: Array<{
    value: AssistantIntentType;
    label: string;
    outputType: AssistantOutputType;
    defaultInstruction: string;
  }> = [
    {
      value: 'market_size',
      label: 'Market size',
      outputType: 'insight',
      defaultInstruction: 'Estimate TAM, SAM and SOM using the deck context and show missing assumptions.'
    },
    {
      value: 'market_research',
      label: 'Market research',
      outputType: 'research',
      defaultInstruction: 'Summarize market claims, evidence quality, and the research needed to strengthen this deck.'
    },
    {
      value: 'financial_projection',
      label: 'Financial projections',
      outputType: 'insight',
      defaultInstruction: 'Review financial projection assumptions, risks, and missing inputs.'
    },
    {
      value: 'competitor_landscape',
      label: 'Competitor landscape',
      outputType: 'research',
      defaultInstruction: 'Assess competitor positioning and suggest clearer differentiation.'
    },
    {
      value: 'customer_persona',
      label: 'Customer persona',
      outputType: 'insight',
      defaultInstruction: 'Infer customer segments and identify evidence needed to validate each persona.'
    },
    {
      value: 'investor_objections',
      label: 'Investor objections',
      outputType: 'insight',
      defaultInstruction: 'Identify likely investor objections and the strongest deck-backed responses.'
    },
    {
      value: 'narrative_flow',
      label: 'Narrative flow',
      outputType: 'critique',
      defaultInstruction: 'Critique the deck sequence and suggest a tighter investor narrative.'
    },
    {
      value: 'slide_critique',
      label: 'Slide critique',
      outputType: 'critique',
      defaultInstruction: 'Critique the selected slide and recommend concrete changes.'
    },
    {
      value: 'due_diligence_risks',
      label: 'Due diligence risks',
      outputType: 'insight',
      defaultInstruction: 'Find diligence risks, unsupported claims, and follow-up questions.'
    },
    {
      value: 'missing_evidence',
      label: 'Missing evidence',
      outputType: 'insight',
      defaultInstruction: 'List the missing evidence that would make the selected claims investor-ready.'
    },
    {
      value: 'rewrite_for_vc',
      label: 'Rewrite for VC',
      outputType: 'critique',
      defaultInstruction: 'Rewrite the selected content for a concise VC pitch while preserving facts.'
    },
    {
      value: 'create_design_version',
      label: 'Create design version',
      outputType: 'design_version',
      defaultInstruction: 'Create a design-version brief that can be passed to Smart Deck generation.'
    }
  ];

  async function readJson<T>(response: Response): Promise<T> {
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(
        typeof payload?.message === 'string'
          ? payload.message
          : typeof payload?.detail === 'string'
            ? payload.detail
            : 'Assistant request failed.'
      );
    }
    return payload as T;
  }

  async function createAssistantRun(payload: CreateAssistantRunRequest): Promise<AssistantRun> {
    const response = await fetch('/api/assistant/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return readJson<AssistantRun>(response);
  }

  interface Props {
    deckId: string;
    audience?: string | null;
    slides?: AssistantSlideOption[];
    currentSlideId?: string | null;
    selectedSlideIds?: string[];
    onAddToSlide?: (run: AssistantRun) => void;
    onCreateDesignVersion?: (run: AssistantRun) => void;
  }

  let {
    deckId,
    audience = null,
    slides = [],
    currentSlideId = null,
    selectedSlideIds = [],
    onAddToSlide,
    onCreateDesignVersion
  }: Props = $props();

  const audienceOptions: Array<{ value: AssistantAudience; label: string }> = [
    { value: 'pre_seed', label: 'Pre-seed' },
    { value: 'seed_vc', label: 'Seed VC' },
    { value: 'series_a', label: 'Series A' },
    { value: 'corporate', label: 'Corporate' },
    { value: 'internal', label: 'Internal' }
  ];

  const scopes: Array<{ value: AssistantScope; label: string }> = [
    { value: 'current_slide', label: 'Current slide' },
    { value: 'selected_slides', label: 'Selected slides' },
    { value: 'whole_deck', label: 'Whole deck' }
  ];

  let intentType = $state<AssistantIntentType>('market_size');
  let scope = $state<AssistantScope>('whole_deck');
  let selectedAudience = $state<AssistantAudience>('seed_vc');
  let instruction = $state(assistantIntents[0].defaultInstruction);
  let status = $state<'idle' | 'running' | 'failed' | 'completed'>('idle');
  let result = $state<AssistantRun | null>(null);
  let errorMessage = $state<string | null>(null);
  let insightSaved = $state(false);

  const selectedIntent = $derived(assistantIntents.find((intent) => intent.value === intentType) ?? assistantIntents[0]);
  const effectiveCurrentSlideId = $derived(currentSlideId ?? selectedSlideIds[0] ?? slides[0]?.id ?? null);
  const effectiveSelectedSlideIds = $derived(selectedSlideIds.length > 0 ? selectedSlideIds : effectiveCurrentSlideId ? [effectiveCurrentSlideId] : []);
  const canGenerate = $derived(Boolean(instruction.trim()) && status !== 'running');
  const recommendedAction = $derived(result?.insight?.recommendedAction ?? 'none');
  const canAddToSlide = $derived(Boolean(result?.insight?.suggestedSlideUpdate));
  const canCreateVersion = $derived(Boolean(result) && (recommendedAction === 'create_version' || selectedIntent.outputType === 'design_version'));
  const isSaved = $derived(insightSaved || Boolean(result?.savedArtifactId));

  $effect(() => {
    if (selectedIntent.defaultInstruction && !result && status === 'idle') {
      instruction = selectedIntent.defaultInstruction;
    }
  });

  function selectIntent(nextIntent: AssistantIntentType) {
    intentType = nextIntent;
    const next = assistantIntents.find((intent) => intent.value === nextIntent);
    if (next) instruction = next.defaultInstruction;
    result = null;
    errorMessage = null;
    status = 'idle';
    insightSaved = false;
  }

  function selectedSlideLabel() {
    if (scope === 'whole_deck') return `${slides.length || 'All'} slides`;
    if (scope === 'current_slide') {
      return slides.find((slide) => slide.id === effectiveCurrentSlideId)?.title ?? 'Current slide';
    }
    return `${effectiveSelectedSlideIds.length} selected slide${effectiveSelectedSlideIds.length === 1 ? '' : 's'}`;
  }

  function renderValue(value: unknown): string {
    if (value == null || value === '') return '';
    if (Array.isArray(value)) return value.map((item) => (typeof item === 'object' ? JSON.stringify(item) : String(item))).join(', ');
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }

  async function generateInsight() {
    if (!canGenerate) return;
    status = 'running';
    errorMessage = null;
    result = null;
    insightSaved = false;

    try {
      const run = await createAssistantRun({
        deckId,
        intentType,
        scope,
        currentSlideId: scope === 'current_slide' ? effectiveCurrentSlideId : null,
        selectedSlideIds: scope === 'selected_slides' ? effectiveSelectedSlideIds : [],
        audience: selectedAudience || audience,
        instruction: instruction.trim()
      });
      result = run;
      status = run.status === 'failed' ? 'failed' : 'completed';
      if (run.status === 'failed') {
        errorMessage = run.errorMessage ?? 'Assistant run failed.';
      }
    } catch (error) {
      status = 'failed';
      errorMessage = error instanceof Error ? error.message : 'Assistant run failed.';
    }
  }

  function addToSlide() {
    if (result && canAddToSlide) onAddToSlide?.(result);
  }

  function createDesignVersion() {
    if (result && canCreateVersion) onCreateDesignVersion?.(result);
  }
</script>

<section class="panel ai-assistant-card">
  <div class="ai-assistant-card__head">
    <div>
      <div class="eyebrow">Deck AIStack Assistant</div>
      <h2>Deck intelligence</h2>
    </div>
    <div class="ai-assistant-card__head-tools">
      <InfoBubble
        label="Assistant workflow"
        text="Choose an insight or action. Deck AIStack retrieves saved deck, company, workspace, and slide context, builds a structured Claude request, validates the JSON answer, then returns it here for saving, adding to a slide, or generating a version."
      />
      <span class={`ai-assistant-card__state ${status}`}>{status === 'idle' ? selectedIntent.outputType : status}</span>
    </div>
  </div>

  <label class="ai-assistant-card__field">
    <span>Insight or action</span>
    <select value={intentType} onchange={(event) => selectIntent((event.currentTarget as HTMLSelectElement).value as AssistantIntentType)}>
      {#each assistantIntents as intent}
        <option value={intent.value}>{intent.label}</option>
      {/each}
    </select>
  </label>

  <div class="ai-assistant-card__field">
    <span>Using</span>
    <div class="ai-assistant-card__segments">
      {#each scopes as item}
        <button type="button" class:active={scope === item.value} onclick={() => (scope = item.value)}>
          {item.label}
        </button>
      {/each}
    </div>
    <small>{selectedSlideLabel()}</small>
  </div>

  <label class="ai-assistant-card__field">
    <span>Audience</span>
    <select bind:value={selectedAudience}>
      {#each audienceOptions as item}
        <option value={item.value}>{item.label}</option>
      {/each}
    </select>
  </label>

  <label class="ai-assistant-card__field">
    <span>Prompt</span>
    <textarea bind:value={instruction} rows="4"></textarea>
  </label>

  <button class="button ai-assistant-card__generate" type="button" disabled={!canGenerate} onclick={generateInsight}>
    {status === 'running' ? 'Generating insight...' : selectedIntent.outputType === 'design_version' ? 'Generate brief' : 'Generate insight'}
  </button>

  {#if status === 'failed' && errorMessage}
    <p class="ai-assistant-card__error">{errorMessage}</p>
  {/if}

  {#if result?.insight}
    <article class="ai-assistant-card__answer">
      <div>
        <div class="eyebrow">{selectedIntent.label}</div>
        <h3>{result.insight.title}</h3>
        <p>{result.insight.summary}</p>
      </div>

      {#if Object.keys(result.insight.content ?? {}).length > 0}
        <dl>
          {#each Object.entries(result.insight.content) as [key, value]}
            <div>
              <dt>{key.replaceAll(/([A-Z])/g, ' $1').replaceAll('_', ' ')}</dt>
              <dd>{renderValue(value)}</dd>
            </div>
          {/each}
        </dl>
      {/if}

      {#if result.insight.assumptions.length > 0}
        <div class="ai-assistant-card__list">
          <strong>Assumptions</strong>
          <ul>
            {#each result.insight.assumptions as item}
              <li>{item}</li>
            {/each}
          </ul>
        </div>
      {/if}

      {#if result.insight.missingEvidence.length > 0}
        <div class="ai-assistant-card__list">
          <strong>Missing evidence</strong>
          <ul>
            {#each result.insight.missingEvidence as item}
              <li>{item}</li>
            {/each}
          </ul>
        </div>
      {/if}

      {#if result.insight.suggestedSlideUpdate}
        <div class="ai-assistant-card__suggested-update">
          <strong>Suggested update</strong>
          <p>{result.insight.suggestedSlideUpdate}</p>
        </div>
      {/if}

      <div class="ai-assistant-card__actions">
        <button class="button secondary" type="button" onclick={() => (insightSaved = true)} disabled={isSaved}>
          {isSaved ? 'Insight saved' : 'Save insight'}
        </button>
        <button class="button secondary" type="button" onclick={addToSlide} disabled={!canAddToSlide}>
          Add to slide
        </button>
        <button class="button" type="button" onclick={createDesignVersion} disabled={!canCreateVersion}>
          Create design version
        </button>
      </div>
    </article>
  {/if}
</section>

<style>
  .ai-assistant-card {
    padding: 1rem;
    display: grid;
    gap: 0.9rem;
    align-content: start;
  }

  .ai-assistant-card__head,
  .ai-assistant-card__actions {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    align-items: start;
    flex-wrap: wrap;
  }

  .ai-assistant-card__head-tools {
    display: flex;
    align-items: center;
    gap: 0.45rem;
  }

  .ai-assistant-card__actions {
    align-items: center;
  }

  .ai-assistant-card__actions .button:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  h2,
  h3,
  p,
  ul,
  dl {
    margin: 0;
  }

  .ai-assistant-card__state {
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 0.35rem 0.65rem;
    color: var(--muted);
    background: var(--surface-soft);
    font-size: 0.78rem;
    text-transform: capitalize;
  }

  .ai-assistant-card__state.completed {
    color: var(--success);
  }

  .ai-assistant-card__state.failed,
  .ai-assistant-card__error {
    color: var(--danger);
  }

  .ai-assistant-card__field {
    display: grid;
    gap: 0.42rem;
  }

  .ai-assistant-card__field span,
  .ai-assistant-card__field small,
  dt {
    color: var(--muted);
    font-size: 0.82rem;
  }

  select,
  textarea {
    width: 100%;
    border-radius: 8px;
    border: 1px solid var(--line);
    background: var(--surface-input);
    color: var(--ink);
    padding: 0.72rem 0.8rem;
  }

  textarea {
    resize: vertical;
    min-height: 6.5rem;
  }

  .ai-assistant-card__segments {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.4rem;
  }

  .ai-assistant-card__segments button {
    min-height: 2.25rem;
    border-radius: 8px;
    border: 1px solid var(--line);
    background: var(--surface-soft);
    color: var(--ink-soft);
  }

  .ai-assistant-card__segments button.active {
    border-color: var(--line-strong);
    color: var(--ink-strong);
    background: var(--surface-active);
  }

  .ai-assistant-card__generate {
    width: 100%;
  }

  .ai-assistant-card__answer {
    display: grid;
    gap: 0.85rem;
    border-top: 1px solid var(--line);
    padding-top: 0.9rem;
  }

  dl {
    display: grid;
    gap: 0.55rem;
  }

  dd {
    margin: 0.18rem 0 0;
    overflow-wrap: anywhere;
  }

  .ai-assistant-card__list {
    display: grid;
    gap: 0.35rem;
  }

  ul {
    padding-left: 1.05rem;
    display: grid;
    gap: 0.25rem;
  }

  .ai-assistant-card__suggested-update {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--surface-soft);
    padding: 0.8rem;
    display: grid;
    gap: 0.35rem;
  }
</style>
