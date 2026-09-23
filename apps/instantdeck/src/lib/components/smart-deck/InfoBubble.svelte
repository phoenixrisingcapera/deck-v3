<!-- Purpose: provides compact help tooltip UI used by Smart Deck cards. -->
<script lang="ts">
  interface Props {
    label: string;
    text: string;
    side?: 'left' | 'right';
  }

  let { label, text, side = 'left' }: Props = $props();
</script>

<span class={`info-bubble info-bubble--${side}`}>
  <button type="button" aria-label={label}>i</button>
  <span class="info-bubble__panel" role="tooltip">{text}</span>
</span>

<style>
  .info-bubble {
    position: relative;
    display: inline-grid;
    place-items: center;
    width: 20px;
    height: 20px;
    flex: 0 0 auto;
  }

  .info-bubble button {
    width: 20px;
    height: 20px;
    display: grid;
    place-items: center;
    border-radius: 999px;
    border: 1px solid var(--line);
    background: var(--surface-soft);
    color: var(--muted);
    font: inherit;
    font-size: 0.68rem;
    line-height: 1;
    padding: 0;
    cursor: help;
  }

  .info-bubble button:hover,
  .info-bubble button:focus-visible {
    border-color: var(--line-strong);
    color: var(--ink-strong);
    background: var(--surface-active);
  }

  .info-bubble__panel {
    position: absolute;
    top: calc(100% + 0.45rem);
    z-index: 20;
    width: min(17rem, 72vw);
    padding: 0.62rem 0.7rem;
    border-radius: 10px;
    border: 1px solid var(--line-strong);
    background: color-mix(in srgb, var(--surface) 96%, transparent);
    color: var(--ink-soft);
    box-shadow: var(--shadow);
    font-size: 0.72rem;
    line-height: 1.35;
    opacity: 0;
    visibility: hidden;
    pointer-events: none;
    transform: translateY(-3px);
    transition:
      opacity 120ms ease,
      transform 120ms ease,
      visibility 120ms ease;
  }

  .info-bubble--left .info-bubble__panel {
    right: 0;
  }

  .info-bubble--right .info-bubble__panel {
    left: 0;
  }

  .info-bubble:hover .info-bubble__panel,
  .info-bubble:focus-within .info-bubble__panel {
    opacity: 1;
    visibility: visible;
    transform: translateY(0);
  }
</style>
