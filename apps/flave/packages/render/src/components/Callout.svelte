<!--
  Callout.

  MUST recurse via the renderer for every child. Never `toString(node)`, never a
  plain-text fallback — that path silently disables nesting and is, per lfm's
  changelog, the most common reason a freshly-copied Callout looks "fine" until
  an author tries to embed something inside it. The nesting fixtures keep this
  honest.

  Styling lives here, scoped, rather than in the app's stylesheet. That is not
  taste: a plain .css file cannot use `:global()`, and writing it there shipped
  a whole stylesheet the browser silently discarded (2026-08-20).
-->
<script lang="ts">
  import FlaveMarkdown from '../FlaveMarkdown.svelte';
  import { toneFor } from '../tones';

  let { node, packs, data }: { node: any; packs: any; data: any } = $props();

  const type: string | undefined = $derived(node?.attributes?.type);
  const tone = $derived(toneFor(type));
  const title: string | undefined = $derived(node?.attributes?.title);
  const cls: string = $derived(node?.data?.hProperties?.class ?? 'callout');
</script>

<aside class={cls} data-callout-tone={tone} data-callout-type={type ?? ''}>
  <div class="callout__marker" aria-hidden="true"></div>
  <div class="callout__content">
    {#if title}
      <p class="callout__title">{title}</p>
    {/if}
    <div class="callout__body">
      {#each node.children ?? [] as child}
        <FlaveMarkdown node={child} {packs} {data} />
      {/each}
    </div>
  </div>
</aside>

<style>
  .callout {
    --tone: var(--color-tone-neutral);
    display: grid;
    grid-template-columns: 3px 1fr;
    gap: var(--space-4);
    margin: var(--space-4) 0;
    padding: var(--space-3) var(--space-4);
    background: var(--color-bg-raised);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  /* Tone is carried by an attribute rather than a class so an unknown type
     still lands somewhere defined. */
  .callout[data-callout-tone='info'] { --tone: var(--color-tone-info); }
  .callout[data-callout-tone='warning'] { --tone: var(--color-tone-warning); }
  .callout[data-callout-tone='danger'] { --tone: var(--color-tone-danger); }

  .callout__marker {
    background: var(--tone);
    border-radius: var(--radius-sm);
  }

  .callout__content { min-width: 0; }

  .callout__title {
    margin: 0 0 var(--space-2);
    font-family: var(--font__display);
    font-weight: 700;
    font-size: 0.95rem;
    letter-spacing: -0.01em;
    color: var(--tone);
  }

  .callout__body :global(> :first-child) { margin-top: 0; }
  .callout__body :global(> :last-child) { margin-bottom: 0; }
</style>
