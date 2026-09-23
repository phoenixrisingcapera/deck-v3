<script lang="ts">
  import InstantDeckWorkspace from '$lib/features/instant-deck/InstantDeckWorkspace.svelte';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();
</script>

{#key data.graph.deck.id}
  <InstantDeckWorkspace
    graph={data.graph}
    initialWorkspace={data.smartDeckWorkspace}
    initialSelectedVersionId={data.selectedDesignVersionId}
    initialSelectedGeneratedSlideId={data.selectedGeneratedSlideId}
    fallbackMessage={data.smartDeckWorkspaceStatus?.message ?? null}
    fallbackActionHref={data.smartDeckWorkspaceStatus?.actionHref ?? null}
    fallbackActionLabel={data.smartDeckWorkspaceStatus?.actionLabel ?? null}
  />
{/key}
