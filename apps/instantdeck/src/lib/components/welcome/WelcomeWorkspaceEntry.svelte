<!-- CANONICAL /welcome ENTRY: this file intentionally reuses the absorbed welcome-v2 visual components. /welcome-v2 itself is redirect-only. -->
<script lang="ts">
  import DeveloperVisibilityCard from '$components/visibility/DeveloperVisibilityCard.svelte';
  import { createDeveloperVisibilityItems, type ProductDeveloperToolsPayload } from '$lib/developer-tools/payload';
  import WelcomeActionCard from '$components/welcome-v2/WelcomeActionCard.svelte';
  import WelcomeHeroStage from '$components/welcome-v2/WelcomeHeroStage.svelte';
  // DISABLED: Admin-role gating for welcome diagnostics was removed on 2026-07-14.
   // Reason: Product visibility should stay on /welcome instead of branching into separate developer surfaces.
  // import { sessionState } from '$lib/stores/session';
  import type { WorkspaceSummary } from '@deck-aistack-codes/shared';

  type WorkspaceLoadStatus = {
    status: 'ready' | 'degraded';
    backendStatus?: number;
    message: string | null;
    requestId?: string | null;
    ticketId?: string | null;
    requestedAt?: string | null;
    loadedAt?: string | null;
    loadDurationMs?: number | null;
  };

  interface Props {
    workspace: WorkspaceSummary;
    routeNotice?: string | null;
    workspaceLoadStatus?: WorkspaceLoadStatus | null;
    developerToolsPayload: ProductDeveloperToolsPayload;
  }

  let { workspace, routeNotice = null, workspaceLoadStatus = null, developerToolsPayload }: Props = $props();

  const uploadDeckRoute = '/decks/new?firstBatch=slide_miniatures';
  const companyWebsiteRoute = '/decks/new?firstBatch=url_branding';
  const brandAssetsRoute = '/decks/new?firstBatch=logo_branding';
  const fallbackMessage =
    'We could not load your previous decks right now. You can still upload a new deck and continue testing.';

  const actionCards = [
    {
      step: '01',
      icon: '↑',
      variant: 'deck',
      title: 'Upload your deck',
      message:
        'Start with a PDF or PowerPoint deck. DeckAiStack will read the slides and prepare a workspace for AI review, edits, and improvements.',
      href: uploadDeckRoute,
      cta: 'Upload deck'
    },
    {
      step: '02',
      icon: '◉',
      variant: 'website',
      title: 'Add company website',
      message:
        'Use the company website to give DeckAiStack extra context about the business, brand, product, and market positioning.',
      href: companyWebsiteRoute,
      cta: 'Add website'
    },
    {
      step: '03',
      icon: '◇',
      variant: 'brand',
      title: 'Add logo or brand assets',
      message:
        'Upload a logo or brand file so DeckAiStack can keep colours, visual style, and brand direction consistent.',
      href: brandAssetsRoute,
      cta: 'Upload brand assets'
    }
  ] as const;

  const previewRows = [
    {
      label: 'AI review',
      copy: 'Narrative, clarity, structure, and investor-readiness'
    },
    {
      label: 'Reviewable edits',
      copy: 'Suggestions stay editable before anything is applied'
    },
    {
      label: 'Reviewable versions',
      copy: 'Prepare versions for VC, board, IC, or advisory review'
    }
  ] as const;

  const workspaceName = $derived(workspace.workspace.name || 'Deck AIStack Workspace');
  const recentDecks = $derived(workspace.latestDecks ?? []);
  const workspaceNotice = $derived(
    workspaceLoadStatus?.status === 'degraded'
      ? workspaceLoadStatus.message ?? fallbackMessage
      : null
  );
  const deckCount = $derived(workspace.deckCount ?? 0);
  const readyDeckCount = $derived(workspace.readyDeckCount ?? 0);
  const exportCount = $derived(workspace.exportCount ?? 0);
  const workspaceSignals = $derived([
    { label: 'Decks', value: deckCount },
    { label: 'Ready', value: readyDeckCount },
    { label: 'Exports', value: exportCount }
  ]);
  const welcomeVisibilityItems = $derived([
    { label: 'Workspace', value: workspaceName },
    { label: 'Deck count', value: deckCount },
    { label: 'Ready decks', value: readyDeckCount },
    { label: 'Exports', value: exportCount },
    { label: 'Active deck', value: workspace.activeDeckId ?? 'n/a' },
    { label: 'Load status', value: workspaceLoadStatus?.status ?? 'ready' }
  ]);
  const productDiagnosticsItems = $derived(
    createDeveloperVisibilityItems(developerToolsPayload, [
      { label: 'Request id', value: workspaceLoadStatus?.requestId ?? null },
      { label: 'Failure ticket', value: workspaceLoadStatus?.ticketId ?? null },
      { label: 'Processing decks', value: workspace.processingDeckCount ?? 0 },
      { label: 'Latest deck count shown', value: recentDecks.length },
      { label: 'Degraded message', value: workspaceLoadStatus?.message ?? null }
    ])
  );
</script>

<svelte:head>
  <title>Welcome | DeckAiStack</title>
</svelte:head>

<section class="welcome-v2">
    <section class="hero panel">
      <div class="hero__copy">
        <div class="eyebrow">AI deck review workspace</div>
        <h1 class="display">Upload a deck.<br />Review it with AI.<br />Improve it faster.</h1>

        <p class="hero__subtitle">
          Review your deck, improve the narrative, and prepare a version for the right audience.
        </p>

        <div class="hero__actions">
          <a class="button hero__primary" href={uploadDeckRoute}>Upload deck</a>
          <a class="button secondary hero__secondary" href={companyWebsiteRoute}>Add context instead</a>
        </div>

        <div class="hero__signals" aria-label="Workspace signals">
          {#each workspaceSignals as signal}
            <span class="pill hero__signal">
              <strong>{signal.value}</strong>
              <span>{signal.label}</span>
            </span>
          {/each}
        </div>

        <p class="hero__trust">
          <span aria-hidden="true">🔒</span>
          Your files remain within your workspace. <a href="/privacy">Privacy</a>
        </p>

        {#if workspaceNotice}
          <div class="hero__notice" role="status">
            <strong>Workspace notice</strong>
            <p>{workspaceNotice}</p>
          </div>
        {/if}
      </div>

      <WelcomeHeroStage
        {workspaceName}
        {workspaceNotice}
        {previewRows}
        {recentDecks}
        deckCount={deckCount}
        readyDeckCount={readyDeckCount}
        exportCount={exportCount}
      />
    </section>

    <section class="content-grid" aria-label="Start here">
      <div class="action-grid">
        {#each actionCards as card}
          <WelcomeActionCard {...card} />
        {/each}
      </div>

      <aside class="preview panel">
        <div class="preview__eyebrow">Deck review workflow</div>
        <h2 class="preview__title display">How Smart Deck works</h2>
        <p class="preview__lede">
          Upload first, then layer in company context and brand assets. Every suggestion stays reviewable before it
          becomes part of the deck.
        </p>

        <div class="preview__tracks">
          <div class="preview__track">
            <span class="preview__track-label">Upload</span>
            <strong>PDF or PowerPoint slides</strong>
          </div>
          <div class="preview__track">
            <span class="preview__track-label">Context</span>
            <strong>Website, brand, and positioning</strong>
          </div>
          <div class="preview__track">
            <span class="preview__track-label">Review</span>
            <strong>Editable AI suggestions and reviewable versions</strong>
          </div>
        </div>

        <div class="preview__footer">
          <span class="pill">Reviewable edits</span>
          <span class="pill">Private workspace</span>
        </div>
      </aside>
    </section>

    <section class="panel welcome-visibility" aria-label="Welcome visibility">
      <div class="welcome-visibility__head">
        <div>
          <div class="eyebrow">Workspace visibility</div>
          <h2>Start from the right surface</h2>
        </div>
        <span class:warning={workspaceLoadStatus?.status === 'degraded'} class="welcome-visibility__status">
          {workspaceLoadStatus?.status === 'degraded' ? 'degraded' : 'ready'}
        </span>
      </div>

      <div class="welcome-visibility__grid">
        {#each welcomeVisibilityItems as item}
          <div class="welcome-visibility__item">
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </div>
        {/each}
      </div>
    </section>

    <div class="welcome-strip panel">
      <div class="welcome-strip__copy">
        <span class="welcome-strip__icon" aria-hidden="true">i</span>
        <div>
          <strong>New to DeckAiStack?</strong>
          <p>Upload a deck to review AI insights, suggestions, and reviewable versions.</p>
        </div>
      </div>

      <a class="welcome-strip__link" href={uploadDeckRoute}>
        Learn how it works
        <span aria-hidden="true">→</span>
      </a>
    </div>

    <DeveloperVisibilityCard
      title="Workspace diagnostics"
      summary="Welcome-route diagnostics for the current workspace. Deeper operator telemetry remains internal."
      items={productDiagnosticsItems}
    />
</section>

<style>
  .welcome-v2 {
    display: grid;
    gap: 1rem;
    padding-bottom: 0.25rem;
  }

  .welcome-visibility {
    display: grid;
    gap: 0.9rem;
    padding: 1rem;
  }

  .welcome-visibility__head {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    align-items: flex-start;
  }

  .welcome-visibility__head h2 {
    margin: 0.25rem 0 0;
    font-size: 1.1rem;
  }

  .welcome-visibility__status {
    padding: 0.3rem 0.65rem;
    border-radius: 999px;
    border: 1px solid var(--line);
    color: var(--text-muted);
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .welcome-visibility__status.warning {
    color: var(--danger);
    border-color: var(--danger);
  }

  .welcome-visibility__grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 0.7rem;
  }

  .welcome-visibility__item {
    display: grid;
    gap: 0.15rem;
    padding: 0.8rem 0.85rem;
    border: 1px solid var(--line);
    border-radius: 14px;
    background: color-mix(in srgb, var(--surface) 92%, transparent);
  }

  .welcome-visibility__item span {
    color: var(--muted);
    font-size: 0.72rem;
  }

  .welcome-visibility__item strong {
    overflow-wrap: anywhere;
    font-size: 0.88rem;
  }

  .hero {
    position: relative;
    overflow: hidden;
    display: grid;
    grid-template-columns: minmax(0, 1.3fr) minmax(19rem, 0.9fr);
    gap: 1.15rem;
    padding: clamp(1.25rem, 2vw, 1.75rem);
    border-color: color-mix(in srgb, var(--line-strong) 56%, var(--line));
    background:
      radial-gradient(circle at top left, color-mix(in srgb, var(--accent-soft) 72%, transparent), transparent 34rem),
      radial-gradient(circle at top right, color-mix(in srgb, var(--accent-2) 28%, transparent), transparent 28rem),
      linear-gradient(180deg, color-mix(in srgb, var(--surface-strong) 86%, transparent), color-mix(in srgb, var(--surface) 96%, transparent));
    box-shadow: var(--shadow-strong);
  }

  .hero__copy {
    min-width: 0;
    display: grid;
    gap: 1rem;
    align-content: start;
  }

  .display,
  h1,
  h2 {
    margin: 0;
    min-width: 0;
    overflow-wrap: anywhere;
    word-break: normal;
    line-height: 0.95;
    letter-spacing: -0.04em;
    font-style: normal;
  }

  h1.display {
    font-size: clamp(2.5rem, 5.1vw, 4.55rem);
    max-width: 12ch;
  }

  .hero__subtitle,
  .preview__lede {
    margin: 0;
    max-width: 58ch;
    color: var(--muted);
    line-height: 1.72;
    font-size: 1rem;
  }

  .hero__actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: center;
  }

  .hero__primary,
  .hero__secondary {
    min-width: 13rem;
    padding-inline: 1.2rem;
  }

  .hero__primary {
    box-shadow: var(--shadow-glow-blue);
  }

  .hero__signals {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
  }

  .hero__signal {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    min-height: 2.55rem;
    padding-inline: 0.9rem;
  }

  .hero__signal strong {
    font-size: 1rem;
    color: var(--ink-strong);
  }

  .hero__signal span {
    color: var(--ink-soft);
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .hero__trust {
    display: inline-flex;
    gap: 0.5rem;
    align-items: center;
    margin: 0;
    color: var(--ink-soft);
    font-size: 0.94rem;
    line-height: 1.5;
  }

  .hero__notice {
    display: grid;
    gap: 0.3rem;
    max-width: 48rem;
    padding: 0.95rem 1rem;
    border-radius: 16px;
    border: 1px solid color-mix(in srgb, var(--accent) 26%, var(--line));
    background:
      linear-gradient(180deg, color-mix(in srgb, var(--accent-soft) 42%, transparent), transparent),
      color-mix(in srgb, var(--surface-soft) 82%, transparent);
  }

  .hero__notice strong {
    color: var(--ink-strong);
    font-size: 0.95rem;
  }

  .hero__notice p {
    margin: 0;
    color: var(--muted);
    line-height: 1.55;
  }

  .content-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(18rem, 0.82fr);
    gap: 1rem;
    align-items: start;
  }

  .action-grid {
    display: grid;
    gap: 0.9rem;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    min-width: 0;
  }

  .preview {
    min-width: 0;
    display: grid;
    gap: 0.95rem;
    align-content: start;
    padding: 1.1rem;
    border-color: color-mix(in srgb, var(--line-strong) 34%, var(--line));
    background:
      radial-gradient(circle at top right, color-mix(in srgb, var(--accent) 16%, transparent), transparent 55%),
      linear-gradient(180deg, color-mix(in srgb, var(--surface-strong) 86%, transparent), color-mix(in srgb, var(--surface) 96%, transparent));
  }

  .preview__eyebrow {
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.76rem;
    color: var(--accent);
  }

  .preview__title {
    font-size: clamp(1.85rem, 3vw, 2.6rem);
  }

  .preview__tracks {
    display: grid;
    gap: 0.7rem;
  }

  .preview__track {
    display: grid;
    gap: 0.2rem;
    padding: 0.8rem 0.9rem;
    border-radius: 14px;
    border: 1px solid color-mix(in srgb, var(--line-strong) 28%, var(--line));
    background: color-mix(in srgb, var(--surface-soft) 72%, transparent);
  }

  .preview__track-label {
    color: var(--accent);
    font-size: 0.74rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .preview__track strong {
    color: var(--ink-strong);
    line-height: 1.35;
  }

  .preview__footer {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
  }

  .welcome-strip {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: center;
    padding: 0.95rem 1.1rem;
  }

  .welcome-strip__copy {
    display: flex;
    gap: 0.75rem;
    align-items: flex-start;
  }

  .welcome-strip__copy p {
    margin: 0.2rem 0 0;
    color: var(--muted);
    line-height: 1.5;
  }

  .welcome-strip__icon {
    width: 2rem;
    height: 2rem;
    display: inline-grid;
    place-items: center;
    border-radius: 999px;
    background: color-mix(in srgb, var(--accent-soft) 54%, transparent);
    color: var(--accent);
    font-weight: 700;
  }

  .welcome-strip__link {
    display: inline-flex;
    gap: 0.45rem;
    align-items: center;
    color: var(--accent);
    font-weight: 700;
    white-space: nowrap;
  }

  @media (max-width: 1080px) {
    .content-grid {
      grid-template-columns: 1fr;
    }

    .action-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 860px) {
    .hero {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 700px) {
    .action-grid {
      grid-template-columns: 1fr;
    }

    .welcome-strip {
      flex-direction: column;
      align-items: flex-start;
    }
  }
</style>
