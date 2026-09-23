import { fetchApiJsonOrThrow } from '$lib/api/apiError';

export type DeckMediaRole = 'logo' | 'board_picture' | 'deck_picture';
export type DeckMediaStatus = 'queued' | 'processing' | 'ready' | 'failed_retryable' | 'failed_final' | 'archived';

export type DeckMediaAsset = {
  id: string;
  deckId: string;
  role: DeckMediaRole;
  label: string | null;
  status: DeckMediaStatus;
  originalFilename: string;
  mimeType: string;
  sizeBytes: number;
  width: number | null;
  height: number | null;
  altText: string | null;
  contentUrl: string;
  thumbnailUrl: string | null;
  workflowJobId: string | null;
  errorMessage: string | null;
  llmEnabled: boolean;
};

export type DeckMediaList = { deckId: string; items: DeckMediaAsset[]; counts: Record<string, number> };

function path(deckId: string, suffix = '') {
  return `/api/products/deck-aistack-codes/decks/${deckId}/media${suffix}`;
}

export function listDeckMedia(deckId: string) {
  return fetchApiJsonOrThrow<DeckMediaList>(path(deckId), undefined, 'Media library could not be loaded.');
}

export function uploadDeckMedia(deckId: string, file: File, role: DeckMediaRole, label?: string) {
  const body = new FormData();
  body.set('file', file);
  body.set('role', role);
  if (label?.trim()) body.set('label', label.trim());
  return fetchApiJsonOrThrow<{ media: DeckMediaAsset }>(path(deckId), { method: 'POST', body }, 'Media upload failed.');
}

export function retryDeckMedia(deckId: string, mediaId: string) {
  return fetchApiJsonOrThrow<{ media: DeckMediaAsset }>(path(deckId, `/${mediaId}/retry`), { method: 'POST' }, 'Media processing could not be retried.');
}

export function archiveDeckMedia(deckId: string, mediaId: string) {
  return fetchApiJsonOrThrow<DeckMediaAsset>(path(deckId, `/${mediaId}/archive`), { method: 'POST' }, 'Media could not be archived.');
}
