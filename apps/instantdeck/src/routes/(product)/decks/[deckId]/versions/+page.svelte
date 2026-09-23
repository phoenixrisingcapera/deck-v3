<script lang="ts">
  import PageHeader from '$components/PageHeader.svelte';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  const instantDeckHref = $derived.by(() => {
    if (!data.requestedDesignVersionId) return null;
    const params = new URLSearchParams({ designVersionId: data.requestedDesignVersionId });
    if (data.requestedGeneratedSlideId) params.set('generatedSlideId', data.requestedGeneratedSlideId);
    if (data.requestedArtifactId) params.set('artifactId', data.requestedArtifactId);
    return `/decks/${data.graph.deck.id}/instant-deck?${params.toString()}`;
  });
</script>

<section class="section-stack versions-page">
  <PageHeader
    eyebrow="Saved deck history"
    title="Versions"
    subtitle="Accepted Instant Deck, Smart Deck, Smart Edit, and Due Diligence changes are saved here as backend-numbered deck states."
    aside={`${data.versions.length} saved`}
  />

  {#if data.requestedDesignVersionId}
    <section
      class="panel selected-version-notice"
      aria-label="Selected generated version"
      data-selected-design-version-id={data.requestedDesignVersionId}
      data-selected-generated-slide-id={data.requestedGeneratedSlideId ?? undefined}
      data-selected-artifact-id={data.requestedArtifactId ?? undefined}
    >
      <strong>Viewing generated Instant Deck version</strong>
      <p>This history view retains the exact DesignVersion selected in Instant Deck.</p>
      {#if instantDeckHref}
        <a href={instantDeckHref}>Return to this Instant Deck version</a>
      {/if}
    </section>
  {/if}

  {#if data.versions.length > 0}
    <section class="version-grid" aria-label="Saved deck versions">
      {#each data.versions as version}
        <a class="panel version-card" href={`/decks/${data.graph.deck.id}/versions/${version.versionId ?? version.id}`}>
          <div class="section-head">
            <strong>{version.versionName ?? version.batchName ?? `Version ${version.versionNumber ?? version.batchNumber}`}</strong>
            <span class="pill">{version.status}</span>
          </div>
          <p>{version.changeSummary ?? 'Accepted deck state'}</p>
          <div class="version-meta">
            <span>{(version.sourceSurface ?? 'deck').replaceAll('_', ' ')}</span>
            <span>{new Date(version.acceptedAt ?? version.createdAt).toLocaleString()}</span>
          </div>
        </a>
      {/each}
    </section>
  {:else}
    <section class="panel empty-panel">
      <strong>No saved versions yet</strong>
      <p>The initial Instant Deck becomes version 1. Later accepted changes create the next version.</p>
    </section>
  {/if}
</section>

<style>
  .versions-page { padding: 1.25rem; }
  .version-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem; }
  .version-card { display: grid; gap: 0.8rem; padding: 1.15rem; text-decoration: none; color: inherit; }
  .version-card p { margin: 0; color: var(--muted); }
  .version-meta { display: flex; justify-content: space-between; gap: 0.75rem; color: var(--muted); font-size: 0.84rem; text-transform: capitalize; }
  .empty-panel { padding: 1.2rem; }
  .selected-version-notice { display: grid; gap: .45rem; padding: 1rem 1.15rem; border-color: color-mix(in srgb, var(--accent) 55%, var(--line)); }
  .selected-version-notice p { margin: 0; color: var(--muted); }
  .selected-version-notice a { width: fit-content; color: var(--accent); font-weight: 700; }
</style>
