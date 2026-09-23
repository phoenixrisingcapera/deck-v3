<script lang="ts">
  import ArtifactDetailsDrawer from '$lib/components/llm/ArtifactDetailsDrawer.svelte';
  import ArtifactHistoryPanel from '$lib/components/llm/ArtifactHistoryPanel.svelte';
  import type { ArtifactHistoryItem } from '$lib/components/llm/artifactTypes';
  import type { DeckGraph } from '$types/domain';
  import { analyzeDeckMap, type DeckMapAnalysis } from './smartDeckUserApi';
  import { trackDeckEvent } from '$lib/analytics/deckAnalytics';
  import { invalidateAll } from '$app/navigation';

  interface Props {
    graph: DeckGraph;
    contextSlides?: Array<{
      slideId: string;
      slideNumber: number;
      title: string;
      role: string | null;
      extractedText: string;
      thumbnailUrl: string | null;
      previewImageUrl: string | null;
      hasGeneratedVersion: boolean;
      generatedSlideId: string | null;
      persistedElements: Array<{
        id: string;
        elementKey: string;
        elementType: string;
        semanticLabel: string;
        locked: boolean;
        visible: boolean;
        targetCapabilities: {
          smartEdit: boolean;
          design: boolean;
        };
        isSelected: boolean;
        rawType: string;
        exactContent: string;
        generatedSlideId: string | null;
        slideId: string;
        x: number;
        y: number;
        width: number;
        height: number;
        zIndex: number;
        contentPreview: string;
      }>;
    }>;
    readyForLlm?: boolean;
  }

  let { graph, contextSlides = [], readyForLlm = false }: Props = $props();

  let analysis = $state<DeckMapAnalysis | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let showFullSlides = $state(false);
  let selectedArtifact = $state<ArtifactHistoryItem | null>(null);
  let focusedStructureSlideId = $state<string | null>(null);
  const llmArtifacts = $derived(
    ((((graph as DeckGraph & { llmArtifacts?: Array<Record<string, unknown>>; llm_artifacts?: Array<Record<string, unknown>> }).llmArtifacts ??
      (graph as DeckGraph & { llmArtifacts?: Array<Record<string, unknown>>; llm_artifacts?: Array<Record<string, unknown>> }).llm_artifacts) ??
      []) as Array<Record<string, unknown>>)
  );
  const deckMapHistory = $derived(
    llmArtifacts
      .filter((artifact) => String(artifact.artifactType ?? artifact.artifact_type ?? '') === 'smart_deck_deck_map_analysis')
      .slice(0, 6)
      .map((artifact) => ({
        id: String(artifact.artifactKey ?? artifact.artifact_key ?? artifact.id ?? ''),
        title: String(artifact.summary ?? 'Deck map analysis'),
        subtitle: String(artifact.artifactType ?? artifact.artifact_type ?? 'smart_deck_deck_map_analysis'),
        timestamp: formatArtifactTimestamp(artifact.createdAt ?? artifact.created_at),
        payload: ((artifact.payloadJson ?? artifact.payload_json ?? null) as Record<string, unknown> | null),
        artifactType: String(artifact.artifactType ?? artifact.artifact_type ?? 'smart_deck_deck_map_analysis')
      }))
  );

  async function triggerAnalysis() {
    loading = true;
    error = null;
    try {
      const result = await analyzeDeckMap(graph.deck.id);
      if (result.analysis) {
        analysis = result.analysis;
        // Reload the canonical graph after the worker has persisted its LLM
        // artifact; job output is immediate display data, not history truth.
        await invalidateAll();
        void trackDeckEvent(graph.deck.id, {
          eventName: 'product.deck_map.completed',
          surface: 'smart_deck',
          entityType: 'artifact',
          entityId: deckMapHistory[0]?.id,
          metadata: { provider: result.analysis.system?.provider, model: result.analysis.system?.model }
        });
      } else {
        error = 'Analysis returned no data.';
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to analyze deck.';
      void trackDeckEvent(graph.deck.id, {
        eventName: 'product.deck_map.failed',
        surface: 'smart_deck',
        entityType: 'deck',
        entityId: graph.deck.id,
        metadata: { message: error }
      });
    } finally {
      loading = false;
    }
  }

  function loadArtifactAnalysis(artifact: ArtifactHistoryItem) {
    const payload = (artifact.payload as DeckMapAnalysis | null);
    if (!payload) {
      error = 'Saved analysis payload is unavailable.';
      return;
    }
    analysis = {
      ...payload,
      system: {
        ...(payload.system ?? {}),
        loadedFromArtifact: true,
        loadedArtifactAt: artifact.timestamp ?? ''
      } as DeckMapAnalysis['system'] & { loadedFromArtifact: boolean; loadedArtifactAt: string }
    };
    error = null;
  }

  // Opening Map or Deck Analysis must never start a provider call. Users can
  // explicitly load a persisted artifact or request a new analysis above.

  function scoreColor(score: number): string {
    if (score >= 80) return '#6ee7b7';
    if (score >= 60) return '#fcd34d';
    if (score >= 40) return '#fb923c';
    return '#fda4af';
  }

  function severityColor(s: string): string {
    if (s === 'critical' || s === 'high') return '#fda4af';
    if (s === 'medium') return '#fcd34d';
    return '#6ee7b7';
  }

  function formatArtifactTimestamp(value: unknown) {
    if (typeof value !== 'string' || !value) return 'Unknown time';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
  }

  function smartEditHref(slideId: string) {
    const params = new URLSearchParams({ slide: slideId });
    return `/decks/${graph.deck.id}/smart-edit?${params.toString()}`;
  }

  const latestDeckMapArtifact = $derived(deckMapHistory[0] ?? null);
  const savedStructureSlides = $derived(
    contextSlides.map((slide) => ({
      ...slide,
      roleLabel: slide.role ? slide.role.replaceAll('_', ' ') : 'unclassified',
      bodyPreview: slide.extractedText.trim().slice(0, 220)
    }))
  );
  const focusedStructureSlide = $derived(
    savedStructureSlides.find((slide) => slide.slideId === focusedStructureSlideId) ?? savedStructureSlides[0] ?? null
  );
  const structureRows = $derived(
    Array.from({ length: Math.ceil(savedStructureSlides.length / 3) }, (_, index) => savedStructureSlides.slice(index * 3, index * 3 + 3))
  );

  $effect(() => {
    if (!savedStructureSlides.length) {
      focusedStructureSlideId = null;
      return;
    }
    if (!focusedStructureSlideId || !savedStructureSlides.some((slide) => slide.slideId === focusedStructureSlideId)) {
      focusedStructureSlideId = savedStructureSlides[0]?.slideId ?? null;
    }
  });
</script>

<section class="deck-map">
  <div class="panel-header">
    <div>
      <h3>Deck Analysis</h3>
      <p class="panel-header__subtitle">Narrative structure, persisted slide fields, and saved analysis state.</p>
    </div>
    {#if !loading}
      <div class="panel-header__actions">
        <button class="refresh-btn" onclick={triggerAnalysis} disabled={loading}>
          {analysis ? 'Re-analyze' : 'Analyze deck'}
        </button>
        <button class="refresh-btn" onclick={() => latestDeckMapArtifact && loadArtifactAnalysis(latestDeckMapArtifact)} disabled={!latestDeckMapArtifact}>
          Load latest
        </button>
      </div>
    {/if}
  </div>

  {#if loading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Analyzing deck narrative...</p>
    </div>
  {:else if error}
    <div class="state-card error">
      <p>{error}</p>
      <button class="retry-btn" onclick={triggerAnalysis}>Retry</button>
    </div>
  {:else if analysis}
    {#if analysis.system?.vectorRetrieval?.status && analysis.system.vectorRetrieval.status !== 'ready'}
      <div class="state-card">
        <p>Vector retrieval unavailable. Using structured deck context only.</p>
      </div>
    {/if}

    <div class="score-banner" style="background: linear-gradient(135deg, {scoreColor(analysis.qualityScore.overall)}22, transparent)">
      <div class="score-ring" style="border-color: {scoreColor(analysis.qualityScore.overall)}">
        <span class="score-value" style="color: {scoreColor(analysis.qualityScore.overall)}">{analysis.qualityScore.overall}</span>
        <span class="score-label">Overall</span>
      </div>
      <div class="sub-scores">
        <div class="sub-score"><span>Narrative</span><span style="color: {scoreColor(analysis.qualityScore.narrativeFlow)}">{analysis.qualityScore.narrativeFlow}</span></div>
        <div class="sub-score"><span>Evidence</span><span style="color: {scoreColor(analysis.qualityScore.evidenceQuality)}">{analysis.qualityScore.evidenceQuality}</span></div>
        <div class="sub-score"><span>Investor Ready</span><span style="color: {scoreColor(analysis.qualityScore.investorReadiness)}">{analysis.qualityScore.investorReadiness}</span></div>
        <div class="sub-score"><span>Visual</span><span style="color: {scoreColor(analysis.qualityScore.visualStructure)}">{analysis.qualityScore.visualStructure}</span></div>
      </div>
    </div>

    {#if analysis.company.name || analysis.company.stage}
      <div class="section-block">
        <h4>Company</h4>
        {#if analysis.company.name}<div class="field-row"><span>Name</span><span>{analysis.company.name}</span></div>{/if}
        {#if analysis.company.stage}<div class="field-row"><span>Stage</span><span>{analysis.company.stage}</span></div>{/if}
        {#if analysis.company.industry}<div class="field-row"><span>Industry</span><span>{analysis.company.industry}</span></div>{/if}
        {#if analysis.company.businessModel}<div class="field-row"><span>Model</span><span>{analysis.company.businessModel}</span></div>{/if}
        {#if analysis.company.foundingTeam}<div class="field-row"><span>Team</span><span>{analysis.company.foundingTeam}</span></div>{/if}
      </div>
    {/if}

    <div class="section-block">
      <h4>Narrative &mdash; {analysis.narrative.arcType}</h4>
      <p>{analysis.narrative.flowAssessment}</p>
      {#if analysis.narrative.strengthAreas.length > 0}
        <div class="tag-list">
          {#each analysis.narrative.strengthAreas as area}
            <span class="tag tag-green">{area}</span>
          {/each}
        </div>
      {/if}
      {#if analysis.narrative.weakAreas.length > 0}
        <div class="tag-list">
          {#each analysis.narrative.weakAreas as area}
            <span class="tag tag-red">{area}</span>
          {/each}
        </div>
      {/if}
      {#if analysis.narrative.recommendedRestructuring}
        <div class="tip-card">
          <strong>Restructuring suggestion</strong>
          <p>{analysis.narrative.recommendedRestructuring}</p>
        </div>
      {/if}
    </div>

    <div class="section-block">
      <div class="section-header">
        <h4>Slides ({analysis.slides.length})</h4>
        <button class="toggle-btn" onclick={() => showFullSlides = !showFullSlides}>
          {showFullSlides ? 'Hide' : 'Show'} details
        </button>
      </div>
      {#each analysis.slides as slide}
        <div class="slide-card" class:expanded={showFullSlides}>
          <div class="slide-header">
            <span class="slide-role">{slide.role.replaceAll('_', ' ')}</span>
            <span class="slide-title">{slide.title}</span>
            <span class="strength-badge" class:strong={slide.strength === 'strong'} class:adequate={slide.strength === 'adequate'} class:weak={slide.strength === 'weak'}>
              {slide.strength}
            </span>
            <a class="slide-link" href={smartEditHref(slide.slideId)}>Open slide</a>
          </div>
          {#if showFullSlides}
            <div class="slide-detail">
              <p><strong>Purpose:</strong> {slide.purposeAssessment}</p>
              <p><strong>Narrative:</strong> {slide.narrativeContribution}</p>
              {#if slide.improvementSuggestion}
                <div class="tip-card"><p>{slide.improvementSuggestion}</p></div>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>

    <div class="section-block">
      <h4>Evidence</h4>
      <p>{analysis.evidence.overallStrength}</p>
      <div class="metric-row">
        <span class="metric"><strong>{analysis.evidence.quantitativeClaims}</strong> quantitative claims</span>
        <span class="metric"><strong>{analysis.evidence.qualitativeClaims}</strong> qualitative claims</span>
        <span class="metric"><strong>{analysis.evidence.dataSourcesCited}</strong> data sources</span>
      </div>
      {#if analysis.evidence.strongAreas.length > 0}
        <div class="tag-list"><span class="tag-label">Strong:</span>{#each analysis.evidence.strongAreas as a}<span class="tag tag-green">{a}</span>{/each}</div>
      {/if}
      {#if analysis.evidence.weakAreas.length > 0}
        <div class="tag-list"><span class="tag-label">Weak:</span>{#each analysis.evidence.weakAreas as a}<span class="tag tag-red">{a}</span>{/each}</div>
      {/if}
    </div>

    {#if analysis.gaps.length > 0}
      <div class="section-block">
        <h4>Gaps</h4>
        {#each analysis.gaps as gap}
          <div class="gap-card">
            <div class="gap-header">
              <span class="importance-badge" style="background: {severityColor(gap.importance)}33; color: {severityColor(gap.importance)}">
                {gap.importance}
              </span>
              <strong>{gap.area}</strong>
            </div>
            <p>{gap.suggestion}</p>
          </div>
        {/each}
      </div>
    {/if}

    <div class="section-block">
      <h4>System</h4>
      <div class="field-row"><span>Provider</span><span>{analysis.system?.provider ?? 'unknown'}</span></div>
      <div class="field-row"><span>Model</span><span>{analysis.system?.model ?? 'unknown'}</span></div>
      <div class="field-row"><span>Prompt Package</span><span>{analysis.system?.promptPackage?.name ?? 'deck_map'} {analysis.system?.promptPackage?.version ?? ''}</span></div>
      <div class="field-row"><span>Vector Retrieval</span><span>{analysis.system?.vectorRetrieval?.status ?? 'unknown'}</span></div>
      <div class="field-row"><span>Vector Chunks</span><span>{analysis.system?.vectorRetrieval?.chunkCount ?? 0}</span></div>
      {#if analysis.system?.vectorRetrieval?.message}
        <p class="desc-note">{analysis.system.vectorRetrieval.message}</p>
      {/if}
    </div>

    <ArtifactHistoryPanel
      title="Saved Analyses"
      items={deckMapHistory}
      emptyText="No saved deck map analyses yet."
      onLoadLatest={() => latestDeckMapArtifact && loadArtifactAnalysis(latestDeckMapArtifact)}
      onLoad={loadArtifactAnalysis}
      onInspect={(item) => selectedArtifact = item}
    />
  {:else}
    <div class="state-card">
      <p>Load a saved analysis or explicitly analyze the deck to get a VC-grade assessment of the narrative, evidence quality, and investor readiness.</p>
    </div>

    {#if savedStructureSlides.length > 0}
      <section class="visual-map-surface">
        <div class="visual-map-surface__header">
          <div>
            <span>Visual deck map</span>
            <h4>Deck flow and persisted fields</h4>
          </div>
          <div class="visual-map-surface__legend">
            <span><i></i>Persisted fields</span>
            <span><b></b>Selected slide</span>
          </div>
        </div>

        <div class="visual-map-surface__layout">
          <div class="visual-map-surface__canvas" role="list" aria-label="Deck flow map">
            {#each structureRows as row, rowIndex}
              <div class="visual-map-row" role="listitem">
                {#each row as slide}
                  <button
                    type="button"
                    class="visual-map-node"
                    class:is-selected={slide.slideId === focusedStructureSlide?.slideId}
                    onclick={() => (focusedStructureSlideId = slide.slideId)}
                  >
                    <div class="visual-map-node__number">{String(slide.slideNumber).padStart(2, '0')}</div>
                    <div class="visual-map-node__body">
                      <strong>{slide.title}</strong>
                      <span>{slide.roleLabel}</span>
                    </div>
                    <div class="visual-map-node__meta">
                      <small>{slide.persistedElements.length} fields</small>
                      {#if slide.hasGeneratedVersion}<small class="generated-pill">Generated</small>{/if}
                    </div>
                  </button>
                {/each}
                {#if rowIndex < structureRows.length - 1}
                  <div class="visual-map-row__connector" aria-hidden="true"></div>
                {/if}
              </div>
            {/each}
          </div>

          {#if focusedStructureSlide}
            <aside class="visual-map-surface__detail">
              <div class="visual-map-surface__detail-head">
                <span>Selected slide</span>
                <strong>{String(focusedStructureSlide.slideNumber).padStart(2, '0')} · {focusedStructureSlide.title}</strong>
              </div>
              <p>{focusedStructureSlide.bodyPreview || 'No extracted text available yet.'}</p>
              <div class="visual-map-surface__chips">
                <span>{focusedStructureSlide.roleLabel}</span>
                <span>{focusedStructureSlide.persistedElements.length} persisted fields</span>
                <span>{focusedStructureSlide.hasGeneratedVersion ? 'Generated preview ready' : 'Generated preview pending'}</span>
              </div>
              <div class="visual-map-surface__detail-list">
                {#each focusedStructureSlide.persistedElements.slice(0, 6) as element}
                  <article>
                    <strong>{element.semanticLabel}</strong>
                    <span>{element.contentPreview || element.elementKey}</span>
                  </article>
                {/each}
              </div>
              <a class="slide-link" href={smartEditHref(focusedStructureSlide.slideId)}>Open slide</a>
            </aside>
          {/if}
        </div>
      </section>

      <div class="section-block">
        <div class="section-header">
          <h4>Saved deck structure ({savedStructureSlides.length})</h4>
          <span class:status-ready={readyForLlm} class:status-pending={!readyForLlm}>
            {readyForLlm ? 'Ready for analysis' : 'Saved context only'}
          </span>
        </div>
        <p class="saved-structure-note">
          This view comes from persisted Smart Deck workspace data already loaded for the mounted route. Opening Deck Map does not need a provider call.
        </p>
        <div class="saved-structure-list" role="list">
          {#each savedStructureSlides as slide}
            <article class="saved-structure-card" role="listitem">
              <div class="saved-structure-card__thumb">
                {#if slide.previewImageUrl || slide.thumbnailUrl}
                  <img src={slide.previewImageUrl ?? slide.thumbnailUrl ?? ''} alt={`${slide.title} preview`} />
                {:else}
                  <div class="saved-structure-card__placeholder">
                    <span>{String(slide.slideNumber).padStart(2, '0')}</span>
                    <strong>{slide.title}</strong>
                  </div>
                {/if}
              </div>
              <div class="saved-structure-card__body">
                <div class="saved-structure-card__meta">
                  <span>Slide {String(slide.slideNumber).padStart(2, '0')}</span>
                  <span>{slide.roleLabel}</span>
                  {#if slide.hasGeneratedVersion}
                    <span class="generated-pill">Generated preview ready</span>
                  {/if}
                </div>
                <h5>{slide.title}</h5>
                <p>{slide.bodyPreview || 'No extracted text available yet.'}</p>
                {#if slide.persistedElements.length > 0}
                  <details class="saved-elements" open>
                    <summary>Slide elements ({slide.persistedElements.length})</summary>
                    <div class="saved-elements__list" role="list">
                      {#each slide.persistedElements as element}
                        <article class="saved-elements__card" role="listitem">
                          <div class="saved-elements__meta" class:selected={element.isSelected}>
                            <strong>{element.semanticLabel}</strong>
                            <span>{element.elementKey}</span>
                            <span>{element.locked ? 'Locked' : 'Editable'} · {element.visible ? 'Visible' : 'Hidden'}</span>
                            <span>Smart Edit: {element.targetCapabilities.smartEdit ? 'yes' : 'no'} · Design: {element.targetCapabilities.design ? 'yes' : 'no'}</span>
                          </div>
                          <p>{element.contentPreview || 'No persisted content preview.'}</p>
                          <small>Bounds: {element.x}, {element.y} · {element.width} × {element.height} · z {element.zIndex}</small>
                          {#if element.isSelected}
                            <div class="saved-elements__selected-note">Selected on canvas</div>
                            <div class="saved-elements__target-card">
                              <strong>Selected element detail</strong>
                              <div><span>Element</span><span>{element.semanticLabel} · raw {element.rawType}</span></div>
                              <div><span>Content</span><span>{element.exactContent || 'No exact persisted content.'}</span></div>
                              <div><span>Target</span><span>slide {element.slideId} · generated {element.generatedSlideId ?? 'none'} · persisted {element.id} · render {element.elementKey}</span></div>
                              <a class="slide-link" href={smartEditHref(slide.slideId)}>Open Smart Edit</a>
                            </div>
                          {/if}
                        </article>
                      {/each}
                    </div>
                  </details>
                {:else}
                  <p class="saved-elements__empty">No persisted generated elements are available for this slide yet.</p>
                {/if}
                <a class="slide-link" href={smartEditHref(slide.slideId)}>Open slide</a>
              </div>
            </article>
          {/each}
        </div>
      </div>
    {/if}
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
  .deck-map {
    display: grid;
    gap: 1rem;
    align-content: start;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.9rem;
    flex-wrap: wrap;
    padding: 0.9rem 1rem;
    border-radius: 16px;
    border: 1px solid rgba(148, 163, 184, 0.12);
    background: linear-gradient(180deg, rgba(15, 23, 42, 0.82), rgba(8, 13, 27, 0.92));
  }

  .panel-header h3 {
    margin: 0;
    color: #f8fafc;
  }

  .panel-header__subtitle {
    margin: 0.3rem 0 0;
    color: #94a3b8;
    font-size: 0.82rem;
    line-height: 1.45;
  }

  .panel-header__actions {
    display: flex;
    gap: 0.55rem;
    flex-wrap: wrap;
  }

  .refresh-btn, .retry-btn {
    min-height: 34px;
    background: rgba(124, 58, 237, 0.16);
    color: #ddd6fe;
    border: 1px solid rgba(124, 58, 237, 0.26);
    border-radius: 10px;
    padding: 0.35rem 0.8rem;
    cursor: pointer;
    font-size: 0.78rem;
    font-weight: 600;
    transition: border-color 120ms ease, background 120ms ease, color 120ms ease;
  }

  .refresh-btn:hover, .retry-btn:hover,
  .refresh-btn:focus-visible, .retry-btn:focus-visible {
    border-color: rgba(129, 140, 248, 0.45);
    background: rgba(99, 102, 241, 0.2);
    color: #f5f3ff;
  }

  .refresh-btn:disabled, .retry-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

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
    border-radius: 14px;
    border: 1px solid rgba(148, 163, 184, 0.12);
    background: rgba(15, 23, 42, 0.6);
    text-align: left;
    color: #94a3b8;
  }

  .state-card.error {
    background: rgba(239, 68, 68, 0.1);
    color: #fda4af;
  }

  .state-card p { margin: 0 0 0.75rem 0; }

  .score-banner {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem;
    border-radius: 12px;
    border: 1px solid rgba(148, 163, 184, 0.12);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
  }

  .score-ring {
    width: 68px;
    height: 68px;
    border-radius: 50%;
    border: 3px solid;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .score-value { font-size: 1.35rem; font-weight: 700; line-height: 1; }
  .score-label { font-size: 0.6rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2px; }

  .sub-scores {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.35rem 0.75rem;
    flex: 1;
  }

  .sub-score {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: #94a3b8;
  }

  .section-block {
    display: grid;
    gap: 0.6rem;
    padding: 0.95rem 1rem;
    border-radius: 16px;
    border: 1px solid rgba(148, 163, 184, 0.1);
    background: rgba(15, 23, 42, 0.48);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02);
  }

  .visual-map-surface {
    display: grid;
    gap: 1rem;
    padding: 1rem;
    border-radius: 18px;
    border: 1px solid rgba(148, 163, 184, 0.16);
    background:
      radial-gradient(circle at top left, rgba(124, 58, 237, 0.16), transparent 28%),
      linear-gradient(180deg, rgba(15, 23, 42, 0.92), rgba(8, 13, 27, 0.96));
  }

  .visual-map-surface__header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .visual-map-surface__header span {
    color: #818cf8;
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .visual-map-surface__header h4 {
    margin: 0.3rem 0 0;
    color: #f8fafc;
    font-size: 1rem;
    text-transform: none;
    letter-spacing: 0;
  }

  .visual-map-surface__legend {
    display: flex;
    gap: 0.8rem;
    flex-wrap: wrap;
    color: #cbd5e1;
    font-size: 0.76rem;
  }

  .visual-map-surface__legend span {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    text-transform: none;
    letter-spacing: 0;
    color: #cbd5e1;
    font-weight: 600;
  }

  .visual-map-surface__legend i,
  .visual-map-surface__legend b {
    display: inline-block;
    width: 0.65rem;
    height: 0.65rem;
    border-radius: 999px;
  }

  .visual-map-surface__legend i {
    background: #22c55e;
  }

  .visual-map-surface__legend b {
    background: #8b5cf6;
  }

  .visual-map-surface__layout {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1rem;
    min-width: 0;
  }

  .visual-map-surface__canvas {
    display: grid;
    gap: 0.9rem;
    padding: 1rem;
    border-radius: 16px;
    border: 1px solid rgba(148, 163, 184, 0.12);
    background: rgba(7, 11, 22, 0.62);
  }

  .visual-map-row {
    position: relative;
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.85rem;
  }

  .visual-map-row__connector {
    position: absolute;
    left: 50%;
    right: auto;
    transform: translateX(-50%);
    bottom: -0.55rem;
    width: 1px;
    height: 0.7rem;
    background: linear-gradient(180deg, rgba(129, 140, 248, 0.72), transparent);
  }

  .visual-map-node {
    display: grid;
    gap: 0.7rem;
    padding: 0.85rem;
    border-radius: 16px;
    border: 1px solid rgba(148, 163, 184, 0.14);
    background: linear-gradient(180deg, rgba(15, 23, 42, 0.94), rgba(9, 13, 25, 0.96));
    color: #e2e8f0;
    text-align: left;
    cursor: pointer;
    transition: transform 120ms ease, border-color 120ms ease, box-shadow 120ms ease;
  }

  .visual-map-node:hover,
  .visual-map-node.is-selected {
    transform: translateY(-1px);
    border-color: rgba(139, 92, 246, 0.78);
    box-shadow: 0 0 0 1px rgba(14, 165, 233, 0.18), 0 18px 30px rgba(15, 23, 42, 0.28);
  }

  .visual-map-node__number {
    width: 2rem;
    height: 2rem;
    display: grid;
    place-items: center;
    border-radius: 10px;
    background: rgba(124, 58, 237, 0.14);
    color: #c4b5fd;
    font-size: 0.8rem;
    font-weight: 800;
  }

  .visual-map-node__body {
    display: grid;
    gap: 0.22rem;
  }

  .visual-map-node__body strong {
    color: #f8fafc;
    font-size: 0.9rem;
  }

  .visual-map-node__body span {
    color: #94a3b8;
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .visual-map-node__meta {
    display: flex;
    gap: 0.45rem;
    flex-wrap: wrap;
  }

  .visual-map-node__meta small {
    color: #86efac;
    font-size: 0.72rem;
    font-weight: 700;
  }

  .visual-map-surface__detail {
    display: grid;
    align-content: start;
    gap: 0.85rem;
    padding: 1rem;
    border-radius: 16px;
    border: 1px solid rgba(148, 163, 184, 0.12);
    background: linear-gradient(180deg, rgba(7, 11, 22, 0.84), rgba(8, 13, 27, 0.94));
  }

  .visual-map-surface__detail-head {
    display: grid;
    gap: 0.2rem;
  }

  .visual-map-surface__detail-head span {
    color: #818cf8;
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .visual-map-surface__detail-head strong {
    color: #f8fafc;
    font-size: 0.96rem;
  }

  .visual-map-surface__chips {
    display: flex;
    gap: 0.45rem;
    flex-wrap: wrap;
  }

  .visual-map-surface__chips span {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 0.28rem 0.58rem;
    background: rgba(15, 23, 42, 0.92);
    border: 1px solid rgba(148, 163, 184, 0.12);
    color: #cbd5e1;
    font-size: 0.72rem;
  }

  .visual-map-surface__detail-list {
    display: grid;
    gap: 0.55rem;
  }

  .visual-map-surface__detail-list article {
    display: grid;
    gap: 0.18rem;
    padding: 0.7rem 0.75rem;
    border-radius: 12px;
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid rgba(148, 163, 184, 0.12);
  }

  .visual-map-surface__detail-list strong {
    color: #e2e8f0;
    font-size: 0.78rem;
  }

  .visual-map-surface__detail-list span {
    color: #94a3b8;
    font-size: 0.74rem;
    line-height: 1.45;
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .status-ready,
  .status-pending {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    border-radius: 999px;
    padding: 0.2rem 0.65rem;
    font-size: 0.72rem;
    border: 1px solid rgba(255, 255, 255, 0.12);
  }

  .status-ready {
    color: #86efac;
    background: rgba(20, 83, 45, 0.35);
  }

  .status-pending {
    color: #fcd34d;
    background: rgba(113, 63, 18, 0.3);
  }

  .saved-structure-note {
    margin: 0;
    color: #cbd5e1;
    font-size: 0.84rem;
  }

  .saved-structure-list {
    display: grid;
    gap: 0.85rem;
  }

  .saved-structure-card {
    display: grid;
    grid-template-columns: 120px minmax(0, 1fr);
    gap: 0.85rem;
    padding: 0.85rem;
    border-radius: 16px;
    border: 1px solid rgba(148, 163, 184, 0.16);
    background: linear-gradient(180deg, rgba(15, 23, 42, 0.72), rgba(8, 13, 27, 0.82));
  }

  .saved-structure-card__thumb {
    width: 120px;
    aspect-ratio: 16 / 9;
    border-radius: 12px;
    overflow: hidden;
    background: rgba(15, 23, 42, 0.9);
    border: 1px solid rgba(148, 163, 184, 0.14);
  }

  .saved-structure-card__thumb img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .saved-structure-card__placeholder {
    width: 100%;
    height: 100%;
    display: grid;
    align-content: space-between;
    padding: 0.55rem;
    background: linear-gradient(180deg, rgba(30, 41, 59, 0.94), rgba(15, 23, 42, 0.98));
    color: #e2e8f0;
  }

  .saved-structure-card__placeholder span {
    font-size: 0.68rem;
    color: #94a3b8;
  }

  .saved-structure-card__placeholder strong {
    font-size: 0.72rem;
    line-height: 1.15;
  }

  .saved-structure-card__body {
    display: grid;
    gap: 0.45rem;
    min-width: 0;
  }

  .saved-structure-card__meta {
    display: flex;
    gap: 0.45rem;
    flex-wrap: wrap;
    color: #94a3b8;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .saved-structure-card__body h5 {
    margin: 0;
    color: #f8fafc;
    font-size: 0.96rem;
  }

  .saved-structure-card__body p {
    margin: 0;
    color: #cbd5e1;
    font-size: 0.84rem;
    line-height: 1.4;
  }

  .saved-elements {
    display: grid;
    gap: 0.55rem;
  }

  .saved-elements summary {
    cursor: pointer;
    color: #cbd5e1;
    font-size: 0.78rem;
  }

  .saved-elements__list {
    display: grid;
    gap: 0.5rem;
  }

  .saved-elements__card {
    display: grid;
    gap: 0.3rem;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.03);
    padding: 0.65rem 0.75rem;
  }

  .saved-elements__meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem 0.7rem;
    align-items: center;
  }

  .saved-elements__meta strong {
    color: #f8fafc;
    font-size: 0.78rem;
    text-transform: capitalize;
  }

  .saved-elements__meta.selected strong {
    color: #bfdbfe;
  }

  .saved-elements__meta span,
  .saved-elements__card small,
  .saved-elements__empty {
    color: #94a3b8;
    font-size: 0.74rem;
  }

  .saved-elements__card p {
    margin: 0;
    color: #dbe4f0;
    font-size: 0.78rem;
    line-height: 1.45;
  }

  .saved-elements__selected-note {
    color: #93c5fd;
    font-size: 0.74rem;
    font-weight: 600;
  }

  .saved-elements__target-card {
    display: grid;
    gap: 0.35rem;
    margin-top: 0.35rem;
    padding: 0.7rem 0.8rem;
    border-radius: 10px;
    border: 1px solid rgba(96, 165, 250, 0.24);
    background: rgba(30, 41, 59, 0.42);
  }

  .saved-elements__target-card strong {
    color: #dbeafe;
    font-size: 0.8rem;
  }

  .saved-elements__target-card div {
    display: grid;
    gap: 0.15rem;
  }

  .saved-elements__target-card div span:first-child {
    color: #93c5fd;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .saved-elements__target-card div span:last-child {
    color: #e2e8f0;
    font-size: 0.78rem;
    line-height: 1.4;
    word-break: break-word;
  }

  .generated-pill {
    color: #93c5fd;
  }

  .section-block h4 {
    margin: 0;
    color: #cbd5e1;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .section-block p {
    margin: 0;
    color: #94a3b8;
    font-size: 0.85rem;
    line-height: 1.6;
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

  .tag-list {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.3rem;
  }

  .tag-label {
    font-size: 0.72rem;
    color: #64748b;
    margin-right: 0.2rem;
  }

  .tag {
    padding: 0.2rem 0.5rem;
    border-radius: 6px;
    font-size: 0.7rem;
    white-space: nowrap;
  }

  .tag-green { background: rgba(52, 211, 153, 0.12); color: #6ee7b7; }
  .tag-red { background: rgba(239, 68, 68, 0.12); color: #fda4af; }

  .tip-card {
    padding: 0.65rem 0.75rem;
    border-radius: 8px;
    background: rgba(124, 58, 237, 0.08);
    border: 1px solid rgba(124, 58, 237, 0.15);
  }

  .tip-card strong {
    color: #c4b5fd;
    font-size: 0.75rem;
    display: block;
    margin-bottom: 0.25rem;
  }

  .tip-card p {
    margin: 0;
    font-size: 0.82rem;
    color: #a5b4fc;
  }

  .desc-note {
    margin: 0;
    font-size: 0.78rem;
    color: #94a3b8;
    line-height: 1.5;
  }

  .toggle-btn {
    background: none;
    border: none;
    color: #7c3aed;
    cursor: pointer;
    font-size: 0.72rem;
  }

  .slide-card {
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: 12px;
    overflow: hidden;
    background: rgba(8, 13, 27, 0.55);
  }

  .slide-header {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem;
    padding: 0.65rem 0.75rem;
    background: rgba(255, 255, 255, 0.03);
  }

  .slide-role {
    font-size: 0.65rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    min-width: 70px;
  }

  .slide-title {
    flex: 1;
    font-size: 0.82rem;
    color: #e2e8f0;
  }

  .slide-link {
    font-size: 0.68rem;
    color: #c4b5fd;
    text-decoration: none;
    white-space: nowrap;
  }

  .strength-badge {
    font-size: 0.65rem;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    text-transform: uppercase;
  }

  .strength-badge.strong { background: rgba(52, 211, 153, 0.15); color: #6ee7b7; }
  .strength-badge.adequate { background: rgba(251, 191, 36, 0.15); color: #fcd34d; }
  .strength-badge.weak { background: rgba(239, 68, 68, 0.15); color: #fda4af; }

  .slide-detail {
    padding: 0.65rem;
    display: grid;
    gap: 0.4rem;
    border-top: 1px solid rgba(255, 255, 255, 0.04);
  }

  .slide-detail p {
    font-size: 0.78rem;
    color: #94a3b8;
    margin: 0;
    line-height: 1.5;
  }

  .slide-detail p strong { color: #cbd5e1; }

  .metric-row {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .metric {
    font-size: 0.78rem;
    color: #94a3b8;
  }

  .metric strong { color: #e2e8f0; }

  .gap-card {
    padding: 0.75rem 0.85rem;
    background: rgba(8, 13, 27, 0.55);
    border-radius: 12px;
    border: 1px solid rgba(148, 163, 184, 0.1);
  }

  .gap-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.3rem;
  }

  .gap-header strong {
    color: #e2e8f0;
    font-size: 0.82rem;
  }

  .gap-card p {
    margin: 0;
    font-size: 0.78rem;
    color: #94a3b8;
  }

  .importance-badge {
    font-size: 0.6rem;
    padding: 0.1rem 0.35rem;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  @media (max-width: 720px) {
    .visual-map-surface__layout,
    .saved-structure-card {
      grid-template-columns: 1fr;
    }

    .visual-map-row {
      grid-template-columns: 1fr;
    }

    .visual-map-row__connector {
      left: 50%;
      right: auto;
      top: auto;
      bottom: -0.45rem;
      width: 1px;
      height: 0.6rem;
      background: linear-gradient(180deg, rgba(129, 140, 248, 0.7), transparent);
    }

    .saved-structure-card__thumb {
      width: 100%;
    }
  }
</style>
