<script lang="ts">
  import type { FirstTimeTemplatePreview } from '@deck-aistack-codes/shared';

  interface Props {
    templates: FirstTimeTemplatePreview[];
  }

  let { templates }: Props = $props();
</script>

<section class="template-row">
  {#each templates as template}
    <article class="panel template-card">
      <div class="eyebrow">{template.audienceLabel}</div>
      <h3>{template.title}</h3>
      <p class="muted">{template.description}</p>
      <div class="template-card__tags">
        {#each template.tags as tag}
          <span class="pill">{tag}</span>
        {/each}
      </div>
      <a class="button secondary" href="/decks/new?mode=guided">{template.ctaLabel}</a>
    </article>
  {/each}
</section>

<style>
  .template-row {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1rem;
  }

  .template-card {
    padding: 1.15rem;
    display: grid;
    gap: 0.8rem;
    align-content: start;
  }

  .template-card__tags {
    display: flex;
    gap: 0.55rem;
    flex-wrap: wrap;
  }

  h3 {
    margin: 0;
  }

  @media (max-width: 980px) {
    .template-row {
      grid-template-columns: 1fr;
    }
  }
</style>
