<script lang="ts">
  import type { SmartDeckEditorMode, SmartDeckUserSaveState, SmartDeckUserSlideViewModel } from './smartDeckUserTypes';

  interface Props {
    deckName: string;
    slides: SmartDeckUserSlideViewModel[];
    selectedSlideId: string | null;
    mode: SmartDeckEditorMode;
    saveState: SmartDeckUserSaveState;
    deckId: string;
    selectedVersionId?: string | null;
    instantResultOnly?: boolean;
    originalDeckHref?: string | null;
    regenerateLabel?: string | null;
    regenerating?: boolean;
    regeneratingLabel?: string;
    onRegenerate?: () => void;
    onModeChange?: (mode: SmartDeckEditorMode) => void;
    onSlideChange?: (slideId: string) => void;
    onOpenSettings?: () => void;
  }

  let {
    deckName,
    slides,
    selectedSlideId,
    mode,
    saveState,
    deckId,
    selectedVersionId = null,
    instantResultOnly = false,
    originalDeckHref = null,
    regenerateLabel = null,
    regenerating = false,
    regeneratingLabel = 'Regenerating...',
    onRegenerate,
    onModeChange,
    onSlideChange,
    onOpenSettings
  }: Props = $props();

  let shareState = $state<'idle' | 'copied' | 'error'>('idle');

  async function shareDeck() {
    shareState = 'idle';
    const url = `${window.location.origin}/decks/${deckId}/smart-deck`;
    try {
      if (navigator.share) {
        await navigator.share({ title: deckName, url });
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(url);
      } else {
        throw new Error('Sharing is unavailable');
      }
      shareState = 'copied';
    } catch {
      shareState = 'error';
    }
  }

  function saveLabel() {
    if (saveState === 'saving') return 'Saving...';
    if (saveState === 'unsaved') return 'Unsaved changes';
    return 'All changes saved';
  }

</script>

<header class="smart-deck-top-bar">
  <!-- DISABLED: Deck/slide selectors repeated internal extracted titles and
       overlapped the shared deck identity. Miniatures now own slide selection. -->
  <!-- DISABLED: Play/Edit/Preview modes did not change meaningful MVP behavior. -->

  <div class="smart-deck-top-bar__group smart-deck-top-bar__group--status" role="status" aria-live="polite">
    <span class="save-indicator" class:is-saving={saveState === 'saving'} class:is-unsaved={saveState === 'unsaved'}>
      ●
    </span>
    <span>{saveLabel()}</span>
    {#if selectedVersionId}
      <span class="design-version-identity" aria-label="DesignVersion identity">DesignVersion {selectedVersionId}</span>
    {/if}
  </div>

  <div class="smart-deck-top-bar__group smart-deck-top-bar__group--actions">
    {#if originalDeckHref}
      <a class="secondary original-deck-link" href={originalDeckHref}>See my original deck</a>
    {/if}
    {#if regenerateLabel && onRegenerate}
      <button type="button" class="regenerate" disabled={regenerating} onclick={onRegenerate}>
        {regenerating ? regeneratingLabel : regenerateLabel}
      </button>
    {/if}
    {#if !instantResultOnly}
      <button type="button" class="secondary" onclick={() => void shareDeck()} title={shareState === 'error' ? 'Sharing is unavailable in this browser.' : undefined}>
        {shareState === 'copied' ? 'Shared' : shareState === 'error' ? 'Share unavailable' : 'Share'}
      </button>
      <span class="share-feedback" role="status" aria-live="polite">
        {shareState === 'copied' ? 'Deck link shared.' : shareState === 'error' ? 'Sharing is unavailable.' : ''}
      </span>
    {/if}
    <!-- DISABLED: Settings is owned by the Smart Deck rail. Keeping a second
         top-bar action duplicated the same destination. -->
    {#if !instantResultOnly}
      <a
        class="export-link"
        href={selectedVersionId
          ? `/decks/${deckId}/export?designVersionId=${encodeURIComponent(selectedVersionId)}`
          : `/decks/${deckId}/export`}
      >Export</a>
    {/if}
  </div>
</header>

<style>
  .smart-deck-top-bar {
    /* Column one belongs exclusively to the persistent app rail. */
    grid-column: 2 / -1;
    grid-row: 1;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0 0.75rem;
    background: rgba(7, 11, 22, 0.82);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(16px);
  }

  .smart-deck-top-bar__group {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    min-width: 0;
  }

  .smart-deck-top-bar label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: #cbd5e1;
    font-size: 0.8rem;
  }

  .smart-deck-top-bar label span {
    color: #94a3b8;
  }

  .smart-deck-top-bar select,
  .secondary,
  .regenerate,
  .original-deck-link,
  .export-link {
    height: 34px;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(15, 23, 42, 0.95);
    color: #f8fafc;
    padding: 0 0.85rem;
    font: inherit;
  }

  .smart-deck-top-bar select {
    min-width: 170px;
  }

  .smart-deck-top-bar__group--modes {
    background: rgba(7, 11, 22, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 0.25rem;
    border-radius: 12px;
  }

  .smart-deck-top-bar__group--modes button {
    height: 36px;
    min-width: 74px;
    border-radius: 10px;
    border: none;
    background: transparent;
    color: #cbd5e1;
    cursor: pointer;
  }

  .smart-deck-top-bar__group--modes button.active {
    background: linear-gradient(135deg, #7c3aed, #0ea5e9);
    color: #fff;
    box-shadow: 0 12px 24px rgba(124, 58, 237, 0.28);
  }

  .smart-deck-top-bar__group--status {
    color: #dbeafe;
    font-size: 0.84rem;
  }

  .design-version-identity {
    max-width: min(42vw, 390px);
    overflow: hidden;
    padding: 0.25rem 0.48rem;
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 7px;
    color: #94a3b8;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.66rem;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .save-indicator {
    color: #22c55e;
    font-size: 0.8rem;
  }

  .save-indicator.is-saving {
    color: #f59e0b;
  }

  .save-indicator.is-unsaved {
    color: #f97316;
  }

  .share-feedback {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  .secondary {
    cursor: pointer;
  }

  .regenerate {
    cursor: pointer;
    border-color: rgba(56, 189, 248, 0.45);
    background: #0284c7;
    color: #fff;
  }

  .regenerate:disabled {
    cursor: wait;
    opacity: 0.65;
  }

  .original-deck-link {
    display: inline-flex;
    align-items: center;
    text-decoration: none;
  }

  .export-link {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    text-decoration: none;
    background: linear-gradient(135deg, #7c3aed, #0ea5e9);
    border-color: transparent;
    box-shadow: 0 14px 28px rgba(76, 29, 149, 0.32);
  }

  /* DISABLED: .debug-link styled the removed developer visibility action in the product top bar.
     Reason: Product Smart Deck no longer exposes a private-surface link from primary workspace actions. */
  /* .debug-link {
    color: #94a3b8;
    font-size: 0.82rem;
    text-decoration: none;
  } */

  @media (max-width: 1200px) {
    .smart-deck-top-bar {
      flex-wrap: wrap;
      height: auto;
      min-height: 64px;
      padding: 0.75rem 1rem;
    }
  }

  @media (max-width: 960px) {
    .smart-deck-top-bar {
      grid-column: 2 / -1;
      padding-left: 0.85rem;
      padding-right: 0.85rem;
    }

    .smart-deck-top-bar__group--actions {
      width: 100%;
      justify-content: flex-start;
      flex-wrap: wrap;
    }
  }

  @media (max-width: 720px) {
    .smart-deck-top-bar {
      grid-column: 1;
      grid-row: 1;
      padding: 0.85rem 1rem;
    }

    .smart-deck-top-bar__group--selectors,
    .smart-deck-top-bar__group--modes,
    .smart-deck-top-bar__group--status,
    .smart-deck-top-bar__group--actions {
      width: 100%;
      justify-content: flex-start;
      flex-wrap: wrap;
    }
  }
</style>
