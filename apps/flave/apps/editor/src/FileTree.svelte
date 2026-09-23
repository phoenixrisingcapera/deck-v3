<!-- The Files surface (§7.3, surface 5). Selecting a file is a READ, which is
     why it does not breach §7.2's capability ceiling. -->
<script lang="ts">
  import Self from './FileTree.svelte';
  import type { FsNode } from './workspace-fs';

  let {
    nodes,
    depth = 0,
    selected,
    onopen,
  }: {
    nodes: FsNode[];
    depth?: number;
    selected: string | null;
    onopen: (path: string) => void;
  } = $props();
</script>

<ul class="tree" style="--depth: {depth}">
  {#each nodes as node (node.path)}
    <li>
      {#if node.is_dir}
        <span class="row row--dir"><span class="glyph">▾</span>{node.name}</span>
        <Self nodes={node.children} depth={depth + 1} {selected} {onopen} />
      {:else}
        <button
          type="button"
          class="row row--file"
          class:is-selected={selected === node.path}
          onclick={() => onopen(node.path)}
        >
          <span class="glyph">·</span>{node.name}
        </button>
      {/if}
    </li>
  {/each}
</ul>

<style>
  .tree { list-style: none; margin: 0; padding: 0; }
  .row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    padding: 3px var(--space-3) 3px calc(var(--space-3) + var(--depth) * 12px);
    font-size: 0.8rem;
    font-family: var(--font__mono);
    color: var(--color-text-soft);
    background: none;
    border: 0;
    text-align: left;
  }
  .row--dir {
    color: var(--color-text-dim);
    text-transform: uppercase;
    font-size: 0.68rem;
    letter-spacing: 0.08em;
  }
  .row--file { cursor: pointer; }
  .row--file:hover { background: var(--color-bg-soft); color: var(--color-text); }
  .row--file.is-selected {
    background: var(--color-bg-soft);
    color: var(--color-accent);
  }
  .glyph { color: var(--color-text-dim); }
</style>
