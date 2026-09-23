<!--
  FlaveMarkdown — the single recursive dispatcher.

  A port of `AstroMarkdown.astro`, not an invention (spec §12.1). Same dispatch
  table, Svelte syntax around it: the component imports itself in place of
  `Astro.self`, `$props()` replaces `Astro.props`, and `{#if}` branches replace
  the `{type === "…" && (…)}` idiom.

  Three rules carried over verbatim, all of them named failure modes:

  1. Heading ids come from lfm's `remarkHeadingIds` and are NEVER recomputed.
  2. Every container recurses through this component. Never stringify children.
  3. `data.hProperties` is passed through, never re-derived. lfm already worked
     out the classes; a renderer that ignores them drops styling silently.

  The `data` bag is threaded unchanged to every child and carries the document's
  citation map, which is how an inline `[^hex]` resolves without a global.

  The final branch is the whole extensibility story: an unrecognized directive
  looks up the trigger-pack registry. One branch, not a system.
-->
<script lang="ts">
  import Self from './FlaveMarkdown.svelte';
  import Callout from './components/Callout.svelte';
  import CodeBlock from './components/CodeBlock.svelte';
  import Table from './components/Table.svelte';
  import Citation from './components/Citation.svelte';
  import Sources from './components/Sources.svelte';
  import { srcAttrs } from './position';
  import { hProps, citationFor, allCitations } from './hprops';
  import type { Component } from 'svelte';

  let {
    node,
    packs = {},
    data = undefined,
  }: { node: any; packs?: Record<string, Component<any>>; data?: unknown } = $props();

  const type: string = $derived(node?.type);
  const kids: any[] = $derived(node?.children ?? []);

  // The root owns the document-level data bag (citations, heading outline) and
  // hands it down. Every other node passes through whatever it received.
  const bag = $derived(type === 'root' ? (node?.data ?? data) : data);

  const attrs = $derived({ ...hProps(node), ...srcAttrs(node) });

  const isDirective = $derived(
    type === 'containerDirective' || type === 'leafDirective' || type === 'textDirective',
  );
  const isCallout = $derived(type === 'containerDirective' && node?.name === 'callout');
  const isHeadingBlock = $derived(type === 'containerDirective' && node?.name === 'heading-block');
  const Pack: Component<any> | undefined = $derived(
    isDirective && !isCallout && !isHeadingBlock ? packs[node?.name as string] : undefined,
  );

  const isTask = $derived(type === 'listItem' && typeof node?.checked === 'boolean');
</script>

{#if type === 'root'}
  {#each kids as child}<Self node={child} {packs} data={bag} />{/each}
  <Sources citations={allCitations(bag)} />

{:else if type === 'text'}{node.value}

{:else if type === 'paragraph'}
  <p {...attrs}>{#each kids as child}<Self node={child} {packs} data={bag} />{/each}</p>

{:else if type === 'heading'}
  {#if node.depth === 1}
    <h1 {...attrs}>{#each kids as c}<Self node={c} {packs} data={bag} />{/each}</h1>
  {:else if node.depth === 2}
    <h2 {...attrs}>{#each kids as c}<Self node={c} {packs} data={bag} />{/each}</h2>
  {:else if node.depth === 3}
    <h3 {...attrs}>{#each kids as c}<Self node={c} {packs} data={bag} />{/each}</h3>
  {:else if node.depth === 4}
    <h4 {...attrs}>{#each kids as c}<Self node={c} {packs} data={bag} />{/each}</h4>
  {:else if node.depth === 5}
    <h5 {...attrs}>{#each kids as c}<Self node={c} {packs} data={bag} />{/each}</h5>
  {:else}
    <h6 {...attrs}>{#each kids as c}<Self node={c} {packs} data={bag} />{/each}</h6>
  {/if}

{:else if type === 'strong'}
  <strong>{#each kids as child}<Self node={child} {packs} data={bag} />{/each}</strong>

{:else if type === 'emphasis'}
  <em>{#each kids as child}<Self node={child} {packs} data={bag} />{/each}</em>

{:else if type === 'delete'}
  <del>{#each kids as child}<Self node={child} {packs} data={bag} />{/each}</del>

{:else if type === 'inlineCode'}<code>{node.value}</code>

{:else if type === 'code'}
  <CodeBlock {node} />

{:else if type === 'blockquote'}
  <blockquote {...attrs}>{#each kids as child}<Self node={child} {packs} data={bag} />{/each}</blockquote>

{:else if type === 'list'}
  {#if node.ordered}
    <ol {...attrs}>{#each kids as child}<Self node={child} {packs} data={bag} />{/each}</ol>
  {:else}
    <ul {...attrs}>{#each kids as child}<Self node={child} {packs} data={bag} />{/each}</ul>
  {/if}

{:else if type === 'listItem'}
  {#if isTask}
    <li {...attrs} class="task" data-checked={node.checked}>
      <input type="checkbox" checked={node.checked} disabled />
      {#each kids as child}<Self node={child} {packs} data={bag} />{/each}
    </li>
  {:else}
    <li {...attrs}>{#each kids as child}<Self node={child} {packs} data={bag} />{/each}</li>
  {/if}

{:else if type === 'link'}
  <a href={node.url} title={node.title ?? undefined} {...hProps(node)}
    >{#each kids as c}<Self node={c} {packs} data={bag} />{/each}</a>

{:else if type === 'image'}
  <img src={node.url} alt={node.alt ?? ''} title={node.title ?? undefined} {...hProps(node)} />

{:else if type === 'thematicBreak'}
  <hr />

{:else if type === 'break'}
  <br />

{:else if type === 'table'}
  <Table {node} {packs} data={bag} />

{:else if type === 'footnoteReference'}
  <Citation citation={citationFor(bag, node.identifier)} identifier={node.identifier} />

{:else if type === 'html'}
  {@html node.value}

{:else if isCallout}
  <Callout {node} {packs} data={bag} />

{:else if isHeadingBlock}
  <!-- lfm's `$$ eyebrow / ## heading / && subheading` block. Semantically an
       <hgroup>; its children already carry their own hProperties classes. -->
  <hgroup {...attrs}>
    {#each kids as child}<Self node={child} {packs} data={bag} />{/each}
  </hgroup>

{:else if isDirective}
  <!--
    The extensibility branch. A registered trigger-pack renders with the
    directive's attributes as props. An unregistered one still renders its
    children, so unknown syntax degrades to its content instead of vanishing.
  -->
  {#if Pack}
    <Pack {...(node.attributes ?? {})} {node} {packs} data={bag} />
  {:else}
    {#each kids as child}<Self node={child} {packs} data={bag} />{/each}
  {/if}

{:else if kids.length}
  {#each kids as child}<Self node={child} {packs} data={bag} />{/each}

{:else if node?.value != null}{node.value}{/if}
