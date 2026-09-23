<script lang="ts">
  import PageHeader from '$components/PageHeader.svelte';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();
  let versionOverride = $state<PageData['version'] | null>(null);
  let savingCandidateId = $state<string | null>(null);
  let reviewError = $state<string | null>(null);
  const version = $derived(versionOverride ?? data.version);
  const versionNumber = $derived(version.versionNumber ?? version.batchNumber);
  const snapshotSlides = $derived(version.snapshot?.slides ?? []);

  async function reviewCandidate(candidate: PageData['version']['candidateSlides'][number], choice: 'generated_version' | 'original') {
    if (!candidate.sourceSlideId) return;
    savingCandidateId = candidate.id;
    reviewError = null;
    try {
      const response = await fetch(
        `/api/decks/${data.graph.deck.id}/iterations/${version.id}/slide-decisions/${candidate.sourceSlideId}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            choice,
            generatedSlideVersionId: choice === 'generated_version' ? candidate.id : null
          })
        }
      );
      const payload = (await response.json().catch(() => null)) as { batch?: PageData['version']; message?: string } | null;
      if (!response.ok || !payload?.batch) throw new Error(payload?.message ?? 'Could not save the slide decision.');
      versionOverride = payload.batch;
    } catch (error) {
      reviewError = error instanceof Error ? error.message : 'Could not save the slide decision.';
    } finally {
      savingCandidateId = null;
    }
  }
</script>

<section class="section-stack version-page">
  <PageHeader
    eyebrow="Saved deck version"
    title={version.versionName ?? version.batchName ?? `Version ${versionNumber}`}
    subtitle={version.changeSummary ?? 'Accepted deck state'}
    aside={new Date(version.acceptedAt ?? version.createdAt).toLocaleString()}
  />

  <section class="panel version-facts">
    <div><strong>Version</strong><span>{versionNumber}</span></div>
    <div><strong>Source</strong><span>{(version.sourceSurface ?? 'deck').replaceAll('_', ' ')}</span></div>
    <div><strong>Audience</strong><span>{version.audienceLabel ?? data.graph.deck.audience}</span></div>
    <div><strong>Status</strong><span>{version.status}</span></div>
  </section>

  {#if version.candidateSlides.length > 0}
    <section class="panel snapshot-panel">
      <div class="section-head"><strong>Slide review</strong><span>{version.candidateSlides.length} generated</span></div>
      {#if reviewError}<p class="review-error">{reviewError}</p>{/if}
      <div class="candidate-list">
        {#each version.candidateSlides as candidate}
          <article>
            <div><strong>{candidate.title}</strong><p>{candidate.summary}</p><span class="pill">{candidate.status.replaceAll('_', ' ')}</span></div>
            <div class="candidate-actions">
              <button type="button" class:chosen={candidate.status === 'applied'} class="button" disabled={savingCandidateId === candidate.id} onclick={() => reviewCandidate(candidate, 'generated_version')}>{candidate.status === 'applied' ? 'Generated kept' : 'Keep generated'}</button>
              <button type="button" class:chosen={candidate.status === 'kept_original'} class="button secondary" disabled={savingCandidateId === candidate.id} onclick={() => reviewCandidate(candidate, 'original')}>{candidate.status === 'kept_original' ? 'Original kept' : 'Keep original'}</button>
            </div>
          </article>
        {/each}
      </div>
    </section>
  {/if}

  <section class="panel snapshot-panel">
    <div class="section-head"><strong>Saved slide state</strong><span>{snapshotSlides.length} slides</span></div>
    <div class="slide-list">
      {#each snapshotSlides as slide, index}
        <article>
          <span>{String(index + 1).padStart(2, '0')}</span>
          <div><strong>{slide.generatedSlide?.title ?? slide.title}</strong><p>{slide.generatedSlide ? 'Generated design saved' : 'Original slide saved'}</p></div>
        </article>
      {/each}
    </div>
  </section>

  <div class="version-actions">
    <a class="button secondary" href={`/decks/${data.graph.deck.id}/versions`}>All versions</a>
    <a class="button" href={`/decks/${data.graph.deck.id}/iterations/${version.id}/compile`}>Prepare Full Deck</a>
  </div>
</section>

<style>
  .version-page { padding: 1.25rem; }
  .version-facts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1rem; padding: 1rem; }
  .version-facts div { display: grid; gap: 0.35rem; text-transform: capitalize; }
  .version-facts span, .snapshot-panel p { color: var(--muted); }
  .snapshot-panel { padding: 1rem; }
  .slide-list { display: grid; gap: 0.65rem; margin-top: 1rem; }
  .slide-list article { display: flex; gap: 0.85rem; padding: 0.75rem; border: 1px solid var(--line); border-radius: 14px; }
  .slide-list p { margin: 0.2rem 0 0; }
  .version-actions { display: flex; justify-content: flex-end; gap: 0.75rem; }
  .candidate-list { display: grid; gap: 0.75rem; margin-top: 1rem; }
  .candidate-list article { display: flex; justify-content: space-between; gap: 1rem; padding: 0.8rem; border: 1px solid var(--line); border-radius: 14px; }
  .candidate-actions { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
  .review-error { color: var(--danger); }
  .candidate-actions .chosen { box-shadow: 0 0 0 2px rgba(24, 200, 255, 0.35); }
  @media (max-width: 760px) { .version-facts { grid-template-columns: 1fr 1fr; } }
</style>
