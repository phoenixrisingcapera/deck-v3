<!-- Purpose: renders compiled deck result summary, slide outcome, and handoff links. -->
<script lang="ts">
  import type { CompiledDeckModel } from '$lib/api/finalDeck';

  interface Props {
    deckId: string;
    batchId: string;
    compiledDeck: CompiledDeckModel | null;
  }

  let { deckId, batchId, compiledDeck }: Props = $props();

  // Count accepted generated versions in the finalized deck for iteration performance metrics.
  const acceptedVersionCount = $derived(
    compiledDeck?.slides.filter((slide) => slide.choice === 'generated_version').length ?? 0
  );
  // Count kept original slides in the finalized deck for review traceability.
  const originalsKeptCount = $derived(
    compiledDeck?.slides.filter((slide) => slide.choice !== 'generated_version').length ?? 0
  );

  // Parse finalization timestamp with graceful fallback for invalid or missing payloads.
  function finalizedDate(value: string | undefined) {
    if (!value) return 'Just now';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Just now';
    return date.toLocaleString();
  }
</script>

{#if compiledDeck}
  <section class="compiled-state">
    <section class="panel compiled-hero">
      <div>
        <div class="eyebrow">Compiled deck</div>
        <h2>{compiledDeck.title}</h2>
        <p class="muted">
          Final deck prepared from accepted versions and originals kept during iteration review.
        </p>
      </div>
      <div class="compiled-actions">
        <a class="button" href={`/decks/${compiledDeck.deckId}/compiled/${compiledDeck.compiledDeckId}`}>Open Final Deck</a>
        <a class="button secondary" href={`/decks/${compiledDeck.deckId}/versions/${compiledDeck.batchId}`}>Review version</a>
      </div>
    </section>

    <section class="compiled-grid">
      <article class="panel metric-card">
        <span>Final deck</span>
        <strong>{compiledDeck.status}</strong>
      </article>
      <article class="panel metric-card">
        <span>Slides</span>
        <strong>{compiledDeck.slideCount}</strong>
      </article>
      <article class="panel metric-card">
        <span>Accepted versions</span>
        <strong>{acceptedVersionCount}</strong>
      </article>
      <article class="panel metric-card">
        <span>Originals kept</span>
        <strong>{originalsKeptCount}</strong>
      </article>
    </section>

    <section class="panel compiled-summary">
      <div class="section-head">
        <div>
          <div class="eyebrow">Finalization</div>
          <h3>Output summary</h3>
        </div>
        <span class="pill">Iteration {compiledDeck.batchId}</span>
      </div>
      <dl>
        <div>
          <dt>Source deck</dt>
          <dd>{compiledDeck.deckId}</dd>
        </div>
        <div>
          <dt>Finalized</dt>
          <dd>{finalizedDate(compiledDeck.finalizedAt)}</dd>
        </div>
        <div>
          <dt>Compiled deck ID</dt>
          <dd>{compiledDeck.compiledDeckId}</dd>
        </div>
      </dl>
    </section>

    <section class="compiled-slides">
      {#each compiledDeck.slides as slide}
        <article class="panel compiled-slide">
          <span>Slide {String(slide.slideIndex).padStart(2, '0')}</span>
          <strong>{slide.title}</strong>
          <small>{slide.choice === 'generated_version' ? 'Accepted version' : 'Original kept'}</small>
        </article>
      {/each}
    </section>
  </section>
{:else}
  <section class="panel compiled-error">
    <div>
      <div class="eyebrow">Compiled deck</div>
      <h2>Could not load the compiled deck</h2>
      <p class="muted">The final deck output is not available yet. Return to the deck library or review the iteration.</p>
    </div>
    <div class="compiled-actions">
      <a class="button" href="/decks">Back to deck library</a>
      <a class="button secondary" href={`/decks/${deckId}/versions/${batchId}`}>Review version</a>
    </div>
  </section>
{/if}

<style>
  .compiled-state {
    display: grid;
    gap: 1rem;
  }

  .compiled-hero,
  .compiled-error {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 1rem;
    align-items: center;
    padding: 1.25rem;
  }

  .compiled-actions {
    display: flex;
    gap: 0.7rem;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  h2,
  h3,
  p,
  dl {
    margin: 0;
  }

  h2 {
    margin-top: 0.35rem;
    font-size: clamp(1.8rem, 3vw, 2.6rem);
  }

  .compiled-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 1rem;
  }

  .metric-card {
    min-height: 7rem;
    display: grid;
    align-content: space-between;
    padding: 1rem;
  }

  .metric-card span,
  dt,
  small {
    color: var(--muted);
  }

  .metric-card strong {
    font-size: 1.55rem;
  }

  .compiled-summary {
    padding: 1.1rem;
  }

  .section-head {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 1rem;
    align-items: start;
  }

  dl {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.85rem;
  }

  dd {
    margin: 0.2rem 0 0;
    font-weight: 700;
    overflow-wrap: anywhere;
  }

  .compiled-slides {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.85rem;
  }

  .compiled-slide {
    padding: 1rem;
    display: grid;
    gap: 0.45rem;
  }

  @media (max-width: 960px) {
    .compiled-hero,
    .compiled-error,
    .compiled-grid,
    dl {
      grid-template-columns: 1fr;
    }

    .compiled-actions {
      justify-content: flex-start;
    }
  }
</style>
