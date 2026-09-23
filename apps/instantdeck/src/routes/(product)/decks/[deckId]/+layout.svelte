<script lang="ts">
  import { page } from '$app/state';
  import ProductSurfaceNav from '$lib/components/navigation/ProductSurfaceNav.svelte';
  import GlobalDeckWorkspaceFrame from '$lib/components/decks/GlobalDeckWorkspaceFrame.svelte';
  import GlobalDeckSidebar from '$lib/components/decks/GlobalDeckSidebar.svelte';
  import GlobalDeckSlideNavigator from '$lib/components/decks/GlobalDeckSlideNavigator.svelte';
  import GlobalDeckVisualizer from '$lib/components/decks/GlobalDeckVisualizer.svelte';
  import GlobalDeckDetailsPanel from '$lib/components/decks/GlobalDeckDetailsPanel.svelte';
  import GlobalDeckChatPanel from '$lib/components/decks/GlobalDeckChatPanel.svelte';
  import {
    createDeckWorkspaceController,
    provideDeckWorkspaceController
  } from '$lib/components/decks/deckWorkspaceController.svelte';

  let { data, children }: { data: { graph?: { deck?: { id?: string; title?: string } } | null }; children: import('svelte').Snippet } = $props();
  const deckId = $derived(data.graph?.deck?.id ?? null);
  const deckTitle = $derived(data.graph?.deck?.title ?? 'Deck workspace');
  const llmReportHref = $derived(deckId ? `/decks/llm-report?deckId=${encodeURIComponent(deckId)}` : undefined);
  const deckSurface = $derived(page.url.pathname.split('/').filter(Boolean).at(-1) ?? 'deck');
  const workspaceSurface = $derived(['smart-deck', 'instant-deck', 'smart-edit', 'due-diligence'].includes(deckSurface));
  const workspaceController = createDeckWorkspaceController();
  provideDeckWorkspaceController(workspaceController);
  const workspaceConfig = $derived(workspaceController.current);
</script>

<div
  class="deck-surface-layout"
  class:deck-surface-layout--workspace={workspaceSurface}
  data-deck-layout={workspaceSurface ? 'four-column-workbench' : 'deck-document'}
  data-deck-surface={deckSurface}
>
  {#if deckId}
    <div class="deck-surface-layout__nav">
      <div class="deck-surface-layout__identity">
        <span>Deck workspace</span>
        <strong title={deckTitle}>{deckTitle}</strong>
      </div>
      <div class="deck-surface-layout__actions">
        <ProductSurfaceNav {deckId} instantOnly={deckSurface === 'instant-deck'} />
        <a class="deck-surface-layout__dashboard" href="/dashboard">Return to dashboard</a>
      </div>
    </div>
  {/if}
  <div class="deck-surface-layout__viewport">
    {#if workspaceSurface}
      <GlobalDeckWorkspaceFrame rows={deckSurface === 'smart-deck' || deckSurface === 'instant-deck' ? 'smart-deck' : 'single'}>
        <!-- Render registration first so SSR has route state before the globals. -->
        {@render children()}
        {#if workspaceConfig}
          {#key `${deckId}:${workspaceConfig.surface}`}
            <GlobalDeckSidebar
              items={workspaceConfig.sidebar.items}
              activeKey={workspaceConfig.sidebar.activeKey}
              ariaLabel={workspaceConfig.sidebar.ariaLabel}
              onItemChange={workspaceConfig.sidebar.onItemChange}
            />
            <GlobalDeckSlideNavigator
              slides={workspaceConfig.navigator.slides}
              selectedSlideId={workspaceConfig.navigator.selectedSlideId}
              selectedSourceSlideIds={workspaceConfig.navigator.selectedSourceSlideIds}
              onSelectSlide={workspaceConfig.navigator.onSelectSlide}
              onToggleSourceSlideSelection={workspaceConfig.navigator.onToggleSourceSlideSelection}
              onOpenSmartEdit={workspaceConfig.navigator.onOpenSmartEdit}
              onAddSlide={workspaceConfig.navigator.onAddSlide}
              addingSlide={workspaceConfig.navigator.addingSlide}
              title={workspaceConfig.navigator.title}
              description={workspaceConfig.navigator.description}
              showSourceSelection={workspaceConfig.navigator.showSourceSelection}
              showSearch={workspaceConfig.navigator.showSearch}
              belowToolbar={workspaceConfig.navigator.belowToolbar}
              visible={workspaceConfig.navigator.visible}
              interactionDisabledReason={workspaceConfig.navigator.interactionDisabledReason}
            />
            <div
              class="deck-surface-layout__visualizer-stack"
              class:deck-surface-layout__visualizer-stack--below-toolbar={deckSurface === 'smart-deck' || deckSurface === 'instant-deck'}
              class:deck-surface-layout__visualizer-stack--full-document={workspaceConfig.visualizer.htmlDisplayMode === 'full-document'}
              data-deck-region="visualizer-stack"
            >
              <GlobalDeckVisualizer
                title={workspaceConfig.visualizer.title}
                subtitle={workspaceConfig.visualizer.subtitle}
                slide={workspaceConfig.visualizer.slide}
                renderSchema={workspaceConfig.visualizer.renderSchema}
                htmlSlide={workspaceConfig.visualizer.htmlSlide}
                designTokens={workspaceConfig.visualizer.designTokens}
                selectedElementId={workspaceConfig.visualizer.selectedElementId}
                lockedElementIds={workspaceConfig.visualizer.lockedElementIds}
                onSelectElement={workspaceConfig.visualizer.onSelectElement}
                onActivateElement={workspaceConfig.visualizer.onActivateElement}
                onActivateCanvas={workspaceConfig.visualizer.onActivateCanvas}
                onChangeElementGeometry={workspaceConfig.visualizer.onChangeElementGeometry}
                interactive={workspaceConfig.visualizer.interactive}
                visualMode={workspaceConfig.visualizer.visualMode}
                htmlDisplayMode={workspaceConfig.visualizer.htmlDisplayMode}
                editable={workspaceConfig.visualizer.editable}
                emptyTitle={workspaceConfig.visualizer.emptyTitle}
                emptyText={workspaceConfig.visualizer.emptyText}
                children={workspaceConfig.visualizer.children}
              />
              {#if workspaceConfig.details && deckId}
                <GlobalDeckDetailsPanel
                  {deckId}
                  title={workspaceConfig.details.title}
                  slideId={workspaceConfig.details.slideId}
                  cacheKey={workspaceConfig.details.cacheKey}
                  persistedSummary={workspaceConfig.details.persistedSummary}
                  content={workspaceConfig.details.content}
                />
              {/if}
            </div>
            <GlobalDeckChatPanel
              messages={workspaceConfig.chat.messages}
              conversationState={workspaceConfig.chat.state}
              conversationMessage={workspaceConfig.chat.message}
              onSendConversation={workspaceConfig.chat.onSend}
              latestAssistantRun={workspaceConfig.chat.latestAssistantRun}
              saveInsightState={workspaceConfig.chat.saveInsightState}
              saveInsightMessage={workspaceConfig.chat.saveInsightMessage}
              onSaveInsight={workspaceConfig.chat.onSaveInsight}
              title={workspaceConfig.chat.title}
              eyebrow={workspaceConfig.chat.eyebrow}
              description={workspaceConfig.chat.description}
              emptyText={workspaceConfig.chat.emptyText}
              placeholder={workspaceConfig.chat.placeholder}
              sendLabel={workspaceConfig.chat.sendLabel}
              sendingLabel={workspaceConfig.chat.sendingLabel}
              retryAvailable={workspaceConfig.chat.retryAvailable}
              onRetry={workspaceConfig.chat.onRetry}
              infoHref={llmReportHref}
              workspaceRegion={true}
              belowToolbar={deckSurface === 'smart-deck' || deckSurface === 'instant-deck'}
            />
          {/key}
        {/if}
      </GlobalDeckWorkspaceFrame>
    {:else}
      {@render children()}
    {/if}
  </div>
</div>

<style>
  .deck-surface-layout {
    /* This deck-scoped layout owns workspace geometry for Smart Deck, Instant
       Deck, Smart Edit, and Due Diligence. Other deck routes remain documents. */
    --deck-workspace-rail-width: 72px;
    --deck-workspace-navigator-width: 280px;
    --deck-workspace-navigator-compact-width: 240px;
    --deck-workspace-assistant-width: 360px;
    --deck-workspace-assistant-compact-width: 320px;
    --deck-workspace-rail-compact-width: 56px;
    --deck-workspace-toolbar-height: 52px;
    --deck-workspace-filmstrip-height: 72px;
    height: 100%;
    min-width: 0;
    min-height: 0;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    overflow: hidden;
    background: var(--bg);
  }

  .deck-surface-layout__viewport {
    position: relative;
    width: 100%;
    height: 100%;
    min-width: 0;
    min-height: 0;
    overflow: auto;
  }

  .deck-surface-layout--workspace .deck-surface-layout__viewport {
    overflow: hidden;
    background:
      radial-gradient(circle at top left, rgba(30, 41, 59, 0.24), transparent 30%),
      linear-gradient(180deg, #070b16, #091122 58%, #0b1324);
  }

  /* The canonical deck route owns the actual four-column workbench. Child
     surfaces register feature-specific content and state only. */
  .deck-surface-layout--workspace :global([data-global-deck-workspace]) {
    width: 100%;
    height: 100%;
    min-width: 0;
    min-height: 0;
    display: grid;
    grid-template-columns:
      var(--deck-workspace-rail-width)
      var(--deck-workspace-navigator-width)
      minmax(0, 1fr)
      var(--deck-workspace-assistant-width);
    grid-template-rows: minmax(0, 1fr);
    gap: 0;
    overflow: hidden;
    position: relative;
  }

  .deck-surface-layout--workspace :global([data-global-deck-workspace][data-deck-workspace-rows='smart-deck']) {
    grid-template-rows:
      var(--deck-workspace-toolbar-height)
      minmax(0, 1fr)
      var(--deck-workspace-filmstrip-height);
  }

  .deck-surface-layout__visualizer-stack {
    grid-column: 3;
    grid-row: 1;
    min-width: 0;
    min-height: 0;
    display: grid;
    align-content: start;
    gap: 0.9rem;
    overflow: auto;
    padding: 1.25rem;
    background: linear-gradient(180deg, rgba(8, 13, 27, 0.98), rgba(10, 17, 33, 0.95));
  }

  .deck-surface-layout__visualizer-stack--below-toolbar {
    grid-row: 2;
  }

  .deck-surface-layout__nav {
    position: relative;
    z-index: 80;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    padding: 0.65rem clamp(0.75rem, 2vw, 1.5rem);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(2, 6, 23, 0.94);
    backdrop-filter: blur(16px);
  }

  .deck-surface-layout__identity {
    min-width: 0;
    display: grid;
    gap: 0.1rem;
  }

  .deck-surface-layout__identity span {
    color: #94a3b8;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .deck-surface-layout__identity strong {
    max-width: min(30vw, 28rem);
    overflow: hidden;
    color: #f8fafc;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .deck-surface-layout__actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.75rem;
    min-width: 0;
  }

  .deck-surface-layout__dashboard {
    display: inline-flex;
    align-items: center;
    min-height: 38px;
    padding: 0 0.95rem;
    border: 1px solid rgba(148, 163, 184, 0.28);
    border-radius: 999px;
    color: #e2e8f0;
    font-size: 0.82rem;
    font-weight: 700;
    text-decoration: none;
    white-space: nowrap;
  }

  .deck-surface-layout__dashboard:hover,
  .deck-surface-layout__dashboard:focus-visible {
    border-color: rgba(96, 165, 250, 0.62);
    background: rgba(59, 130, 246, 0.12);
    color: #f8fafc;
  }

  @media (max-width: 800px) {
    .deck-surface-layout__nav {
      align-items: flex-start;
      flex-direction: column;
    }

    .deck-surface-layout__identity strong {
      max-width: 90vw;
    }

    .deck-surface-layout__actions {
      width: 100%;
      align-items: flex-start;
      justify-content: space-between;
      flex-wrap: wrap;
    }
  }

  @media (max-width: 1200px) {
    .deck-surface-layout--workspace :global([data-global-deck-workspace]) {
      grid-template-columns:
        var(--deck-workspace-rail-width)
        var(--deck-workspace-navigator-compact-width)
        minmax(0, 1fr)
        var(--deck-workspace-assistant-compact-width);
    }

  }

  @media (max-width: 960px) {
    .deck-surface-layout__visualizer-stack {
      grid-column: 2;
      grid-row: 2;
      padding: 1rem;
    }

    .deck-surface-layout--workspace :global([data-global-deck-workspace]) {
      grid-template-columns:
        var(--deck-workspace-rail-compact-width)
        minmax(0, 1fr)
        var(--deck-workspace-assistant-compact-width);
      grid-template-rows: auto minmax(0, 1fr) 88px;
    }
  }

  @media (max-width: 720px) {
    .deck-surface-layout__visualizer-stack {
      grid-column: 1;
      grid-row: 3;
      padding: 0.9rem;
    }

    .deck-surface-layout {
      --deck-workspace-toolbar-height: auto;
      --deck-workspace-filmstrip-height: 88px;
      --deck-mobile-visualizer-row-height: max(18rem, 55dvh);
    }

    .deck-surface-layout--workspace :global([data-global-deck-workspace]) {
      grid-template-columns: minmax(0, 1fr);
      grid-template-rows: auto auto var(--deck-mobile-visualizer-row-height) minmax(28rem, 70dvh) 88px;
      overflow-x: hidden;
      overflow-y: auto;
      align-content: start;
    }

    .deck-surface-layout__visualizer-stack--full-document {
      box-sizing: border-box;
      height: var(--deck-mobile-visualizer-row-height);
      max-height: var(--deck-mobile-visualizer-row-height);
      align-content: stretch;
      overflow: hidden;
    }
  }
</style>
