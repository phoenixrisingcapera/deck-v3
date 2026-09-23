<script lang="ts">
  import type { WorkspaceAiProviderRouteResponse, WorkspaceSummary } from '@deck-aistack-codes/shared';

  interface Props {
    workspace: WorkspaceSummary;
    aiProviderSummary: WorkspaceAiProviderRouteResponse['summary'];
  }

  let { workspace, aiProviderSummary }: Props = $props();
  const aiConfigured = $derived(aiProviderSummary.isConfigured);
</script>

<section class="empty-state panel">
  <div class="eyebrow">Get started</div>
  <h2>Upload your first deck</h2>
  <p class="muted">AI-powered analysis of narrative, traction, market fit, and ask quality.</p>
  <a class="button" href="/decks/new">Upload deck</a>
  <div class="status">
    <span class="status-dot" class:connected={aiConfigured}></span>
    <span>{aiConfigured ? 'AI connected' : 'Built-in AI ready'}</span>
  </div>
</section>

<style>
  .empty-state { padding: 48px; display: grid; gap: 12px; align-content: start; max-width: 420px; }
  .empty-state h2 { font-size: 20px; }
  .empty-state p { font-size: 13px; line-height: 1.6; }
  .status { display: flex; align-items: center; gap: 8px; margin-top: 8px; color: var(--text-muted); font-size: 12px; }
  .status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--text-muted); }
  .status-dot.connected { background: var(--success); }
</style>
