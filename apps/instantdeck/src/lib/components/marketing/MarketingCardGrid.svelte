<script lang="ts">
  interface CardItem {
    title: string;
    body: string;
  }

  interface Props {
    eyebrow?: string;
    title: string;
    body?: string;
    items: CardItem[];
    columns?: 2 | 3;
  }

  let { eyebrow = '', title, body = '', items, columns = 3 }: Props = $props();
</script>

<section class="panel section">
  <div class="section__head">
    {#if eyebrow}
      <div class="eyebrow">{eyebrow}</div>
    {/if}
    <h2>{title}</h2>
    {#if body}
      <p class="muted">{body}</p>
    {/if}
  </div>

  <div class:three-up={columns === 3} class:two-up={columns === 2} class="section__grid">
    {#each items as item}
      <article class="section__card">
        <strong>{item.title}</strong>
        <p class="muted">{item.body}</p>
      </article>
    {/each}
  </div>
</section>

<style>
  .section {
    padding: 1.45rem;
    display: grid;
    gap: 1rem;
  }

  .section__head {
    display: grid;
    gap: 0.65rem;
    max-width: 48rem;
  }

  .section__head h2 {
    margin: 0;
  }

  .section__grid {
    display: grid;
    gap: 1rem;
  }

  .three-up {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .two-up {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .section__card {
    border: 1px solid var(--line);
    border-radius: var(--radius-card);
    background: var(--surface-soft);
    padding: 1.1rem;
    display: grid;
    gap: 0.65rem;
  }

  .section__card p {
    margin: 0;
  }

  @media (max-width: 960px) {
    .three-up,
    .two-up {
      grid-template-columns: 1fr;
    }
  }
</style>
