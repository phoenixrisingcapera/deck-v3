import { error, redirect } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { createDependencyStatus, createDeveloperToolsPayload } from '$lib/developer-tools/payload';
import { normalizeSmartDeckProcessingStatus, type SmartDeckProcessingStatusWithDiagnostics } from '$lib/api/deckService/workflow.client';

function fallbackProcessingStatus(deckId: string, backendStatus = 503, message = 'Could not load deck processing status.'): SmartDeckProcessingStatusWithDiagnostics {
  return {
    deckId,
    status: 'failed',
    // A status-service outage is not evidence that deck processing itself
    // failed. Keep workflow retry disabled and let the page retry only the
    // read request.
    nextAction: 'manual_review',
    sourceFileSaved: false,
    sourceSlideCount: 0,
    sourceSlides: [],
    deckExtractionStatus: 'failed',
    phases: [],
    stages: [],
    canOpenSmartDeck: false,
    canOpenInstantDeck: false,
    canRetry: false,
    processingStage: 'preparing_workspace',
    processingStageLabel: 'Preparing workspace',
    message,
    errorMessage: message,
    backendStatus,
    requestId: null,
    ticketId: null
  };
}

function firstString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return null;
}

function readTicketId(payload: unknown) {
  const record = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : null;
  const detail = record?.detail && typeof record.detail === 'object' ? (record.detail as Record<string, unknown>) : null;
  return firstString(record?.ticketId, record?.ticket_id, detail?.ticketId, detail?.ticket_id);
}

export async function load({ params, url, fetch }) {
  const startedAt = Date.now();
  const workflowStatePath = deckProductApiPath(`/decks/${params.deckId}/workflow-state`);
  // Contract name: fetchWorkflowState. The canonical product proxy performs
  // this shared backend fetch for the processing route.
  let response: Response;
  try {
    response = await fetch(workflowStatePath);
  } catch {
    const completedAt = Date.now();
    return {
      deckId: params.deckId,
      initialStatus: fallbackProcessingStatus(params.deckId, 503, 'Could not reach the processing status endpoint.'),
      initialDiagnostics: {
        requestedAt: new Date(startedAt).toISOString(),
        loadedAt: new Date(completedAt).toISOString(),
        loadDurationMs: completedAt - startedAt
      },
      developerToolsPayload: createDeveloperToolsPayload({
        route: {
          canonicalPath: `/decks/${params.deckId}/processing`,
          routeStatus: 'mounted_but_degraded',
          routeNotice: null
        },
        subject: {
          workspaceId: null,
          deckId: params.deckId,
          audience: null,
          activeDeckId: params.deckId
        },
        load: {
          requestedAt: new Date(startedAt).toISOString(),
          loadedAt: new Date(completedAt).toISOString(),
          loadDurationMs: completedAt - startedAt
        },
        correlation: {
          backendStatus: 503,
          requestId: null,
          ticketId: null,
          backendPath: workflowStatePath,
          message: 'Could not reach the processing status endpoint.'
        },
        workflow: {
          status: 'failed',
          nextAction: 'retry_job',
          activeStage: 'preparing_workspace',
          runId: null,
          jobId: null,
          canRetry: false,
          canOpenSmartDeck: false
        },
        degradation: {
          status: 'degraded',
          issues: [
            {
              key: 'workflow-state',
              label: 'Workflow state',
              status: 503,
              requestId: null,
              ticketId: null,
              message: 'Could not reach the processing status endpoint.'
            }
          ],
          actionHref: null,
          actionLabel: null
        },
        dependencies: [
          createDependencyStatus('workflow-state', 'Workflow state', {
            status: 503,
            backendPath: workflowStatePath,
            message: 'Could not reach the processing status endpoint.'
          })
        ]
      })
    };
  }

  if (response.status === 401 || response.status === 403) {
    throw redirect(303, `/auth/sign-in?next=${encodeURIComponent(url.pathname + url.search)}`);
  }
  if (response.status === 404) {
    throw error(404, 'Deck processing status was not found.');
  }

  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload) {
    const completedAt = Date.now();
    const status = fallbackProcessingStatus(
      params.deckId,
      response.status || 503,
      typeof payload?.message === 'string' ? payload.message : 'Could not load deck processing status.'
    );
    status.requestId = response.headers.get('x-request-id');
    status.ticketId = readTicketId(payload);
    return {
      deckId: params.deckId,
      initialStatus: status,
      initialDiagnostics: {
        requestedAt: new Date(startedAt).toISOString(),
        loadedAt: new Date(completedAt).toISOString(),
        loadDurationMs: completedAt - startedAt
      },
      developerToolsPayload: createDeveloperToolsPayload({
        route: {
          canonicalPath: `/decks/${params.deckId}/processing`,
          routeStatus: 'mounted_but_degraded',
          routeNotice: null
        },
        subject: {
          workspaceId: null,
          deckId: params.deckId,
          audience: null,
          activeDeckId: params.deckId
        },
        load: {
          requestedAt: new Date(startedAt).toISOString(),
          loadedAt: new Date(completedAt).toISOString(),
          loadDurationMs: completedAt - startedAt
        },
        correlation: {
          backendStatus: status.backendStatus ?? response.status,
          requestId: status.requestId,
          ticketId: status.ticketId,
          backendPath: workflowStatePath,
          message: status.message ?? status.errorMessage ?? null
        },
        workflow: {
          status: status.status,
          nextAction: status.nextAction ?? null,
          activeStage: status.activeStage ?? status.processingStage ?? null,
          runId: null,
          jobId: null,
          canRetry: status.canRetry,
          canOpenSmartDeck: status.canOpenSmartDeck
        },
        artifacts: {
          sourceFileStatus: status.sourceFileStatus ?? (status.sourceFileSaved ? 'saved' : 'missing'),
          sourceSlideCount: status.sourceSlideCount ?? null,
          generatedSlideCount: null,
          latestExportId: null,
          latestExportType: null,
          activeDesignVersionId: null,
          activeGeneratedSlideId: null,
          knowledgePackageName: null,
          knowledgePackageVersion: null
        },
        degradation: {
          status: 'degraded',
          issues: [
            {
              key: 'workflow-state',
              label: 'Workflow state',
              status: status.backendStatus ?? response.status,
              requestId: status.requestId,
              ticketId: status.ticketId,
              message: status.message ?? status.errorMessage ?? 'Could not load deck processing status.'
            }
          ],
          actionHref: null,
          actionLabel: null
        },
        dependencies: [
          createDependencyStatus('workflow-state', 'Workflow state', {
            status: status.backendStatus ?? response.status,
            requestId: status.requestId,
            ticketId: status.ticketId,
            backendPath: workflowStatePath,
            message: status.message ?? status.errorMessage ?? null
          })
        ]
      })
    };
  }

  const enrichedPayload =
    payload && typeof payload === 'object'
      ? {
          ...(payload as Record<string, unknown>),
          backendStatus: (payload as Record<string, unknown>).backendStatus ?? response.status,
          backendPath: (payload as Record<string, unknown>).backendPath ?? workflowStatePath,
          requestId:
            (payload as Record<string, unknown>).requestId ??
            (payload as Record<string, unknown>).request_id ??
            response.headers.get('x-request-id'),
          ticketId:
            (payload as Record<string, unknown>).ticketId ??
            (payload as Record<string, unknown>).ticket_id ??
            readTicketId(payload)
        }
      : payload;

  const completedAt = Date.now();
  const initialStatus = normalizeSmartDeckProcessingStatus(enrichedPayload, params.deckId);
  return {
    deckId: params.deckId,
    initialStatus,
    initialDiagnostics: {
      requestedAt: new Date(startedAt).toISOString(),
      loadedAt: new Date(completedAt).toISOString(),
      loadDurationMs: completedAt - startedAt
    },
    developerToolsPayload: createDeveloperToolsPayload({
      route: {
        canonicalPath: `/decks/${params.deckId}/processing`,
        routeStatus: 'mounted_and_wired',
        routeNotice: null
      },
      subject: {
        workspaceId: null,
        deckId: params.deckId,
        audience: null,
        activeDeckId: params.deckId
      },
      load: {
        requestedAt: new Date(startedAt).toISOString(),
        loadedAt: new Date(completedAt).toISOString(),
        loadDurationMs: completedAt - startedAt
      },
      correlation: {
        backendStatus: initialStatus.backendStatus ?? response.status,
        requestId: initialStatus.requestId ?? null,
        ticketId: initialStatus.ticketId ?? null,
        backendPath: initialStatus.backendPath ?? workflowStatePath,
        message: initialStatus.backendMessage ?? initialStatus.message ?? initialStatus.errorMessage ?? null
      },
      workflow: {
        status: initialStatus.status,
        nextAction: initialStatus.nextAction ?? null,
        activeStage: initialStatus.activeStage ?? initialStatus.processingStage ?? null,
        runId: null,
        jobId: null,
        canRetry: initialStatus.canRetry,
        canOpenSmartDeck: initialStatus.canOpenSmartDeck
      },
      artifacts: {
        sourceFileStatus: initialStatus.sourceFileStatus ?? (initialStatus.sourceFileSaved ? 'saved' : 'missing'),
        sourceSlideCount: initialStatus.sourceSlideCount ?? null,
        generatedSlideCount: null,
        latestExportId: null,
        latestExportType: null,
        activeDesignVersionId: null,
        activeGeneratedSlideId: null,
        knowledgePackageName: null,
        knowledgePackageVersion: null
      },
      dependencies: [
        createDependencyStatus('workflow-state', 'Workflow state', {
          status: initialStatus.backendStatus ?? response.status,
          requestId: initialStatus.requestId ?? null,
          ticketId: initialStatus.ticketId ?? null,
          backendPath: initialStatus.backendPath ?? workflowStatePath,
          message: initialStatus.backendMessage ?? initialStatus.message ?? initialStatus.errorMessage ?? null
        })
      ]
    })
  };
}
