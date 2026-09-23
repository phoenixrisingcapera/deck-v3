<script lang="ts">
  interface Props {
    label: string;
    text: string;
    side?: 'top' | 'right' | 'bottom' | 'left';
  }

  let { label, text, side = 'top' }: Props = $props();
  let open = $state(false);

  function close() {
    open = false;
  }
</script>

<span class="info-icon" class:open data-side={side}>
  <button
    type="button"
    aria-label={label}
    aria-expanded={open}
    onclick={() => (open = !open)}
    onblur={close}
    onkeydown={(event) => {
      if (event.key === 'Escape') close();
    }}
  >
    i
  </button>
  <span class="tooltip" role="tooltip" aria-hidden={!open}>{text}</span>
</span>

<style>
  .info-icon {
    position: relative;
    display: inline-grid;
    place-items: center;
    vertical-align: middle;
  }

  button {
    width: 1.1rem;
    height: 1.1rem;
    display: grid;
    place-items: center;
    border: 1px solid color-mix(in srgb, currentColor 26%, transparent);
    border-radius: 999px;
    padding: 0;
    color: inherit;
    background: transparent;
    font: 700 0.72rem/1 system-ui, sans-serif;
    cursor: help;
    opacity: 0.72;
  }

  button:hover,
  button:focus-visible,
  .open button {
    opacity: 1;
    outline: none;
    border-color: currentColor;
  }

  .tooltip {
    position: absolute;
    z-index: 60;
    width: max-content;
    max-width: min(18rem, calc(100vw - 2rem));
    padding: 0.55rem 0.65rem;
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 0.65rem;
    color: #e5e7eb;
    background: rgba(15, 23, 42, 0.98);
    box-shadow: 0 14px 36px rgba(2, 6, 23, 0.35);
    font-size: 0.76rem;
    font-weight: 500;
    line-height: 1.45;
    pointer-events: none;
    opacity: 0;
    visibility: hidden;
    transform: translateY(0.25rem);
    transition: opacity 120ms ease, transform 120ms ease, visibility 120ms ease;
  }

  .open .tooltip,
  .info-icon:hover .tooltip,
  .info-icon:focus-within .tooltip {
    opacity: 1;
    visibility: visible;
    transform: translateY(0);
  }

  [data-side='top'] .tooltip {
    left: 50%;
    bottom: calc(100% + 0.45rem);
    transform: translate(-50%, 0.25rem);
  }

  [data-side='top'].open .tooltip,
  [data-side='top']:hover .tooltip,
  [data-side='top']:focus-within .tooltip {
    transform: translate(-50%, 0);
  }

  [data-side='bottom'] .tooltip {
    left: 50%;
    top: calc(100% + 0.45rem);
    transform: translate(-50%, -0.25rem);
  }

  [data-side='bottom'].open .tooltip,
  [data-side='bottom']:hover .tooltip,
  [data-side='bottom']:focus-within .tooltip {
    transform: translate(-50%, 0);
  }

  [data-side='left'] .tooltip {
    right: calc(100% + 0.45rem);
    top: 50%;
    transform: translate(0.25rem, -50%);
  }

  [data-side='left'].open .tooltip,
  [data-side='left']:hover .tooltip,
  [data-side='left']:focus-within .tooltip {
    transform: translate(0, -50%);
  }

  [data-side='right'] .tooltip {
    left: calc(100% + 0.45rem);
    top: 50%;
    transform: translate(-0.25rem, -50%);
  }

  [data-side='right'].open .tooltip,
  [data-side='right']:hover .tooltip,
  [data-side='right']:focus-within .tooltip {
    transform: translate(0, -50%);
  }

  @media (hover: none) {
    .info-icon:not(.open) .tooltip {
      opacity: 0;
      visibility: hidden;
    }
  }
</style>
