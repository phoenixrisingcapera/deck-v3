<script lang="ts">
  import ThemeToggle from '$components/ThemeToggle.svelte';
  import { sessionState } from '$lib/stores/session';

  interface Props {
    title: string;
    subtitle?: string;
    status?: string;
    workspaceLabel?: string;
    showTopBarCopy?: boolean;
    compactTopBar?: boolean;
    showTopBarSearch?: boolean;
    showUtilities?: boolean;
    deckLabel?: string;
    surfaceNav?: any;
    surfaceNavProps?: Record<string, unknown>;
    actions?: import('svelte').Snippet;
    headerExtension?: import('svelte').Snippet;
  }

  let {
    title,
    subtitle = '',
    status = '',
    workspaceLabel = '',
    showTopBarCopy = true,
    compactTopBar = false,
    showTopBarSearch = true,
    showUtilities = true,
    deckLabel = '',
    surfaceNav = null,
    surfaceNavProps = {},
    actions,
    headerExtension
  }: Props = $props();
</script>

<header class:app-topbar--compact={compactTopBar} class="app-topbar">
  {#if showTopBarCopy}
    <div class="app-topbar__page">
      <div class="app-topbar__page-copy">
        {#if workspaceLabel || deckLabel}
          <div class="app-topbar__context">
            {#if workspaceLabel}
              <span class="app-topbar__workspace">{workspaceLabel}</span>
            {/if}
            {#if deckLabel}
              <span class="app-topbar__deck">{deckLabel}</span>
            {/if}
          </div>
        {/if}
        <strong>{title}</strong>
        {#if subtitle}
          <span>{subtitle}</span>
        {/if}
      </div>
    </div>
  {/if}

  {#if surfaceNav}
    <div class="app-topbar__surfaces">
      <surfaceNav {...surfaceNavProps}></surfaceNav>
    </div>
  {/if}

  <div class="app-topbar__right">
    {#if actions}
      <div class="app-topbar__actions">{@render actions()}</div>
    {/if}
    {#if showUtilities}
      <div data-utilities-placement="topbar">
        <ThemeToggle compact={true} />
      </div>
    {/if}
  </div>

  {#if headerExtension}
    <div class="app-topbar__extension">
      {@render headerExtension()}
    </div>
  {/if}
</header>

<style>
  .app-topbar__context {
    display: flex;
    gap: 0.55rem;
    flex-wrap: wrap;
    align-items: center;
    margin-bottom: 0.2rem;
  }

  .app-topbar__workspace,
  .app-topbar__deck {
    display: inline-flex;
    align-items: center;
    min-height: 22px;
    padding: 0 0.55rem;
    border-radius: 999px;
    font-size: 0.72rem;
    line-height: 1;
  }

  .app-topbar__workspace {
    background: rgba(59, 130, 246, 0.12);
    color: #bfdbfe;
  }

  .app-topbar__deck {
    background: rgba(148, 163, 184, 0.12);
    color: #cbd5e1;
  }

  .app-topbar__surfaces {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    justify-content: center;
  }

  @media (max-width: 1100px) {
    .app-topbar {
      flex-wrap: wrap;
      align-items: flex-start;
      gap: 0.9rem;
    }

    .app-topbar__surfaces {
      order: 3;
      width: 100%;
      justify-content: flex-start;
    }
  }
</style>
