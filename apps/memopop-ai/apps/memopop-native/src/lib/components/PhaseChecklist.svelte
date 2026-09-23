<script lang="ts">
  import type { Milestone } from '$lib/stores/flow.svelte';
  import type { MilestoneStage } from '$lib/transport';

  interface Props {
    milestones: Milestone[];
    isRunning: boolean;
  }

  let { milestones, isRunning }: Props = $props();

  type PhaseState = 'pending' | 'in_progress' | 'done' | 'failed';

  interface Phase {
    id: string;
    stages: MilestoneStage[];
    label: string;
    icon: string;
  }

  // Phases in the order the orchestrator's pipeline runs. Each phase maps to
  // one (or two) MilestoneStage values from the server's MilestoneExtractor.
  const PHASES: Phase[] = [
    { id: 'start', stages: ['start'], label: 'Run started', icon: '▶' },
    { id: 'deck', stages: ['deck_analysis'], label: 'Pitch deck parsed', icon: '📄' },
    { id: 'research', stages: ['research'], label: 'Section research', icon: '🔍' },
    {
      id: 'competitive',
      stages: ['competitive'],
      label: 'Competitive landscape',
      icon: '🎯',
    },
    { id: 'writing', stages: ['writing'], label: 'Memo sections drafted', icon: '📝' },
    {
      id: 'enrichment',
      stages: ['enrichment'],
      label: 'Enrichments applied',
      icon: '✨',
    },
    { id: 'assembly', stages: ['assembly'], label: 'Final draft assembled', icon: '🧩' },
    {
      id: 'validation',
      stages: ['validation'],
      label: 'Validation & scoring',
      icon: '✓',
    },
    { id: 'artifacts', stages: ['artifacts'], label: 'One-pager generated', icon: '📦' },
    { id: 'complete', stages: ['complete'], label: 'Memo complete', icon: '🏁' },
  ];

  // Compute the highest pipeline phase any milestone has reached. Any phase
  // before that is considered done; the max phase itself is in_progress unless
  // its own success milestone has fired.
  let maxPhaseIndex = $derived(computeMaxPhaseIndex(milestones));

  function computeMaxPhaseIndex(items: Milestone[]): number {
    let max = -1;
    for (const m of items) {
      const idx = PHASES.findIndex((p) => p.stages.includes(m.stage));
      if (idx > max) max = idx;
    }
    return max;
  }

  function phaseState(phase: Phase, idx: number): PhaseState {
    const matching = milestones.filter((m) => phase.stages.includes(m.stage));
    if (matching.length === 0) {
      return idx <= maxPhaseIndex ? 'done' : 'pending';
    }
    const anyError = matching.some((m) => m.level === 'error');
    if (anyError) return 'failed';
    const anySuccess = matching.some((m) => m.level === 'success');
    if (anySuccess) return 'done';
    return idx === maxPhaseIndex ? 'in_progress' : 'done';
  }

  function latestSubDetail(phase: Phase): string | null {
    const matching = milestones.filter((m) => phase.stages.includes(m.stage));
    if (matching.length === 0) return null;
    const latest = matching[matching.length - 1];
    // Don't repeat the phase title back when it's already the success milestone.
    if (latest.level === 'success') {
      return latest.detail ?? null;
    }
    return latest.label;
  }

  function relativeTime(milestone: Milestone | undefined): string | null {
    if (!milestone) return null;
    try {
      const seconds = Math.floor((Date.now() - new Date(milestone.ts).getTime()) / 1000);
      if (seconds < 5) return 'just now';
      if (seconds < 60) return `${seconds}s ago`;
      const minutes = Math.floor(seconds / 60);
      if (minutes < 60) return `${minutes}m ago`;
      const hours = Math.floor(minutes / 60);
      return `${hours}h ago`;
    } catch {
      return null;
    }
  }

  function lastSuccessFor(phase: Phase): Milestone | undefined {
    return [...milestones]
      .reverse()
      .find((m) => phase.stages.includes(m.stage) && m.level === 'success');
  }
</script>

<aside class="checklist">
  <header class="head">
    <h3>Progress</h3>
    {#if isRunning}
      <span class="working">
        <span class="dot"></span>
        Working
      </span>
    {/if}
  </header>

  <ol>
    {#each PHASES as phase, i (phase.id)}
      {@const state = phaseState(phase, i)}
      {@const subDetail = state !== 'pending' ? latestSubDetail(phase) : null}
      {@const ts = state === 'done' ? relativeTime(lastSuccessFor(phase)) : null}
      <li class="phase phase-{state}">
        <span class="bullet" aria-hidden="true">
          {#if state === 'done'}
            <svg viewBox="0 0 16 16" width="14" height="14"
              ><path
                d="M3 8.5l3 3 7-7"
                fill="none"
                stroke="currentColor"
                stroke-width="2.2"
                stroke-linecap="round"
                stroke-linejoin="round"
              ></path></svg
            >
          {:else if state === 'in_progress'}
            <span class="spinner"></span>
          {:else if state === 'failed'}
            <svg viewBox="0 0 16 16" width="14" height="14"
              ><path
                d="M4 4l8 8M12 4l-8 8"
                fill="none"
                stroke="currentColor"
                stroke-width="2.2"
                stroke-linecap="round"
              ></path></svg
            >
          {:else}
            <span class="empty-bullet"></span>
          {/if}
        </span>
        <div class="content">
          <div class="row">
            <span class="icon">{phase.icon}</span>
            <span class="label">{phase.label}</span>
            {#if ts}
              <span class="time">{ts}</span>
            {/if}
          </div>
          {#if subDetail}
            <div class="sub">{subDetail}</div>
          {/if}
        </div>
      </li>
    {/each}
  </ol>
</aside>

<style>
  .checklist {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: #fafaf9;
    border-right: 1px solid #e5e7eb;
    overflow-y: auto;
  }

  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.1rem 0.6rem;
    position: sticky;
    top: 0;
    background: #fafaf9;
    z-index: 1;
  }

  h3 {
    margin: 0;
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6b7280;
  }

  .working {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.7rem;
    color: #5b21b6;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 600;
  }

  .working .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #5b21b6;
    animation: pulse 1.4s ease-in-out infinite;
  }

  @keyframes pulse {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.3;
    }
  }

  ol {
    list-style: none;
    margin: 0;
    padding: 0.25rem 0.6rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.05rem;
  }

  .phase {
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
    padding: 0.5rem 0.5rem;
    border-radius: 6px;
    transition: background 200ms ease;
  }

  .phase-in_progress {
    background: #f5f3ff;
  }

  .bullet {
    flex-shrink: 0;
    width: 22px;
    height: 22px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    margin-top: 0.05rem;
    transition: background 200ms ease, color 200ms ease;
  }

  .phase-pending .bullet {
    color: #9ca3af;
  }

  .phase-in_progress .bullet {
    background: #ede9fe;
    color: #5b21b6;
  }

  .phase-done .bullet {
    background: #d1fae5;
    color: #059669;
  }

  .phase-failed .bullet {
    background: #fee2e2;
    color: #b91c1c;
  }

  .empty-bullet {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    border: 1.5px solid currentColor;
  }

  .spinner {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    border: 2px solid currentColor;
    border-right-color: transparent;
    animation: spin 0.9s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .content {
    flex: 1;
    min-width: 0;
  }

  .row {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .icon {
    font-size: 0.95rem;
    line-height: 1;
  }

  .label {
    font-size: 0.88rem;
    font-weight: 500;
    color: #0f0f0f;
    flex: 1;
  }

  .phase-pending .label {
    color: #9ca3af;
    font-weight: 400;
  }

  .phase-in_progress .label {
    color: #5b21b6;
    font-weight: 600;
  }

  .phase-failed .label {
    color: #991b1b;
  }

  .time {
    font-size: 0.7rem;
    color: #9ca3af;
    font-variant-numeric: tabular-nums;
  }

  .sub {
    margin-top: 0.2rem;
    margin-left: 0.05rem;
    font-size: 0.78rem;
    color: #6b7280;
    line-height: 1.4;
  }

  .phase-in_progress .sub {
    color: #5b21b6;
  }

  @media (prefers-color-scheme: dark) {
    .checklist {
      background: #1c1c1e;
      border-right-color: #2a2a2c;
    }

    .head {
      background: #1c1c1e;
    }

    h3 {
      color: #9ca3af;
    }

    .working {
      color: #c4b5fd;
    }

    .working .dot {
      background: #c4b5fd;
    }

    .phase-in_progress {
      background: #2a1f3d;
    }

    .phase-pending .bullet {
      color: #6b7280;
    }

    .phase-in_progress .bullet {
      background: #3a2964;
      color: #c4b5fd;
    }

    .phase-done .bullet {
      background: #064e3b;
      color: #6ee7b7;
    }

    .phase-failed .bullet {
      background: #2a1c1c;
      color: #fca5a5;
    }

    .label {
      color: #f6f6f6;
    }

    .phase-pending .label {
      color: #6b7280;
    }

    .phase-in_progress .label {
      color: #c4b5fd;
    }

    .phase-failed .label {
      color: #fca5a5;
    }

    .time {
      color: #6b7280;
    }

    .sub {
      color: #9ca3af;
    }

    .phase-in_progress .sub {
      color: #c4b5fd;
    }
  }
</style>
