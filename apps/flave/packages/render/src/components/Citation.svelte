<!-- An inline citation marker. Renders the sequential index, links to the
     bibliography entry, and carries the source domain as a tooltip so a reader
     can judge a claim without leaving the paragraph. -->
<script lang="ts">
  import type { Citation } from '../hprops';
  let { citation, identifier }: { citation?: Citation; identifier: string } = $props();
</script>

{#if citation}
  <sup class="citation"><a href={`#cite-${citation.hex}`} title={citation.title ?? citation.source ?? ''}>{citation.index}</a></sup>
{:else}
  <!-- Unknown identifier: show it rather than silently dropping the claim's source. -->
  <sup class="citation citation--unresolved" title="no matching citation definition">?{identifier}</sup>
{/if}

<style>
  .citation { font-family: var(--font__mono); font-size: 0.7em; }
  .citation a { color: var(--color-accent); text-decoration: none; }
  .citation a::before { content: '['; }
  .citation a::after { content: ']'; }
  .citation--unresolved { color: var(--color-tone-danger); }
</style>
