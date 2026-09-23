<!-- Purpose: shows latest compiled deck handoff summary card and deep links for final deck / iteration review. -->
<script lang="ts">
  import type { LatestGeneratedDeckCardModel } from '$lib/api/finalDeck';

  let {
    card
  }: {
    card: LatestGeneratedDeckCardModel;
  } = $props();

  const statusLabel = $derived(card.status === 'ready' ? 'Ready' : card.status === 'under_review' ? 'Under review' : 'Failed');
  // Keep the batch label readable for compact UI copy.
  const iterationLabel = $derived(card.latestBatchId.replace(/^batch_0*/, '') || card.latestBatchId);
</script>

<section class="panel latest-generated-card" aria-label="Latest generated deck">
  <div class="latest-generated-card__copy">
    <div class="eyebrow">Latest Generated Deck</div>
    <h2>{card.title}</h2>
    <p class="muted">
      {card.sourceFileName ? `Generated from ${card.sourceFileName}` : 'Generated from the active Smart Deck workspace'}
    </p>
    <div class="latest-generated-card__meta">
      <span>{card.slideCount ?? 0} slides</span>
      <span>Iteration {iterationLabel}</span>
      <span>{statusLabel}</span>
      <span>Finalized {new Date(card.finalizedAt).toLocaleString()}</span>
    </div>
  </div>

  <div class="latest-generated-card__actions">
    <a class="button" href={card.openHref}>Open final deck</a>
    {#if card.batchHref}
      <a class="button secondary" href={card.batchHref}>Review iteration</a>
    {/if}
    <button class="button secondary" type="button" disabled title="Analytics coming next: track recipient views and time spent.">
      Send Deck
    </button>
  </div>
</section>

<style>
  .latest-generated-card {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 1rem;
    align-items: center;
    padding: 1.15rem;
    border-color: rgba(24, 200, 255, 0.34);
    background:
      linear-gradient(135deg, rgba(24, 200, 255, 0.1), rgba(120, 90, 255, 0.08)),
      rgba(255, 255, 255, 0.025);
  }

  h2 {
    margin: 0.3rem 0 0;
  }

  .latest-generated-card__copy {
    display: grid;
    gap: 0.5rem;
  }

  .latest-generated-card__meta,
  .latest-generated-card__actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
    align-items: center;
  }

  .latest-generated-card__meta span {
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 0.42rem 0.62rem;
    color: var(--ink-soft);
    font-size: 0.84rem;
  }

  .latest-generated-card__actions {
    justify-content: end;
  }

  .latest-generated-card__actions button:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  @media (max-width: 960px) {
    .latest-generated-card {
      grid-template-columns: 1fr;
    }

    .latest-generated-card__actions {
      justify-content: start;
    }
  }
</style>
