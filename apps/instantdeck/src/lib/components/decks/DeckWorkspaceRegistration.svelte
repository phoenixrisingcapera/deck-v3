<script lang="ts">
  import { onDestroy, type Snippet } from 'svelte';
  import { useDeckWorkspaceController, type DeckWorkspaceRegistration } from './deckWorkspaceController.svelte';

  interface Props {
    config: () => DeckWorkspaceRegistration;
    children?: Snippet;
  }

  let { config, children }: Props = $props();
  const controller = useDeckWorkspaceController();
  const unregister = controller.register(() => config());

  onDestroy(unregister);
</script>

{#if children}
  {@render children()}
{/if}
