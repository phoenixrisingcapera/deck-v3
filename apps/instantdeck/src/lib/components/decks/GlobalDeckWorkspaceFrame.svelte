<!--
  GLOBAL DECK WORKSPACE FRAME: marks the child surface consumed by the
  canonical decks/[deckId]/+layout.svelte four-column grid. This component
  owns no column widths; the route layout is the single geometry owner.
-->
<script lang="ts">
  interface Props {
    children: import('svelte').Snippet;
    rows?: 'single' | 'smart-deck';
    focused?: boolean;
  }

  let { children, rows = 'single', focused = false }: Props = $props();
</script>

<div
  class="global-deck-workspace-frame"
  class:global-deck-workspace-frame--focused={focused}
  data-global-deck-workspace
  data-deck-workspace-rows={rows}
>
  {@render children()}
</div>

<style>
  .global-deck-workspace-frame {
    width: 100%;
    height: 100%;
    min-width: 0;
    min-height: 0;
    overflow: clip;
    position: relative;
    isolation: isolate;
    color: #f8fafc;
  }

  @supports not (overflow: clip) {
    .global-deck-workspace-frame {
      overflow: hidden;
    }
  }
</style>
