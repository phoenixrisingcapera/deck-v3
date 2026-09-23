<script lang="ts">
  import AudienceSelector from '$components/due-diligence/AudienceSelector.svelte';

  type AudienceAction = 'analyze' | 'plan' | 'generate-smart-deck-instructions' | 'latest';

  type Claim = {
    id: string;
    claimText: string;
    claimType: string;
    slideTitle?: string | null;
    evidenceStatus: string;
    riskLevel: 'low' | 'medium' | 'high';
    confidence: number;
    recommendedAction: string;
  };

  type AudienceResult = {
    status: string;
    selectedAudience: string;
    audiencePriorities: string[];
    audienceObjections: Array<Record<string, unknown>>;
    audienceDecisionCriteria: string[];
    currentDeckFit: string;
    currentDeckFitScore: number;
    currentDeckFitReason: string;
    financialInsights?: Record<string, unknown>;
    narrativeShift: string;
    slideLevelInstructions: Array<Record<string, unknown>>;
    missingEvidence: unknown[];
    requiresReview: boolean;
  };

  interface Props {
    audience: string;
    audienceOptions: Array<{ value: string; label: string }>;
    audienceDisabled?: boolean;
    audienceFitExpanded?: boolean;
    onAudienceChange?: (audience: string) => void;
    workspace?: {
      claims?: Claim[];
      audienceFit?: {
        audience: string;
        fitScore: number;
        strengths: string[];
        weaknesses: string[];
        likelyQuestions: string[];
      };
      icMemo?: {
        thesis: string;
        reasonsToBelieve: string[];
        mainRisks: string[];
        recommendation: string;
      };
    } | null;
    audienceResult?: AudienceResult | null;
    audienceActionLoading?: AudienceAction | null;
    audienceActionError?: string | null;
    onAudienceAction?: (action: AudienceAction, instruction: string) => void;
    onGenerateAdaptedDeck?: (instruction: string) => void;
    generatingAdaptedDeck?: boolean;
    selectedClaimId?: string | null;
    onClaimSelect?: (claimId: string) => void;
    onQuickAction?: (action: 'ic_ready' | 'smart_edit' | 'export') => void;
    exportEnabled?: boolean;
    runLabel?: string;
    runDisabled?: boolean;
    loadDisabled?: boolean;
    onRun?: () => void;
    onLoad?: () => void;
    onToggleAudienceFit?: () => void;
  }

  let {
    audience,
    audienceOptions,
    audienceDisabled = false,
    audienceFitExpanded = false,
    onAudienceChange,
    workspace = null,
    audienceResult = null,
    audienceActionLoading = null,
    audienceActionError = null,
    onAudienceAction,
    onGenerateAdaptedDeck,
    generatingAdaptedDeck = false,
    selectedClaimId = null,
    onClaimSelect,
    onQuickAction,
    exportEnabled = false,
    runLabel = 'Run diligence',
    runDisabled = false,
    loadDisabled = false,
    onRun,
    onLoad,
    onToggleAudienceFit
  }: Props = $props();

  let audienceInstruction = $state('');

  function readableValue(record: Record<string, unknown>): string {
    return Object.entries(record)
      .filter(([, value]) => value !== null && value !== undefined && value !== '')
      .map(([key, value]) => `${key.replaceAll('_', ' ')}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`)
      .join(' · ');
  }

  const financialInsightSummary = $derived.by(() => {
    const insights = audienceResult?.financialInsights;
    if (!insights || typeof insights !== 'object') return null;
    const credibility = typeof insights.overallFinancialCredibility === 'object' && insights.overallFinancialCredibility
      ? insights.overallFinancialCredibility as Record<string, unknown>
      : null;
    const claims = Array.isArray(insights.financialClaims) ? insights.financialClaims.length : 0;
    const missingEvidence = Array.isArray(insights.missingFinancialEvidence) ? insights.missingFinancialEvidence.length : 0;
    const consistencyIssues = Array.isArray(insights.financialConsistencyIssues) ? insights.financialConsistencyIssues.length : 0;
    return {
      label: typeof credibility?.label === 'string' ? credibility.label : 'needs review',
      score: typeof credibility?.score === 'number' ? credibility.score : null,
      reason: typeof credibility?.reason === 'string' ? credibility.reason : 'Financial evidence still needs review.',
      claims,
      missingEvidence,
      consistencyIssues,
    };
  });
</script>

<div class="dd-tools">
  <section class="dd-tools__run" aria-label="Diligence run controls">
    <button type="button" disabled={loadDisabled} onclick={onLoad}>Load latest</button>
    <button type="button" class="primary" disabled={runDisabled} onclick={onRun}>{runLabel}</button>
  </section>

  <section class="dd-tools__section" aria-label="Audience diligence controls">
    <AudienceSelector label="Audience" value={audience} options={audienceOptions} disabled={audienceDisabled} onChange={onAudienceChange} />
    <h3>Audience adaptation</h3>
    <p>The prompt follows your instruction first, then uses deck evidence, extracted financial claims, LLM report insights, and market research to keep the output coherent and evidence-safe.</p>
    <label class="dd-tools__instruction">
      <span>Additional instruction (optional)</span>
      <textarea bind:value={audienceInstruction} rows="3" placeholder="Emphasize capital efficiency and milestone evidence."></textarea>
    </label>
    <div class="dd-tools__actions">
      <button type="button" disabled={!!audienceActionLoading} onclick={() => onAudienceAction?.('analyze', audienceInstruction)}>
        {audienceActionLoading === 'analyze' ? 'Analyzing...' : 'Analyze audience fit'}
      </button>
      <button type="button" disabled={!!audienceActionLoading} onclick={() => onAudienceAction?.('plan', audienceInstruction)}>
        {audienceActionLoading === 'plan' ? 'Planning...' : 'Plan adaptation'}
      </button>
      <button type="button" class="primary" disabled={!!audienceActionLoading || generatingAdaptedDeck} onclick={() => onGenerateAdaptedDeck?.(audienceInstruction)}>
        {generatingAdaptedDeck || audienceActionLoading === 'generate-smart-deck-instructions' ? 'Generating deck...' : 'Generate adapted deck'}
      </button>
      <button type="button" disabled={!!audienceActionLoading} onclick={() => onAudienceAction?.('latest', audienceInstruction)}>
        {audienceActionLoading === 'latest' ? 'Loading...' : 'Load latest audience result'}
      </button>
    </div>
    {#if audienceActionError}<p class="dd-tools__error" role="alert">{audienceActionError}</p>{/if}
    {#if audienceResult}
      <article class="dd-tools__card" aria-live="polite">
        <div class="dd-tools__card-header">
          <strong>{audienceResult.selectedAudience}</strong>
          <span>{audienceResult.status}</span>
        </div>
        <p>{audienceResult.currentDeckFitReason || audienceResult.narrativeShift || 'Audience guidance is ready for review.'}</p>
        <div class="dd-tools__meta">
          <span>Fit: {audienceResult.currentDeckFit || 'not scored'} ({audienceResult.currentDeckFitScore}/100)</span>
          <span>{audienceResult.slideLevelInstructions.length} slide instructions</span>
          <span>{audienceResult.missingEvidence.length} evidence gaps</span>
        </div>
      </article>
      {#if financialInsightSummary}
        <article class="dd-tools__card" aria-label="Financial grounding summary">
          <div class="dd-tools__card-header">
            <strong>Financial grounding</strong>
            <span>{financialInsightSummary.score ?? '—'}/100 · {financialInsightSummary.label}</span>
          </div>
          <p>{financialInsightSummary.reason}</p>
          <div class="dd-tools__meta">
            <span>{financialInsightSummary.claims} financial claims</span>
            <span>{financialInsightSummary.consistencyIssues} consistency issues</span>
            <span>{financialInsightSummary.missingEvidence} missing evidence items</span>
          </div>
        </article>
      {/if}
    {/if}
  </section>

  <section class="dd-tools__section" aria-label="Audience fit rationale">
    <button class="dd-tools__toggle" type="button" aria-expanded={audienceFitExpanded} onclick={onToggleAudienceFit}>
      Audience fit {audienceFitExpanded ? 'shown' : 'hidden'}
    </button>
    {#if audienceFitExpanded}
      {#if audienceResult}
        <article class="dd-tools__card">
          <h3>Audience rationale</h3>
          {#if audienceResult.narrativeShift}<p>{audienceResult.narrativeShift}</p>{/if}
          {#if audienceResult.audiencePriorities.length}<div><strong>Priorities</strong><ul>{#each audienceResult.audiencePriorities as item}<li>{item}</li>{/each}</ul></div>{/if}
          {#if audienceResult.audienceDecisionCriteria.length}<div><strong>Decision criteria</strong><ul>{#each audienceResult.audienceDecisionCriteria as item}<li>{item}</li>{/each}</ul></div>{/if}
          {#if audienceResult.audienceObjections.length}<div><strong>Objections</strong><ul>{#each audienceResult.audienceObjections as item}<li>{readableValue(item)}</li>{/each}</ul></div>{/if}
        </article>
      {/if}
      {#if workspace?.audienceFit}
        <article class="dd-tools__card">
          <div class="dd-tools__card-header"><strong>{workspace.audienceFit.audience}</strong><span>{workspace.audienceFit.fitScore}/100</span></div>
          {#if workspace.audienceFit.strengths.length}<div><strong>Strengths</strong><ul>{#each workspace.audienceFit.strengths as item}<li>{item}</li>{/each}</ul></div>{/if}
          {#if workspace.audienceFit.weaknesses.length}<div><strong>Weaknesses</strong><ul>{#each workspace.audienceFit.weaknesses as item}<li>{item}</li>{/each}</ul></div>{/if}
          {#if workspace.audienceFit.likelyQuestions.length}<div><strong>Likely questions</strong><ul>{#each workspace.audienceFit.likelyQuestions as item}<li>{item}</li>{/each}</ul></div>{/if}
        </article>
      {/if}
    {/if}
  </section>

  {#if workspace?.claims?.length}
    <section class="dd-tools__section" aria-label="Evidence recommendations">
      <h3>Evidence recommendations</h3>
      <p>Select a finding to inspect its source slide in the visualizer.</p>
      <div class="dd-tools__claims">
        {#each workspace.claims as claim}
          <button
            type="button"
            class="dd-tools__claim"
            class:selected={claim.id === selectedClaimId}
            aria-pressed={claim.id === selectedClaimId}
            onclick={() => onClaimSelect?.(claim.id)}
          >
            <span><strong>{claim.claimType}</strong><small>{claim.riskLevel} risk · {claim.evidenceStatus}</small></span>
            <span>{claim.claimText}</span>
            <small>{claim.slideTitle ?? 'Deck evidence'} · {claim.recommendedAction}</small>
          </button>
        {/each}
      </div>
    </section>
  {/if}

  <section class="dd-tools__section" aria-label="Diligence recommendation controls">
    <h3>Recommendation</h3>
    <article class="dd-tools__card">
      <strong>{workspace?.icMemo?.recommendation ?? 'Needs review'}</strong>
      <p>{workspace?.icMemo?.thesis ?? 'Run diligence to generate an investment recommendation.'}</p>
    </article>
    <div class="dd-tools__actions">
      <button type="button" onclick={() => onQuickAction?.('ic_ready')}>Prepare IC review</button>
      <button type="button" onclick={() => onQuickAction?.('smart_edit')}>Open Smart Edit</button>
      <button type="button" disabled={!exportEnabled} onclick={() => onQuickAction?.('export')}>Export report</button>
    </div>
  </section>
</div>

<style>
  .dd-tools, .dd-tools__section, .dd-tools__instruction, .dd-tools__card { display: grid; gap: .65rem; }
  .dd-tools { align-content: start; }
  .dd-tools__run, .dd-tools__actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .45rem; }
  .dd-tools__section { padding-top: .75rem; border-top: 1px solid rgba(255,255,255,.08); }
  .dd-tools h3, .dd-tools p { margin: 0; }
  .dd-tools h3 { color: #f8fafc; font-size: .82rem; }
  .dd-tools p, .dd-tools li { color: #cbd5e1; font-size: .76rem; line-height: 1.45; }
  .dd-tools ul { margin: .3rem 0 0; padding-left: 1rem; }
  .dd-tools button { border: 1px solid rgba(148,163,184,.22); border-radius: 8px; background: rgba(15,23,42,.82); color: #e2e8f0; padding: .55rem; font: inherit; font-size: .72rem; cursor: pointer; }
  .dd-tools button.primary { border-color: transparent; background: #4f46e5; color: #fff; font-weight: 800; }
  .dd-tools button:disabled { opacity: .45; cursor: not-allowed; }
  .dd-tools__instruction span, .dd-tools__meta, .dd-tools__card-header span { color: #94a3b8; font-size: .7rem; }
  .dd-tools__instruction textarea { min-height: 5rem; resize: vertical; border: 1px solid rgba(255,255,255,.1); border-radius: 8px; background: rgba(15,23,42,.72); color: #f8fafc; padding: .65rem; font: inherit; }
  .dd-tools__card { border: 1px solid rgba(255,255,255,.09); border-radius: 9px; background: rgba(15,23,42,.72); padding: .7rem; }
  .dd-tools__card-header { display: flex; justify-content: space-between; gap: .5rem; }
  .dd-tools__meta { display: flex; flex-wrap: wrap; gap: .45rem; }
  .dd-tools__toggle { justify-self: start; }
  .dd-tools__error { color: #fca5a5 !important; }
  .dd-tools__claims { display: grid; gap: .45rem; }
  .dd-tools .dd-tools__claim { display: grid; gap: .35rem; text-align: left; }
  .dd-tools__claim > span:first-child { display: flex; justify-content: space-between; gap: .5rem; text-transform: capitalize; }
  .dd-tools__claim small { color: #94a3b8; font-size: .68rem; }
  .dd-tools .dd-tools__claim.selected { border-color: rgba(99,102,241,.72); background: rgba(49,46,129,.3); }
</style>
