<script lang="ts">
  type DeckLoaderStep = {
    label: string;
    status?: 'pending' | 'running' | 'complete' | 'failed';
  };

  interface Props {
    open?: boolean;
    title?: string;
    subtitle?: string;
    statusLabel?: string;
    progress?: number;
    steps?: DeckLoaderStep[];
    errorMessage?: string;
  }

  let {
    open = false,
    title = 'Preparing your deck...',
    subtitle = 'Saving the source file and preparing the workspace.',
    statusLabel = 'Working',
    progress = 18,
    steps = [],
    errorMessage = ''
  }: Props = $props();

  const clampedProgress = $derived(Math.max(8, Math.min(100, Math.round(progress))));

  $effect(() => {
    if (!open) return;

    const previousBodyOverflow = document.body.style.overflow;
    const previousHtmlOverflow = document.documentElement.style.overflow;
    document.body.style.overflow = 'hidden';
    document.documentElement.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.documentElement.style.overflow = previousHtmlOverflow;
    };
  });
</script>

{#if open}
  <div class="deck-loader-overlay" role="status" aria-live="polite" aria-busy={!errorMessage}>
    <section class="deck-loader-panel panel">
      <div class="deck-loader-panel__top">
        <div class="deck-loader-panel__icon" aria-hidden="true">
          <span></span>
          <span></span>
          <span></span>
        </div>

        <div class="deck-loader-panel__copy">
          <div class="eyebrow">Deck intake</div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>

        <span class="deck-loader-panel__status">{errorMessage ? 'Needs attention' : statusLabel}</span>
      </div>

      {#if steps.length}
        <ol class="deck-loader-panel__steps" aria-label="Deck preparation steps">
          {#each steps as step}
            <li class={`deck-loader-panel__step deck-loader-panel__step--${step.status ?? 'pending'}`}>
              <span></span>
              <strong>{step.label}</strong>
            </li>
          {/each}
        </ol>
      {/if}

      {#if errorMessage}
        <p class="deck-loader-panel__error">{errorMessage}</p>
      {:else}
        <div class="deck-loader-panel__progress" aria-label={`${clampedProgress}% complete`}>
          <span style={`width: ${clampedProgress}%`}></span>
        </div>
      {/if}
    </section>
  </div>
{/if}

<style>
  .deck-loader-overlay {
    position: fixed;
    inset: 0;
    z-index: 80;
    display: grid;
    place-items: center;
    padding: 1rem;
    background: rgba(5, 9, 20, 0.64);
    backdrop-filter: blur(10px);
  }

  .deck-loader-panel {
    width: min(100%, 32rem);
    max-height: min(32rem, calc(100svh - 2rem));
    overflow: hidden;
    display: grid;
    gap: 1rem;
    padding: 1.1rem;
    border-radius: 12px;
    box-shadow: 0 24px 76px rgba(0, 0, 0, 0.32);
  }

  .deck-loader-panel__top {
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: start;
    gap: 0.85rem;
    min-width: 0;
  }

  .deck-loader-panel__icon {
    width: 3rem;
    aspect-ratio: 1;
    display: grid;
    place-items: center;
    position: relative;
    border-radius: 10px;
    border: 1px solid var(--line);
    background: var(--surface-soft);
  }

  .deck-loader-panel__icon span {
    position: absolute;
    width: 1.4rem;
    height: 1rem;
    border: 1px solid rgba(95, 135, 255, 0.72);
    border-radius: 4px;
    background: rgba(40, 70, 145, 0.38);
  }

  .deck-loader-panel__icon span:nth-child(1) {
    transform: translate(-0.18rem, -0.22rem) rotate(-7deg);
  }

  .deck-loader-panel__icon span:nth-child(2) {
    transform: translate(0.1rem, 0) rotate(4deg);
  }

  .deck-loader-panel__icon span:nth-child(3) {
    transform: translate(0.28rem, 0.24rem) rotate(9deg);
    animation: deck-loader-card 1.2s ease-in-out infinite alternate;
  }

  .deck-loader-panel__copy {
    min-width: 0;
    display: grid;
    gap: 0.28rem;
  }

  .deck-loader-panel__copy h2,
  .deck-loader-panel__copy p {
    margin: 0;
  }

  .deck-loader-panel__copy h2 {
    font-size: 1.28rem;
    line-height: 1.12;
    letter-spacing: 0;
  }

  .deck-loader-panel__copy p {
    color: var(--muted);
    font-size: 0.92rem;
    line-height: 1.45;
  }

  .deck-loader-panel__status {
    min-height: 1.8rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.3rem 0.58rem;
    border: 1px solid var(--line);
    border-radius: 999px;
    color: var(--muted);
    font-size: 0.76rem;
    white-space: nowrap;
  }

  .deck-loader-panel__steps {
    display: grid;
    gap: 0.5rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .deck-loader-panel__step {
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: center;
    gap: 0.6rem;
    min-height: 2.35rem;
    padding: 0.55rem 0.7rem;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--surface-soft);
    color: var(--muted);
  }

  .deck-loader-panel__step span {
    width: 0.55rem;
    aspect-ratio: 1;
    border-radius: 999px;
    border: 1px solid currentColor;
  }

  .deck-loader-panel__step strong {
    min-width: 0;
    color: inherit;
    font-size: 0.86rem;
    font-weight: 650;
  }

  .deck-loader-panel__step--running {
    color: #7aa2ff;
  }

  .deck-loader-panel__step--running span {
    background: currentColor;
    animation: deck-loader-dot 0.9s ease-in-out infinite alternate;
  }

  .deck-loader-panel__step--complete {
    color: #57d4a0;
  }

  .deck-loader-panel__step--complete span {
    background: currentColor;
  }

  .deck-loader-panel__step--failed {
    color: var(--danger);
  }

  .deck-loader-panel__progress {
    height: 0.45rem;
    overflow: hidden;
    border: 1px solid var(--line);
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.06);
  }

  .deck-loader-panel__progress span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, #4f86ff, #57d4a0);
    transition: width 240ms ease;
  }

  .deck-loader-panel__error {
    margin: 0;
    color: var(--danger);
  }

  @keyframes deck-loader-card {
    from { transform: translate(0.2rem, 0.18rem) rotate(6deg); }
    to { transform: translate(0.34rem, 0.28rem) rotate(10deg); }
  }

  @keyframes deck-loader-dot {
    from { opacity: 0.55; transform: scale(0.9); }
    to { opacity: 1; transform: scale(1.08); }
  }

  @media (max-width: 560px) {
    .deck-loader-panel {
      padding: 0.95rem;
    }

    .deck-loader-panel__top {
      grid-template-columns: auto 1fr;
    }

    .deck-loader-panel__status {
      grid-column: 1 / -1;
      justify-self: start;
    }
  }
</style>
