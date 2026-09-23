import { error, redirect } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import type { SmartDeckWorkspacePayload } from '$lib/api/smartDeckWorkspace';
import type { DeckGraph } from '$types/domain';

const FETCH_TIMEOUT_MS = 20_000;

type LoadInput = {
  deckId: string;
  url: URL;
  fetcher: typeof fetch;
  parent: () => Promise<Record<string, unknown>>;
};

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? value as Record<string, unknown> : {};
}

function safeMessage(payload: unknown, fallback: string) {
  const body = record(payload);
  const detail = record(body.detail);
  for (const value of [body.message, body.error, detail.message, detail.error]) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return fallback;
}

async function fetchBounded(fetcher: typeof fetch, path: string) {
  return fetcher(path, { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) }).catch(() => null);
}

export async function loadInstantDeckPage({ deckId, url, fetcher, parent }: LoadInput) {
  const workflowPath = deckProductApiPath(`/decks/${deckId}/workflow-state`);
  const workflowResponse = await fetchBounded(fetcher, workflowPath);
  if (workflowResponse?.status === 401 || workflowResponse?.status === 403) {
    throw redirect(303, `/auth/sign-in?next=${encodeURIComponent(url.pathname + url.search)}`);
  }
  if (workflowResponse?.status === 404) throw error(404, 'Deck not found');
  if (!workflowResponse?.ok) {
    const payload = await workflowResponse?.json().catch(() => null);
    throw error(workflowResponse?.status ?? 503, safeMessage(payload, 'Instant Deck status is temporarily unavailable.'));
  }

  const workflow = record(await workflowResponse.json().catch(() => null));
  const sourceReady = workflow.canOpenSmartDeck === true;
  const instantReady = workflow.canOpenInstantDeck === true;
  if (!sourceReady && !instantReady) {
    throw redirect(303, `/decks/${deckId}/processing${url.search}`);
  }

  const parentData = await parent();
  const graph = parentData.graph as DeckGraph | null | undefined;
  if (!graph) throw error(503, 'The persisted deck identity is temporarily unavailable.');

  const workspaceResponse = await fetchBounded(
    fetcher,
    deckProductApiPath(`/decks/${deckId}/instant-deck`)
  );
  if (workspaceResponse?.status === 401 || workspaceResponse?.status === 403) {
    throw redirect(303, `/auth/sign-in?next=${encodeURIComponent(url.pathname + url.search)}`);
  }
  const workspacePayload = workspaceResponse?.ok
    ? await workspaceResponse.json().catch(() => null) as SmartDeckWorkspacePayload | null
    : null;
  const workspaceErrorPayload = !workspaceResponse?.ok
    ? await workspaceResponse?.json().catch(() => null)
    : null;

  return {
    graph,
    smartDeckWorkspace: workspacePayload,
    smartDeckWorkspaceStatus: workspacePayload
      ? { status: 'ready' as const, backendStatus: workspaceResponse?.status ?? 200, message: null }
      : {
          status: 'degraded' as const,
          backendStatus: workspaceResponse?.status ?? 503,
          message: safeMessage(workspaceErrorPayload, 'The persisted Instant Deck workspace is temporarily unavailable.'),
          actionHref: `/decks/${deckId}/processing`,
          actionLabel: 'View processing'
        },
    workflowState: workflow,
    selectedDesignVersionId: url.searchParams.get('designVersionId'),
    selectedGeneratedSlideId: url.searchParams.get('generatedSlideId')
  };
}
