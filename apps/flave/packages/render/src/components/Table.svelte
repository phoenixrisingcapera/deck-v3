<!--
  Table.

  mdast puts the header in the first row and column alignment on the table
  node, not on the cells — so alignment has to be threaded down by index.
-->
<script lang="ts">
  import FlaveMarkdown from '../FlaveMarkdown.svelte';
  import { srcAttrs } from '../position';

  let { node, packs, data }: { node: any; packs: any; data: any } = $props();

  const rows: any[] = $derived(node?.children ?? []);
  const headRow = $derived(rows[0]);
  const bodyRows = $derived(rows.slice(1));
  const align: (string | null)[] = $derived(node?.align ?? []);
</script>

<div class="flave-table__scroll">
  <table class="flave-table" {...srcAttrs(node)}>
    {#if headRow}
      <thead>
        <tr>
          {#each headRow.children ?? [] as cell, i}
            <th data-align={align[i] ?? 'left'}>
              {#each cell.children ?? [] as c}<FlaveMarkdown node={c} {packs} {data} />{/each}
            </th>
          {/each}
        </tr>
      </thead>
    {/if}
    <tbody>
      {#each bodyRows as row}
        <tr>
          {#each row.children ?? [] as cell, i}
            <td data-align={align[i] ?? 'left'}>
              {#each cell.children ?? [] as c}<FlaveMarkdown node={c} {packs} {data} />{/each}
            </td>
          {/each}
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  /* Wide tables scroll inside their own box rather than pushing the document
     sideways — which matters more inside a callout than anywhere else. */
  .flave-table__scroll {
    overflow-x: auto;
    margin: var(--space-4) 0;
  }

  .flave-table {
    border-collapse: collapse;
    width: 100%;
    font-size: 0.9rem;
  }

  .flave-table :global(th),
  .flave-table :global(td) {
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--color-border);
    vertical-align: top;
  }

  .flave-table :global(th) {
    font-family: var(--font__display);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-dim);
    border-bottom: 1px solid var(--color-border-strong);
    white-space: nowrap;
  }

  .flave-table :global(tbody tr:last-child td) { border-bottom: 0; }

  .flave-table :global([data-align='center']) { text-align: center; }
  .flave-table :global([data-align='right']) { text-align: right; }
</style>
