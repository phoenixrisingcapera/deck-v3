import type { Cookies } from '@sveltejs/kit';
import type {
  DeckWorkspacePreferences,
  DeckShellToolId,
  UpdateDeckWorkspacePreferencesRequest
} from '@deck-aistack-codes/shared';
import { deckProductApiPath } from '$lib/contracts';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { requireBackendUrl } from '$server/backendApi';
const ALLOWED_TOOLS = new Set<DeckShellToolId>([
  'deck_map',
  'research',
  'slides',
  'design',
  'elements',
  'text',
  'media',
  'data',
  'ai_tools',
  'brand',
  'settings'
]);

function requireCookies(cookies: Cookies | undefined): Cookies {
  if (!cookies) {
    throw new Error('Authenticated backend access requires request cookies.');
  }
  return cookies;
}

function defaultWorkspacePreferences(deckId: string): DeckWorkspacePreferences {
  return {
    deckId,
    activeTool: 'slides',
    leftPanelOpen: true,
    selectedSlideId: null,
    lastBatchId: null,
    lastSlideVersionId: null,
    selectedElementType: null,
    selectedDataView: null,
    chatOpen: false,
    updatedAt: null
  };
}

function normalizeToolId(value: unknown): DeckShellToolId {
  const candidate = String(value ?? 'slides') as DeckShellToolId;
  return ALLOWED_TOOLS.has(candidate) ? candidate : 'slides';
}

function normalizeWorkspacePreferences(
  deckId: string,
  payload: Record<string, unknown> | undefined
): DeckWorkspacePreferences {
  if (!payload) {
    return defaultWorkspacePreferences(deckId);
  }

  return {
    deckId,
    activeTool: normalizeToolId(payload.activeTool),
    leftPanelOpen: Boolean(payload.leftPanelOpen ?? true),
    selectedSlideId: payload.selectedSlideId ? String(payload.selectedSlideId) : null,
    lastBatchId: payload.lastBatchId ? String(payload.lastBatchId) : null,
    lastSlideVersionId: payload.lastSlideVersionId ? String(payload.lastSlideVersionId) : null,
    selectedElementType: payload.selectedElementType ? String(payload.selectedElementType) : null,
    selectedDataView: payload.selectedDataView ? String(payload.selectedDataView) : null,
    chatOpen: Boolean(payload.chatOpen ?? false),
    updatedAt: payload.updatedAt ? String(payload.updatedAt) : null
  };
}

export async function getDeckWorkspacePreferences(deckId: string, cookies?: Cookies): Promise<DeckWorkspacePreferences> {
  const backendUrl = requireBackendUrl();

  const response = await fetch(`${backendUrl}${deckProductApiPath(`/decks/${deckId}/workspace/preferences`)}`, {
    headers: requireBackendAuthHeaders(requireCookies(cookies))
  });
  if (!response.ok) {
    if (response.status === 404) {
      return defaultWorkspacePreferences(deckId);
    }

    throw new Error('Could not load shell workspace preferences from the backend.');
  }

  const payload = (await response.json()) as { workspace?: Record<string, unknown> };
  return normalizeWorkspacePreferences(deckId, payload.workspace);
}

export async function updateDeckWorkspacePreferences(
  deckId: string,
  input: UpdateDeckWorkspacePreferencesRequest,
  cookies?: Cookies
): Promise<DeckWorkspacePreferences> {
  const backendUrl = requireBackendUrl();

  const response = await fetch(`${backendUrl}${deckProductApiPath(`/decks/${deckId}/workspace/preferences`)}`, {
    method: 'PATCH',
    headers: {
      ...requireBackendAuthHeaders(requireCookies(cookies)),
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(input)
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  const payload = (await response.json()) as { workspace?: Record<string, unknown> };
  return normalizeWorkspacePreferences(deckId, payload.workspace);
}
