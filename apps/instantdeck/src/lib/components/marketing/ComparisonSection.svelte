<script lang="ts">
  import { deckServiceAdvantages, genericToolLimitations } from '$lib/data/marketing/home';
</script>

<section class="panel comparison">
  <div class="comparison__lead">
    <div class="eyebrow">Why Deck AIStack</div>
    <h2>Not a generic deck generator.</h2>
    <p class="muted">
      Deck AIStack starts from the uploaded deck, keeps company context attached to the workflow, and exposes
      every AI suggestion before the user accepts, rejects, or edits it.
    </p>
  </div>

  <article class="comparison__column comparison__column--neutral">
    <div class="pill">Generic tools</div>
    <ul>
      {#each genericToolLimitations as item}
        <li>{item}</li>
      {/each}
    </ul>
  </article>

  <article class="comparison__column comparison__column--brand">
    <div class="pill">Deck AIStack</div>
    <ul>
      {#each deckServiceAdvantages as item}
        <li>{item}</li>
      {/each}
    </ul>
  </article>
</section>

<style>
  .comparison {
    padding: 1.8rem;
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(240px, 0.8fr) minmax(240px, 0.9fr);
    gap: 1.25rem;
    align-items: stretch;
  }

  .comparison__lead {
    display: grid;
    gap: 0.8rem;
    align-content: start;
    padding-right: 0.35rem;
  }

  .comparison__lead h2 {
    margin: 0;
    font-size: clamp(1.7rem, 2.6vw, 2.5rem);
    line-height: 1.02;
    letter-spacing: -0.04em;
  }

  .comparison__lead p {
    margin: 0;
    line-height: 1.65;
  }

  .comparison__column {
    border: 1px solid var(--line);
    border-radius: var(--radius-card);
    padding: 1.25rem;
    background: var(--surface-soft);
    display: grid;
    align-content: start;
    gap: 1rem;
  }

  .comparison__column--brand {
    background:
      linear-gradient(135deg, var(--surface-active), var(--surface-soft)),
      var(--surface-soft);
    border-color: var(--line-strong);
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
    display: grid;
    gap: 0.7rem;
  }

  li {
    display: flex;
    gap: 0.7rem;
    align-items: start;
    color: var(--ink-soft);
  }

  li::before {
    content: '';
    width: 0.65rem;
    height: 0.65rem;
    flex: 0 0 auto;
    margin-top: 0.35rem;
    border-radius: 999px;
    background: var(--line-strong);
    box-shadow: var(--shadow-glow-blue);
  }

  .comparison__column--neutral li::before {
    background: var(--line);
    box-shadow: none;
  }

  @media (max-width: 1080px) {
    .comparison {
      grid-template-columns: 1fr;
    }
  }
</style>
