<script lang="ts">
  import StatusBadge from '$components/StatusBadge.svelte';
  import type { Deck } from '$types/domain';

  interface Props {
    deck: Deck;
  }

  let { deck }: Props = $props();
</script>

<a class="panel deck-card" href={`/decks/${deck.id}/smart-deck`}>
  {#if deck.thumbnailUrl || deck.previewUrl}
    <div class="deck-card__preview">
      <img src={deck.thumbnailUrl ?? deck.previewUrl ?? ''} alt="" loading="lazy" />
    </div>
  {/if}
  <div class="topline">
    <StatusBadge status={deck.status} />
    <span class="deck-id">{deck.id}</span>
  </div>
  <h3>{deck.title}</h3>
  <p>{deck.summary}</p>
  <dl>
    <div>
      <dt>Audience</dt>
      <dd>{deck.audience}</dd>
    </div>
    <div>
      <dt>Purpose</dt>
      <dd>{deck.purpose}</dd>
    </div>
  </dl>
</a>

<style>
  .deck-card {
    display: grid;
    gap: 1rem;
    padding: 1.2rem;
    background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02));
  }

  .deck-card__preview {
    aspect-ratio: 16 / 9;
    border: 1px solid var(--line);
    border-radius: 8px;
    overflow: hidden;
    background: #020617;
  }

  .deck-card__preview img {
    width: 100%;
    height: 100%;
    display: block;
    object-fit: cover;
  }

  .topline {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    align-items: center;
  }

  .deck-id {
    color: var(--muted);
    font-size: 0.78rem;
  }

  h3 {
    margin: 0 0 0.4rem;
  }

  p {
    margin: 0 0 1rem;
    color: var(--muted);
  }

  dl {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.75rem;
    margin: 0;
  }

  dt {
    color: var(--muted);
    font-size: 0.8rem;
  }

  dd {
    margin: 0.2rem 0 0;
    font-weight: 600;
  }
</style>
