<script lang="ts">
  import { theme } from '$lib/stores/theme';

  interface Props {
    compact?: boolean;
  }

  let { compact = false }: Props = $props();
</script>

<button type="button" class:theme-toggle--compact={compact} class="theme-toggle" aria-label="Toggle theme" onclick={() => theme.toggle()}>
  <span class="theme-toggle__dot"></span>
  <span>{compact ? ($theme === 'dark' ? 'Light' : 'Dark') : ($theme === 'dark' ? 'Light mode' : 'Dark mode')}</span>
</button>
