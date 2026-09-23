<script lang="ts">
  let { data }: { data: Record<string, unknown> } = $props();
</script>

<svelte:head>
  {@html `<script type="application/ld+json">${JSON.stringify(data)}</script>`}
</svelte:head>
