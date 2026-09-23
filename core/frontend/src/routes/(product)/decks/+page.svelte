<script lang="ts">
  import AppShell from '$components/AppShell.svelte';
  import DeckLibraryPage from '$lib/components/decks/DeckLibraryPage.svelte';
  import DeveloperVisibilityCard from '$components/visibility/DeveloperVisibilityCard.svelte';
  import { createDeveloperVisibilityItems } from '$lib/developer-tools/payload';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();
  const developerDiagnostics = $derived(
    createDeveloperVisibilityItems(data.developerToolsPayload, [
      { label: 'Deck count', value: data.workspace.deckCount },
      { label: 'Ready decks', value: data.workspace.readyDeckCount },
      { label: 'Processing decks', value: data.workspace.processingDeckCount },
      { label: 'Latest generated deck', value: data.latestGeneratedDeck?.compiledDeckId ?? null }
    ])
  );
</script>

<AppShell
  title="Deck library"
  subtitle="Manage uploaded decks, recent decks, and final deck handoffs."
  activeNav="decks"
  deckLabel="All decks"
>
  {#snippet actions()}
    <a class="button" href={data.workspace.deckCount === 0 ? '/welcome' : '/decks/new'}>
      {data.workspace.deckCount === 0 ? 'Upload first deck' : 'New deck'}
    </a>
  {/snippet}

  <DeckLibraryPage
    workspace={data.workspace}
    decks={data.decks}
    latestGeneratedDeck={data.latestGeneratedDeck}
  />
  <DeveloperVisibilityCard
    title="Deck library developer tools"
    summary="Workspace counts, request correlation, and generated handoff visibility for this product route."
    items={developerDiagnostics}
  />
</AppShell>
