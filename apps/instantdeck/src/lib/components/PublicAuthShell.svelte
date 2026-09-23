<script lang="ts">
  import AppLogo from '$components/AppLogo.svelte';

  interface Props {
    eyebrow?: string;
    title: string;
    subtitle?: string;
    alternateHref?: string;
    alternateLabel?: string;
    alternateCta?: string;
    children?: import('svelte').Snippet;
  }

  let {
    eyebrow = 'Deck',
    title,
    subtitle = '',
    alternateHref = '/auth/sign-up',
    alternateLabel = "Don't have an account?",
    alternateCta = 'Sign up',
    children
  }: Props = $props();

  const features = [
    'AI-powered deck analysis',
    'Reviewable edits and structured blocks',
    'Export-ready diligence workflows',
    'Team collaboration and workspace'
  ];
</script>

<section class="auth-shell">
  <!-- Branded side panel -->
  <aside class="auth-shell__brand">
    <div class="auth-shell__brand-atmosphere" aria-hidden="true">
      <span class="auth-shell__orb auth-shell__orb--blue"></span>
      <span class="auth-shell__orb auth-shell__orb--pink"></span>
      <span class="auth-shell__grid"></span>
    </div>

    <div class="auth-shell__brand-content">
      <div class="auth-shell__logo-row">
        <AppLogo size="sm" alt="Deck" />
        <strong>Deck</strong>
      </div>

      <h2 class="auth-shell__headline">Turn founder decks into live diligence workspaces.</h2>

      <ul class="auth-shell__features">
        {#each features as feature}
          <li class="auth-shell__feature">
            <span class="auth-shell__feature-dot"></span>
            {feature}
          </li>
        {/each}
      </ul>
    </div>
  </aside>

  <!-- Form panel -->
  <main class="panel auth-shell__panel">
    <div class="auth-shell__panel-header">
      <div class="eyebrow">{eyebrow}</div>
      <h1>{title}</h1>
      {#if subtitle}
        <p class="auth-shell__subtitle">{subtitle}</p>
      {/if}
    </div>

    <div class="auth-shell__form-area">
      {@render children?.()}
    </div>

    <p class="auth-shell__alternate">{alternateLabel} <a href={alternateHref}>{alternateCta}</a></p>
  </main>
</section>

<style>
  .auth-shell {
    width: min(100%, 56rem);
    margin: auto;
    padding: clamp(1.5rem, 5vh, 3rem) clamp(1rem, 3vw, 2rem);
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(22rem, 1.1fr);
    align-items: stretch;
    gap: 0;
    min-height: 100vh;
  }

  /* ---- Branded side panel ---- */
  .auth-shell__brand {
    position: relative;
    display: grid;
    align-content: center;
    padding: clamp(2rem, 4vw, 3.5rem);
    background:
      radial-gradient(circle at 25% 70%, rgba(48, 154, 255, 0.14), transparent 40%),
      radial-gradient(circle at 75% 20%, rgba(255, 82, 168, 0.10), transparent 35%),
      linear-gradient(180deg, rgba(6, 13, 30, 0.98), rgba(2, 6, 23, 1));
    border-radius: var(--radius-xl) 0 0 var(--radius-xl);
    overflow: hidden;
    isolation: isolate;
  }

  .auth-shell__brand-atmosphere {
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 0;
  }

  .auth-shell__orb {
    position: absolute;
    border-radius: 999px;
    filter: blur(20px);
    opacity: 0.5;
  }

  .auth-shell__orb--blue {
    width: 16rem;
    height: 16rem;
    left: -4rem;
    bottom: -4rem;
    background: rgba(48, 154, 255, 0.16);
  }

  .auth-shell__orb--pink {
    width: 12rem;
    height: 12rem;
    right: -2rem;
    top: -3rem;
    background: rgba(255, 82, 168, 0.12);
  }

  .auth-shell__grid {
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
    background-size: 32px 32px;
    mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.3), transparent 70%);
    opacity: 0.25;
  }

  .auth-shell__brand-content {
    position: relative;
    z-index: 1;
    display: grid;
    gap: 1.5rem;
  }

  .auth-shell__logo-row {
    display: inline-flex;
    align-items: center;
    gap: 0.6rem;
  }

  .auth-shell__logo-row strong {
    color: #f8fbff;
    font-size: 1.1rem;
  }

  .auth-shell__headline {
    color: #f8fbff;
    font-size: clamp(1.4rem, 3vw, 1.8rem);
    line-height: 1.3;
    letter-spacing: -0.03em;
    margin: 0;
  }

  .auth-shell__features {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.7rem;
  }

  .auth-shell__feature {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    color: rgba(223, 232, 248, 0.82);
    font-size: 0.875rem;
    line-height: 1.5;
  }

  .auth-shell__feature-dot {
    width: 6px;
    height: 6px;
    border-radius: 999px;
    background: linear-gradient(180deg, #53a7ff, #45d7a5);
    box-shadow: 0 0 8px rgba(83, 167, 255, 0.4);
    flex-shrink: 0;
  }

  /* ---- Form panel ---- */
  .auth-shell__panel {
    width: 100%;
    padding: clamp(2rem, 4vw, 3rem);
    display: grid;
    gap: 1.5rem;
    align-content: center;
    border-radius: 0 var(--radius-xl) var(--radius-xl) 0;
    border-left: 1px solid rgba(148, 163, 184, 0.12);
    background:
      radial-gradient(circle at 85% 15%, rgba(240, 84, 197, 0.06), transparent 40%),
      radial-gradient(circle at 15% 85%, rgba(78, 122, 255, 0.06), transparent 40%),
      var(--gradient-surface);
  }

  .auth-shell__panel-header {
    display: grid;
    gap: 0.5rem;
  }

  .auth-shell__panel-header h1 {
    font-size: clamp(1.5rem, 3.5vw, 2rem);
    letter-spacing: -0.03em;
    margin: 0;
  }

  .auth-shell__subtitle {
    color: var(--text-secondary);
    font-size: 0.875rem;
    line-height: 1.5;
    margin: 0;
  }

  .auth-shell__form-area {
    display: grid;
    gap: 1rem;
  }

  .auth-shell__alternate {
    color: var(--text-secondary);
    font-size: 0.8125rem;
    text-align: center;
    margin: 0;
  }

  .auth-shell__alternate a {
    color: var(--accent);
    font-weight: 600;
    text-decoration: none;
  }

  .auth-shell__alternate a:hover {
    text-decoration: underline;
  }

  /* ---- Mobile ---- */
  @media (max-width: 768px) {
    .auth-shell {
      grid-template-columns: 1fr;
      min-height: auto;
      padding: 0;
    }

    .auth-shell__brand {
      display: none;
    }

    .auth-shell__panel {
      border-radius: 0;
      border-left: none;
      min-height: 100vh;
      align-content: center;
      padding: clamp(2rem, 6vw, 3rem);
    }
  }

  @media (min-width: 769px) and (max-width: 1024px) {
    .auth-shell__brand {
      padding: clamp(1.5rem, 3vw, 2.5rem);
    }

    .auth-shell__headline {
      font-size: 1.3rem;
    }

    .auth-shell__panel {
      padding: clamp(1.5rem, 3vw, 2.5rem);
    }
  }
</style>
