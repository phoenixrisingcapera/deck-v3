<script lang="ts">
  interface QuickAction {
    label: string;
    href: string;
    icon: string;
    tone: 'violet' | 'green' | 'amber' | 'blue';
  }

  interface Props {
    currentDeckId?: string | null;
  }

  let { currentDeckId = null }: Props = $props();

  const actions = $derived<QuickAction[]>([
    { label: 'New Deck', href: '/decks/new', icon: '↑', tone: 'violet' },
    { label: 'Smart Edit', href: currentDeckId ? `/decks/${currentDeckId}/smart-edit` : '/decks', icon: '✦', tone: 'green' },
    { label: 'Rebuild Deck', href: currentDeckId ? `/decks/${currentDeckId}/smart-deck` : '/decks', icon: '↻', tone: 'amber' },
    { label: 'Import Deck', href: '/decks/new', icon: '↓', tone: 'blue' },
    { label: 'Export Deck', href: currentDeckId ? `/decks/${currentDeckId}/export` : '/decks', icon: '⇪', tone: 'violet' },
    { label: 'LLM Report', href: currentDeckId ? `/decks/llm-report?deckId=${currentDeckId}` : '/decks/llm-report', icon: '◎', tone: 'green' }
  ]);
</script>

<section class="panel dashboard-card">
  <div class="dashboard-card__head">
    <h2>Quick Actions</h2>
  </div>

  <div class="quick-actions">
    {#each actions as action}
      <a class="quick-actions__item" href={action.href}>
        <span class={`quick-actions__icon quick-actions__icon--${action.tone}`}>{action.icon}</span>
        <strong>{action.label}</strong>
      </a>
    {/each}
  </div>
</section>
