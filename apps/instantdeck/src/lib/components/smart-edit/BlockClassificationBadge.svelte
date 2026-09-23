<script lang="ts">
  interface Props {
    semanticTag: string;
    diligenceCategory: string;
  }

  let { semanticTag, diligenceCategory }: Props = $props();

  function humanize(value: string) {
    return value
      .replace(/[_-]+/g, ' ')
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }
</script>

<div class="badge-group">
  <span class="pill">Content: {humanize(semanticTag)}</span>
  <span class="pill">Review: {humanize(diligenceCategory)}</span>
</div>

<style>
  .badge-group {
    display: flex;
    gap: 0.45rem;
    flex-wrap: wrap;
  }
</style>
