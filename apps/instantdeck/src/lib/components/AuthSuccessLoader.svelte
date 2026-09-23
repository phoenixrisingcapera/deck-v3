<script lang="ts">
  interface Props {
    open?: boolean;
    overlay?: boolean;
    title?: string;
    subtitle?: string;
    notice?: string;
    statusLabel?: string;
    steps?: string[];
    errorMessage?: string;
  }

  let {
    open = true,
    overlay = false,
    title = 'You are signed in.',
    subtitle = 'Preparing your Deck AIStack workspace...',
    notice = '',
    statusLabel = 'Loading',
    steps = [],
    errorMessage = ''
  }: Props = $props();

  $effect(() => {
    if (!overlay || !open) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  });
</script>

{#if open}
  <div class:overlay class="loader-frame" role="status" aria-live="polite" aria-busy="true">
    <section class="loader-shell panel">
      <div class="loader-top">
        <div class="loader-mark" aria-hidden="true">
          <span></span>
        </div>
        <div class="loader-copy">
          <div class="eyebrow">Auth success</div>
          <h1>{title}</h1>
          <p class="muted">{subtitle}</p>
        </div>
        <span class="loader-pill">{statusLabel}</span>
      </div>

      {#if notice}
        <p class="loader-notice">{notice}</p>
      {/if}

      {#if steps.length}
        <div class="loader-steps">
          {#each steps as step, index}
            <div class="loader-step">
              <span>0{index + 1}</span>
              <strong>{step}</strong>
            </div>
          {/each}
        </div>
      {/if}

      {#if errorMessage}
        <p class="loader-error">{errorMessage}</p>
      {:else}
        <div class="loader-progress" aria-hidden="true">
          <span></span>
        </div>
      {/if}
    </section>
  </div>
{/if}

<style>
  .loader-frame {
    display: grid;
    place-items: center;
  }

  .loader-frame.overlay {
    position: fixed;
    inset: 0;
    z-index: 60;
    padding: 1rem;
    background: rgba(8, 12, 24, 0.62);
    backdrop-filter: blur(10px);
  }

  .loader-shell {
    width: min(100%, 560px);
    padding: 1.4rem 1.35rem;
    display: grid;
    gap: 1rem;
    border-radius: 18px;
    box-shadow: 0 28px 90px rgba(3, 8, 24, 0.28);
  }

  .loader-top {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 0.9rem;
    align-items: start;
  }

  .loader-mark {
    width: 2.8rem;
    height: 2.8rem;
    border-radius: 14px;
    background: rgba(91, 120, 255, 0.12);
    border: 1px solid rgba(120, 145, 255, 0.22);
    display: grid;
    place-items: center;
  }

  .loader-mark span {
    width: 1.05rem;
    height: 1.05rem;
    border-radius: 50%;
    background: var(--gradient-brand);
    box-shadow: var(--shadow-glow-blue);
    animation: loader-pulse 1.2s ease-in-out infinite;
  }

  .loader-copy {
    min-width: 0;
  }

  h1 {
    margin: 0;
    font-size: clamp(1.5rem, 2.3vw, 2.1rem);
    letter-spacing: -0.04em;
    line-height: 1.05;
  }

  .loader-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 2rem;
    padding: 0.35rem 0.65rem;
    border-radius: 999px;
    border: 1px solid var(--line);
    color: var(--muted);
    font-size: 0.78rem;
    white-space: nowrap;
  }

  .loader-notice {
    margin: 0;
    padding: 0.8rem 0.9rem;
    border-radius: 14px;
    border: 1px solid rgba(120, 145, 255, 0.18);
    background: rgba(91, 120, 255, 0.08);
    color: var(--text);
    line-height: 1.4;
  }

  .loader-steps {
    display: grid;
    gap: 0.65rem;
  }

  .loader-step {
    border: 1px solid var(--line);
    border-radius: 14px;
    background: var(--surface-soft);
    padding: 0.85rem 0.95rem;
    display: grid;
    gap: 0.3rem;
  }

  .loader-step span {
    font-size: 0.72rem;
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .loader-progress {
    height: 0.5rem;
    border-radius: 999px;
    background: var(--surface-soft);
    overflow: hidden;
    border: 1px solid var(--line);
  }

  .loader-progress span {
    display: block;
    width: 42%;
    height: 100%;
    border-radius: inherit;
    background: var(--gradient-brand);
    box-shadow: var(--shadow-glow-blue);
    animation: auth-progress 1.4s ease-in-out infinite alternate;
  }

  .loader-error {
    margin: 0;
    color: var(--danger);
  }

  @keyframes loader-pulse {
    0%, 100% { transform: scale(0.9); opacity: 0.75; }
    50% { transform: scale(1); opacity: 1; }
  }

  @keyframes auth-progress {
    from { transform: translateX(0); }
    to { transform: translateX(110%); }
  }

  @media (max-width: 560px) {
    .loader-shell {
      padding: 1.1rem 1rem;
      border-radius: 16px;
    }

    .loader-top {
      grid-template-columns: auto 1fr;
    }

    .loader-pill {
      grid-column: 1 / -1;
      justify-self: start;
    }
  }
</style>
