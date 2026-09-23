export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE';

export interface ApiError {
  status: number;
  code: string;
  message: string;
  details?: unknown;
}

export type JobEventType =
  | 'log'
  | 'status'
  | 'complete'
  | 'error'
  | 'milestone'
  | 'file_added'
  | 'file_modified'
  | 'file_removed';

export type MilestoneStage =
  | 'start'
  | 'deck_analysis'
  | 'research'
  | 'competitive'
  | 'writing'
  | 'enrichment'
  | 'assembly'
  | 'validation'
  | 'artifacts'
  | 'complete';

export type MilestoneLevel = 'info' | 'success' | 'warning' | 'error';

export interface JobEvent {
  type: JobEventType;
  ts: string;
  // Discriminated by `type`. Concrete shapes from the FastAPI sidecar:
  //   log:           { line: string }
  //   status:        { status: 'queued' | 'running' | 'completed' | 'failed' }
  //   complete:      { output_dir: string | null, version: string | null, overall_score?: number }
  //   error:         { message: string, traceback?: string }
  //   milestone:     { id: string, stage: MilestoneStage, level: MilestoneLevel, label: string, detail?: string }
  //   file_added:    { path: string, size: number }    // path relative to output_dir
  //   file_modified: { path: string, size: number }
  //   file_removed:  { path: string }
  [k: string]: unknown;
}

export type JobEventHandler = (event: JobEvent) => void;

export interface Transport {
  request<T = unknown>(method: HttpMethod, path: string, body?: unknown): Promise<T>;
  /**
   * Subscribe to a running job's event stream. Returns an unsubscribe fn that
   * tears down the underlying connection (EventSource in local mode).
   */
  subscribeEvents(jobId: string, onEvent: JobEventHandler): () => void;
}
