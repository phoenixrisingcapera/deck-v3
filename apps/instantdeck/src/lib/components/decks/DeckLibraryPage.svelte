<!-- Purpose: deck library dashboard, entry actions, and recent deck list wiring for smart-deck and final-deck flows. -->
<script lang="ts">
  import { goto } from '$app/navigation';
  import EmptyState from '$components/EmptyState.svelte';
  import SampleTemplatesRow from '$components/SampleTemplatesRow.svelte';
  import UploadFirstDeckCard from '$components/UploadFirstDeckCard.svelte';
  import LatestGeneratedDeckCard from '$lib/components/decks/LatestGeneratedDeckCard.svelte';
  import UploadedDecksList from '$lib/components/deckService/upload/UploadedDecksList.svelte';
  import {
    mapDeckToUploadedDeck,
    type UploadedDeckListItem
  } from '$lib/components/deckService/upload/uploaded-decks-list.types';
  import type { LatestGeneratedDeckCardModel } from '$lib/api/finalDeck';
  import type { Deck } from '$types/domain';
  import type { DeckSummary, WorkspaceSummary } from '$lib/contracts/types';

  interface Props {
    workspace: WorkspaceSummary;
    decks: DeckSummary[];
    latestGeneratedDeck: LatestGeneratedDeckCardModel | null;
  }

  let { workspace, decks, latestGeneratedDeck }: Props = $props();

  function formatFileSize(size: number) {
    // Preserve compact human-friendly file-size labels used by uploaded deck list rows.
    if (size < 1024 * 1024) {
      return `${Math.max(1, Math.round(size / 1024))} KB`;
    }

    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }

  function formatRelativeUploadDate(value: string | null | undefined) {
    // Convert upload date into fuzzy age text, with safe fallback for invalid inputs.
    if (!value) return null;

    const timestamp = new Date(value).getTime();
    if (Number.isNaN(timestamp)) return null;

    const deltaSeconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
    if (deltaSeconds < 60) return 'Just now';

    const deltaMinutes = Math.round(deltaSeconds / 60);
    if (deltaMinutes < 60) return `${deltaMinutes}m ago`;

    const deltaHours = Math.round(deltaMinutes / 60);
    if (deltaHours < 24) return `${deltaHours}h ago`;

    const deltaDays = Math.round(deltaHours / 24);
    if (deltaDays < 7) return `${deltaDays}d ago`;

    return new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric' }).format(new Date(timestamp));
  }

  // Build normalized uploaded-deck rows from backend deck summaries.
  const uploadedDecks = $derived(
    decks.map((deck) =>
      mapDeckToUploadedDeck(deck as unknown as Deck, {
        formatFileSize,
        formatRelativeUploadDate
      })
    )
  );
  // Only the three most recent decks are surfaced in the sidebar.
  const recentDecks = $derived(decks.slice(0, 3));
</script>

<section class="deck-library">
  <main class="deck-library__main">
    <section class="panel library-hero">
      <div class="library-hero__copy">
        <div class="eyebrow">Decks</div>
        <h2>Your decks</h2>
        <p class="muted">Open a deck or start a new one.</p>
        <div class="library-hero__actions">
          <a class="button" href="/decks/new">
            {workspace.deckCount === 0 ? 'Upload first deck' : 'New deck'}
          </a>
          {#if workspace.activeDeckId}
            <a class="button secondary" href={`/decks/${workspace.activeDeckId}/smart-deck`}>Open deck</a>
          {/if}
        </div>
      </div>

      <div class="library-hero__metrics">
        <article>
          <span>Uploaded decks</span>
          <strong>{workspace.deckCount}</strong>
        </article>
        <article>
          <span>Ready to review</span>
          <strong>{workspace.readyDeckCount}</strong>
        </article>
        <article>
          <span>Recent decks</span>
          <strong>{recentDecks.length}</strong>
        </article>
      </div>
    </section>

    <section class="panel list-shell">
      <div class="header-row">
        <div>
          <div class="eyebrow">Library</div>
          <h2>Uploaded decks</h2>
        </div>
        <a class="link" href="/decks/new">New deck</a>
      </div>

      {#if workspace.deckCount === 0}
        <div class="section-stack">
          <EmptyState
            eyebrow="Deck library"
            title="No decks yet"
            message="Upload a deck to start your workspace, review AI suggestions, and track new versions in one place."
          />
          <UploadFirstDeckCard
            on:uploaded={(event) => {
              goto(`/decks/${event.detail.deckId}/processing`);
            }}
          />
          <SampleTemplatesRow templates={workspace.firstTimeTemplates} />
        </div>
      {:else}
        <UploadedDecksList
          decks={uploadedDecks}
          maxHeight={420}
          onSelectDeck={(deck) => {
            goto(`/decks/${deck.id}/smart-deck`);
          }}
        />
      {/if}
    </section>

    {#if latestGeneratedDeck}
      <LatestGeneratedDeckCard card={latestGeneratedDeck} />
    {/if}
  </main>

  <aside class="deck-library__rail">
    <!-- DISABLED: Status filters have no query or local filter contract. Preserve the
         historical controls without presenting unavailable actions to users. -->
    {#if false}
    <section class="panel rail-card">
      <div class="section-head">
        <div>
          <div class="eyebrow">Views</div>
          <h3>Deck status</h3>
        </div>
      </div>
      <!-- DISABLED: status-filter controls are not wired to a real query or local
           filter state yet. Keep the current view visible, but do not present
           the other states as working product controls. -->
      <button type="button" class="view active" disabled aria-disabled="true">All decks</button>
      <button type="button" class="view" disabled aria-disabled="true" title="Status filter is not wired yet">Under review</button>
      <button type="button" class="view" disabled aria-disabled="true" title="Status filter is not wired yet">Ready</button>
      <button type="button" class="view" disabled aria-disabled="true" title="Status filter is not wired yet">Failed</button>
    </section>
    {/if}

    <section class="panel rail-card">
      <div class="section-head">
        <div>
          <div class="eyebrow">Recent decks</div>
          <h3>Open deck</h3>
        </div>
        <a class="link" href="/decks">View all</a>
      </div>
      <div class="recent-decks">
        {#each recentDecks as deck}
          <a class="recent-deck" href={`/decks/${deck.id}/smart-deck`}>
            <strong>{deck.title}</strong>
            <span>{deck.purpose}</span>
          </a>
        {:else}
          <p class="muted">No recent decks yet.</p>
        {/each}
      </div>
    </section>
  </aside>
</section>

<style>
  .deck-library {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 360px;
    gap: 1rem;
    align-items: start;
  }

  .deck-library__main,
  .deck-library__rail {
    display: grid;
    gap: 1rem;
    min-width: 0;
  }

  .rail-card,
  .list-shell,
  .library-hero {
    padding: 1.1rem;
  }

  .library-hero {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(280px, 0.55fr);
    gap: 1rem;
    align-items: end;
  }

  .library-hero__copy {
    display: grid;
    gap: 0.8rem;
  }

  .library-hero__actions {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .library-hero__metrics {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.65rem;
  }

  .library-hero__metrics article {
    min-height: 6rem;
    display: grid;
    align-content: space-between;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--surface-soft);
    padding: 0.85rem;
  }

  .library-hero__metrics span,
  .recent-deck span {
    color: var(--muted);
    font-size: 0.82rem;
  }

  .library-hero__metrics strong {
    font-size: 1.65rem;
  }

  .rail-card {
    display: grid;
    align-content: start;
    gap: 0.65rem;
  }

  .view {
    border: 1px solid var(--line);
    border-radius: 14px;
    background: transparent;
    color: var(--ink-soft);
    text-align: left;
    padding: 0.8rem 0.9rem;
  }

  .view.active {
    background: rgba(24, 200, 255, 0.1);
    color: var(--accent);
  }

  .header-row {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: end;
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }

  h2 {
    margin: 0.35rem 0 0;
  }

  h3 {
    margin: 0.25rem 0 0;
  }

  .section-head {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: start;
  }

  .link {
    color: var(--muted);
    font-weight: 700;
  }

  .recent-decks {
    display: grid;
    gap: 0.7rem;
  }

  .recent-deck {
    display: grid;
    gap: 0.2rem;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--surface-soft);
    padding: 0.85rem;
  }

  @media (max-width: 1180px) {
    .deck-library,
    .library-hero,
    .library-hero__metrics {
      grid-template-columns: 1fr;
    }
  }
</style>
