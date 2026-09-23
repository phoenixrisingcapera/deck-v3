<script lang="ts">
  interface Props {
    eyebrow?: string;
    title: string;
    subtitle?: string;
    aside?: string;
  }

  let { eyebrow = '', title, subtitle = '', aside = '' }: Props = $props();
</script>

<section class="panel page-header">
  <div>
    {#if eyebrow}
      <div class="eyebrow">{eyebrow}</div>
    {/if}
    <h2>{title}</h2>
    {#if subtitle}
      <p class="muted">{subtitle}</p>
    {/if}
  </div>
  {#if aside}
    <p class="muted aside">{aside}</p>
  {/if}
</section>

<style>
  .page-header {
    padding: 1rem 1.1rem;
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: end;
    flex-wrap: wrap;
  }

  h2 {
    margin: 0.35rem 0 0;
  }

  .aside {
    max-width: 28rem;
    text-align: right;
  }

  @media (max-width: 720px) {
    .aside {
      text-align: left;
    }
  }
</style>
