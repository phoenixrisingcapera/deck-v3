<script lang="ts">
  import { vcUseCases } from '$lib/data/marketing/home';
</script>

<section class="panel section">
  <div class="grid">
    <div class="copy">
      <div class="eyebrow">For VCs</div>
      <h2>Built for funds that need a better review system than PDFs, chat threads, and last-minute rewrites.</h2>
      <p class="muted">
        From first-look screening to partner discussion and IC prep, Deck AIStack keeps the source narrative,
        review state, and AI output inside one operating surface the team can actually trust.
      </p>
      <a class="button secondary" href="/vcs">Learn more for VCs</a>
    </div>

    <div class="use-cases">
      {#each vcUseCases as useCase}
        <article>
          <strong>{useCase.title}</strong>
          <p class="muted">{useCase.body}</p>
        </article>
      {/each}
    </div>
  </div>
</section>

<style>
  .section {
    padding: clamp(2rem, 3vw, 3.5rem) clamp(1.8rem, 3vw, 3.5rem);
  }

  .grid {
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) 420px;
    gap: 1.65rem;
    align-items: start;
  }

  .copy {
    display: grid;
    gap: 1.1rem;
    align-content: start;
  }

  .copy h2 {
    margin: 0;
    font-size: clamp(1.8rem, 2.8vw, 2.8rem);
    line-height: 1.02;
    letter-spacing: -0.04em;
  }

  .copy p {
    margin: 0;
    line-height: 1.65;
  }

  .use-cases {
    display: grid;
    gap: 1.15rem;
  }

  .use-cases article {
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 1.3rem 1.25rem;
    background: var(--surface-soft);
    display: grid;
    gap: 0.6rem;
    transition: transform 180ms ease, box-shadow 180ms ease;
  }

  .use-cases article:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.18);
  }

  .use-cases p {
    margin: 0.45rem 0 0;
  }

  @media (max-width: 960px) {
    .grid {
      grid-template-columns: 1fr;
    }
  }
</style>
