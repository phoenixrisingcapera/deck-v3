<script lang="ts">
  import { page } from '$app/state';
  import DealWorkspace from '$lib/components/DealWorkspace.svelte';

  // SvelteKit guarantees these are present once the [firm]/[deal] route
  // has matched, but the param map's TS type allows undefined. Coerce to
  // string and treat empty as a routing error (renders the empty state).
  let firm = $derived(page.params.firm ?? '');
  let deal = $derived(page.params.deal ?? '');
</script>

{#key `${firm}/${deal}`}
  <DealWorkspace {firm} {deal} />
{/key}
