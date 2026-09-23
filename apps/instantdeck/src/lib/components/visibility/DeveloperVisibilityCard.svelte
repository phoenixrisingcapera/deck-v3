<script lang="ts">
  export type DeveloperVisibilityItem = {
    label: string;
    value: string | number | boolean | null | undefined;
  };

  interface Props {
    title?: string;
    summary?: string;
    items: DeveloperVisibilityItem[];
    href?: string | null;
    linkLabel?: string;
    open?: boolean;
  }

  let {
    title = 'Developer tools',
    summary = 'Page-scoped diagnostics and workflow visibility.',
    items,
    href = null,
    linkLabel = 'Open diagnostics',
    open = false
  }: Props = $props();

  const isDevMode = $derived(
    typeof window !== 'undefined' &&
    (window.location.search.includes('dev=1') ||
     window.location.search.includes('developerTools=1') ||
     window.location.hostname === 'localhost')
  );

  function formatValue(value: DeveloperVisibilityItem['value']) {
    if (typeof value === 'boolean') return value ? 'yes' : 'no';
    if (value === null || value === undefined || value === '') return 'n/a';
    return String(value);
  }
</script>

{#if isDevMode}
<details class="panel developer-visibility" {open}>
  <summary>
    <div>
      <strong>{title}</strong>
      <p>{summary}</p>
    </div>
  </summary>

  <div class="developer-visibility__grid">
    {#each items as item}
      <div class="developer-visibility__item">
        <span>{item.label}</span>
        <strong>{formatValue(item.value)}</strong>
      </div>
    {/each}
  </div>

  {#if href}
    <a class="developer-visibility__link" href={href}>{linkLabel}</a>
  {/if}
</details>
{/if}

<style>
  .developer-visibility {
    display: grid;
    gap: 12px;
    padding: 14px 16px;
    border-style: dashed;
  }

  summary {
    list-style: none;
    cursor: pointer;
  }

  summary::-webkit-details-marker {
    display: none;
  }

  summary > div {
    display: grid;
    gap: 4px;
  }

  summary strong {
    font-size: 13px;
  }

  summary p {
    margin: 0;
    color: var(--text-muted);
    font-size: 12px;
    line-height: 1.5;
  }

  .developer-visibility__grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 10px;
  }

  .developer-visibility__item {
    display: grid;
    gap: 2px;
    padding: 10px 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--bg-subtle);
  }

  .developer-visibility__item span {
    color: var(--text-muted);
    font-size: 11px;
  }

  .developer-visibility__item strong {
    font-size: 13px;
    overflow-wrap: anywhere;
  }

  .developer-visibility__link {
    width: fit-content;
    font-size: 12px;
    color: var(--accent);
  }
</style>
