<script lang="ts">
  const steps = [
    {
      number: '01',
      title: 'Upload your deck',
      detail: 'Start with the existing PDF so Deck AIStack keeps the real source material as the parent artifact.'
    },
    {
      number: '02',
      title: 'AI extracts structure and content',
      detail: 'Slides, blocks, and classifications are generated before diligence findings or Smart Edit become available.'
    },
    {
      number: '03',
      title: 'Review, adapt, export',
      detail: 'Every suggestion stays reviewable so the AI never overwrites the deck silently.'
    }
  ];
</script>

<section class="workflow-grid">
  {#each steps as step}
    <article class="panel workflow-card">
      <span class="workflow-card__number">{step.number}</span>
      <h3>{step.title}</h3>
      <p class="muted">{step.detail}</p>
    </article>
  {/each}
</section>

<style>
  .workflow-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1rem;
  }

  .workflow-card {
    padding: 1.15rem;
    display: grid;
    gap: 0.7rem;
  }

  .workflow-card__number {
    color: var(--accent);
    font-size: 0.78rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  h3 {
    margin: 0;
  }

  @media (max-width: 900px) {
    .workflow-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
