<script lang="ts">
  import type { ComponentProps } from 'svelte';
  import SmartDeckAITools from '$lib/components/ai-tool-sidebar/smart-deck/SmartDeckAITools.svelte';

  type Props = Omit<ComponentProps<typeof SmartDeckAITools>, 'surface'>;
  let props: Props = $props();
</script>

<SmartDeckAITools {...props} surface="instant-deck" />
