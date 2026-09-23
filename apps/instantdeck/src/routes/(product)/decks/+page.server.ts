import type { Cookies } from '@sveltejs/kit';
import { listLatestDesignBatches } from '$server/services/designBatchService';
import { listDeckSummaries } from '$server/services/deckService';
import { loadLatestGeneratedDeck } from '$server/services/latestGeneratedDeckService';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { requireBackendUrl } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';
import { createDependencyStatus, createDeveloperToolsPayload } from '$lib/developer-tools/payload';
import type { DeckSummary, FirstTimeTemplatePreview, WorkspaceAiProviderRouteResponse, WorkspaceSummary } from '@deck-aistack-codes/shared';

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

const EMPTY_FIRST_TIME_TEMPLATES: FirstTimeTemplatePreview[] = [
  {
    id: 'template_vc_diligence',
    title: 'VC diligence rewrite',
    audienceLabel: 'Investment Committee',
    description: 'Restructure an uploaded founder deck into a cleaner diligence narrative with proof gaps called out.',
    tags: ['VC', 'Diligence', 'Investment committee'],
    ctaLabel: 'Browse template'
  },
  {
    id: 'template_lp_update',
    title: 'LP or board update',
    audienceLabel: 'LP / Board',
    description: 'Turn source material into an update format that keeps the signal high and the narrative compact.',
    tags: ['Board', 'LP', 'Status update'],
    ctaLabel: 'View sample'
  },
  {
    id: 'template_advisory_version',
    title: 'Advisory review version',
    audienceLabel: 'Advisor',
    description: 'Frame the same deck for operating partners, advisers, or strategic reviewers before export.',
    tags: ['Advisory', 'Strategy', 'Review'],
    ctaLabel: 'Open preview'
  }
];

type WorkspaceAiProviderSummary = WorkspaceAiProviderRouteResponse['summary'];

function emptyWorkspaceSummary(): WorkspaceSummary {
  return {
    workspace: {
      id: 'ws_default',
      name: 'Deck AIStack Workspace'
    },
    deckCount: 0,
    activeDeckId: null,
    latestDecks: [],
    processingDeckCount: 0,
    readyDeckCount: 0,
    exportCount: 0,
    firstTimeTemplates: EMPTY_FIRST_TIME_TEMPLATES
  };
}

function toDeckSummary(deck: {
  id: string;
  title: string;
  audience: string;
  purpose: string;
  status: string;
  summary: string;
  updatedAt: string;
}): DeckSummary {
  return {
    id: deck.id,
    title: deck.title,
    audience: deck.audience as DeckSummary['audience'],
    purpose: deck.purpose,
    status: deck.status as DeckSummary['status'],
    summary: deck.summary,
    updatedAt: deck.updatedAt
  };
}

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

async function loadPrivateWorkspacePageData(cookies: Cookies, fetcher: typeof fetch) {
  const startedAt = Date.now();
  const backendUrl = requireBackendUrl();

  const [workspaceResponse, aiProviderResponse, deckSummaries] = await Promise.all([
    fetcher(`${backendUrl}${deckProductApiPath('/workspace-summary')}`, {
      headers: requireBackendAuthHeaders(cookies)
    }),
    fetcher(`${backendUrl}/api/settings/workspace/ai-provider`, {
      headers: requireBackendAuthHeaders(cookies)
    }),
    listDeckSummaries({ cookies })
  ]);

  if (!workspaceResponse.ok) {
    throw new Error('Could not load workspace summary from the backend.');
  }
  if (!aiProviderResponse.ok) {
    throw new Error('Could not load workspace AI provider from the backend.');
  }

  const workspacePayload = (await workspaceResponse.json()) as Record<string, unknown>;
  const workspaceRecord = workspacePayload.workspace as Record<string, unknown> | undefined;
  const latestDecks = (workspacePayload.latest_decks as Record<string, unknown>[] | undefined) ?? [];
  const workspace: WorkspaceSummary = {
    workspace: {
      id: String(workspaceRecord?.id ?? 'ws_default'),
      name: String(workspaceRecord?.name ?? 'Deck AIStack Workspace')
    },
    deckCount: Number(workspacePayload.deck_count ?? 0),
    activeDeckId: (workspacePayload.active_deck_id as string | null | undefined) ?? null,
    latestDecks: latestDecks.map((deck) =>
      toDeckSummary({
        id: String(deck.id ?? ''),
        title: String(deck.title ?? 'Uploaded deck'),
        audience: String(deck.audience ?? 'Investment Committee'),
        purpose: String(deck.purpose ?? 'Initial diligence review'),
        status: String(deck.status ?? 'uploaded'),
        summary: String(deck.summary ?? ''),
        updatedAt: String(deck.updated_at ?? deck.updatedAt ?? '')
      })
    ),
    processingDeckCount: Number(workspacePayload.processing_deck_count ?? 0),
    readyDeckCount: Number(workspacePayload.ready_deck_count ?? 0),
    exportCount: Number(workspacePayload.export_count ?? 0),
    firstTimeTemplates: EMPTY_FIRST_TIME_TEMPLATES
  };

  const decks: DeckSummary[] = deckSummaries.map((deck) => ({
    id: deck.id,
    title: deck.title,
    audience: deck.audience as DeckSummary['audience'],
    purpose: deck.purpose,
    status: deck.status as DeckSummary['status'],
    summary: deck.summary,
    updatedAt: deck.updatedAt
  }));
  const latestBatches = workspace.activeDeckId ? await listLatestDesignBatches(workspace.activeDeckId, 3, cookies).catch(() => []) : [];
  const normalizedWorkspace = {
    ...workspace,
    latestDecks: workspace.latestDecks.length > 0 ? workspace.latestDecks : decks,
    deckCount: Math.max(workspace.deckCount, decks.length),
    readyDeckCount: Math.max(
      workspace.readyDeckCount,
      decks.filter((deck) => deck.status === 'ready' || deck.status === 'reviewed').length
    ),
    processingDeckCount:
      workspace.processingDeckCount ||
      decks.filter((deck) =>
        ['uploaded', 'parsing', 'structuring', 'extracting_blocks', 'classifying_blocks', 'analysing', 'adapting'].includes(deck.status)
      ).length
  };

  const completedAt = Date.now();

  return {
    workspace: normalizedWorkspace,
    decks,
    aiProviderSummary: normalizeAiProviderSummary(await aiProviderResponse.json()),
    latestBatches,
    backendDiagnostics: {
      workspaceStatus: workspaceResponse.status,
      workspaceRequestId: workspaceResponse.headers.get('x-request-id'),
      aiProviderStatus: aiProviderResponse.status,
      aiProviderRequestId: aiProviderResponse.headers.get('x-request-id'),
      requestedAt: new Date(startedAt).toISOString(),
      loadedAt: new Date(completedAt).toISOString(),
      loadDurationMs: completedAt - startedAt
    },
    developerToolsPayload: createDeveloperToolsPayload({
      route: {
        canonicalPath: '/decks',
        routeStatus: 'mounted_and_wired',
        routeNotice: null
      },
      subject: {
        workspaceId: normalizedWorkspace.workspace.id,
        deckId: normalizedWorkspace.activeDeckId,
        audience: decks[0]?.audience ?? null,
        activeDeckId: normalizedWorkspace.activeDeckId
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
        backendPath: `${backendUrl}${deckProductApiPath('/workspace-summary')}`,
        message: null
      },
      dependencies: [
        createDependencyStatus('workspace-summary', 'Workspace summary', {
          status: workspaceResponse.status,
          requestId: workspaceResponse.headers.get('x-request-id'),
          backendPath: `${backendUrl}${deckProductApiPath('/workspace-summary')}`
        }),
        createDependencyStatus('ai-provider', 'AI provider', {
          status: aiProviderResponse.status,
          requestId: aiProviderResponse.headers.get('x-request-id'),
          backendPath: `${backendUrl}/api/settings/workspace/ai-provider`
        })
      ]
    })
  };
}

export async function load({ cookies, fetch }) {
  const workspace = await loadPrivateWorkspacePageData(cookies, fetch);
  const latestGeneratedDeck = await loadLatestGeneratedDeck(fetch, cookies);

  return {
    ...workspace,
    latestGeneratedDeck
  };
}
