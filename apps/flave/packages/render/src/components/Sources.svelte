<!-- The bibliography for hex-code citations. lfm consumes footnoteDefinition
     nodes out of the tree and attaches them to tree.data.citations, so this
     renders from the data bag rather than from children. -->
<script lang="ts">
  import type { Citation } from '../hprops';
  let { citations }: { citations: Citation[] } = $props();
</script>

{#if citations.length}
  <section class="sources" aria-label="Sources">
    <h2 class="sources__title">Sources</h2>
    <ol class="sources__list">
      {#each citations as c (c.identifier)}
        <li id={`cite-${c.hex}`}>
          {#if c.url}
            <a href={c.url} rel="noopener noreferrer" target="_blank">{c.title ?? c.url}</a>
          {:else}
            {c.title ?? c.identifier}
          {/if}
          {#if c.source}<span class="sources__domain">{c.source}</span>{/if}
        </li>
      {/each}
    </ol>
  </section>
{/if}

<style>
  .sources {
    margin-top: var(--space-12);
    padding-top: var(--space-4);
    border-top: 1px solid var(--color-border);
  }
  .sources__title {
    font-family: var(--font__display);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--color-text-dim);
    margin: 0 0 var(--space-3);
  }
  .sources__list { margin: 0; padding-left: var(--space-6); font-size: 0.85rem; }
  .sources__list li { margin: var(--space-2) 0; }
  .sources__domain {
    font-family: var(--font__mono);
    font-size: 0.72rem;
    color: var(--color-text-dim);
    margin-left: var(--space-2);
  }
</style>
