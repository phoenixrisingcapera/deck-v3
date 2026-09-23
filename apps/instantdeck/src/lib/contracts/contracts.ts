export * from './types';

export interface WorkspaceSummaryRouteResponse {
  workspace: import('./types').WorkspaceSummary;
}

export interface WorkspaceAiProviderRouteResponse {
  summary: import('./types').WorkspaceAiProviderSummary;
}

export interface WorkspaceAiProviderSaveRouteResponse {
  summary: import('./types').WorkspaceAiProviderSummary;
  nextUrl: string;
}

export type FirstDeckUploadRouteResponse = import('./types').FirstDeckUploadResult;
export type SubmitSlideFeedbackRouteRequest = import('./types').SubmitSlideFeedbackRequest;
export type WorkspaceAiProviderSaveRequest = import('./types').SaveWorkspaceAiProviderRequest;
