export type SmartEditWorkflowStatus =
  | 'queued'
  | 'running'
  | 'failed_retryable'
  | 'failed_final'
  | 'timed_out'
  | 'pending'
  | 'previewed'
  | 'completed'
  | 'no_change'
  | 'accepted'
  | 'rejected'
  | 'applied'
  | 'failed';

export type ProductDeveloperDependencyStatus = {
  key: 'workflow-job' | 'smart-edit-artifact' | 'smart-edit-suggestion';
  status: string;
  resourceId?: string | null;
};

export type ProductDeveloperArtifactLineage = {
  runId: string;
  workflowJobId?: string | null;
  artifactId?: string | null;
  suggestionId?: string | null;
};

export type ProductDeveloperEnvelope = {
  schemaVersion: 'product-developer-envelope.v1';
  dependencies: ProductDeveloperDependencyStatus[];
  artifactLineage: ProductDeveloperArtifactLineage;
  degradation: 'ready' | 'pending' | 'degraded';
  failureStage?: 'queue' | 'worker' | 'artifact' | 'suggestion' | null;
  errorCode?: string | null;
};

export type SmartEditIntentResponse = {
  label: string;
  confidence: string;
  rationale?: string | null;
  missingInputs: string[];
};

export type SmartEditPatchRunResponse = {
  runId: string;
  deckId: string;
  slideId: string;
  blockId?: string | null;
  status: SmartEditWorkflowStatus;
  artifactId?: string | null;
  suggestionId?: string | null;
  cached?: boolean;
  intent?: SmartEditIntentResponse | null;
  patch?: {
    beforeText: string;
    afterText: string;
    layoutPatch?: Record<string, unknown>;
    riskControls?: string[];
    confidence?: string;
    requiresReview?: boolean;
    sourceFactsUsed?: string[];
    sourceFactIds?: string[];
    missingInputs?: string[];
  };
  system?: Record<string, unknown>;
  error?: { code?: string | null; message?: string | null; recoverable?: boolean } | null;
  developer?: ProductDeveloperEnvelope | null;
};
