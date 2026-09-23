<script lang="ts">
  import type { JobEvent } from '$lib/transport';

  // Hard cap on rendered log lines. The DOM cost of a `<div>` per event with
  // pre-wrap layout is the dominant frame-time cost on long runs. The full
  // event history is in the store (capped at 2000) and on disk in server-log.txt;
  // the live UI just shows the recent tail.
  const MAX_RENDERED_LINES = 1000;

  interface Props {
    events: JobEvent[];
    isRunning: boolean;
  }

  let { events, isRunning }: Props = $props();

  let logEl = $state<HTMLElement | null>(null);

  // Filter out milestones (they have their own panel) and cap to the tail.
  let visibleEvents = $derived.by(() => {
    const filtered = events.filter((e) => e.type !== 'milestone');
    return filtered.length > MAX_RENDERED_LINES
      ? filtered.slice(-MAX_RENDERED_LINES)
      : filtered;
  });

  let droppedFromHead = $derived(
    Math.max(0, events.filter((e) => e.type !== 'milestone').length - MAX_RENDERED_LINES)
  );

  // Coalesce auto-scroll into one rAF per frame. Without this, every new event
  // forced a synchronous `scrollHeight` read + scroll write, which is the most
  // expensive layout operation in the render path. Bursts of 50+ events from a
  // single agent print would each thrash layout.
  let scrollPending = false;
  $effect(() => {
    void visibleEvents.length;
    if (scrollPending || !logEl) return;
    scrollPending = true;
    requestAnimationFrame(() => {
      if (logEl) logEl.scrollTop = logEl.scrollHeight;
      scrollPending = false;
    });
  });

  function formatLine(event: JobEvent): string {
    if (event.type === 'log' && typeof event.line === 'string') return event.line;
    if (event.type === 'status' && typeof event.status === 'string')
      return `▸ status: ${event.status}`;
    if (event.type === 'complete') {
      const dir = typeof event.output_dir === 'string' ? event.output_dir : '';
      return `✓ complete${dir ? ` — ${dir}` : ''}`;
    }
    if (event.type === 'error' && typeof event.message === 'string')
      return `✗ error: ${event.message}`;
    return JSON.stringify(event);
  }
</script>

<section class="stream">
  <header class="head">
    <h3>Live log</h3>
    <span class="meta">
      {visibleEvents.length}
      {visibleEvents.length === 1 ? 'line' : 'lines'}
      {#if isRunning}
        <span class="cursor" aria-hidden="true">▍</span>
      {/if}
    </span>
  </header>

  <div class="pane" bind:this={logEl}>
    {#if visibleEvents.length === 0}
      <div class="placeholder">
        Waiting for the orchestrator to start…
        <span class="blink" aria-hidden="true">▍</span>
      </div>
    {:else}
      {#if droppedFromHead > 0}
        <div class="dropped">
          ⋯ {droppedFromHead} earlier {droppedFromHead === 1 ? 'line' : 'lines'} hidden — full log on disk in <code>server-log.txt</code>
        </div>
      {/if}
      {#each visibleEvents as event, i (i)}
        <div class="line line-{event.type}">{formatLine(event)}</div>
      {/each}
      {#if isRunning}
        <div class="line live"><span class="cursor">▍</span></div>
      {/if}
    {/if}
  </div>
</section>

<style>
  .stream {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: #0b0b0d;
    overflow: hidden;
  }

  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.85rem 1.25rem 0.6rem;
    border-bottom: 1px solid #1f2024;
    background: #0b0b0d;
  }

  h3 {
    margin: 0;
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #6b7280;
  }

  .meta {
    font-size: 0.7rem;
    color: #6b7280;
    font-variant-numeric: tabular-nums;
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }

  .meta .cursor {
    color: #a855f7;
    animation: blink 1.1s steps(2, jump-none) infinite;
  }

  .pane {
    flex: 1;
    overflow-y: auto;
    padding: 0.85rem 1.25rem 1.25rem;
    font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Consolas, monospace;
    font-size: 0.8rem;
    line-height: 1.6;
    color: #d1d5db;
  }

  .placeholder {
    color: #6b7280;
    font-style: italic;
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }

  .placeholder .blink {
    color: #a855f7;
    font-style: normal;
    animation: blink 1.1s steps(2, jump-none) infinite;
  }

  .line {
    white-space: pre-wrap;
    word-break: break-word;
  }

  .dropped {
    color: #6b7280;
    font-style: italic;
    font-size: 0.7rem;
    padding: 0.4rem 0.5rem;
    margin-bottom: 0.25rem;
    border-bottom: 1px dashed #2a2a2c;
  }

  .dropped code {
    color: #c4b5fd;
    background: rgba(164, 99, 255, 0.1);
    padding: 0.05rem 0.25rem;
    border-radius: 3px;
  }

  .line-status {
    color: #c4b5fd;
  }

  .line-complete {
    color: #6ee7b7;
    font-weight: 600;
  }

  .line-error {
    color: #fca5a5;
    font-weight: 600;
  }

  .line.live .cursor {
    color: #a855f7;
    animation: blink 1.1s steps(2, jump-none) infinite;
  }

  @keyframes blink {
    50% {
      opacity: 0;
    }
  }
</style>
