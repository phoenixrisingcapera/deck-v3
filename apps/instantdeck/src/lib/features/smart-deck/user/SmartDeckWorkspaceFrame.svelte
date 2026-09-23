<script lang="ts">
  interface Props {
    children: import('svelte').Snippet;
    focusedGeneration?: boolean;
  }

  let { children, focusedGeneration = false }: Props = $props();
</script>

<div class="smart-deck-workspace-frame" class:smart-deck-workspace-frame--focused={focusedGeneration}>
  {@render children()}
</div>

<style>
  .smart-deck-workspace-frame {
    width: 100%;
    height: 100%;
    min-height: 0;
    overflow: clip;
    display: grid;
    /* 4-column grid: app rail | slide miniatures | visualizer | global assistant.
       Track sizes come from the canonical decks/[deckId] layout. */
    grid-template-columns:
      var(--deck-workspace-rail-width, 72px)
      var(--deck-workspace-navigator-width, 280px)
      minmax(0, 1fr)
      var(--deck-workspace-assistant-width, 360px);
    grid-template-rows:
      var(--deck-workspace-toolbar-height, 52px)
      minmax(0, 1fr)
      var(--deck-workspace-filmstrip-height, 72px);
    color: #f8fafc;
    position: relative;
    isolation: isolate;
  }

  .smart-deck-workspace-frame--focused {
    grid-template-columns:
      var(--deck-workspace-rail-width, 72px)
      var(--deck-workspace-navigator-width, 280px)
      minmax(0, 1fr)
      var(--deck-workspace-assistant-width, 360px);
  }

  @media (max-width: 1200px) {
    .smart-deck-workspace-frame {
      grid-template-columns:
        var(--deck-workspace-rail-width, 72px)
        var(--deck-workspace-navigator-compact-width, 240px)
        minmax(0, 1fr)
        var(--deck-workspace-assistant-compact-width, 320px);
    }

    .smart-deck-workspace-frame--focused {
      grid-template-columns:
        var(--deck-workspace-rail-width, 72px)
        var(--deck-workspace-navigator-compact-width, 240px)
        minmax(0, 1fr)
        var(--deck-workspace-assistant-compact-width, 320px);
    }
  }

  @media (max-width: 960px) {
    .smart-deck-workspace-frame {
      /* Tablet keeps the inspector docked in reserved space. */
      grid-template-columns:
        var(--deck-workspace-rail-compact-width, 56px)
        minmax(0, 1fr)
        var(--deck-workspace-assistant-compact-width, 320px);
      grid-template-rows: auto minmax(0, 1fr) 88px;
    }
  }

  @media (max-width: 720px) {
    .smart-deck-workspace-frame {
      grid-template-columns: 1fr;
      /* Mobile scrolls through canvas, inspector, and filmstrip as separate
         regions so persistent assistant controls never cover canvas controls. */
      grid-template-rows: auto auto minmax(18rem, 55vh) minmax(28rem, 70vh) 88px;
      overflow-y: auto;
      overflow-x: hidden;
      align-content: start;
    }
  }

  @supports not (overflow: clip) {
    .smart-deck-workspace-frame {
      overflow: hidden;
    }
  }
</style>
