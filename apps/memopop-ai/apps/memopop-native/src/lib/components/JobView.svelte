<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { settings } from '$lib/stores/settings.svelte';
  import { flow } from '$lib/stores/flow.svelte';
  import { getTransport, type JobEvent } from '$lib/transport';
  import type { Outline } from '$lib/types';
  import PhaseChecklist from './PhaseChecklist.svelte';
  import LogStream from './LogStream.svelte';
  import ArtifactBrowser from './ArtifactBrowser.svelte';
  import CharacterRow from './CharacterRow.svelte';

  interface Props {
    outline: Outline;
    jobId: string;
  }

  let { outline, jobId }: Props = $props();

  let unsubscribe: (() => void) | null = null;

  let stage = $derived(flow.stage.kind === 'running_job' ? flow.stage : null);
  let status = $derived(stage?.status ?? 'queued');
  let events = $derived(flow.events);
  let milestones = $derived(stage?.milestones ?? []);
  let outputDir = $derived(stage?.outputDir ?? null);
  let version = $derived(stage?.version ?? null);
  let errorMessage = $derived(stage?.errorMessage ?? null);

  let isTerminal = $derived(status === 'completed' || status === 'failed');
  let isRunning = $derived(status === 'queued' || status === 'running');

  // Wall-clock timer. Anchored on flow.startedAtMs (set once when the run
  // is dispatched), so it's immune to events-array churn — slicing the
  // 2000-cap tail and EventSource backlog replays no longer move the origin.
  let now = $state(Date.now());
  let elapsedSeconds = $derived(
    flow.startedAtMs && (isRunning || isTerminal)
      ? Math.floor((now - flow.startedAtMs) / 1000)
      : 0
  );

  let tickHandle: ReturnType<typeof setInterval> | null = null;

  onMount(() => {
    const transport = getTransport();
    unsubscribe = transport.subscribeEvents(jobId, (event: JobEvent) => {
      flow.appendEvent(event);
    });
    tickHandle = setInterval(() => {
      now = Date.now();
    }, 1000);
  });

  onDestroy(() => {
    unsubscribe?.();
    if (tickHandle) clearInterval(tickHandle);
  });

  let stopping = $state(false);
  let resuming = $state(false);
  let resumeError = $state<string | null>(null);

  // Resume is available whenever a run failed (user-stopped or errored) AND we
  // have a firm to scope the lookup. We deliberately don't require outputDir:
  // it's only populated by the 'complete' event, which never fires for runs
  // that stall mid-flight — but those are exactly the runs the user most wants
  // to resume. The resume endpoint walks io/{firm}/deals/{deal}/outputs/ itself
  // and reports gracefully if there's nothing to pick up.
  let canResume = $derived(
    status === 'failed' && !!settings.activeFirm
  );

  function close() {
    flow.close();
  }

  function backToGallery() {
    flow.close();
  }

  function startBrandSetup() {
    if (!settings.activeFirm) return;
    flow.startBrandSetup(settings.activeFirm);
  }

  async function resumeRun() {
    if (resuming || !canResume || !stage) return;
    resuming = true;
    resumeError = null;
    try {
      const dealName = stage.payload.companyName;
      const result = await getTransport().request<{ job_id: string; status: string }>(
        'POST',
        '/memos/resume',
        {
          repoPath: settings.repoPath,
          firm: settings.activeFirm,
          company_name: dealName,
        }
      );
      // Reset the JobView to a fresh running state with the new job_id.
      // markRunning clears events/files/timer, so the resume looks like a
      // brand-new run visually — but the orchestrator picks up at the last
      // checkpoint and the file watcher's initial snapshot fills the tree
      // with everything already on disk.
      flow.markRunning(stage.outline, stage.payload, result.job_id);
    } catch (e) {
      resumeError =
        (e as { message?: string })?.message ?? 'Failed to start resume';
    } finally {
      resuming = false;
    }
  }

  async function stopRun() {
    if (stopping) return;
    stopping = true;
    try {
      // Direct hit on the Rust action — does NOT go through the Python sidecar's
      // HTTP API, because the whole reason to "stop" is that Python may be wedged.
      // The Rust dispatcher kills the child process via the stored CommandChild.
      await getTransport().request('POST', '/actions/stop-sidecar', {
        repoPath: settings.repoPath,
      });
    } catch {
      // Even if the action errors (sidecar already dead, no manager state),
      // the user pressed Stop — honor it locally regardless.
    } finally {
      flow.markCancelled('Stopped by user');
      stopping = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && isTerminal) close();
  }

  function statusLabel(s: string): string {
    switch (s) {
      case 'queued':
        return 'Queued';
      case 'running':
        return 'Generating';
      case 'completed':
        return 'Completed';
      case 'failed':
        return 'Failed';
      default:
        return s;
    }
  }

  function formatElapsed(secs: number): string {
    if (secs < 60) return `${secs}s`;
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}m ${s.toString().padStart(2, '0')}s`;
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="job-view">
  <header class="job-head">
    <div class="head-left">
      <span class="status-pill status-{status}">
        <span class="dot"></span>
        {statusLabel(status)}
      </span>
      <div class="title-block">
        <h2 class="title">{outline.title}</h2>
        <div class="title-meta">
          <span class="firm-tag">{settings.activeFirm ?? '—'}</span>
          <span class="job-id" title="Job ID"><code>{jobId}</code></span>
          {#if elapsedSeconds > 0}
            <span class="elapsed">⏱ {formatElapsed(elapsedSeconds)}</span>
          {/if}
        </div>
      </div>
    </div>

    <div class="head-right">
      {#if !isTerminal}
        <button type="button" class="ghost" onclick={backToGallery}>
          ← Back to gallery
        </button>
        <button
          type="button"
          class="danger"
          onclick={stopRun}
          disabled={stopping}
          title="Kill the orchestrator process. Files written so far are kept."
        >
          {stopping ? 'Stopping…' : '⏹ Stop'}
        </button>
      {:else}
        <button type="button" class="cta" onclick={close}>
          {status === 'completed' ? 'Done' : 'Close'}
        </button>
      {/if}
    </div>
  </header>

  {#if errorMessage}
    <div class="banner banner-error">
      <div class="banner-text">
        <strong>Run failed.</strong>
        {errorMessage}
        {#if resumeError}
          <span class="resume-error"> — {resumeError}</span>
        {/if}
      </div>
      {#if canResume}
        <button
          type="button"
          class="banner-cta resume-cta"
          onclick={resumeRun}
          disabled={resuming}
          title="Pick up from the last on-disk checkpoint. Skips agents that already produced artifacts — no redundant API spend."
        >
          {resuming ? 'Resuming…' : 'Resume from last checkpoint →'}
        </button>
      {/if}
    </div>
  {:else if status === 'completed' && outputDir}
    <div class="banner banner-success">
      <div class="banner-text">
        <strong>Memo generated{version ? ` (${version})` : ''}.</strong>
        Artifacts at <code>{outputDir}</code>
      </div>
      {#if settings.activeFirm}
        <button type="button" class="banner-cta" onclick={startBrandSetup}>
          Make this look like your firm →
        </button>
      {/if}
    </div>
  {/if}

  <CharacterRow {milestones} {isRunning} />

  <div class="grid">
    <div class="col col-checklist">
      <PhaseChecklist {milestones} {isRunning} />
    </div>
    <div class="col col-files">
      <ArtifactBrowser {jobId} {isRunning} />
    </div>
    <div class="col col-stream">
      <LogStream {events} {isRunning} />
    </div>
  </div>
</div>

<style>
  .job-view {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    background: #fafaf9;
  }

  .job-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.85rem 1.25rem;
    background: white;
    border-bottom: 1px solid #e5e7eb;
    flex-shrink: 0;
  }

  .head-left {
    display: flex;
    align-items: flex-start;
    gap: 0.85rem;
    min-width: 0;
  }

  .status-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 0.35rem 0.75rem;
    border-radius: 999px;
    flex-shrink: 0;
    margin-top: 0.15rem;
  }

  .status-pill .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: currentColor;
  }

  .status-queued {
    background: #f3f4f6;
    color: #4b5563;
  }

  .status-running {
    background: linear-gradient(135deg, #ede9fe, #fef3c7);
    color: #5b21b6;
  }

  .status-running .dot {
    animation: pulse 1.4s ease-in-out infinite;
  }

  @keyframes pulse {
    0%,
    100% {
      opacity: 1;
      transform: scale(1);
    }
    50% {
      opacity: 0.4;
      transform: scale(1.4);
    }
  }

  .status-completed {
    background: #dcfce7;
    color: #166534;
  }

  .status-failed {
    background: #fee2e2;
    color: #991b1b;
  }

  .title-block {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    min-width: 0;
  }

  .title {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 600;
    color: #0f0f0f;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .title-meta {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    font-size: 0.78rem;
  }

  .firm-tag {
    color: #5b21b6;
    background: #f3e8ff;
    padding: 0.15rem 0.5rem;
    border-radius: 999px;
    font-weight: 500;
  }

  .job-id {
    color: #9ca3af;
  }

  .elapsed {
    color: #6b7280;
    font-variant-numeric: tabular-nums;
  }

  .head-right {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-shrink: 0;
  }

  .hint {
    font-size: 0.75rem;
    color: #9ca3af;
  }

  button.ghost {
    background: transparent;
    border: 1px solid #d1d5db;
    color: #4b5563;
    padding: 0.4rem 0.8rem;
    border-radius: 6px;
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
  }

  button.ghost:hover {
    background: #f3f4f6;
    color: #0f0f0f;
  }

  button.cta {
    background: #5b21b6;
    color: white;
    border: none;
    padding: 0.45rem 1rem;
    border-radius: 6px;
    font: inherit;
    font-weight: 500;
    cursor: pointer;
  }

  button.cta:hover {
    background: #4c1d95;
  }

  button.danger {
    background: #dc2626;
    color: white;
    border: none;
    padding: 0.45rem 0.95rem;
    border-radius: 6px;
    font: inherit;
    font-weight: 600;
    cursor: pointer;
    letter-spacing: 0.01em;
  }

  button.danger:hover:not(:disabled) {
    background: #b91c1c;
  }

  button.danger:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .banner {
    padding: 0.65rem 1.25rem;
    font-size: 0.85rem;
    border-bottom: 1px solid;
    flex-shrink: 0;
  }

  .banner-success {
    background: #f0fdf4;
    color: #166534;
    border-bottom-color: #bbf7d0;
  }

  .banner-error {
    background: #fef2f2;
    color: #991b1b;
    border-bottom-color: #fecaca;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .resume-cta {
    background: #5b21b6;
    color: white;
  }

  .resume-cta:hover:not(:disabled) {
    background: #4c1d95;
  }

  .resume-cta:disabled {
    opacity: 0.65;
    cursor: not-allowed;
  }

  .resume-error {
    font-style: italic;
    opacity: 0.9;
  }

  .banner code {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 0.85em;
    background: rgba(0, 0, 0, 0.04);
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
  }

  .banner-success {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .banner-text {
    flex: 1;
    min-width: 0;
  }

  .banner-cta {
    background: #166534;
    color: white;
    border: none;
    padding: 0.45rem 0.9rem;
    border-radius: 6px;
    font: inherit;
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    flex-shrink: 0;
  }

  .banner-cta:hover {
    background: #14532d;
  }

  .grid {
    flex: 1;
    display: grid;
    /* Files panel is the main column — the user's primary "what's happening
       to my outputs" view. Logs are the nerd sidebar (still useful, smaller).
       Checklist is the narrow status spine on the left. */
    grid-template-columns: 280px minmax(0, 1fr) 340px;
    min-height: 0;
    overflow: hidden;
  }

  .col {
    min-height: 0;
    overflow: hidden;
  }

  .col-files {
    border-left: 1px solid #e5e7eb;
    background: #fafaf9;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .col-stream {
    border-left: 1px solid #1f2024;
  }

  /* Narrow viewport: drop the log column first — files stay visible because
     they're the primary "did anything actually happen" signal. */
  @media (max-width: 1100px) {
    .grid {
      grid-template-columns: 260px minmax(0, 1fr);
    }
    .col-stream {
      display: none;
    }
  }

  @media (max-width: 720px) {
    .grid {
      grid-template-columns: minmax(0, 1fr);
    }
    .col-checklist {
      display: none;
    }
  }

  @media (prefers-color-scheme: dark) {
    .job-view {
      background: #1c1c1e;
    }

    .job-head {
      background: #1c1c1e;
      border-bottom-color: #2a2a2c;
    }

    .status-queued {
      background: #2a2a2c;
      color: #9ca3af;
    }

    .status-running {
      background: linear-gradient(135deg, #2a1f3d, #3f2f0a);
      color: #c4b5fd;
    }

    .status-completed {
      background: #052e1c;
      color: #6ee7b7;
    }

    .status-failed {
      background: #2a1c1c;
      color: #fca5a5;
    }

    .title {
      color: #f6f6f6;
    }

    .firm-tag {
      background: #2a1f3d;
      color: #c4b5fd;
    }

    .job-id {
      color: #6b7280;
    }

    .elapsed {
      color: #9ca3af;
    }

    .hint {
      color: #6b7280;
    }

    button.ghost {
      border-color: #3a3a3c;
      color: #d1d5db;
    }

    button.ghost:hover {
      background: #2a2a2c;
      color: #f6f6f6;
    }

    .banner-success {
      background: #052e1c;
      color: #6ee7b7;
      border-bottom-color: #166534;
    }

    .banner-error {
      background: #2a1c1c;
      color: #fca5a5;
      border-bottom-color: #7f1d1d;
    }

    .col-files {
      background: #1c1c1e;
      border-left-color: #2a2a2c;
    }
  }
</style>
