<script lang="ts">
  import ArtifactDetailsDrawer from '$lib/components/llm/ArtifactDetailsDrawer.svelte';
  import ArtifactHistoryPanel from '$lib/components/llm/ArtifactHistoryPanel.svelte';
  import type { ArtifactHistoryItem } from '$lib/components/llm/artifactTypes';
  import type { DeckGraph } from '$types/domain';
  import { generateMarketResearch, type MarketResearchData } from './smartDeckUserApi';
  import { trackDeckEvent } from '$lib/analytics/deckAnalytics';
  import { invalidateAll } from '$app/navigation';

  interface Props {
    graph: DeckGraph;
  }

  let { graph }: Props = $props();

  let research = $state<MarketResearchData | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let selectedArtifact = $state<ArtifactHistoryItem | null>(null);
  let confirmationPending = $state(false);
  const llmArtifacts = $derived(
    ((((graph as DeckGraph & { llmArtifacts?: Array<Record<string, unknown>>; llm_artifacts?: Array<Record<string, unknown>> }).llmArtifacts ??
      (graph as DeckGraph & { llmArtifacts?: Array<Record<string, unknown>>; llm_artifacts?: Array<Record<string, unknown>> }).llm_artifacts) ??
      []) as Array<Record<string, unknown>>)
  );
  const marketResearchHistory = $derived(
    llmArtifacts
      .filter((artifact) => String(artifact.artifactType ?? artifact.artifact_type ?? '') === 'smart_deck_market_research')
      .slice(0, 6)
      .map((artifact) => ({
        id: String(artifact.artifactKey ?? artifact.artifact_key ?? artifact.id ?? ''),
        title: String(artifact.summary ?? 'Market research report'),
        subtitle: String(artifact.artifactType ?? artifact.artifact_type ?? 'smart_deck_market_research'),
        timestamp: formatArtifactTimestamp(artifact.createdAt ?? artifact.created_at),
        payload: ((artifact.payloadJson ?? artifact.payload_json ?? null) as Record<string, unknown> | null),
        artifactType: String(artifact.artifactType ?? artifact.artifact_type ?? 'smart_deck_market_research')
      }))
  );

  async function triggerResearch() {
    loading = true;
    error = null;
    try {
      const result = await generateMarketResearch(graph.deck.id);
      if (result.research) {
        research = result.research;
        // Refresh the graph only after durable completion so persisted artifact
        // history, not the command receipt, remains the reload source of truth.
        await invalidateAll();
        void trackDeckEvent(graph.deck.id, {
          eventName: 'product.market_research.completed',
          surface: 'smart_deck',
          entityType: 'artifact',
          entityId: marketResearchHistory[0]?.id,
          metadata: { provider: result.research.system?.provider, model: result.research.system?.model }
        });
      } else {
        error = 'Market research returned no data.';
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to generate market research.';
      void trackDeckEvent(graph.deck.id, {
        eventName: 'product.market_research.failed',
        surface: 'smart_deck',
        entityType: 'deck',
        entityId: graph.deck.id,
        metadata: { message: error }
      });
    } finally {
      loading = false;
    }
  }

  function loadArtifactResearch(artifact: ArtifactHistoryItem) {
    const payload = (artifact.payload as MarketResearchData | null);
    if (!payload) {
      error = 'Saved market research payload is unavailable.';
      return;
    }
    research = {
      ...payload,
      sources: Array.isArray(payload.sources) ? payload.sources : [],
      citationStatus: payload.citationStatus ?? 'no_sources',
      system: {
        ...(payload.system ?? {}),
        loadedFromArtifact: true,
        loadedArtifactAt: artifact.timestamp ?? ''
      } as MarketResearchData['system'] & { loadedFromArtifact: boolean; loadedArtifactAt: string }
    };
    error = null;
  }

  $effect(() => {
    const latest = latestMarketResearchArtifact;
    if (graph.deck.id && !research && !loading && !error && latest) loadArtifactResearch(latest);
  });

  function safeSourceUrl(value: string | null | undefined): string | null {
    if (!value || /[\u0000-\u001f\u007f]/.test(value)) return null;
    try {
      const url = new URL(value);
      return (url.protocol === 'http:' || url.protocol === 'https:') && !url.username && !url.password ? url.href : null;
    } catch {
      return null;
    }
  }

  function sourceById(id: string) {
    return research?.sources?.find((source) => source.id === id) ?? null;
  }

  function citationIds(ids: string[] | undefined): string {
    return ids?.length ? ids.join(', ') : 'None';
  }

  function severityColor(s: string): string {
    if (s === 'critical' || s === 'high') return '#fda4af';
    if (s === 'medium') return '#fcd34d';
    return '#6ee7b7';
  }

  function confidenceColor(c: string): string {
    if (c === 'high') return '#6ee7b7';
    if (c === 'medium') return '#fcd34d';
    return '#fb923c';
  }

  function formatArtifactTimestamp(value: unknown) {
    if (typeof value !== 'string' || !value) return 'Unknown time';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
  }

  const latestMarketResearchArtifact = $derived(marketResearchHistory[0] ?? null);
  const sourceDisclosure = $derived(
    research?.citationStatus === 'linked' && research.sources?.length
      ? `${research.sources.length} source records are linked to supported claims below.`
      : 'No reliable source citations were returned. Treat market figures and the VC score as unsupported model analysis requiring independent verification.'
  );

  function requestResearch() {
    confirmationPending = true;
  }

  function confirmResearch() {
    confirmationPending = false;
    void triggerResearch();
  }
</script>

{#snippet CitationLinks(ids: string[] | undefined)}
  {#if ids?.length}
    {#each ids as id, index}
      {@const source = sourceById(id)}
      {@const href = safeSourceUrl(source?.url)}
      {#if index > 0}<span aria-hidden="true">, </span>{/if}
      {#if source && href}
        <a class="citation-link" href={href} target="_blank" rel="noopener noreferrer">{source.title || id}</a>
      {:else}
        <span class="citation-label">{source?.title ?? `Unavailable source (${id})`}</span>
      {/if}
    {/each}
  {:else}
    <span class="citation-label">No citations attached</span>
  {/if}
{/snippet}

<section class="market-research">
  <div class="panel-header">
    <h3>Market Research</h3>
    {#if !loading}
      <button class="refresh-btn" onclick={requestResearch} disabled={loading}>
        {research ? 'Regenerate research' : 'Generate research'}
      </button>
      <button class="refresh-btn" onclick={() => latestMarketResearchArtifact && loadArtifactResearch(latestMarketResearchArtifact)} disabled={!latestMarketResearchArtifact}>
        Load latest
      </button>
    {/if}
  </div>

  {#if confirmationPending}
    <div class="confirmation-card" role="alert">
      <strong>{research ? 'Replace the current view with a new persisted report?' : 'Generate and persist a market research report?'}</strong>
      <p>This runs the configured provider using deck context. Existing saved reports remain available in history.</p>
      <div><button type="button" onclick={confirmResearch}>Confirm generation</button><button type="button" onclick={() => confirmationPending = false}>Cancel</button></div>
    </div>
  {/if}

  {#if loading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Generating market intelligence...</p>
    </div>
  {:else if error}
    <div class="state-card error">
      <p>{error}</p>
      <button class="retry-btn" onclick={triggerResearch}>Retry</button>
    </div>
  {:else if research}
    <div class="state-card evidence-status">
      <strong>Evidence status: {research.citationStatus ?? 'no_sources'}</strong>
      <p>{research.citationStatus === 'cited' ? 'Every typed evidence claim group includes a source reference.' : research.citationStatus === 'partial' ? 'Only some typed evidence claim groups include source references.' : research.citationStatus === 'uncited' ? 'Source records exist, but typed evidence claims do not cite them.' : 'No external source records are attached.'}</p>
    </div>
    {#if !research.sources?.length || research.citationStatus === 'no_sources'}
      <div class="state-card evidence-warning"><strong>No external sources returned</strong><p>Claims below are unsupported by first-class citations and require independent verification.</p></div>
    {/if}
    {#if research.system?.vectorRetrieval?.status && research.system.vectorRetrieval.status !== 'ready'}
      <div class="state-card">
        <p>Vector retrieval unavailable. Using structured deck context only.</p>
      </div>
    {/if}

    {#if research.company.name}
      <div class="section-block">
        <h4>Company Intelligence</h4>
        {#if research.company.name}<div class="field-row"><span>Company</span><span>{research.company.name}</span></div>{/if}
        {#if research.company.description}<p class="desc-text">{research.company.description}</p>{/if}
        {#if research.company.businessModel}<div class="field-row"><span>Business Model</span><span>{research.company.businessModel}</span></div>{/if}
        {#if research.company.fundingStage}<div class="field-row"><span>Funding Stage</span><span>{research.company.fundingStage}</span></div>{/if}
        {#if research.company.totalRaised}<div class="field-row"><span>Total Raised</span><span>{research.company.totalRaised}</span></div>{/if}
        {#if research.company.teamSize}<div class="field-row"><span>Team Size</span><span>{research.company.teamSize}</span></div>{/if}
        {#if research.company.headquarters}<div class="field-row"><span>HQ</span><span>{research.company.headquarters}</span></div>{/if}
        {#if research.company.foundedYear}<div class="field-row"><span>Founded</span><span>{research.company.foundedYear}</span></div>{/if}
        <p class="citation-line">Citation IDs: {citationIds(research.company.citationIds)} · Sources: {@render CitationLinks(research.company.citationIds)}</p>
        {#if research.company.keyFinding}
          <div class="finding-card">
            <strong>Key Finding</strong>
            <p>{research.company.keyFinding}</p>
            <p class="citation-line">Citation IDs: {citationIds(research.company.keyFindingCitationIds)} · Sources: {@render CitationLinks(research.company.keyFindingCitationIds)}</p>
          </div>
        {/if}
      </div>
    {/if}

    {#if research.marketSizing.tam}
      <div class="section-block">
        <h4>Market Sizing</h4>
        <div class="sizing-grid">
          <div class="sizing-card">
            <span class="sizing-label">TAM</span>
            <span class="sizing-value">{research.marketSizing.tam}</span>
          </div>
          <div class="sizing-card">
            <span class="sizing-label">SAM</span>
            <span class="sizing-value">{research.marketSizing.sam}</span>
          </div>
          <div class="sizing-card">
            <span class="sizing-label">SOM</span>
            <span class="sizing-value">{research.marketSizing.som}</span>
          </div>
        </div>
        {#if research.marketSizing.growthRate}
          <div class="field-row"><span>Growth Rate</span><span>{research.marketSizing.growthRate}</span></div>
        {/if}
        <div class="field-row">
          <span>Confidence</span>
          <span style="color: {confidenceColor(research.marketSizing.sourceConfidence)}">{research.marketSizing.sourceConfidence}</span>
        </div>
        {#if research.marketSizing.note}
          <p class="desc-text">{research.marketSizing.note}</p>
        {/if}
        <p class="citation-line">Citation IDs: {citationIds(research.marketSizing.citationIds)} · Sources: {@render CitationLinks(research.marketSizing.citationIds)}</p>
      </div>
    {/if}

    {#if research.competitors.length > 0}
      <div class="section-block">
        <h4>Competitors ({research.competitors.length})</h4>
        {#each research.competitors as comp}
          <div class="competitor-card">
            <div class="comp-header">
              <strong>{comp.name}</strong>
              <span class="pill">{comp.category}</span>
            </div>
            {#if comp.threats}<p class="comp-detail"><strong>Threat:</strong> {comp.threats}</p>{/if}
            {#if comp.weaknesses}<p class="comp-detail"><strong>Weakness:</strong> {comp.weaknesses}</p>{/if}
            {#if comp.differentiation}<p class="comp-detail"><strong>Our edge:</strong> {comp.differentiation}</p>{/if}
            <p class="citation-line">Citation IDs: {citationIds(comp.citationIds)} · Sources: {@render CitationLinks(comp.citationIds)}</p>
          </div>
        {/each}
      </div>
    {/if}

    {#if research.industryTrends}
      <div class="section-block">
        <h4>Industry Trends</h4>
        <p class="desc-text">{research.industryTrends}</p>
        <p class="citation-line">Citation IDs: {citationIds(research.industryTrendCitationIds)} · Sources: {@render CitationLinks(research.industryTrendCitationIds)}</p>
      </div>
    {/if}

    {#if research.investmentThesis.summary}
      <div class="section-block">
        <h4>Investment Thesis</h4>
        <p class="thesis-text">{research.investmentThesis.summary}</p>
        <div class="thesis-grid">
          {#if research.investmentThesis.strengths.length > 0}
            <div class="thesis-col">
              <strong class="thesis-label strong-label">Strengths</strong>
              {#each research.investmentThesis.strengths as s}
                <span class="thesis-item">{s}</span>
              {/each}
            </div>
          {/if}
          {#if research.investmentThesis.weaknesses.length > 0}
            <div class="thesis-col">
              <strong class="thesis-label weak-label">Weaknesses</strong>
              {#each research.investmentThesis.weaknesses as w}
                <span class="thesis-item">{w}</span>
              {/each}
            </div>
          {/if}
        </div>
        {#if research.investmentThesis.differentiators.length > 0}
          <div class="diff-section">
            <strong>Differentiators</strong>
            <div class="tag-list">
              {#each research.investmentThesis.differentiators as d}
                <span class="tag">{d}</span>
              {/each}
            </div>
          </div>
        {/if}
        <p class="citation-line">Citation IDs: {citationIds(research.investmentThesis.citationIds)} · Sources: {@render CitationLinks(research.investmentThesis.citationIds)}</p>
      </div>
    {/if}

    {#if research.risks.length > 0}
      <div class="section-block">
        <h4>Risks</h4>
        {#each research.risks as risk}
          <div class="risk-card">
            <div class="risk-header">
              <span class="risk-severity" style="color: {severityColor(risk.severity)}; background: {severityColor(risk.severity)}15">
                {risk.severity}
              </span>
              <span>{risk.risk}</span>
            </div>
            {#if risk.mitigation}
              <p class="risk-mitigation">{risk.mitigation}</p>
            {/if}
            <p class="citation-line">Citation IDs: {citationIds(risk.citationIds)} · Sources: {@render CitationLinks(risk.citationIds)}</p>
          </div>
        {/each}
      </div>
    {/if}

    <div class="section-block">
      <h4>Sources</h4>
      {#if research.sources?.length}
        {#each research.sources as source}
          <div class="source-row"><strong>{source.title}</strong>{#if safeSourceUrl(source.url)}<a href={safeSourceUrl(source.url) ?? undefined} target="_blank" rel="noopener noreferrer">Open source</a>{:else}<span>No safe URL</span>{/if}<small>{[source.provider, source.publishedDate].filter(Boolean).join(' · ')}</small></div>
        {/each}
      {:else}<p class="desc-text">No source records are attached to this report.</p>{/if}
    </div>

    <div class="section-block">
      <div class="vc-score-card">
        <div class="vc-score-main">
          <span class="vc-score-value" style="color: {confidenceColor(research.vcAssessment.score >= 70 ? 'high' : research.vcAssessment.score >= 40 ? 'medium' : 'low')}">
            {research.vcAssessment.score}
          </span>
          <div class="vc-score-info">
            <strong>VC Readiness</strong>
            <span>{research.vcAssessment.stageFit}</span>
          </div>
        </div>
        <p class="score-disclosure"><strong>How to read this score:</strong> It is a model assessment based on the displayed strengths, concerns, stage fit, and available deck context—not an investment recommendation.</p>
        {#if research.vcAssessment.strengths.length > 0}
          <div class="vc-detail">
            <strong>Strengths</strong>
            {#each research.vcAssessment.strengths as s}
              <span class="vc-item">{s}</span>
            {/each}
          </div>
        {/if}
        {#if research.vcAssessment.concerns.length > 0}
          <div class="vc-detail">
            <strong>Concerns</strong>
            {#each research.vcAssessment.concerns as c}
              <span class="vc-item">{c}</span>
            {/each}
          </div>
        {/if}
        {#if research.vcAssessment.diligenceQuestions.length > 0}
          <div class="vc-detail">
            <strong>Diligence Questions</strong>
            {#each research.vcAssessment.diligenceQuestions as q}
              <span class="vc-item vc-question">{q}</span>
            {/each}
          </div>
        {/if}
        <p class="citation-line">Citation IDs: {citationIds(research.vcAssessment.citationIds)} · Sources: {@render CitationLinks(research.vcAssessment.citationIds)}</p>
      </div>
    </div>

    <div class="section-block source-disclosure">
      <h4>Sources and limitations</h4>
      <p>{sourceDisclosure}</p>
      {#if research.sources?.length}
        {#each research.sources as source}
          <article class="competitor-card"><strong>[{source.id}] {source.title}</strong><p class="comp-detail">{source.provider ?? 'Provider not supplied'} · {(source as any).publishedAt ?? (source as any).accessedAt ?? 'Date not supplied'}</p>{#if source.url}<a href={source.url} target="_blank" rel="noreferrer">Open source</a>{:else}<p>{(source as any).reference ?? ''}</p>{/if}</article>
        {/each}
      {/if}
    </div>

    <div class="section-block">
      <h4>System</h4>
      <div class="field-row"><span>Provider</span><span>{research.system?.provider ?? 'unknown'}</span></div>
      <div class="field-row"><span>Model</span><span>{research.system?.model ?? 'unknown'}</span></div>
      <div class="field-row"><span>Prompt Package</span><span>{research.system?.promptPackage?.name ?? 'market_research'} {research.system?.promptPackage?.version ?? ''}</span></div>
      <div class="field-row"><span>Vector Retrieval</span><span>{research.system?.vectorRetrieval?.status ?? 'unknown'}</span></div>
      <div class="field-row"><span>Vector Chunks</span><span>{research.system?.vectorRetrieval?.chunkCount ?? 0}</span></div>
      {#if research.system?.vectorRetrieval?.message}
        <p class="desc-text">{research.system.vectorRetrieval.message}</p>
      {/if}
    </div>

    <ArtifactHistoryPanel
      title="Saved Reports"
      items={marketResearchHistory}
      emptyText="No saved market research reports yet."
      onLoadLatest={() => latestMarketResearchArtifact && loadArtifactResearch(latestMarketResearchArtifact)}
      onLoad={loadArtifactResearch}
      onInspect={(item) => selectedArtifact = item}
    />
  {:else}
    <div class="state-card">
      <p>Generate market intelligence to see company analysis, market sizing, competitor landscape, and VC readiness assessment.</p>
    </div>
  {/if}
</section>

<ArtifactDetailsDrawer
  open={selectedArtifact !== null}
  title={selectedArtifact?.title ?? 'Artifact details'}
  subtitle={selectedArtifact?.timestamp ?? null}
  payload={selectedArtifact?.payload ?? null}
  onClose={() => selectedArtifact = null}
/>

<style>
  .market-research {
    display: grid;
    gap: 1rem;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .panel-header h3 {
    margin: 0;
    color: #f8fafc;
  }

  .refresh-btn, .retry-btn {
    background: rgba(124, 58, 237, 0.2);
    color: #c4b5fd;
    border: 1px solid rgba(124, 58, 237, 0.3);
    border-radius: 8px;
    padding: 0.35rem 0.75rem;
    cursor: pointer;
    font-size: 0.78rem;
  }

  .refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  .confirmation-card {
    display: grid;
    gap: 0.65rem;
    padding: 0.9rem;
    border: 1px solid rgba(124, 58, 237, 0.4);
    border-radius: 10px;
    background: rgba(76, 29, 149, 0.2);
    color: #e2e8f0;
  }

  .confirmation-card p,
  .source-disclosure p,
  .score-disclosure { margin: 0; color: #cbd5e1; line-height: 1.5; }
  .confirmation-card div { display: flex; gap: 0.5rem; }
  .confirmation-card button { padding: 0.45rem 0.7rem; border: 1px solid rgba(255,255,255,.15); border-radius: 8px; background: #312e81; color: white; cursor: pointer; }

  .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.75rem;
    padding: 2rem 0;
    color: #94a3b8;
  }

  .spinner {
    width: 28px;
    height: 28px;
    border: 3px solid rgba(124, 58, 237, 0.2);
    border-top-color: #7c3aed;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  .state-card {
    padding: 1rem;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.03);
    text-align: center;
    color: #94a3b8;
  }

  .state-card.error { background: rgba(239, 68, 68, 0.1); color: #fda4af; }
  .evidence-warning { text-align: left; border: 1px solid rgba(251, 146, 60, 0.35); }
  .state-card p { margin: 0 0 0.75rem 0; }

  .section-block {
    display: grid;
    gap: 0.5rem;
  }

  .section-block h4 {
    margin: 0;
    color: #cbd5e1;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .field-row {
    display: flex;
    justify-content: space-between;
    padding: 0.3rem 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    font-size: 0.82rem;
  }

  .field-row span:first-child { color: #94a3b8; }
  .field-row span:last-child { color: #f8fafc; text-align: right; max-width: 60%; }

  .desc-text {
    margin: 0;
    font-size: 0.82rem;
    color: #94a3b8;
    line-height: 1.6;
  }
  .citation-line { margin: 0; color: #c4b5fd; font-size: 0.75rem; }
  .citation-link { color: #c4b5fd; text-decoration: underline; text-underline-offset: 0.15em; }
  .citation-link:focus-visible { outline: 2px solid #c4b5fd; outline-offset: 2px; border-radius: 2px; }
  .citation-label { color: #94a3b8; }
  .source-row { display: grid; gap: 0.2rem; padding: 0.5rem; border: 1px solid rgba(255,255,255,.06); border-radius: 8px; }
  .source-row a { color: #c4b5fd; }
  .source-row small, .source-row span { color: #94a3b8; }

  .finding-card {
    padding: 0.6rem 0.75rem;
    border-radius: 8px;
    background: rgba(124, 58, 237, 0.08);
    border: 1px solid rgba(124, 58, 237, 0.15);
  }

  .finding-card strong { color: #c4b5fd; font-size: 0.72rem; display: block; margin-bottom: 0.25rem; text-transform: uppercase; letter-spacing: 0.04em; }
  .finding-card p { margin: 0; font-size: 0.82rem; color: #a5b4fc; }

  .sizing-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.4rem;
  }

  .sizing-card {
    text-align: center;
    padding: 0.6rem 0.4rem;
    background: rgba(255, 255, 255, 0.03);
    border-radius: 8px;
  }

  .sizing-label { display: block; font-size: 0.65rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.04em; }
  .sizing-value { display: block; font-size: 0.85rem; color: #f8fafc; font-weight: 600; margin-top: 0.2rem; }

  .competitor-card {
    padding: 0.6rem 0.75rem;
    background: rgba(255, 255, 255, 0.02);
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.05);
  }

  .comp-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.3rem;
  }

  .comp-header strong { color: #e2e8f0; font-size: 0.82rem; }

  .pill {
    background: rgba(124, 58, 237, 0.15);
    color: #c4b5fd;
    padding: 0.1rem 0.4rem;
    border-radius: 999px;
    font-size: 0.65rem;
  }

  .comp-detail { margin: 0.15rem 0; font-size: 0.75rem; color: #94a3b8; line-height: 1.5; }
  .comp-detail strong { color: #cbd5e1; }

  .thesis-text {
    margin: 0;
    font-size: 0.85rem;
    color: #e2e8f0;
    line-height: 1.6;
    font-weight: 500;
  }

  .thesis-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
  }

  .thesis-col { display: grid; gap: 0.3rem; }

  .thesis-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .strong-label { color: #6ee7b7; }
  .weak-label { color: #fda4af; }

  .thesis-item {
    font-size: 0.75rem;
    color: #94a3b8;
    padding: 0.2rem 0.4rem;
    background: rgba(255, 255, 255, 0.03);
    border-radius: 4px;
  }

  .diff-section {
    display: grid;
    gap: 0.3rem;
  }

  .diff-section strong { color: #cbd5e1; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; }

  .tag-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
  }

  .tag {
    padding: 0.2rem 0.5rem;
    border-radius: 6px;
    font-size: 0.7rem;
    background: rgba(52, 211, 153, 0.1);
    color: #6ee7b7;
    white-space: nowrap;
  }

  .risk-card {
    padding: 0.6rem 0.75rem;
    background: rgba(255, 255, 255, 0.02);
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.05);
  }

  .risk-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.82rem;
    color: #e2e8f0;
  }

  .risk-severity {
    font-size: 0.6rem;
    padding: 0.1rem 0.35rem;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .risk-mitigation {
    margin: 0.3rem 0 0 0;
    font-size: 0.75rem;
    color: #94a3b8;
    line-height: 1.5;
  }

  .vc-score-card {
    padding: 1rem;
    background: rgba(255, 255, 255, 0.03);
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.06);
  }

  .vc-score-main {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
  }

  .vc-score-value {
    font-size: 2rem;
    font-weight: 700;
    line-height: 1;
  }

  .vc-score-info strong { display: block; color: #f8fafc; font-size: 0.85rem; }
  .vc-score-info span { color: #94a3b8; font-size: 0.75rem; }

  .vc-detail {
    margin-top: 0.6rem;
    display: grid;
    gap: 0.3rem;
  }

  .vc-detail strong {
    color: #cbd5e1;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .vc-item {
    font-size: 0.78rem;
    color: #94a3b8;
    padding: 0.2rem 0.4rem;
    background: rgba(255, 255, 255, 0.03);
    border-radius: 4px;
  }

  .vc-question {
    color: #c4b5fd;
    font-style: italic;
  }

</style>
