<script lang="ts">
  interface HighlightItem {
    label: string;
    value: string;
  }

  interface Props {
    eyebrow: string;
    title: string;
    body: string;
    secondaryBody?: string;
    highlights?: HighlightItem[];
  }

  let { eyebrow, title, body, secondaryBody = '', highlights = [] }: Props = $props();
</script>

<section class="panel hero">
  <div class="hero__copy">
    <div class="eyebrow">{eyebrow}</div>
    <h1>{title}</h1>
    <p class="hero__body">{body}</p>
    {#if secondaryBody}
      <p class="muted">{secondaryBody}</p>
    {/if}
  </div>

  {#if highlights.length}
    <div class="hero__highlights">
      {#each highlights as item}
        <article class="hero__card">
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </article>
      {/each}
    </div>
  {/if}
</section>

<style>
  .hero {
    padding: 1.5rem;
    display: grid;
    grid-template-columns: minmax(0, 1.05fr) minmax(260px, 0.95fr);
    gap: 1rem;
    align-items: stretch;
  }

  .hero__copy {
    display: grid;
    gap: 0.8rem;
    align-content: start;
  }

  h1 {
    margin: 0;
    font-size: clamp(2rem, 3vw, 3.35rem);
    letter-spacing: -0.05em;
  }

  .hero__body {
    margin: 0;
    font-size: 1.04rem;
    color: var(--ink-soft);
    max-width: 44rem;
  }

  .hero__highlights {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.85rem;
  }

  .hero__card {
    border: 1px solid var(--line);
    border-radius: var(--radius-card);
    background: var(--surface-soft);
    padding: 1rem;
    display: grid;
    gap: 0.45rem;
  }

  .hero__card span {
    color: var(--muted);
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .hero__card strong {
    font-size: 1.1rem;
    color: var(--ink-strong);
  }

  @media (max-width: 960px) {
    .hero,
    .hero__highlights {
      grid-template-columns: 1fr;
    }
  }
</style>
