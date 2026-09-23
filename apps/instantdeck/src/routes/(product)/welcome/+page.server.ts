import type { WorkspaceSummary } from '@deck-aistack-codes/shared';
import { deckProductApiPath } from '$lib/contracts';
import { createDependencyStatus, createDeveloperToolsPayload } from '$lib/developer-tools/payload';
import type { PageServerLoad } from './$types';

const EMPTY_AI_PROVIDER_SUMMARY = {
  provider: null,
  preferredModel: null,
  apiKeyLast4: null,
  isConfigured: false,
  configuredAt: null,
  skippedAt: null
} as const;

const TESTER_EMPTY_WORKSPACE = {
  workspace: { id: 'ws_tester_entry', name: 'Deck AIStack Workspace' },
  deckCount: 0,
  activeDeckId: null,
  latestDecks: [],
  processingDeckCount: 0,
  readyDeckCount: 0,
  exportCount: 0,
  firstTimeTemplates: []
} satisfies WorkspaceSummary;

const FALLBACK_MESSAGE =
  'We could not load your previous decks right now. You can still upload a new deck and continue testing.';

async function readJsonResponse(response: Response) {
  return response.json().catch(() => null);
}

function firstString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return null;
}

function readFailureTicketId(payload: unknown) {
  const record = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : null;
  const detail = record?.detail && typeof record.detail === 'object' ? (record.detail as Record<string, unknown>) : null;
  return firstString(record?.ticketId, record?.ticket_id, detail?.ticketId, detail?.ticket_id);
}

function workspaceFallback(
  status: number,
  message: string,
  locals: App.Locals,
  routeNotice: string | null,
  options: {
    requestId?: string | null;
    ticketId?: string | null;
    requestedAt?: string | null;
    loadedAt?: string | null;
    loadDurationMs?: number | null;
  } = {}
) {
  const dependency = createDependencyStatus('workspace-summary', 'Workspace summary', {
    status,
    requestId: options.requestId ?? null,
    ticketId: options.ticketId ?? null,
    backendPath: deckProductApiPath('/workspace-summary'),
    message
  });
  return {
    workspace: TESTER_EMPTY_WORKSPACE,
    decks: [],
    aiProviderSummary: EMPTY_AI_PROVIDER_SUMMARY,
    latestBatches: [],
    routeNotice,
    workspaceLoadStatus: {
      status: 'degraded' as const,
      backendStatus: status,
      message,
      requestId: options.requestId ?? null,
      ticketId: options.ticketId ?? null,
      requestedAt: options.requestedAt ?? null,
      loadedAt: options.loadedAt ?? null,
      loadDurationMs: options.loadDurationMs ?? null
    },
    developerToolsPayload: createDeveloperToolsPayload({
      route: {
        canonicalPath: '/welcome',
        routeStatus: 'mounted_but_degraded',
        routeNotice
      },
      subject: {
        workspaceId: TESTER_EMPTY_WORKSPACE.workspace.id,
        deckId: null,
        audience: null,
        activeDeckId: TESTER_EMPTY_WORKSPACE.activeDeckId
      },
      load: {
        requestedAt: options.requestedAt ?? null,
        loadedAt: options.loadedAt ?? null,
        loadDurationMs: options.loadDurationMs ?? null
      },
      correlation: {
        backendStatus: status,
        requestId: options.requestId ?? null,
        ticketId: options.ticketId ?? null,
        backendPath: deckProductApiPath('/workspace-summary'),
        message
      },
      degradation: {
        status: 'degraded',
        issues: [
          {
            key: dependency.key,
            label: dependency.label,
            status: dependency.status,
            requestId: dependency.requestId,
            ticketId: dependency.ticketId,
            message: dependency.message
          }
        ],
        actionHref: '/decks/new',
        actionLabel: 'Upload deck'
      },
      dependencies: [dependency]
    })
  };
}

export const load: PageServerLoad = async ({ fetch, locals, url }) => {
  const startedAt = Date.now();
  const routeNotice = url.searchParams.get('notice') === 'admin-internal' ? 'admin-internal' : null;
  const workspaceResult = await fetch(deckProductApiPath('/workspace-summary')).catch(() => null);

  if (!workspaceResult) {
    const completedAt = Date.now();
    console.error('[welcome] workspace summary request rejected before reaching backend');
    return workspaceFallback(503, FALLBACK_MESSAGE, locals, routeNotice, {
      requestedAt: new Date(startedAt).toISOString(),
      loadedAt: new Date(completedAt).toISOString(),
      loadDurationMs: completedAt - startedAt
    });
  }

  const workspaceResponse = workspaceResult;
  if (!workspaceResponse.ok) {
    const payload = await readJsonResponse(workspaceResponse);
    const requestId = workspaceResponse.headers.get('x-request-id');
    const ticketId = readFailureTicketId(payload);
    const completedAt = Date.now();
    console.error('[welcome] workspace summary request failed', {
      status: workspaceResponse.status,
      hasPayload: Boolean(payload),
      requestId,
      ticketId
    });
    return workspaceFallback(workspaceResponse.status, FALLBACK_MESSAGE, locals, routeNotice, {
      requestId,
      ticketId,
      requestedAt: new Date(startedAt).toISOString(),
      loadedAt: new Date(completedAt).toISOString(),
      loadDurationMs: completedAt - startedAt
    });
  }

  const workspacePayload = (await workspaceResponse.json()) as { workspace: WorkspaceSummary };
  const completedAt = Date.now();
  const data = {
    workspace: workspacePayload.workspace,
    decks: workspacePayload.workspace.latestDecks ?? [],
    aiProviderSummary: EMPTY_AI_PROVIDER_SUMMARY,
    latestBatches: [],
    sessionUser: locals.sessionUser
      ? {
          id: locals.sessionUser.id,
          email: locals.sessionUser.email,
          name: locals.sessionUser.name,
          role: locals.sessionUser.role
        }
      : null,
    routeNotice,
    workspaceLoadStatus: {
      status: 'ready' as const,
      backendStatus: workspaceResponse.status,
      message: null,
      requestId: workspaceResponse.headers.get('x-request-id'),
      ticketId: null,
      requestedAt: new Date(startedAt).toISOString(),
      loadedAt: new Date(completedAt).toISOString(),
      loadDurationMs: completedAt - startedAt
    },
    developerToolsPayload: createDeveloperToolsPayload({
      route: {
        canonicalPath: '/welcome',
        routeStatus: 'mounted_and_wired',
        routeNotice
      },
      subject: {
        workspaceId: workspacePayload.workspace.workspace.id,
        deckId: workspacePayload.workspace.activeDeckId,
        audience: workspacePayload.workspace.latestDecks?.[0]?.audience ?? null,
        activeDeckId: workspacePayload.workspace.activeDeckId
      },
      load: {
        requestedAt: new Date(startedAt).toISOString(),
        loadedAt: new Date(completedAt).toISOString(),
        loadDurationMs: completedAt - startedAt
      },
      correlation: {
        backendStatus: workspaceResponse.status,
        requestId: workspaceResponse.headers.get('x-request-id'),
        ticketId: null,
        backendPath: deckProductApiPath('/workspace-summary'),
        message: null
      },
      dependencies: [
        createDependencyStatus('workspace-summary', 'Workspace summary', {
          status: workspaceResponse.status,
          requestId: workspaceResponse.headers.get('x-request-id'),
          backendPath: deckProductApiPath('/workspace-summary')
        })
      ]
    })
  };

  return data;
};
