import type { Outline } from '$lib/types';
import type { JobEvent, MilestoneStage, MilestoneLevel } from '$lib/transport';

export interface Milestone {
  id: string;
  ts: string;
  stage: MilestoneStage;
  level: MilestoneLevel;
  label: string;
  detail?: string;
}

// Live state of one artifact under the run's output_dir. `status` is an
// ephemeral UI flag — 'fresh' (just created) or 'modified' (just changed) —
// that fades back to 'idle' after a short window so the file tree can flash
// the entry without redrawing forever.
export interface FileEntry {
  path: string;
  size: number;
  status: 'idle' | 'fresh' | 'modified';
  changedAt: number;
}

const FILE_HIGHLIGHT_MS = 3000;

export interface DealPayload {
  companyUrl: string;
  companyName: string;
  deckPath: string | null;
  mode: 'consider' | 'justify';
}

export type JobRunStatus = 'queued' | 'running' | 'completed' | 'failed';

// In-memory event cap for live tailing. Two independent reasons to keep this
// finite: (a) a 1000-line DOM is the comfortable upper bound for a {#each} pane
// in WebView, (b) any cap at all means slice() runs occasionally — which is
// fine because events live in $state.raw (see below) and slice is a flat
// array allocation, not a proxy regeneration. Full event history is persisted
// to .logs/runs/{job}.jsonl by the sidecar.
const MAX_EVENTS = 2000;

// Events do NOT live on the stage object — they live as $state.raw on the
// FlowState class itself. Reasons:
//   1. The stage object is $state (deep), which Proxy-wraps every nested
//      value. With events on stage, every JobEvent becomes a Proxy, and every
//      slice() regenerates 2000 Proxies wholesale. That's the cause of the
//      "screen going black" GC/layout spike that 30+ events/sec triggered.
//   2. $state.raw skips the deep proxy entirely. Reactivity fires only on
//      reassignment, which is exactly what we want for an append-only log:
//      we mutate via [...prev, evt] and the array reference change triggers
//      one tick of downstream rerender.
//   3. Timer reset bug: when events overflowed and slice(-MAX) ran,
//      events[0].ts shifted forward, and any timer derived from events[0]
//      (or worse, from a re-replayed backlog after an EventSource reconnect)
//      jumped. startedAtMs is captured exactly once per run instead.

export type FlowStage =
  | { kind: 'idle' }
  | { kind: 'outline_detail'; outline: Outline }
  | { kind: 'create_firm'; outline: Outline }
  | { kind: 'create_deal'; outline: Outline }
  // Source approval sits between defining the memo and running it. Curation
  // is frontloaded on purpose: candidates come from a search index (never a
  // language model), so no run ever starts against an unconstrained corpus.
  // See context-v/loops/Frontloaded-Source-Approval-Loop.md.
  | { kind: 'approving_sources'; outline: Outline; payload: DealPayload }
  | { kind: 'ready_to_run'; outline: Outline; payload: DealPayload }
  | {
      kind: 'running_job';
      outline: Outline;
      payload: DealPayload;
      jobId: string;
      status: JobRunStatus;
      milestones: Milestone[];
      outputDir: string | null;
      version: string | null;
      errorMessage: string | null;
    }
  | { kind: 'brand_setup'; firm: string };

class FlowState {
  stage = $state<FlowStage>({ kind: 'idle' });
  events = $state.raw<JobEvent[]>([]);
  startedAtMs = $state<number | null>(null);
  // Live mirror of the run's output_dir, populated by file_added /
  // file_modified / file_removed events from the sidecar's filesystem
  // watcher. Map for O(1) upsert by path; raw because the consumer
  // (ArtifactBrowser) re-derives a tree on every reassignment, and we don't
  // want the per-entry deep proxy that $state would impose.
  files = $state.raw<Map<string, FileEntry>>(new Map());
  // Monotonic seq from the sidecar's bus. EventSource reconnects cause the
  // server to replay its backlog (no Last-Event-ID is honored), so the same
  // event can arrive twice. Dropping events with seq <= lastSeenSeq keeps the
  // client log idempotent across reconnects. Plain field — not reactive,
  // we don't render it.
  private lastSeenSeq = -1;

  showDetail(outline: Outline) {
    this.stage = { kind: 'outline_detail', outline };
  }

  startTrying(outline: Outline, hasActiveFirm: boolean) {
    this.stage = hasActiveFirm
      ? { kind: 'create_deal', outline }
      : { kind: 'create_firm', outline };
  }

  proceedToDeal(outline: Outline) {
    this.stage = { kind: 'create_deal', outline };
  }

  markReady(outline: Outline, payload: DealPayload) {
    this.stage = { kind: 'ready_to_run', outline, payload };
  }

  /** Move from a defined deal into source approval. */
  startApprovingSources(outline: Outline, payload: DealPayload) {
    this.stage = { kind: 'approving_sources', outline, payload };
  }

  /** Sources approved (or skipped) — the run may now be launched. */
  sourcesSettled() {
    if (this.stage.kind !== 'approving_sources') return;
    this.stage = {
      kind: 'ready_to_run',
      outline: this.stage.outline,
      payload: this.stage.payload,
    };
  }

  editDeal() {
    if (
      this.stage.kind === 'ready_to_run' ||
      this.stage.kind === 'running_job' ||
      this.stage.kind === 'approving_sources'
    ) {
      this.stage = { kind: 'create_deal', outline: this.stage.outline };
    }
  }

  markCancelled(reason: string) {
    if (this.stage.kind !== 'running_job') return;
    this.stage.status = 'failed';
    this.stage.errorMessage = reason;
    this.stage.milestones.push({
      id: `cancelled-${Date.now()}`,
      ts: new Date().toISOString(),
      stage: 'complete',
      level: 'error',
      label: 'Stopped by user',
    });
  }

  markRunning(outline: Outline, payload: DealPayload, jobId: string) {
    this.events = [];
    this.files = new Map();
    this.startedAtMs = Date.now();
    this.lastSeenSeq = -1;
    this.stage = {
      kind: 'running_job',
      outline,
      payload,
      jobId,
      status: 'queued',
      milestones: [],
      outputDir: null,
      version: null,
      errorMessage: null,
    };
  }

  appendEvent(event: JobEvent) {
    if (this.stage.kind !== 'running_job') return;

    // Dedup by monotonic seq from the sidecar bus. If the server didn't stamp
    // a seq (older sidecar, or a non-bus-published event), fall through.
    const seq = (event as { seq?: number }).seq;
    if (typeof seq === 'number') {
      if (seq <= this.lastSeenSeq) return;
      this.lastSeenSeq = seq;
    }

    // Append-then-cap as a single reassignment. Spreading 2000 items is a flat
    // memcpy (~50µs on a modern machine) and the array is raw, so this is one
    // reactivity tick per event — no proxy creation churn.
    const next = this.events.length >= MAX_EVENTS
      ? [...this.events.slice(-(MAX_EVENTS - 1)), event]
      : [...this.events, event];
    this.events = next;

    if (event.type === 'status' && typeof event.status === 'string') {
      this.stage.status = event.status as JobRunStatus;
    } else if (event.type === 'complete') {
      this.stage.status = 'completed';
      if (typeof event.output_dir === 'string') this.stage.outputDir = event.output_dir;
      if (typeof event.version === 'string') this.stage.version = event.version;
      // Synthesize a "complete" milestone for the timeline.
      this.stage.milestones.push({
        id: `complete-${Date.now()}`,
        ts: event.ts,
        stage: 'complete',
        level: 'success',
        label: 'Memo complete',
        detail:
          typeof event.version === 'string' ? `Version ${event.version}` : undefined,
      });
    } else if (event.type === 'error') {
      this.stage.status = 'failed';
      if (typeof event.message === 'string') this.stage.errorMessage = event.message;
      this.stage.milestones.push({
        id: `error-${Date.now()}`,
        ts: event.ts,
        stage: 'complete',
        level: 'error',
        label: 'Run failed',
        detail: typeof event.message === 'string' ? event.message : undefined,
      });
    } else if (event.type === 'milestone') {
      this.stage.milestones.push({
        id: typeof event.id === 'string' ? event.id : `m-${Date.now()}`,
        ts: event.ts,
        stage: (typeof event.stage === 'string' ? event.stage : 'start') as MilestoneStage,
        level: (typeof event.level === 'string' ? event.level : 'info') as MilestoneLevel,
        label: typeof event.label === 'string' ? event.label : 'Update',
        detail: typeof event.detail === 'string' ? event.detail : undefined,
      });
    } else if (event.type === 'file_added' || event.type === 'file_modified') {
      const path = typeof event.path === 'string' ? event.path : null;
      if (!path) return;
      const size = typeof event.size === 'number' ? event.size : 0;
      this.upsertFile(path, size, event.type === 'file_added' ? 'fresh' : 'modified');
    } else if (event.type === 'file_removed') {
      const path = typeof event.path === 'string' ? event.path : null;
      if (!path) return;
      this.removeFile(path);
    }
  }

  private upsertFile(path: string, size: number, kind: 'fresh' | 'modified') {
    const changedAt = Date.now();
    const next = new Map(this.files);
    next.set(path, { path, size, status: kind, changedAt });
    this.files = next;
    // Fade the highlight back to 'idle' after the window expires — but only
    // if no newer change has landed in the meantime (compared by changedAt
    // identity, captured above).
    setTimeout(() => {
      const cur = this.files.get(path);
      if (!cur || cur.changedAt !== changedAt) return;
      const fresher = new Map(this.files);
      fresher.set(path, { ...cur, status: 'idle' });
      this.files = fresher;
    }, FILE_HIGHLIGHT_MS);
  }

  private removeFile(path: string) {
    if (!this.files.has(path)) return;
    const next = new Map(this.files);
    next.delete(path);
    this.files = next;
  }

  startBrandSetup(firm: string) {
    this.stage = { kind: 'brand_setup', firm };
  }

  close() {
    this.events = [];
    this.files = new Map();
    this.startedAtMs = null;
    this.lastSeenSeq = -1;
    this.stage = { kind: 'idle' };
  }
}

export const flow = new FlowState();
