export type ProductLayoutMode = 'page' | 'deck-workspace' | 'deck-document';

const DECK_WORKSPACE_PATH =
  /^\/decks\/[^/]+\/(?:smart-deck|instant-deck|smart-edit|due-diligence)(?:\/|$)/;
const DECK_DOCUMENT_PATH =
  /^\/decks\/[^/]+\/(?:diligence|export)(?:\/|$)/;

/**
 * Keep product-frame geometry in one place for every interactive deck surface.
 */
export function classifyProductLayoutMode(pathname: string): ProductLayoutMode {
  if (DECK_WORKSPACE_PATH.test(pathname)) return 'deck-workspace';
  if (DECK_DOCUMENT_PATH.test(pathname)) return 'deck-document';
  return 'page';
}

export function isFullHeightProductWorkspace(mode: ProductLayoutMode) {
  return mode === 'deck-workspace';
}
