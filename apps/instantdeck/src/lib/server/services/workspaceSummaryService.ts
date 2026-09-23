export function normalizeWorkspaceSummary(workspace: Record<string, unknown>) {
  return {
    workspace: {
      workspace: workspace.workspace,
      deckCount: workspace.deck_count ?? workspace.deckCount ?? 0,
      activeDeckId: workspace.active_deck_id ?? workspace.activeDeckId ?? null,
      latestDecks: workspace.latest_decks ?? workspace.latestDecks ?? [],
      processingDeckCount: workspace.processing_deck_count ?? workspace.processingDeckCount ?? 0,
      readyDeckCount: workspace.ready_deck_count ?? workspace.readyDeckCount ?? 0,
      exportCount: workspace.export_count ?? workspace.exportCount ?? 0,
      firstTimeTemplates: workspace.first_time_templates ?? workspace.firstTimeTemplates ?? []
    }
  };
}
