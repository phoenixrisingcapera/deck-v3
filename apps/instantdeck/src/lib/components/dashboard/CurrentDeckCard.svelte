<script lang="ts">
  import { safeDashboardImageUrl } from '$lib/dashboard/imagePolicy';
  import type { DashboardDeckSummary } from '$lib/types/workspace-dashboard';

  interface Props {
    deck: DashboardDeckSummary | null;
  }

  let { deck }: Props = $props();
  const thumbnailUrl = $derived(safeDashboardImageUrl(deck?.thumbnailUrl));

  function editedDate(value: string | undefined) {
    // Keep the dashboard resilient when the backend has not sent an updated timestamp yet.
    if (!value) return 'Not edited yet';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Recently edited';
    // Use the visitor/server locale instead of hard-coded formatting so Railway deployments work globally.
    return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(date);
  }
</script>

<article class="panel current-deck">
  <div class="eyebrow">Current deck</div>
  {#if deck}
    <div class="thumb">
      {#if thumbnailUrl}
        <!-- Backend-provided deck thumbnail; the title remains the accessible alt text for screen readers. -->
        <img src={thumbnailUrl} alt={deck.title} />
      {:else}
        <!-- Fallback when no thumbnail has been generated yet. -->
        <span>{deck.title}</span>
      {/if}
    </div>
    <h3>{deck.title}</h3>
    <p>{deck.purpose}</p>
    <dl>
      <div>
        <dt>Last edited</dt>
        <dd>{editedDate(deck.updatedAt)}</dd>
      </div>
      <div>
        <dt>Slides</dt>
        <dd>{deck.slideCount}</dd>
      </div>
    </dl>
    <a class="button secondary" href={`/decks/${deck.id}/smart-deck`}>Open current deck</a>
  {:else}
    <p>No current deck yet.</p>
    <a class="button secondary" href="/decks/new">Upload new deck</a>
  {/if}
</article>

<style>
  .current-deck {
    display: grid;
    gap: 0.85rem;
    padding: 1rem;
  }

  .thumb {
    min-height: 9rem;
    display: grid;
    place-items: end start;
    overflow: hidden;
    border: 1px solid var(--line);
    border-radius: 8px;
    background:
      linear-gradient(145deg, rgba(14, 165, 233, 0.2), transparent 42%),
      linear-gradient(35deg, rgba(168, 85, 247, 0.2), transparent 52%),
      var(--surface-soft);
    padding: 1rem;
  }

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  h3,
  p,
  dl {
    margin: 0;
  }

  p,
  dt {
    color: var(--muted);
  }

  dl {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.75rem;
  }

  dd {
    margin: 0.15rem 0 0;
    font-weight: 700;
  }
</style>
