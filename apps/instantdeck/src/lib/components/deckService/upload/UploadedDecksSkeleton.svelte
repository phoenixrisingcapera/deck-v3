<!-- Purpose: renders loading skeleton rows while uploaded deck data is fetched. -->
<div class="uploaded-decks-skeleton" aria-hidden="true">
  {#each Array.from({ length: 3 }) as _, index}
    <div class="uploaded-decks-skeleton__row" style={`animation-delay:${index * 90}ms`}>
      <div class="uploaded-decks-skeleton__icon"></div>
      <div class="uploaded-decks-skeleton__copy">
        <span></span>
        <span></span>
      </div>
      <div class="uploaded-decks-skeleton__badge"></div>
    </div>
  {/each}
</div>

<style>
  .uploaded-decks-skeleton {
    display: grid;
    gap: 0.75rem;
  }

  .uploaded-decks-skeleton__row {
    display: grid;
    grid-template-columns: 44px minmax(0, 1fr) 96px;
    gap: 0.8rem;
    align-items: center;
    padding: 0.9rem 1rem;
    border-radius: 14px;
    border: 1px solid rgba(81, 107, 165, 0.26);
    background: rgba(18, 29, 56, 0.9);
    animation: uploaded-decks-pulse 1.2s ease-in-out infinite;
  }

  .uploaded-decks-skeleton__icon,
  .uploaded-decks-skeleton__copy span,
  .uploaded-decks-skeleton__badge {
    border-radius: 999px;
    background: linear-gradient(90deg, rgba(90, 111, 162, 0.22), rgba(125, 148, 208, 0.34), rgba(90, 111, 162, 0.22));
  }

  .uploaded-decks-skeleton__icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
  }

  .uploaded-decks-skeleton__copy {
    display: grid;
    gap: 0.45rem;
  }

  .uploaded-decks-skeleton__copy span:first-child {
    width: min(260px, 80%);
    height: 14px;
  }

  .uploaded-decks-skeleton__copy span:last-child {
    width: min(140px, 55%);
    height: 11px;
  }

  .uploaded-decks-skeleton__badge {
    width: 96px;
    height: 32px;
    justify-self: end;
  }

  @keyframes uploaded-decks-pulse {
    0%, 100% {
      opacity: 0.72;
    }

    50% {
      opacity: 1;
    }
  }

  @media (max-width: 720px) {
    .uploaded-decks-skeleton__row {
      grid-template-columns: 44px minmax(0, 1fr);
    }

    .uploaded-decks-skeleton__badge {
      grid-column: 2;
      justify-self: start;
    }
  }
</style>
