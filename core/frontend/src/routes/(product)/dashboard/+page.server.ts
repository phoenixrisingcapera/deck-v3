import { error, isHttpError, isRedirect, redirect } from '@sveltejs/kit';
import type { Cookies } from '@sveltejs/kit';
import { getBackendAccessToken, requireBackendAuthHeaders } from '$server/backendAuth';
import { requireBackendUrl } from '$server/backendApi';
import { createDependencyStatus, createDeveloperToolsPayload } from '$lib/developer-tools/payload';
import { dashboardStatusToDeckSummaryStatus, dashboardStatusToDomainDeckStatus } from '$lib/dashboard/status';
import { workspaceDashboardSchema } from '$lib/dashboard/workspaceDashboardSchema';
import type { WorkspaceDashboardResponse } from '$lib/types/workspace-dashboard';
import type { Deck } from '$types/domain';
import type { DeckSummary, WorkspaceAiProviderRouteResponse, WorkspaceSummary } from '@deck-aistack-codes/shared';

const VALIDATION_STATUSES = new Set(['validated', 'skipped', 'degraded', 'unconfigured'] as const);

const EMPTY_AI_PROVIDER_SUMMARY: WorkspaceAiProviderSummary = {
  provider: null,
  preferredModel: null,
  reasoningModel: null,
  embeddingModel: null,
  apiKeyLast4: null,
  isConfigured: false,
  configuredAt: null,
  skippedAt: null,
  providerLabel: null,
  providerEnabled: true,
  discoverySupported: false,
  validationStatus: 'unconfigured',
  availableModels: [],
  defaults: {}
};

type WorkspaceAiProviderSummary = WorkspaceAiProviderRouteResponse['summary'];
type DashboardBackendDiagnostics = {
  dashboardStatus: number | null;
  dashboardRequestId: string | null;
  aiProviderStatus: number | null;
  aiProviderRequestId: string | null;
  routeNotice: string | null;
  requestedAt: string | null;
  loadedAt: string | null;
  loadDurationMs: number | null;
};

// DISABLED: Local status mappers were replaced by shared dashboard/status.ts helpers on 2026-07-14.
// Reason: The route and dashboard components must normalize backend deck states the same way.
// function deckSummaryStatus(status: string): DeckSummary['status'] {
//   if (status === 'preparing') return 'uploaded';
//   if (status === 'ready_to_review') return 'ready';
//   if (status === 'exported') return 'reviewed';
//   return status as DeckSummary['status'];
// }

// DISABLED: Local status mappers were replaced by shared dashboard/status.ts helpers on 2026-07-14.
// Reason: The route and dashboard components must normalize backend deck states the same way.
// function domainDeckStatus(status: string): Deck['status'] {
//   if (status === 'preparing') return 'uploaded';
//   if (status === 'ready_to_review') return 'ready';
//   if (status === 'exported') return 'reviewed';
//   return status as Deck['status'];
// }

function normalizeAiProviderSummary(payload: unknown): WorkspaceAiProviderSummary {
  const record = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {};
  const summary = record.summary && typeof record.summary === 'object' ? (record.summary as Record<string, unknown>) : record;

  const validationStatusCandidate =
    summary.validation_status === 'validated' ||
    summary.validation_status === 'skipped' ||
    summary.validation_status === 'degraded' ||
    summary.validation_status === 'unconfigured'
      ? summary.validation_status
      : summary.validationStatus === 'validated' ||
          summary.validationStatus === 'skipped' ||
          summary.validationStatus === 'degraded' ||
          summary.validationStatus === 'unconfigured'
        ? summary.validationStatus
        : 'unconfigured';
  const validationStatus: WorkspaceAiProviderSummary['validationStatus'] = VALIDATION_STATUSES.has(
    validationStatusCandidate as WorkspaceAiProviderSummary['validationStatus']
  )
    ? (validationStatusCandidate as WorkspaceAiProviderSummary['validationStatus'])
    : 'unconfigured';

  return {
    provider: typeof summary.provider === 'string' ? (summary.provider as WorkspaceAiProviderSummary['provider']) : null,
    preferredModel:
      typeof summary.preferred_model === 'string'
        ? summary.preferred_model
        : typeof summary.preferredModel === 'string'
          ? summary.preferredModel
          : null,
    reasoningModel:
      typeof summary.reasoning_model === 'string'
        ? summary.reasoning_model
        : typeof summary.reasoningModel === 'string'
          ? summary.reasoningModel
          : null,
    embeddingModel:
      typeof summary.embedding_model === 'string'
        ? summary.embedding_model
        : typeof summary.embeddingModel === 'string'
          ? summary.embeddingModel
          : null,
    apiKeyLast4:
      typeof summary.api_key_last4 === 'string'
        ? summary.api_key_last4
        : typeof summary.apiKeyLast4 === 'string'
          ? summary.apiKeyLast4
          : null,
    isConfigured: Boolean(summary.is_configured ?? summary.isConfigured ?? false),
    configuredAt:
      typeof summary.configured_at === 'string'
        ? summary.configured_at
        : typeof summary.configuredAt === 'string'
          ? summary.configuredAt
          : null,
    skippedAt:
      typeof summary.skipped_at === 'string'
        ? summary.skipped_at
        : typeof summary.skippedAt === 'string'
          ? summary.skippedAt
          : null,
    providerLabel:
      typeof summary.provider_label === 'string'
        ? summary.provider_label
        : typeof summary.providerLabel === 'string'
          ? summary.providerLabel
          : null,
    providerEnabled: Boolean(summary.provider_enabled ?? summary.providerEnabled ?? true),
    discoverySupported: Boolean(summary.discovery_supported ?? summary.discoverySupported ?? false),
    validationStatus,
    availableModels: Array.isArray(summary.available_models)
      ? summary.available_models
      : Array.isArray(summary.availableModels)
        ? summary.availableModels
        : [],
    defaults: typeof summary.defaults === 'object' && summary.defaults ? (summary.defaults as WorkspaceAiProviderSummary['defaults']) : {}
  };
}

async function loadBackendAiProviderSummary(fetcher: typeof fetch, cookies: Cookies, nextPath: string) {
  const backendUrl = requireBackendUrl();
  const response = await fetcher(`${backendUrl}/api/settings/workspace/ai-provider`, {
    headers: requireBackendAuthHeaders(cookies)
  });

  if (response.status === 401 || response.status === 403) {
    throw redirect(303, `/auth/sign-in?next=${encodeURIComponent(nextPath)}`);
  }
  if (!response.ok) {
    const message = await response.text().catch(() => 'Workspace AI provider request failed.');
    logDashboardLoadFailure('ai_provider_response_not_ok', message, { status: response.status });
    // DISABLED: Provider settings are optional dashboard context. Throwing here
    // hid otherwise healthy persisted deck data behind the global error page.
    // throw error(response.status, 'Workspace AI provider request failed.');
    return {
      summary: EMPTY_AI_PROVIDER_SUMMARY,
      backendDiagnostics: {
        aiProviderStatus: response.status,
        aiProviderRequestId: response.headers.get('x-request-id')
      },
      response
    };
  }

  return {
    summary: normalizeAiProviderSummary(await response.json()),
    backendDiagnostics: {
      aiProviderStatus: response.status,
      aiProviderRequestId: response.headers.get('x-request-id')
    },
    response
  };
}

function pageDataFromDashboard(
  dashboard: WorkspaceDashboardResponse,
  aiProviderSummary: WorkspaceAiProviderSummary = EMPTY_AI_PROVIDER_SUMMARY,
  backendDiagnostics: DashboardBackendDiagnostics
) {
  const latestDecks: DeckSummary[] = dashboard.decks.slice(0, 3).map((deck) => ({
    id: deck.id,
    title: deck.title,
    audience: deck.audience as DeckSummary['audience'],
    purpose: deck.purpose,
    status: dashboardStatusToDeckSummaryStatus(deck.status),
    summary: deck.description,
    updatedAt: deck.updatedAt
  }));
  const workspaceId = dashboard.workspace?.id ?? 'ws_backend';
  const workspaceName = dashboard.workspace?.name ?? 'Deck AIStack Workspace';
  const workspace: WorkspaceSummary = {
    workspace: {
      id: workspaceId,
      name: workspaceName
    },
    deckCount: dashboard.stats.uploadedDecks,
    activeDeckId: dashboard.latestDeck?.id ?? dashboard.decks[0]?.id ?? null,
    latestDecks,
    processingDeckCount: dashboard.decks.filter((deck) => deck.status === 'preparing').length,
    readyDeckCount: dashboard.decks.filter((deck) => ['ready_to_review', 'reviewed'].includes(deck.status)).length,
    exportCount: dashboard.decks.filter((deck) => deck.status === 'exported').length,
    firstTimeTemplates: []
  };
  const decks: Deck[] = dashboard.decks.map((deck) => ({
    id: deck.id,
    workspaceId,
    title: deck.title,
    audience: deck.audience,
    purpose: deck.purpose,
    status: dashboardStatusToDomainDeckStatus(deck.status),
    summary: deck.description,
    createdAt: deck.updatedAt,
    updatedAt: deck.updatedAt
  }));

  return {
    workspace,
    decks,
    aiProviderSummary,
    latestBatches: [],
    backendDiagnostics
  };
}

function logDashboardLoadFailure(reason: string, error: unknown, details: Record<string, unknown> = {}) {
  console.error('Dashboard load failed', {
    reason,
    ...details,
    error: error instanceof Error ? error.message : String(error)
  });
}

export async function load({ cookies, fetch, locals, url }) {
  const startedAt = Date.now();
  const backendUrl = requireBackendUrl();
  const nextPath = `${url.pathname}${url.search}`;
  const routeNotice = url.searchParams.get('notice');
  const token = getBackendAccessToken(cookies);
  if (!token) {
    throw redirect(303, `/auth/sign-in?next=${encodeURIComponent(nextPath)}`);
  }

  try {
    const [response, aiProviderResult] = await Promise.all([
      fetch(`${backendUrl}/api/workspace/dashboard`, {
        headers: requireBackendAuthHeaders(cookies)
      }),
      loadBackendAiProviderSummary(fetch, cookies, nextPath).catch((providerError) => {
        if (isRedirect(providerError)) throw providerError;
        logDashboardLoadFailure('ai_provider_request_failed', providerError);
        return {
          summary: EMPTY_AI_PROVIDER_SUMMARY,
          backendDiagnostics: {
            aiProviderStatus: null,
            aiProviderRequestId: null
          },
          response: null
        };
      })
    ]);

    if (response.status === 401 || response.status === 403) {
      throw redirect(303, `/auth/sign-in?next=${encodeURIComponent(nextPath)}`);
    }

    if (!response.ok) {
      const message = await response.text().catch(() => 'Backend dashboard request failed.');
      logDashboardLoadFailure('backend_response_not_ok', message, { status: response.status });
      throw error(response.status, 'Workspace dashboard backend request failed.');
    }

    const rawDashboard = await response.json();
    const parsedDashboard = workspaceDashboardSchema.safeParse(rawDashboard);
    if (!parsedDashboard.success) {
      logDashboardLoadFailure('backend_payload_invalid', parsedDashboard.error.flatten());
      throw error(502, 'Workspace dashboard backend returned invalid data.');
    }

    const dashboard = parsedDashboard.data satisfies WorkspaceDashboardResponse;
    if (dashboard.stats.uploadedDecks === 0 || dashboard.decks.length === 0) {
      const nextWelcome = routeNotice ? `/welcome?notice=${encodeURIComponent(routeNotice)}` : '/welcome';
      throw redirect(303, nextWelcome);
    }
    const completedAt = Date.now();
    const backendDiagnostics: DashboardBackendDiagnostics = {
      dashboardStatus: response.status,
      dashboardRequestId: response.headers.get('x-request-id'),
      aiProviderStatus: aiProviderResult.backendDiagnostics.aiProviderStatus,
      aiProviderRequestId: aiProviderResult.backendDiagnostics.aiProviderRequestId,
      routeNotice,
      requestedAt: new Date(startedAt).toISOString(),
      loadedAt: new Date(completedAt).toISOString(),
      loadDurationMs: completedAt - startedAt
    };
    const dashboardPath = `${backendUrl}/api/workspace/dashboard`;
    const aiProviderPath = `${backendUrl}/api/settings/workspace/ai-provider`;
    return {
      dashboard,
      ...pageDataFromDashboard(dashboard, aiProviderResult.summary, backendDiagnostics),
      developerToolsPayload: createDeveloperToolsPayload({
        route: {
          canonicalPath: '/dashboard',
          routeStatus: 'mounted_and_wired',
          routeNotice
        },
        subject: {
          workspaceId: dashboard.workspace?.id ?? 'ws_backend',
          deckId: dashboard.latestDeck?.id ?? dashboard.decks[0]?.id ?? null,
          audience: dashboard.latestDeck?.audience ?? dashboard.decks[0]?.audience ?? null,
          activeDeckId: dashboard.latestDeck?.id ?? dashboard.decks[0]?.id ?? null
        },
        load: {
          requestedAt: backendDiagnostics.requestedAt,
          loadedAt: backendDiagnostics.loadedAt,
          loadDurationMs: backendDiagnostics.loadDurationMs
        },
        correlation: {
          backendStatus: response.status,
          requestId: response.headers.get('x-request-id'),
          ticketId: null,
          backendPath: dashboardPath,
          message: null
        },
        dependencies: [
          createDependencyStatus('dashboard', 'Dashboard', {
            status: response.status,
            requestId: response.headers.get('x-request-id'),
            backendPath: dashboardPath
          }),
          createDependencyStatus('ai-provider', 'AI provider', {
            status: aiProviderResult.backendDiagnostics.aiProviderStatus,
            requestId: aiProviderResult.backendDiagnostics.aiProviderRequestId,
            backendPath: aiProviderPath
          })
        ]
      })
    };
  } catch (err) {
    if (isRedirect(err)) {
      throw err;
    }
    if (isHttpError(err)) {
      throw err;
    }

    logDashboardLoadFailure('backend_fetch_failed', err, { backendConfigured: true });
    throw error(503, 'Workspace dashboard backend is unavailable.');
  }
}
