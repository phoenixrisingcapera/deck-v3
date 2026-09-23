export type DeveloperVisibilityValue = string | number | boolean | null | undefined;

export type DeveloperVisibilityItem = {
  label: string;
  value: DeveloperVisibilityValue;
};

export type ProductDeveloperToolsDependency = {
  key: string;
  label: string;
  status: number | null;
  requestId: string | null;
  ticketId: string | null;
  backendPath: string | null;
  message: string | null;
};

export type ProductDeveloperToolsIssue = {
  key: string;
  label: string;
  status: number | null;
  requestId: string | null;
  ticketId: string | null;
  message: string | null;
};

export type ProductDeveloperToolsPayload = {
  route: {
    canonicalPath: string;
    routeStatus: 'mounted_and_wired' | 'mounted_but_degraded';
    routeNotice: string | null;
  };
  subject: {
    workspaceId: string | null;
    deckId: string | null;
    audience: string | null;
    activeDeckId: string | null;
  };
  load: {
    requestedAt: string | null;
    loadedAt: string | null;
    loadDurationMs: number | null;
  };
  correlation: {
    backendStatus: number | null;
    requestId: string | null;
    ticketId: string | null;
    backendPath: string | null;
    message: string | null;
  };
  workflow: {
    status: string | null;
    nextAction: string | null;
    activeStage: string | null;
    runId: string | null;
    jobId: string | null;
    canRetry: boolean | null;
    canOpenSmartDeck: boolean | null;
  };
  artifacts: {
    sourceFileStatus: string | null;
    sourceSlideCount: number | null;
    generatedSlideCount: number | null;
    latestExportId: string | null;
    latestExportType: string | null;
    activeDesignVersionId: string | null;
    activeGeneratedSlideId: string | null;
    knowledgePackageName: string | null;
    knowledgePackageVersion: string | null;
  };
  degradation: {
    status: 'ready' | 'degraded' | 'unavailable' | null;
    issues: ProductDeveloperToolsIssue[];
    actionHref: string | null;
    actionLabel: string | null;
  };
  dependencies: ProductDeveloperToolsDependency[];
};

function push(items: DeveloperVisibilityItem[], label: string, value: DeveloperVisibilityValue) {
  if (value === null || value === undefined) return;
  if (typeof value === 'string' && value.trim().length === 0) return;
  items.push({ label, value });
}

export function createDependencyStatus(
  key: string,
  label: string,
  values: Partial<Omit<ProductDeveloperToolsDependency, 'key' | 'label'>> = {}
): ProductDeveloperToolsDependency {
  return {
    key,
    label,
    status: values.status ?? null,
    requestId: values.requestId ?? null,
    ticketId: values.ticketId ?? null,
    backendPath: values.backendPath ?? null,
    message: values.message ?? null
  };
}

export function createDeveloperToolsPayload(
  payload: Partial<ProductDeveloperToolsPayload> & Pick<ProductDeveloperToolsPayload, 'route'>
): ProductDeveloperToolsPayload {
  return {
    route: payload.route,
    subject: {
      workspaceId: payload.subject?.workspaceId ?? null,
      deckId: payload.subject?.deckId ?? null,
      audience: payload.subject?.audience ?? null,
      activeDeckId: payload.subject?.activeDeckId ?? null
    },
    load: {
      requestedAt: payload.load?.requestedAt ?? null,
      loadedAt: payload.load?.loadedAt ?? null,
      loadDurationMs: payload.load?.loadDurationMs ?? null
    },
    correlation: {
      backendStatus: payload.correlation?.backendStatus ?? null,
      requestId: payload.correlation?.requestId ?? null,
      ticketId: payload.correlation?.ticketId ?? null,
      backendPath: payload.correlation?.backendPath ?? null,
      message: payload.correlation?.message ?? null
    },
    workflow: {
      status: payload.workflow?.status ?? null,
      nextAction: payload.workflow?.nextAction ?? null,
      activeStage: payload.workflow?.activeStage ?? null,
      runId: payload.workflow?.runId ?? null,
      jobId: payload.workflow?.jobId ?? null,
      canRetry: payload.workflow?.canRetry ?? null,
      canOpenSmartDeck: payload.workflow?.canOpenSmartDeck ?? null
    },
    artifacts: {
      sourceFileStatus: payload.artifacts?.sourceFileStatus ?? null,
      sourceSlideCount: payload.artifacts?.sourceSlideCount ?? null,
      generatedSlideCount: payload.artifacts?.generatedSlideCount ?? null,
      latestExportId: payload.artifacts?.latestExportId ?? null,
      latestExportType: payload.artifacts?.latestExportType ?? null,
      activeDesignVersionId: payload.artifacts?.activeDesignVersionId ?? null,
      activeGeneratedSlideId: payload.artifacts?.activeGeneratedSlideId ?? null,
      knowledgePackageName: payload.artifacts?.knowledgePackageName ?? null,
      knowledgePackageVersion: payload.artifacts?.knowledgePackageVersion ?? null
    },
    degradation: {
      status: payload.degradation?.status ?? null,
      issues: payload.degradation?.issues ?? [],
      actionHref: payload.degradation?.actionHref ?? null,
      actionLabel: payload.degradation?.actionLabel ?? null
    },
    dependencies: payload.dependencies ?? []
  };
}

export function createDeveloperVisibilityItems(
  payload: ProductDeveloperToolsPayload,
  extras: DeveloperVisibilityItem[] = []
): DeveloperVisibilityItem[] {
  const items: DeveloperVisibilityItem[] = [];

  push(items, 'Canonical route', payload.route.canonicalPath);
  push(items, 'Route status', payload.route.routeStatus);
  push(items, 'Route notice', payload.route.routeNotice);
  push(items, 'Workspace id', payload.subject.workspaceId);
  push(items, 'Deck id', payload.subject.deckId);
  push(items, 'Audience', payload.subject.audience);
  push(items, 'Active deck id', payload.subject.activeDeckId);
  push(items, 'Backend status', payload.correlation.backendStatus);
  push(items, 'Request id', payload.correlation.requestId);
  push(items, 'Failure ticket', payload.correlation.ticketId);
  push(items, 'Backend path', payload.correlation.backendPath);
  push(items, 'Backend message', payload.correlation.message);
  push(items, 'Workflow status', payload.workflow.status);
  push(items, 'Workflow next action', payload.workflow.nextAction);
  push(items, 'Workflow active stage', payload.workflow.activeStage);
  push(items, 'Workflow run id', payload.workflow.runId);
  push(items, 'Workflow job id', payload.workflow.jobId);
  push(items, 'Can retry', payload.workflow.canRetry);
  push(items, 'Can open Smart Deck', payload.workflow.canOpenSmartDeck);
  push(items, 'Requested at', payload.load.requestedAt);
  push(items, 'Loaded at', payload.load.loadedAt);
  push(items, 'Load duration ms', payload.load.loadDurationMs);
  push(items, 'Source file status', payload.artifacts.sourceFileStatus);
  push(items, 'Source slide count', payload.artifacts.sourceSlideCount);
  push(items, 'Generated slide count', payload.artifacts.generatedSlideCount);
  push(items, 'Latest export id', payload.artifacts.latestExportId);
  push(items, 'Latest export type', payload.artifacts.latestExportType);
  push(items, 'Active design version', payload.artifacts.activeDesignVersionId);
  push(items, 'Active generated slide', payload.artifacts.activeGeneratedSlideId);
  push(items, 'Knowledge package', payload.artifacts.knowledgePackageName);
  push(items, 'Knowledge version', payload.artifacts.knowledgePackageVersion);
  push(items, 'Degradation status', payload.degradation.status);
  push(items, 'Degraded issues', payload.degradation.issues.length);
  push(items, 'Fallback action', payload.degradation.actionLabel);
  push(items, 'Fallback href', payload.degradation.actionHref);

  for (const dependency of payload.dependencies) {
    push(items, `${dependency.label} status`, dependency.status);
    push(items, `${dependency.label} request id`, dependency.requestId);
    push(items, `${dependency.label} failure ticket`, dependency.ticketId);
    push(items, `${dependency.label} path`, dependency.backendPath);
    push(items, `${dependency.label} message`, dependency.message);
  }

  for (const extra of extras) {
    push(items, extra.label, extra.value);
  }

  return items;
}
